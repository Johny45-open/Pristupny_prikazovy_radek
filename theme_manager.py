from PyQt6.QtWidgets import QWidget


_DARK = """
    QWidget {background-color: #2b2b2b; color: #f0f0f0;}
    QLineEdit, QPlainTextEdit {background-color: #2b2b2b; color: #f0f0f0;}
    QPushButton {background-color: #444; color: #f0f0f0;}
"""

_LIGHT = """
    QWidget {background-color: white; color: black;}
    QLineEdit, QPlainTextEdit {background-color: white; color: black;}
    QPushButton {background-color: lightgray; color: black;}
"""


class ThemeManager:
    def __init__(self, widget: QWidget, dark_mode: bool):
        self.widget = widget
        self.dark_mode = dark_mode
        self._apply()

    def toggle(self):
        self.dark_mode = not self.dark_mode
        self._apply()
        return self.dark_mode

    def _apply(self):
        self.widget.setStyleSheet(_DARK if self.dark_mode else _LIGHT)
