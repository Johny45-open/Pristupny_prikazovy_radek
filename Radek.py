import sys
import subprocess
import threading
import io
import os
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPlainTextEdit, QPushButton
from gtts import gTTS
import pygame
from langdetect import detect

class AccessibleGitTerminal(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Přístupný Git terminál")
        self.resize(700, 500)

        # Layout a widgety
        self.layout = QVBoxLayout()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.input = QLineEdit()
        self.input.returnPressed.connect(self.run_command)

        # Tlačítko pro přepínání světlého/tmavého režimu
        self.toggle_btn = QPushButton("Tmavý režim")
        self.toggle_btn.clicked.connect(self.toggle_theme)
        self.dark_mode = False

        self.layout.addWidget(self.toggle_btn)
        self.layout.addWidget(self.output)
        self.layout.addWidget(self.input)
        self.setLayout(self.layout)

        # Dát focus hned po spuštění
        self.input.setFocus()

        # Inicializace hlasu
        pygame.mixer.init()
        self.history = []
        self.history_index = -1
        self.input.keyPressEvent = self.custom_keypress

        # Ukázat startovní adresář
        self.output.appendPlainText(f"Startovní adresář: {os.getcwd()}")

    # Přepínání světlého/tmavého režimu
    def toggle_theme(self):
        if self.dark_mode:
            # Světlý režim
            self.setStyleSheet("""
                QWidget {
                    background-color: white;
                    color: black;
                }
                QLineEdit, QPlainTextEdit {
                    background-color: white;
                    color: black;
                }
                QPushButton {
                    background-color: lightgray;
                    color: black;
                }
            """)
            self.toggle_btn.setText("Tmavý režim")
            self.dark_mode = False
        else:
            # Tmavý režim
            self.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    color: #f0f0f0;
                }
                QLineEdit, QPlainTextEdit {
                    background-color: #2b2b2b;
                    color: #f0f0f0;
                }
                QPushButton {
                    background-color: #444;
                    color: #f0f0f0;
                }
            """)
            self.toggle_btn.setText("Světlý režim")
            self.dark_mode = True

    # Hlasový výstup s detekcí jazyka
    def speak(self, text):
        try:
            lang = detect(text)
        except:
            lang = 'cs'
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        pygame.mixer.music.load(fp, 'mp3')
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    # Spuštění příkazu
    def run_command(self):
        cmd = self.input.text()
        if not cmd.strip():
            return

        # Speciální příkaz: cd
        if cmd.lower().startswith("cd "):
            path = cmd[3:].strip().replace('"', '')
            try:
                os.chdir(path)
                self.output.appendPlainText(f"Nový aktuální adresář: {os.getcwd()}")
            except Exception as e:
                self.output.appendPlainText(f"CHYBA při změně adresáře: {e}")
            self.input.clear()
            self.input.setFocus()
            return

        self.output.appendPlainText(f"> {cmd}")
        self.history.append(cmd)
        self.history_index = len(self.history)
        self.input.clear()
        self.input.setFocus()

        if cmd.lower() == "exit":
            self.output.appendPlainText("Ukončuji terminál...")
            threading.Thread(target=self.speak, args=("Ukončuji terminál",), daemon=True).start()
            QApplication.quit()
            return

        threading.Thread(target=self.execute_async, args=(cmd,), daemon=True).start()

    # Asynchronní provedení příkazu
    def execute_async(self, cmd):
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, encoding='utf-8')
            stdout, stderr = process.communicate()

            # Výstup z příkazu
            if stdout:
                self.output.appendPlainText(stdout)
                threading.Thread(target=self.speak, args=(stdout,), daemon=True).start()

            # Chyby – jen pokud skutečně obsahují fatal/error
            if stderr:
                for line in stderr.splitlines():
                    if "fatal" in line.lower() or "error" in line.lower():
                        self.output.appendPlainText(f"CHYBA: {line}")
                        threading.Thread(target=self.speak, args=(f"CHYBA: {line}",), daemon=True).start()
                    else:
                        self.output.appendPlainText(line)
                        threading.Thread(target=self.speak, args=(line,), daemon=True).start()

        except Exception as e:
            self.output.appendPlainText(f"Výjimka: {e}")
            threading.Thread(target=self.speak, args=(str(e),), daemon=True).start()

    # Historie příkazů (šipky nahoru/dolů)
    def custom_keypress(self, event):
        key = event.key()
        from PyQt6.QtCore import Qt
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
        else:
            QLineEdit.keyPressEvent(self.input, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    term = AccessibleGitTerminal()
    term.show()
    sys.exit(app.exec())
