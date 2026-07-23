import sys
from PyQt6.QtWidgets import QApplication
from terminal_ui import FriendlyTerminal

if __name__ == "__main__":
    app = QApplication(sys.argv)
    term = FriendlyTerminal()
    term.show()
    sys.exit(app.exec())
