import sys
import subprocess
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPlainTextEdit, QPushButton

class MyTerminal(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Přístupná příkazovka")
        self.resize(600, 400)

        self.layout = QVBoxLayout()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.input = QLineEdit()
        self.input.returnPressed.connect(self.run_command)

        # Tlačítko pro přepínání režimu
        self.toggle_btn = QPushButton("Tmavý režim")
        self.toggle_btn.clicked.connect(self.toggle_theme)
        self.dark_mode = False  # výchozí světlý

        self.layout.addWidget(self.toggle_btn)
        self.layout.addWidget(self.output)
        self.layout.addWidget(self.input)
        self.setLayout(self.layout)

        # Dát focus hned po spuštění
        self.input.setFocus()

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

    def run_command(self):
        cmd = self.input.text()
        if not cmd.strip():
            return

        self.output.appendPlainText(f"> {cmd}")
        self.input.clear()
        self.input.setFocus()  # zpět focus

        if cmd.lower() == "exit":
            self.output.appendPlainText("Ukončuji terminál...")
            QApplication.quit()
            return

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            output_text = result.stdout
            error_text = result.stderr
            if output_text:
                self.output.appendPlainText(output_text)
            if error_text:
                self.output.appendPlainText(f"CHYBA: {error_text}")
        except Exception as e:
            self.output.appendPlainText(f"Výjimka: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    term = MyTerminal()
    term.show()
    sys.exit(app.exec())
