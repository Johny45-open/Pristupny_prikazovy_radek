import sys
import subprocess
import threading
import io
import os
import json
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPlainTextEdit, QPushButton
from PyQt6.QtCore import Qt
from gtts import gTTS
import pygame

CONFIG_FILE = "terminal_config.json"

def safe_thread(target, *args):
    """Spustí thread a nikdy nenechá spadnout GUI."""
    def wrapper():
        try:
            target(*args)
        except Exception as e:
            print(f"CHYBA VE THREADU: {e}")
    threading.Thread(target=wrapper, daemon=True).start()

class FriendlyTerminal(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Přístupný a lidský terminál")
        self.resize(700, 500)

        # Layout a widgety
        self.layout = QVBoxLayout()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.input = QLineEdit()
        self.input.returnPressed.connect(self.run_command)

        self.toggle_btn = QPushButton()
        self.toggle_btn.clicked.connect(self.toggle_theme)

        self.layout.addWidget(self.toggle_btn)
        self.layout.addWidget(self.output)
        self.layout.addWidget(self.input)
        self.setLayout(self.layout)

        # Hlas a historie
        pygame.mixer.init()
        self.history = []
        self.history_index = -1
        self.input.keyPressEvent = self.custom_keypress

        # Jazyk TTS
        self.tts_lang = "cs"

        # Startovní adresář
        self.output.appendPlainText(f"Čau! Jsem tvůj přístupný terminál. Začínáme v: {os.getcwd()}")
        safe_thread(self.speak, f"Čau! Jsem tvůj přístupný terminál. Začínáme v: {os.getcwd()}")

        # Načíst téma z configu
        self.load_theme()

        # Focus
        self.input.setFocus()

        # Pro doplňování složek
        self.tab_index = 0
        self.last_tab_text = ""

    # ---- TÉMA ----
    def apply_dark_theme(self):
        self.setStyleSheet("""
            QWidget {background-color: #2b2b2b; color: #f0f0f0;}
            QLineEdit, QPlainTextEdit {background-color: #2b2b2b; color: #f0f0f0;}
            QPushButton {background-color: #444; color: #f0f0f0;}
        """)
        self.toggle_btn.setText("Světlý režim")

    def apply_light_theme(self):
        self.setStyleSheet("""
            QWidget {background-color: white; color: black;}
            QLineEdit, QPlainTextEdit {background-color: white; color: black;}
            QPushButton {background-color: lightgray; color: black;}
        """)
        self.toggle_btn.setText("Tmavý režim")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()
        self.save_theme()

    def save_theme(self):
        data = {"theme": "dark" if self.dark_mode else "light"}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_theme(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    theme = data.get("theme", "light")
                    self.dark_mode = (theme == "dark")
            except:
                self.dark_mode = False
        else:
            self.dark_mode = False

        if self.dark_mode:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

    # ---- HLAS ----
    def speak(self, text):
        try:
            # Filtrovat znaky, které TTS neumí
            safe_text = ''.join([c if 32 <= ord(c) <= 126 or ord(c) > 160 else ' ' for c in text])
            if not safe_text.strip():
                return
            tts = gTTS(text=safe_text, lang=self.tts_lang)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            pygame.mixer.music.load(fp, 'mp3')
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            self.output.appendPlainText(f"CHYBA HLASU: {e}")

    # ---- PŘÍKAZY ----
    def run_command(self):
        cmd = self.input.text().strip()
        if not cmd:
            return

        if cmd.lower() in ["ahoj", "čau"]:
            self.output.appendPlainText("Ahoj kámo! 😎 Jak se máš?")
            safe_thread(self.speak, "Ahoj kámo! Jak se máš?")
            self.input.clear()
            return

        if cmd.lower().startswith("lang "):
            self.tts_lang = cmd[5:].strip()
            self.output.appendPlainText(f"Jazyk TTS nastaven na: {self.tts_lang}")
            self.input.clear()
            return

        if cmd.lower().startswith("cd "):
            path = cmd[3:].strip().replace('"', '')
            try:
                os.chdir(path)
                self.output.appendPlainText(f"Super! Nový aktuální adresář: {os.getcwd()}")
                safe_thread(self.speak, f"Nový aktuální adresář: {os.getcwd()}")
            except Exception as e:
                self.output.appendPlainText(f"Ups, složku jsem nenašel 😅 {e}")
                safe_thread(self.speak, f"Ups, složku jsem nenašel. {e}")
            self.input.clear()
            return

        self.output.appendPlainText(f"> {cmd}")
        self.history.append(cmd)
        self.history_index = len(self.history)
        self.input.clear()

        if cmd.lower() == "exit":
            self.output.appendPlainText("Ukončuji terminál… měj se fajn! 👋")
            safe_thread(self.speak, "Ukončuji terminál, měj se fajn!")
            QApplication.quit()
            return

        safe_thread(self.execute_async, cmd)

    # ---- ASYNCHRONNÍ SPUŠTĚNÍ PŘÍKAZŮ ----
    def execute_async(self, cmd):
        try:
            # Git commit kontrola - musí mít -m
            if cmd.startswith("git commit") and "-m" not in cmd:
                self.output.appendPlainText(
                    'Git commit potřebuje -m "message". Např.: git commit -m "Popis změn"'
                )
                safe_thread(self.speak, "Git commit potřebuje zprávu s -m")
                return

            # Git push hlášení před spuštěním
            if cmd.startswith("git push"):
                self.output.appendPlainText("Push probíhá… čekej chvíli 🤞")
                safe_thread(self.speak, "Push probíhá… čekej chvíli")

            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            stdout, stderr = process.communicate()

            if stdout:
                self.output.appendPlainText(stdout)
                safe_thread(self.speak, stdout)

            if stderr:
                for line in stderr.splitlines():
                    low = line.lower()
                    if "fatal" in low or "error" in low:
                        self.output.appendPlainText(f"CHYBA: {line}")
                        safe_thread(self.speak, f"CHYBA: {line}")
                    else:
                        self.output.appendPlainText(line)
                        safe_thread(self.speak, line)

            # Přátelské zprávy po Gitu
            if cmd.startswith("git commit"):
                self.output.appendPlainText("Skvěle! Commit proběhl v pořádku 💪")
                safe_thread(self.speak, "Commit proběhl v pořádku!")
            if cmd.startswith("git push"):
                self.output.appendPlainText("Push dokončen! 💪")
                safe_thread(self.speak, "Push dokončen!")

        except Exception as e:
            self.output.appendPlainText(f"Výjimka: {e}")
            safe_thread(self.speak, str(e))

    # ---- HISTORIE A TAB ----
    def custom_keypress(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Up:
            if self.history and self.history_index > 0:
                self.history_index -= 1
                self.input.setText(self.history[self.history_index])
        elif key == Qt.Key.Key_Down:
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.input.setText(self.history[self.history_index])
            else:
                self.history_index = len(self.history)
                self.input.clear()
        elif key == Qt.Key.Key_Tab:
            text = self.input.text()
            if text.lower().startswith("cd "):
                partial = text[3:].strip()
                dir_to_search = os.path.dirname(partial) if os.path.dirname(partial) else os.getcwd()
                prefix = os.path.basename(partial)
                try:
                    all_dirs = [d for d in os.listdir(dir_to_search) if os.path.isdir(os.path.join(dir_to_search, d))]
                    matching_dirs = [d for d in all_dirs if d.startswith(prefix)]
                    if matching_dirs:
                        if getattr(self, 'last_tab_text', '') != partial:
                            self.tab_index = 0
                        if modifiers & Qt.KeyboardModifier.ShiftModifier:
                            self.tab_index = (self.tab_index - 1) % len(matching_dirs)
                        self.input.setText(f"cd {os.path.join(dir_to_search, matching_dirs[self.tab_index])}")
                        if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
                            self.tab_index = (self.tab_index + 1) % len(matching_dirs)
                        self.last_tab_text = partial
                except:
                    pass
        else:
            QLineEdit.keyPressEvent(self.input, event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    term = FriendlyTerminal()
    term.show()
    sys.exit(app.exec())
