import os
import re
import subprocess
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal

FLUTTER_COMMANDS = [
    "flutter run",
    "flutter build",
    "flutter analyze",
    "flutter test",
    "flutter clean",
    "flutter pub",
    "flutter create",
    "flutter format",
]

# Maximalni delka textu pro TTS – delsi vystup se zkracuje na souhrn
MAX_TTS_CHARS = 400
MAX_TTS_LINES = 3


class ExecutorSignals(QObject):
    """Signaly pro bezpecnou komunikaci worker -> GUI thread."""
    output = pyqtSignal(str)
    speak = pyqtSignal(str, bool)  # text, force
    started = pyqtSignal(str)
    finished = pyqtSignal(int)


class CommandExecutor:
    def __init__(self, output_callback=None, speak_callback=None, signals: ExecutorSignals | None = None):
        # Zpetna kompatibilita: puvodni API s lambdami
        self._output = output_callback
        self._speak = speak_callback
        self.signals = signals
        self._current_proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def set_signals(self, signals: ExecutorSignals) -> None:
        self.signals = signals

    def _emit_output(self, text: str) -> None:
        if self.signals is not None:
            self.signals.output.emit(text)
        elif self._output:
            # fallback pro testy / legacy – stale mimo GUI thread, ale lepsi nez nic
            self._output(text)

    def _emit_speak(self, text: str, force: bool = False) -> None:
        if self.signals is not None:
            self.signals.speak.emit(text, force)
        elif self._speak:
            self._speak(text)

    def execute(self, cmd: str) -> None:
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def terminate_current(self) -> None:
        """Prerusi bezici prikaz (Ctrl+C) – ukoncí i strom podprocesů ve Windows."""
        with self._lock:
            proc = self._current_proc
        if proc and proc.poll() is None:
            try:
                # na Windows zkus taskkill pro cely strom
                if os.name == "nt":
                    try:
                        subprocess.run(
                            f"taskkill /PID {proc.pid} /T /F",
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=3,
                        )
                    except Exception:
                        pass
                proc.terminate()
                # dej 2s na ukonceni, pak kill
                for _ in range(20):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                else:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    # jeste jednou taskkill
                    if os.name == "nt":
                        try:
                            subprocess.run(
                                f"taskkill /PID {proc.pid} /T /F",
                                shell=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=2,
                            )
                        except Exception:
                            pass
            except Exception:
                pass

    @staticmethod
    def _semicolon_to_ampersand(cmd: str) -> str:
        result = []
        in_quotes = False
        quote_char = None
        for ch in cmd:
            if ch in ('"', "'"):
                if not in_quotes:
                    in_quotes = True
                    quote_char = ch
                elif ch == quote_char:
                    in_quotes = False
                    quote_char = None
                result.append(ch)
            elif ch == ";" and not in_quotes:
                result.append("&")
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _summarize_for_speech(text: str) -> str:
        """Zkrati dlouhy vystup na souhrn pro TTS, aby nevznikl spam."""
        if not text or not text.strip():
            return ""
        # odstran prebytecne prazdne radky pro ucely souhrnu
        lines = [l for l in text.strip().splitlines() if l.strip()]
        if not lines:
            return ""
        if len(text) <= MAX_TTS_CHARS and len(lines) <= MAX_TTS_LINES:
            return text.strip()
        preview = "; ".join(lines[:MAX_TTS_LINES])
        if len(preview) > MAX_TTS_CHARS:
            preview = preview[:MAX_TTS_CHARS].rstrip() + "…"
        return f"Výstup {len(lines)} řádků, celkem {len(text)} znaků. Začátek: {preview}"

    def _run(self, cmd: str) -> None:
        try:
            fixed = self._semicolon_to_ampersand(cmd)
            if fixed != cmd:
                self._emit_output("Středník ; jsem nahradil znakem &, aby to cmd.exe pochopilo.")
            cmd = fixed

            if not self._pre_hooks(cmd):
                if self.signals:
                    self.signals.finished.emit(0)
                return

            if self.signals:
                self.signals.started.emit(cmd)

            with self._lock:
                self._current_proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                proc = self._current_proc

            # Prubezne cteni – streaming misto communicate()
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []

            # Cteme po radcich s timeoutem pomoci poll + readline v cyklu
            # Abychom neblokovali navzdy, pouzijeme iteraci s kratkym cekanim
            def _drain_pipe(pipe, chunks: list[str], is_stderr: bool):
                try:
                    while True:
                        line = pipe.readline()
                        if not line:
                            break
                        chunks.append(line)
                        stripped = line.rstrip("\n")
                        if not stripped:
                            continue
                        if is_stderr:
                            low = stripped.lower()
                            if "fatal" in low or "error" in low:
                                self._emit_output(f"Hmm, tady je problém: {stripped}")
                            else:
                                self._emit_output(stripped)
                        else:
                            self._emit_output(stripped)
                except Exception:
                    pass

            # Pouzijeme vlakna pro stdout/stderr aby nedoslo k deadlocku
            t_out = threading.Thread(target=_drain_pipe, args=(proc.stdout, stdout_chunks, False), daemon=True)
            t_err = threading.Thread(target=_drain_pipe, args=(proc.stderr, stderr_chunks, True), daemon=True)
            t_out.start()
            t_err.start()

            # Cekame na dokonceni procesu
            try:
                returncode = proc.wait()
            except Exception:
                returncode = proc.poll() or 1

            t_out.join(timeout=2)
            t_err.join(timeout=2)

            stdout = "".join(stdout_chunks)
            stderr = "".join(stderr_chunks)

            # TTS – jen souhrn, ne plny vystup, aby nedoslo k zahlceni
            if stdout and stdout.strip():
                summary = self._summarize_for_speech(stdout)
                if summary:
                    self._emit_speak(summary)

            if stderr and stderr.strip():
                # Rozlis chyby vs bezne info
                error_lines = [l for l in stderr.splitlines() if "fatal" in l.lower() or "error" in l.lower()]
                normal_lines = [l for l in stderr.splitlines() if l not in error_lines]
                # GUI uz bylo streamovano, takze jen TTS souhrn
                if error_lines:
                    for line in error_lines[:MAX_TTS_LINES]:
                        # GUI uz ma Hmm hlasku? Pridame jen pokud nebyla vypsana
                        # Zajistime, ze kazda error hlaska je zvyraznena
                        pass
                    # Mluvime jen souhrn chyb, ne kazdy radek zvlast
                    err_preview = "; ".join(error_lines[:2])
                    if len(err_preview) > MAX_TTS_CHARS:
                        err_preview = err_preview[:MAX_TTS_CHARS] + "…"
                    self._emit_speak(f"Hmm, tady je problém: {err_preview}")
                if normal_lines:
                    # Pro normalni stderr staci souhrn
                    norm_summary = self._summarize_for_speech("\n".join(normal_lines))
                    if norm_summary and not error_lines:
                        self._emit_speak(norm_summary)

            self._post_hooks(cmd, returncode)
            if self.signals:
                self.signals.finished.emit(returncode)

        except Exception as e:
            self._emit_output(f"Nastala neočekávaná chyba: {e}")
            self._emit_speak(f"Nastala neočekávaná chyba: {e}")
            if self.signals:
                self.signals.finished.emit(1)
        finally:
            with self._lock:
                self._current_proc = None

    def _pre_hooks(self, cmd: str) -> bool:
        if cmd.startswith("git commit") and "-m" not in cmd:
            self._emit_output('Git commit potřebuje -m "zpráva". Např.: git commit -m "Opravena chyba"')
            self._emit_speak("Git commit potřebuje zprávu s parametrem minus m")
            return False

        if cmd.startswith("git push"):
            self._emit_output("Posílám změny na server… vydrž chvíli 🤞")
            self._emit_speak("Posílám změny na server, vydrž chvíli")

        if self._is_flutter(cmd):
            self._emit_speak(self._flutter_pre(cmd))

        if re.search(r'<[^>]+>', cmd):
            self._emit_output(
                "Všiml jsem si, že příkaz obsahuje znaky < >. "
                "Shell je používá pro přesměrování souborů. "
                "Pokud to není záměr, zkus příkaz napsat jinak."
            )

        return True

    def _exit_message(self, code: int) -> str:
        friendly = {
            1: "Něco se nepovedlo. Zkus to znovu nebo zkontroluj parametry.",
            2: "Příkaz má chybnou syntaxi. Zkontroluj, co jsi napsal.",
            9009: "Program se nenašel. Zkontroluj, jestli je nainstalovaný.",
            128: "Git hlásí fatální chybu. Zkontroluj repozitář a oprávnění.",
        }
        return friendly.get(code, f"Příkaz skončil s kódem {code}. Zkus napsat help, pokud si nevíš rady.")

    def _post_hooks(self, cmd: str, returncode: int) -> None:
        if returncode != 0:
            msg = self._exit_message(returncode)
            self._emit_output(msg)
            self._emit_speak(msg)
            return

        if cmd.startswith("git commit"):
            self._emit_output("Skvěle! Commit proběhl v pořádku 💪")
            self._emit_speak("Commit proběhl v pořádku!")

        if cmd.startswith("git push"):
            self._emit_output("Push dokončen! 💪")
            self._emit_speak("Push dokončen!")

        if self._is_flutter(cmd):
            msg = self._flutter_post(cmd)
            self._emit_output(f"{msg} 💪")
            self._emit_speak(msg)

    def _is_flutter(self, cmd: str) -> bool:
        return any(cmd.startswith(c) for c in FLUTTER_COMMANDS)

    @staticmethod
    def _flutter_pre(cmd: str) -> str:
        if cmd.startswith("flutter run"):
            return "Spouštím Flutter aplikaci..."
        if cmd.startswith("flutter build"):
            return "Buildím Flutter projekt..."
        if cmd.startswith("flutter analyze"):
            return "Analyzuji Flutter kód..."
        if cmd.startswith("flutter test"):
            return "Spouštím Flutter testy..."
        if cmd.startswith("flutter clean"):
            return "Čistím Flutter projekt..."
        if cmd.startswith("flutter pub"):
            return "Pracuji s Flutter balíčky..."
        if cmd.startswith("flutter create"):
            return "Vytvářím nový Flutter projekt..."
        if cmd.startswith("flutter format"):
            return "Formátuji Flutter kód..."
        return "Spouštím Flutter příkaz..."

    @staticmethod
    def _flutter_post(cmd: str) -> str:
        if cmd.startswith("flutter run"):
            return "Flutter aplikace běží!"
        if cmd.startswith("flutter build"):
            return "Flutter build dokončen!"
        if cmd.startswith("flutter analyze"):
            return "Analýza Flutter kódu dokončena!"
        if cmd.startswith("flutter test"):
            return "Flutter testy dokončeny!"
        if cmd.startswith("flutter clean"):
            return "Flutter projekt vyčištěn!"
        if cmd.startswith("flutter pub"):
            return "Flutter balíčky aktualizovány!"
        if cmd.startswith("flutter create"):
            return "Nový Flutter projekt vytvořen!"
        if cmd.startswith("flutter format"):
            return "Flutter kód naformátován!"
        return "Flutter příkaz dokončen!"
