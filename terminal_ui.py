import os
import re
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPlainTextEdit, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from config_manager import load_config, save_config
from tts_engine import TtsEngine
from theme_manager import ThemeManager
from command_history import CommandHistory
from tab_completer import TabCompleter
from command_executor import CommandExecutor

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # misc
    "]+"
)


def strip_emoji(text: str) -> str:
    return EMOJI_RE.sub("", text).strip()


class FriendlyTerminal(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.setWindowTitle("Přístupný a lidský terminál")
        self._restore_geometry()

        self.tts = TtsEngine()
        self.history = CommandHistory(maxlen=self.config.get("history_limit", 100))
        self.tab = TabCompleter()

        self._build_ui()
        self._apply_config_ui()
        self._init_theme()
        self._wire_events()

        self.executor = CommandExecutor(
            output_callback=lambda t: self._output(t),
            speak_callback=lambda t: self._speak(t),
        )

        self._show_greeting()
        self.input.setFocus()

    # ---------- UI setup ----------

    def _build_ui(self):
        self.layout = QVBoxLayout()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.input = QLineEdit()
        self.toggle_btn = QPushButton()
        self.layout.addWidget(self.toggle_btn)
        self.layout.addWidget(self.output)
        self.layout.addWidget(self.input)
        self.setLayout(self.layout)

    def _apply_config_ui(self):
        font = QFont(
            self.config.get("font_family", "Consolas"),
            self.config.get("font_size", 12),
        )
        self.output.setFont(font)
        self.input.setFont(font)
        limit = self.config.get("history_limit", 1000)
        self.output.setMaximumBlockCount(limit)

    def _restore_geometry(self):
        geo = self.config.get("window_geometry")
        if geo and isinstance(geo, dict):
            self.setGeometry(
                geo.get("x", 100), geo.get("y", 100),
                geo.get("w", 700), geo.get("h", 500),
            )
        else:
            self.resize(700, 500)

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)

    def _save_geometry(self):
        geo = self.geometry()
        self.config["window_geometry"] = {
            "x": geo.x(), "y": geo.y(),
            "w": geo.width(), "h": geo.height(),
        }
        save_config(self.config)

    def _init_theme(self):
        dark = self.config.get("theme", "light") == "dark"
        self.theme = ThemeManager(self, dark)
        self.toggle_btn.setText("Světlý režim" if dark else "Tmavý režim")

    def _wire_events(self):
        self.input.returnPressed.connect(self.run_command)
        self.toggle_btn.clicked.connect(self._toggle_theme)
        self.input.keyPressEvent = self._custom_keypress

    def _toggle_theme(self):
        self.theme.toggle()
        self.config["theme"] = "dark" if self.theme.dark_mode else "light"
        save_config(self.config)
        self.toggle_btn.setText(
            "Světlý režim" if self.theme.dark_mode else "Tmavý režim",
        )

    def _show_greeting(self):
        greeting = self.config.get("greeting", "")
        if not greeting:
            greeting = f"Čau! Jsem tvůj přístupný terminál. Začínáme v: {os.getcwd()}"
        self._output(greeting)
        self._speak(greeting)

    def _show_help(self):
        lines = [
            "Můžeš používat tyhle příkazy:",
            "",
            "  ahoj / čau       – pozdrav, terminál odpoví",
            "  cd <cesta>       – změna adresáře",
            "  exit             – ukončení terminálu",
            "  set              – zobrazí aktuální nastavení",
            "  set <klíč> <hodnota> – změní nastavení",
            "  help / ?         – tahle nápověda",
            "",
            "Nastavení, která jde měnit:",
            "  voice on/off         – hlasová odezva",
            "  fontsize <6-72>      – velikost písma",
            "  font <název>         – typ písma",
            "  emoji on/off         – zobrazování emoji",
            "  greeting <text>      – vlastní uvítání",
            "  alias <z> <příkaz>   – zkratka pro příkaz",
            "",
            "Aliasy:",
            "  set alias g git    – pak stačí napsat g místo git",
            "  set alias f flutter – pak stačí napsat f místo flutter",
            "  set alias g        – smaže alias g",
            "",
            "Cokoliv jiného se pošle do příkazové řádky Windows.",
            "Terminál zná i speciální hlášky pro git a flutter.",
        ]
        self._output("\n".join(lines))
        self._speak(
            "Zobrazuji nápovědu. K dispozici jsou příkazy: ahoj, cd, set, exit a help. "
            "Všechna nastavení se mění přes set. Cokoliv jiného jde do příkazové řádky."
        )

    # ---------- output helpers ----------

    def _output(self, text: str) -> None:
        if not self.config.get("emoji_enabled", True):
            text = strip_emoji(text)
        self.output.appendPlainText(text)

    def _speak(self, text: str, force: bool = False) -> None:
        if not force and not self.config.get("voice_enabled", True):
            return
        self.tts.speak(text)

    # ---------- key events ----------

    def _custom_keypress(self, event):
        key = event.key()
        mod = event.modifiers()

        if key == Qt.Key.Key_Up:
            cmd = self.history.back()
            if cmd is not None:
                self.input.setText(cmd)

        elif key == Qt.Key.Key_Down:
            cmd = self.history.forward()
            if cmd is not None:
                self.input.setText(cmd)
            else:
                self.input.clear()

        elif key == Qt.Key.Key_Tab:
            text = self.input.text()
            shift = bool(mod & Qt.KeyboardModifier.ShiftModifier)
            completed = self.tab.complete_cd(text, shift)
            if completed is not None:
                self.input.setText(completed)

        else:
            QLineEdit.keyPressEvent(self.input, event)

    # ---------- command execution ----------

    def run_command(self):
        cmd = self.input.text().strip()
        if not cmd:
            return

        if cmd.lower() in ["ahoj", "čau"]:
            self._output("Ahoj kámo! 😎 Jak se máš?")
            self._speak("Ahoj kámo! Jak se máš?")
            self.input.clear()
            return

        if cmd.lower() in ("help", "nápověda", "?"):
            self._show_help()
            self.input.clear()
            return

        if cmd.lower().startswith("set "):
            self._handle_set(cmd[4:].strip())
            self.input.clear()
            return

        if cmd.lower().startswith("cd "):
            path = cmd[3:].strip().replace('"', "")
            try:
                os.chdir(path)
                msg = f"Super! Nový aktuální adresář: {os.getcwd()}"
                self._output(msg)
                self._speak(msg)
            except Exception as e:
                self._output(f"Ups, složku jsem nenašel 😅 {e}")
                self._speak(f"Ups, složku jsem nenašel. {e}")
            self.input.clear()
            return

        self._output(f"> {cmd}")
        self.history.add(cmd)
        self.input.clear()

        if cmd.lower() == "exit":
            self._output("Ukončuji terminál… měj se fajn! 👋")
            self._speak("Ukončuji terminál, měj se fajn!")
            QApplication.quit()
            return

        cmd = self._expand_aliases(cmd)
        self.executor.execute(cmd)

    def _expand_aliases(self, cmd: str) -> str:
        aliases = self.config.get("aliases", {})
        words = cmd.split()
        if words and words[0] in aliases:
            rest = " ".join(words[1:])
            expanded = aliases[words[0]]
            return f"{expanded} {rest}" if rest else expanded
        return cmd

    # ---------- set commands ----------

    def _handle_set(self, args: str):
        if not args:
            self._show_settings()
            return

        parts = args.split(maxsplit=1)
        key = parts[0].lower()

        if len(parts) > 1:
            value = parts[1]
        else:
            value = None

        handler = {
            "voice": self._set_voice,
            "fontsize": self._set_fontsize,
            "font": self._set_font,
            "fontfamily": self._set_font,
            "emoji": self._set_emoji,
            "greeting": self._set_greeting,
            "alias": self._set_alias,
        }.get(key)

        if handler:
            handler(value)
            save_config(self.config)
        else:
            self._output(f"Neznámé nastavení: {key}")
            self._speak(f"Neznámé nastavení: {key}")

    def _show_settings(self):
        def fmt(name: str) -> str:
            val = self.config.get(name)
            if isinstance(val, bool):
                return "zapnuto" if val else "vypnuto"
            return str(val)

        lines = [
            "Aktuální nastavení:",
            f"  téma: {self.config.get('theme')}",
            f"  písmo: {self.config.get('font_family')}",
            f"  velikost písma: {self.config.get('font_size')}",
            f"  hlas: {fmt('voice_enabled')}",
            f"  emoji: {fmt('emoji_enabled')}",
            f"  limit historie: {self.config.get('history_limit')}",
        ]
        aliases = self.config.get("aliases", {})
        if aliases:
            lines.append("  aliasy:")
            for k, v in aliases.items():
                lines.append(f"    {k} => {v}")
        self._output("\n".join(lines))
        self._speak("Zobrazuji aktuální nastavení.")

    def _set_voice(self, value):
        if value in ("on", "1", "true", "yes"):
            self.config["voice_enabled"] = True
            msg = "Hlas zapnut."
        elif value in ("off", "0", "false", "no"):
            self.config["voice_enabled"] = False
            msg = "Hlas vypnut."
        else:
            msg = "Použij: set voice on/off"
        self._output(msg)
        self._speak(msg, force=True)

    def _set_fontsize(self, value):
        try:
            size = int(value)
            if size < 6 or size > 72:
                raise ValueError
            self.config["font_size"] = size
            font = QFont(self.config.get("font_family", "Consolas"), size)
            self.output.setFont(font)
            self.input.setFont(font)
            msg = f"Velikost písma nastavena na {size}."
        except (ValueError, TypeError):
            msg = "Použij: set fontsize <číslo 6-72>"
        self._output(msg)
        self._speak(msg)

    def _set_font(self, value):
        if not value:
            msg = "Použij: set font <název písma>"
        else:
            self.config["font_family"] = value
            font = QFont(value, self.config.get("font_size", 12))
            self.output.setFont(font)
            self.input.setFont(font)
            msg = f"Písmo nastaveno na {value}."
        self._output(msg)
        self._speak(msg)

    def _set_emoji(self, value):
        if value in ("on", "1", "true", "yes"):
            self.config["emoji_enabled"] = True
            msg = "Emoji zapnuto."
        elif value in ("off", "0", "false", "no"):
            self.config["emoji_enabled"] = False
            msg = "Emoji vypnuto."
        else:
            msg = "Použij: set emoji on/off"
        self._output(msg)
        self._speak(msg)

    def _set_greeting(self, value):
        if not value:
            self.config["greeting"] = ""
            msg = "Uvítací zpráva vrácena na výchozí."
        else:
            self.config["greeting"] = value
            msg = "Uvítací zpráva nastavena."
        self._output(msg)
        self._speak(msg)

    def _set_alias(self, value):
        if not value:
            msg = "Použij: set alias <zkratka> <příkaz>"
        else:
            parts = value.split(maxsplit=1)
            alias_key = parts[0]
            if len(parts) == 1:
                aliases = self.config.get("aliases", {})
                if alias_key in aliases:
                    removed = aliases.pop(alias_key)
                    self.config["aliases"] = aliases
                    msg = f"Alias {alias_key} => {removed} smazán."
                else:
                    msg = f"Alias {alias_key} neexistuje."
            else:
                alias_val = parts[1]
                aliases = self.config.get("aliases", {})
                aliases[alias_key] = alias_val
                self.config["aliases"] = aliases
                msg = f"Alias nastaven: {alias_key} => {alias_val}."
        self._output(msg)
        self._speak(msg)
