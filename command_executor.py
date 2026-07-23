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

    def _run(self, cmd: str) -> None:
        try:
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

            self._post_hooks(cmd)

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

        return True

    def _post_hooks(self, cmd: str) -> None:
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
