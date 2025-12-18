import sys
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
        # jednoduchá simulace příkazu
        if cmd.lower() == "ahoj":
            self.output.appendPlainText("Ahoj, kámo!")
        elif cmd.lower() == "help":
            self.output.appendPlainText("Dostupné příkazy: ahoj, help, exit")
        elif cmd.lower() == "exit":
            self.output.appendPlainText("Ukončuji terminál...")
            QApplication.quit()
        else:
            self.output.appendPlainText(f"Nerozumím příkazu: {cmd}")

        self.input.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    term = MyTerminal()
    term.show()
    sys.exit(app.exec())
