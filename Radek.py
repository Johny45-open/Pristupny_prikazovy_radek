import sys
import subprocess
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPlainTextEdit

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

        self.layout.addWidget(self.output)
        self.layout.addWidget(self.input)
        self.setLayout(self.layout)

    def run_command(self):
        cmd = self.input.text()
        self.output.appendPlainText(f"> {cmd}")
        self.input.clear()

        if cmd.lower() == "exit":
            self.output.appendPlainText("Ukončuji terminál...")
            QApplication.quit()
            return

        # Spuštění příkazu přes CMD / PowerShell
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
