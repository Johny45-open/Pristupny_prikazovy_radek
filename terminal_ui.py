import os
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPlainTextEdit, QPushButton
from PyQt6.QtCore import Qt

from config_manager import save_theme, load_theme
from tts_engine import TtsEngine
from theme_manager import ThemeManager
from command_history import CommandHistory
from tab_completer import TabCompleter
from command_executor import CommandExecutor


class FriendlyTerminal(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Přístupný a lidský terminál")
        self.resize(700, 500)

        self.tts = TtsEngine()
        self.history = CommandHistory()
        self.tab = TabCompleter()

        self._build_ui()
        self._init_theme()
        self._wire_events()

        self.output.appendPlainText(f"Čau! Jsem tvůj přístupný terminál. Začínáme v: {os.getcwd()}")
        self.tts.speak(f"Čau! Jsem tvůj přístupný terminál. Začínáme v: {os.getcwd()}")

        self.executor = CommandExecutor(
            output_callback=lambda t: self.output.appendPlainText(t),
            speak_callback=self.tts.speak,
        )

        self.input.setFocus()

    def _build_ui(self):
        self.layout = QVBoxLayout()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.input = QLineEdit()
        self.toggle_btn = QPushButton()

        self.layout.addWidget(self.toggle_btn)
        self.layout.addWidget(self.output)
        self.layout.addWidget(self.input)
        self.setLayout(self.layout)

    def _init_theme(self):
        self.theme = ThemeManager(self, load_theme())
        self.toggle_btn.setText(
            "Světlý režim" if self.theme.dark_mode else "Tmavý režim"
        )

    def _wire_events(self):
        self.input.returnPressed.connect(self.run_command)
        self.toggle_btn.clicked.connect(self._toggle_theme)
        self.input.keyPressEvent = self._custom_keypress

    def _toggle_theme(self):
        self.theme.toggle()
        save_theme(self.theme.dark_mode)
        self.toggle_btn.setText(
            "Světlý režim" if self.theme.dark_mode else "Tmavý režim"
        )

    def _custom_keypress(self, event):
        key = event.key()
        mod = event.modifiers()

        if key == Qt.Key.Key_Up:
            cmd = self.history.back()
            if cmd is not None:
                self.input.setText(cmd)

        elif key == Qt.Key.Key_Down:
            cmd = self.history.forward()
            if cmd is not None:
                self.input.setText(cmd)
            else:
                self.input.clear()

        elif key == Qt.Key.Key_Tab:
            text = self.input.text()
            shift = bool(mod & Qt.KeyboardModifier.ShiftModifier)
            completed = self.tab.complete_cd(text, shift)
            if completed is not None:
                self.input.setText(completed)

        else:
            QLineEdit.keyPressEvent(self.input, event)

    def run_command(self):
        cmd = self.input.text().strip()
        if not cmd:
            return

        if cmd.lower() in ["ahoj", "čau"]:
            self.output.appendPlainText("Ahoj kámo! 😎 Jak se máš?")
            self.tts.speak("Ahoj kámo! Jak se máš?")
            self.input.clear()
            return

        if cmd.lower().startswith("cd "):
            path = cmd[3:].strip().replace('"', "")
            try:
                os.chdir(path)
                msg = f"Super! Nový aktuální adresář: {os.getcwd()}"
                self.output.appendPlainText(msg)
                self.tts.speak(msg)
            except Exception as e:
                self.output.appendPlainText(f"Ups, složku jsem nenašel 😅 {e}")
                self.tts.speak(f"Ups, složku jsem nenašel. {e}")
            self.input.clear()
            return

        self.output.appendPlainText(f"> {cmd}")
        self.history.add(cmd)
        self.input.clear()

        if cmd.lower() == "exit":
            self.output.appendPlainText("Ukončuji terminál… měj se fajn! 👋")
            self.tts.speak("Ukončuji terminál, měj se fajn!")
            QApplication.quit()
            return

        self.executor.execute(cmd)
