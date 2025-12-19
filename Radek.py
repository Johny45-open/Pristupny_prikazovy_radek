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

        # Hlas
        pygame.mixer.init()
        self.history = []
        self.history_index = -1
        self.input.keyPressEvent = self.custom_keypress

        # Startovní adresář
        self.output.appendPlainText(f"Čau! Jsem tvůj přístupný terminál. Začínáme v: {os.getcwd()}")
        threading.Thread(target=self.speak, args=(f"Čau! Jsem tvůj přístupný terminál. Začínáme v: {os.getcwd()}",), daemon=True).start()

        # Jazyk TTS
        self.tts_lang = "cs"

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
        if self.dark_mode:
            self.dark_mode = False
            self.apply_light_theme()
        else:
            self.dark_mode = True
            self.apply_dark_theme()
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
                    if theme == "dark":
                        self.dark_mode = True
                        self.apply_dark_theme()
                    else:
                        self.dark_mode = False
                        self.apply_light_theme()
            except:
                self.dark_mode = False
                self.apply_light_theme()
        else:
            self.dark_mode = False
            self.apply_light_theme()

    # ---- HLAS ----
    def speak(self, text):
        try:
            tts = gTTS(text=text, lang=self.tts_lang)
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

        # Přátelské reakce na pozdravy
        if cmd.lower() in ["ahoj", "čau"]:
            self.output.appendPlainText("Ahoj kámo! 😎 Jak se máš?")
            threading.Thread(target=self.speak, args=("Ahoj kámo! Jak se máš?",), daemon=True).start()
            self.input.clear()
            return

        # Přepnutí jazyka TTS
        if cmd.lower().startswith("lang "):
            new_lang = cmd[5:].strip()
            self.tts_lang = new_lang
            self.output.appendPlainText(f"Jazyk TTS nastaven na: {self.tts_lang}")
            self.input.clear()
            return

        # cd + doplňování složek
        if cmd.lower().startswith("cd "):
            path = cmd[3:].strip().replace('"', '')
            try:
                os.chdir(path)
                self.output.appendPlainText(f"Super! Nový aktuální adresář: {os.getcwd()}")
                threading.Thread(target=self.speak, args=(f"Nový aktuální adresář: {os.getcwd()}",), daemon=True).start()
            except Exception as e:
                self.output.appendPlainText(f"Ups, složku jsem nenašel 😅 {e}")
                threading.Thread(target=self.speak, args=(f"Ups, složku jsem nenašel. {e}",), daemon=True).start()
            self.input.clear()
            return

        self.output.appendPlainText(f"> {cmd}")
        self.history.append(cmd)
        self.history_index = len(self.history)
        self.input.clear()

        if cmd.lower() == "exit":
            self.output.appendPlainText("Ukončuji terminál… měj se fajn! 👋")
            threading.Thread(target=self.speak, args=("Ukončuji terminál, měj se fajn!",), daemon=True).start()
            QApplication.quit()
            return

        threading.Thread(target=self.execute_async, args=(cmd,), daemon=True).start()

    def execute_async(self, cmd):
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, encoding='utf-8')
            stdout, stderr = process.communicate()

            if stdout:
                self.output.appendPlainText(stdout)
                threading.Thread(target=self.speak, args=(stdout,), daemon=True).start()

            if stderr:
                for line in stderr.splitlines():
                    if "fatal" in line.lower() or "error" in line.lower():
                        self.output.appendPlainText(f"CHYBA: {line}")
                        threading.Thread(target=self.speak, args=(f"CHYBA: {line}",), daemon=True).start()
                    else:
                        self.output.appendPlainText(line)
                        threading.Thread(target=self.speak, args=(line,), daemon=True).start()

            # Přátelská zpráva při Git commit/push
            if cmd.startswith("git commit"):
                self.output.appendPlainText("Skvěle! Commit proběhl v pořádku 💪")
                threading.Thread(target=self.speak, args=("Commit proběhl v pořádku!",), daemon=True).start()
            if cmd.startswith("git push"):
                self.output.appendPlainText("Push probíhá… držíme palce! 🤞")
                threading.Thread(target=self.speak, args=("Push probíhá, držíme palce!",), daemon=True).start()

        except Exception as e:
            self.output.appendPlainText(f"Výjimka: {e}")
            threading.Thread(target=self.speak, args=(str(e),), daemon=True).start()

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
