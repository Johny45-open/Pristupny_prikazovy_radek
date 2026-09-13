from PyQt6.QtWidgets import QWidget


_DARK = """
    QWidget {background-color: #2b2b2b; color: #f0f0f0;}
    QLineEdit, QPlainTextEdit {background-color: #2b2b2b; color: #f0f0f0; border: 1px solid #666;}
    QPushButton {background-color: #555; color: #f0f0f0; border: 1px solid #888; padding: 4px 10px;}
    QPushButton:hover {background-color: #666;}
    QPushButton:focus {border: 2px solid #4a90e2;}
    QMenuBar {background-color: #2b2b2b; color: #f0f0f0;}
    QMenu {background-color: #3a3a3a; color: #f0f0f0;}
"""

_LIGHT = """
    QWidget {background-color: white; color: black;}
    QLineEdit, QPlainTextEdit {background-color: white; color: black; border: 1px solid #999;}
    QPushButton {background-color: #e0e0e0; color: black; border: 1px solid #999; padding: 4px 10px;}
    QPushButton:hover {background-color: #d0d0d0;}
    QPushButton:focus {border: 2px solid #0066cc;}
    QMenuBar {background-color: #f0f0f0; color: black;}
    QMenu {background-color: white; color: black;}
"""

_HIGH_CONTRAST = """
    QWidget {background-color: black; color: white;}
    QLineEdit, QPlainTextEdit {background-color: black; color: white; border: 2px solid yellow;}
    QPushButton {background-color: black; color: yellow; border: 2px solid yellow; padding: 4px 10px;}
    QPushButton:hover {background-color: #222;}
    QPushButton:focus {border: 3px solid white;}
    QMenuBar {background-color: black; color: yellow;}
    QMenu {background-color: black; color: white; border: 1px solid yellow;}
"""


class ThemeManager:
    def __init__(self, widget: QWidget, dark_mode: bool):
        self.widget = widget
        self.dark_mode = dark_mode
        self.high_contrast = False
        self._apply()

    def toggle(self):
        # pokud je high contrast, nejprve ho vypni
        if self.high_contrast:
            self.high_contrast = False
            self.dark_mode = False
        else:
            self.dark_mode = not self.dark_mode
        self._apply()
        return self.dark_mode

    def set_high_contrast(self, enabled: bool):
        self.high_contrast = enabled
        self._apply()

    def _apply(self):
        if self.high_contrast:
            self.widget.setStyleSheet(_HIGH_CONTRAST)
        else:
            self.widget.setStyleSheet(_DARK if self.dark_mode else _LIGHT)
