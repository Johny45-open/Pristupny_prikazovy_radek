from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QCheckBox, QSpinBox,
    QComboBox, QLineEdit, QLabel, QGroupBox, QHBoxLayout, QFontComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Nastavení terminálu")
        self.setAccessibleName("Nastavení terminálu")
        self.setAccessibleDescription("Dialog pro změnu nastavení terminálu. Použij Tab pro pohyb mezi prvky.")
        self.setModal(True)
        self.resize(480, 520)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        info = QLabel("Všechna nastavení se ukládají do terminal_config.json. Změny se projeví ihned po potvrzení.")
        info.setWordWrap(True)
        info.setAccessibleName("Informace")
        info.setAccessibleDescription("Všechna nastavení se ukládají do souboru terminal_config.json")
        layout.addWidget(info)

        # Skupina: Vzhled
        grp_appearance = QGroupBox("Vzhled")
        grp_appearance.setAccessibleName("Vzhled")
        form_appearance = QFormLayout()
        form_appearance.setSpacing(8)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Světlý", "Tmavý"])
        self.theme_combo.setAccessibleName("Motiv")
        self.theme_combo.setAccessibleDescription("Vyber světlý nebo tmavý motiv. Tmavý je šetrnější pro oči.")
        form_appearance.addRow("Motiv:", self.theme_combo)

        self.font_combo = QFontComboBox()
        self.font_combo.setAccessibleName("Typ písma")
        self.font_combo.setAccessibleDescription("Vyber font pro výstup a příkazový řádek.")
        form_appearance.addRow("Písmo:", self.font_combo)

        self.fontsize_spin = QSpinBox()
        self.fontsize_spin.setRange(6, 72)
        self.fontsize_spin.setSuffix(" pt")
        self.fontsize_spin.setAccessibleName("Velikost písma")
        self.fontsize_spin.setAccessibleDescription("Velikost písma od 6 do 72 bodů.")
        form_appearance.addRow("Velikost písma:", self.fontsize_spin)

        self.emoji_check = QCheckBox("Zobrazovat emoji ve výstupu")
        self.emoji_check.setAccessibleName("Zobrazovat emoji")
        self.emoji_check.setAccessibleDescription("Pokud vypnuto, emoji se z výstupu odstraní a nebudou čtena hlasem.")
        form_appearance.addRow(self.emoji_check)

        grp_appearance.setLayout(form_appearance)
        layout.addWidget(grp_appearance)

        # Skupina: Hlas
        grp_voice = QGroupBox("Hlasový výstup")
        grp_voice.setAccessibleName("Hlasový výstup")
        form_voice = QFormLayout()

        self.voice_check = QCheckBox("Hlas zapnut")
        self.voice_check.setAccessibleName("Hlas zapnut")
        self.voice_check.setAccessibleDescription("Zapíná nebo vypíná hlasové oznamování přes accessible_output2.")
        form_voice.addRow(self.voice_check)

        self.speak_mode_combo = QComboBox()
        self.speak_mode_combo.addItem("Automaticky (doporučeno)", "auto")
        self.speak_mode_combo.addItem("Vždy číst celý výstup", "full")
        self.speak_mode_combo.addItem("Nikdy nečíst výstup (jen stav)", "off")
        self.speak_mode_combo.setAccessibleName("Režim řeči")
        self.speak_mode_combo.setAccessibleDescription(
            "Automaticky zkracuje dlouhé výstupy, aby nedošlo k zahlcení hlasu. Vhodné pro NVDA."
        )
        form_voice.addRow("Režim řeči:", self.speak_mode_combo)

        grp_voice.setLayout(form_voice)
        layout.addWidget(grp_voice)

        # Skupina: Chování
        grp_behavior = QGroupBox("Chování")
        grp_behavior.setAccessibleName("Chování")
        form_behavior = QFormLayout()

        self.history_spin = QSpinBox()
        self.history_spin.setRange(10, 5000)
        self.history_spin.setAccessibleName("Limit historie výstupu")
        self.history_spin.setAccessibleDescription("Maximální počet řádků uchovaných ve výstupu.")
        form_behavior.addRow("Limit historie:", self.history_spin)

        self.greeting_edit = QLineEdit()
        self.greeting_edit.setAccessibleName("Uvítací zpráva")
        self.greeting_edit.setAccessibleDescription(
            "Text zobrazený při startu. Může obsahovat {cmd} pro vložení aktuální cesty nebo {cmd příkaz} pro výstup příkazu."
        )
        self.greeting_edit.setPlaceholderText("např. Vítej! Jsi v {cmd}")
        form_behavior.addRow("Uvítání:", self.greeting_edit)

        hint = QLabel("Tip: {cmd} vloží cestu, {cmd echo %date%} vloží datum.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 9pt;")
        hint.setAccessibleName("Nápověda k uvítání")
        form_behavior.addRow("", hint)

        grp_behavior.setLayout(form_behavior)
        layout.addWidget(grp_behavior)

        # Tlacitka
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.setAccessibleName("Potvrdit nebo zrušit")
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        # Prejmenuj tlacitka pro cestinu
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Uložit")
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Zrušit")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setAccessibleName("Uložit nastavení")
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setAccessibleName("Zrušit bez uložení")
        layout.addWidget(self.button_box)

        self.setLayout(layout)
        # Fokus na prvni prvek
        self.theme_combo.setFocus()

    def _load_values(self):
        theme = self.config.get("theme", "light")
        self.theme_combo.setCurrentIndex(0 if theme == "light" else 1)

        font_name = self.config.get("font_family", "Consolas")
        # QFontComboBox setCurrentFont
        self.font_combo.setCurrentFont(QFont(font_name))

        self.fontsize_spin.setValue(int(self.config.get("font_size", 12)))
        self.emoji_check.setChecked(bool(self.config.get("emoji_enabled", True)))
        self.voice_check.setChecked(bool(self.config.get("voice_enabled", True)))

        speak_mode = self.config.get("speak_mode", "auto")
        idx = {"auto": 0, "full": 1, "off": 2}.get(speak_mode, 0)
        self.speak_mode_combo.setCurrentIndex(idx)

        self.history_spin.setValue(int(self.config.get("history_limit", 100)))
        self.greeting_edit.setText(self.config.get("greeting", ""))

    def _on_accept(self):
        # Uloz do configu
        self.config["theme"] = "light" if self.theme_combo.currentIndex() == 0 else "dark"
        self.config["font_family"] = self.font_combo.currentFont().family()
        self.config["font_size"] = int(self.fontsize_spin.value())
        self.config["emoji_enabled"] = bool(self.emoji_check.isChecked())
        self.config["voice_enabled"] = bool(self.voice_check.isChecked())
        self.config["speak_mode"] = self.speak_mode_combo.currentData()
        self.config["history_limit"] = int(self.history_spin.value())
        self.config["greeting"] = self.greeting_edit.text().strip()
        self.accept()
