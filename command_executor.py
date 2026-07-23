import re
import subprocess
import threading

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


class CommandExecutor:
    def __init__(self, output_callback, speak_callback):
        self._output = output_callback
        self._speak = speak_callback

    def execute(self, cmd: str) -> None:
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

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

    def _run(self, cmd: str) -> None:
        try:
            fixed = self._semicolon_to_ampersand(cmd)
            if fixed != cmd:
                self._output("Pozor: středník ; byl nahrazen & pro cmd.exe.")
            cmd = fixed

            if not self._pre_hooks(cmd):
                return

            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            stdout, stderr = proc.communicate()

            if stdout:
                self._output(stdout)
                self._speak(stdout)

            if stderr:
                for line in stderr.splitlines():
                    low = line.lower()
                    if "fatal" in low or "error" in low:
                        self._output(f"CHYBA: {line}")
                        self._speak(f"CHYBA: {line}")
                    else:
                        self._output(line)
                        self._speak(line)

            self._post_hooks(cmd, proc.returncode)

        except Exception as e:
            self._output(f"Výjimka: {e}")
            self._speak(str(e))

    def _pre_hooks(self, cmd: str) -> bool:
        if cmd.startswith("git commit") and "-m" not in cmd:
            self._output('Git commit potřebuje -m "message". Např.: git commit -m "Popis změn"')
            self._speak("Git commit potřebuje zprávu s -m")
            return False

        if cmd.startswith("git push"):
            self._output("Push probíhá… čekej chvíli 🤞")
            self._speak("Push probíhá… čekej chvíli")

        if self._is_flutter(cmd):
            self._speak(self._flutter_pre(cmd))

        if re.search(r'<[^>]+>', cmd):
            self._output(
                "Pozor: příkaz obsahuje znaky < >, "
                "které shell používá pro přesměrování souborů. "
                "Pokud to není záměr, zkus příkaz zapsat jinak."
            )

        return True

    def _post_hooks(self, cmd: str, returncode: int) -> None:
        if returncode != 0:
            self._speak(f"Příkaz skončil s chybou číslo {returncode}")
            return

        if cmd.startswith("git commit"):
            self._output("Skvěle! Commit proběhl v pořádku 💪")
            self._speak("Commit proběhl v pořádku!")

        if cmd.startswith("git push"):
            self._output("Push dokončen! 💪")
            self._speak("Push dokončen!")

        if self._is_flutter(cmd):
            msg = self._flutter_post(cmd)
            self._output(f"{msg} 💪")
            self._speak(msg)

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
