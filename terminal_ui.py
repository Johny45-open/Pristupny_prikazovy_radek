import os
import re
import subprocess
import threading
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton,
    QMenuBar, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QEvent, QObject, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QAction, QShortcut

from config_manager import load_config, save_config
from tts_engine import TtsEngine
from theme_manager import ThemeManager
from command_history import CommandHistory
from tab_completer import TabCompleter
from command_executor import CommandExecutor, ExecutorSignals
from PyQt6.QtCore import pyqtSignal


class _GreetingSignals(QObject):
    greet = pyqtSignal(str, bool)

try:
    from PyQt6.QtGui import QAccessible
    HAS_ACCESSIBLE = True
except ImportError:
    HAS_ACCESSIBLE = False

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


MAX_SPEAK_CHARS = 500


def truncate_for_speech(text: str, limit: int = MAX_SPEAK_CHARS) -> str:
    clean = strip_emoji(text)
    if len(clean) > limit:
        return clean[:limit].rstrip() + " … zkráceno"
    return clean


class FriendlyTerminal(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.setWindowTitle("Přístupný a lidský terminál")
        self._restore_geometry()

        self.tts = TtsEngine()
        self.history = CommandHistory(maxlen=self.config.get("history_limit", 100))
        self.tab = TabCompleter()
        # draft pro historii – uchovava rozepsany text pri prochazeni Up/Down
        self._draft_input = ""

        self._build_ui()
        self._apply_config_ui()
        self._init_theme()
        self._init_executor()
        self._wire_events()

        self._show_greeting()
        # Fokus s mirnym zpozdenim, aby NVDA stihla okno nahlasit
        QTimer.singleShot(100, lambda: self.input.setFocus())

    # ---------- UI setup ----------

    def _build_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(8, 4, 8, 8)
        self.layout.setSpacing(6)

        # Menu bar pro objevitelnost (NVDA ho precte)
        self.menu_bar = QMenuBar()
        self.menu_bar.setAccessibleName("Hlavní nabídka")
        file_menu = self.menu_bar.addMenu("&Soubor")
        file_menu.setAccessibleName("Soubor")

        self.action_settings = QAction("Nastavení…", self)
        self.action_settings.setShortcut(QKeySequence("Ctrl+,"))
        self.action_settings.setStatusTip("Otevře dialog nastavení")
        self.action_settings.triggered.connect(self._open_settings)
        file_menu.addAction(self.action_settings)

        self.action_help = QAction("Nápověda", self)
        self.action_help.setShortcut(QKeySequence("F1"))
        self.action_help.triggered.connect(self._show_help)
        file_menu.addAction(self.action_help)

        self.action_clear = QAction("Vymazat výstup", self)
        self.action_clear.setShortcut(QKeySequence("Ctrl+L"))
        self.action_clear.triggered.connect(self.clear_output)
        file_menu.addAction(self.action_clear)

        file_menu.addSeparator()
        self.action_quit = QAction("Ukončit", self)
        self.action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.action_quit.triggered.connect(self.close)
        file_menu.addAction(self.action_quit)

        self.layout.addWidget(self.menu_bar)

        # Horni panel s tlacitky
        btn_row = QHBoxLayout()
        self.toggle_btn = QPushButton()
        self.toggle_btn.setAccessibleName("Přepnout motiv")
        self.toggle_btn.setAccessibleDescription("Přepíná mezi světlým a tmavým režimem. Klávesová zkratka Ctrl+T.")
        self.toggle_btn.setToolTip("Přepnout světlý/tmavý režim (Ctrl+T)")
        self.toggle_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.settings_btn = QPushButton("Nastavení…")
        self.settings_btn.setAccessibleName("Nastavení")
        self.settings_btn.setAccessibleDescription("Otevře dialog nastavení. Klávesová zkratka Ctrl+čárka.")
        self.settings_btn.setToolTip("Otevřít nastavení (Ctrl+,)")
        self.settings_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        btn_row.addWidget(self.toggle_btn)
        btn_row.addWidget(self.settings_btn)
        btn_row.addStretch()
        self.layout.addLayout(btn_row)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setAccessibleName("Výstup terminálu")
        self.output.setAccessibleDescription(
            "Historie výstupu, pouze pro čtení. Procházej šipkami, když má fokus. Nové řádky se oznamují automaticky."
        )
        self.output.setToolTip("Výstup příkazů – procházej šipkami, kopíruj Ctrl+C")
        self.output.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.output.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        # Umozni NVDA cist po radcich i v browse modu
        self.output.setUndoRedoEnabled(False)

        self.input = QLineEdit()
        self.input.setAccessibleName("Příkazový řádek")
        self.input.setAccessibleDescription(
            "Zadej příkaz a stiskni Enter. Šipka nahoru a dolů prochází historii, Tab doplňuje složky po cd. "
            "Ctrl+Tab přepne fokus, Ctrl+C přeruší běžící příkaz."
        )
        self.input.setPlaceholderText("Zadej příkaz, např. dir, help, cd ..")
        self.input.setToolTip("Příkazový řádek – Enter spustí, šipky historie, Tab doplnění")
        self.input.setClearButtonEnabled(True)
        self.input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Spravne poradi fokusu: input -> tlacitka -> output (aby Tab nezacyklil input)
        # Ale logicky chceme Tab z inputu na tlacitka, Shift+Tab zpet
        self.setTabOrder(self.input, self.toggle_btn)
        self.setTabOrder(self.toggle_btn, self.settings_btn)
        self.setTabOrder(self.settings_btn, self.output)

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
        # QPlainTextEdit maximumBlockCount 0 = neomezene
        try:
            self.output.setMaximumBlockCount(int(limit))
        except Exception:
            self.output.setMaximumBlockCount(1000)

    def _restore_geometry(self):
        geo = self.config.get("window_geometry")
        if geo and isinstance(geo, dict):
            try:
                from PyQt6.QtGui import QGuiApplication
                screen_geo = QGuiApplication.primaryScreen().availableGeometry()
                x, y, w, h = geo.get("x", 100), geo.get("y", 100), geo.get("w", 700), geo.get("h", 500)
                # validace – okno musi byt viditelne
                if w < 400: w = 700
                if h < 300: h = 500
                # pokud je mimo obrazovku, vycentruj
                if x < screen_geo.x() - w or x > screen_geo.right() or y < screen_geo.y() - 50 or y > screen_geo.bottom():
                    self.resize(w, h)
                else:
                    self.setGeometry(x, y, w, h)
                return
            except Exception:
                pass
        self.resize(700, 500)

    def closeEvent(self, event):
        self._save_geometry()
        # ukoncit bezici prikaz
        try:
            if hasattr(self, 'executor'):
                self.executor.terminate_current()
        except Exception:
            pass
        super().closeEvent(event)

    def _save_geometry(self):
        try:
            geo = self.geometry()
            self.config["window_geometry"] = {
                "x": geo.x(), "y": geo.y(),
                "w": geo.width(), "h": geo.height(),
            }
            save_config(self.config)
        except Exception:
            pass

    def _init_theme(self):
        dark = self.config.get("theme", "light") == "dark"
        self.theme = ThemeManager(self, dark)
        self.toggle_btn.setText("Světlý režim" if dark else "Tmavý režim")

    def _init_executor(self):
        self.signals = ExecutorSignals()
        self.signals.output.connect(self._output)
        self.signals.speak.connect(self._speak)
        self.signals.started.connect(self._on_command_started)
        self.signals.finished.connect(self._on_command_finished)
        # pro async greeting
        self._greet_obj = _GreetingSignals()
        self._greet_obj.greet.connect(self._on_greeting_ready)
        self.executor = CommandExecutor(signals=self.signals)

    def _wire_events(self):
        self.input.returnPressed.connect(self.run_command)
        self.toggle_btn.clicked.connect(self._toggle_theme)
        self.settings_btn.clicked.connect(self._open_settings)

        # Event filter misto monkey-patch keyPressEvent
        self.input.installEventFilter(self)

        # Globalni zkratky
        sc_toggle = QShortcut(QKeySequence("Ctrl+T"), self)
        sc_toggle.activated.connect(self._toggle_theme)
        sc_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        sc_copy.activated.connect(self._handle_ctrl_c)
        sc_esc = QShortcut(QKeySequence("Escape"), self)
        sc_esc.activated.connect(lambda: self.input.setFocus())
        sc_next = QShortcut(QKeySequence("Ctrl+Tab"), self)
        sc_next.activated.connect(self._focus_next)
        sc_prev = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        sc_prev.activated.connect(self._focus_prev)

        # Kdyz ma fokus output, Escape vrati na input
        self.output.installEventFilter(self)

        # Accessible Shortcut pro napovedu uz je v menu (F1), ale pridame i primo
        sc_help = QShortcut(QKeySequence("F1"), self)
        sc_help.activated.connect(self._show_help)

    def _focus_next(self):
        self.focusNextChild()

    def _focus_prev(self):
        self.focusPreviousChild()

    def _handle_ctrl_c(self):
        # Pokud bezi prikaz, prerus ho; jinak kopiruj chovani terminalu (zrus radek)
        if hasattr(self.executor, '_current_proc') and self.executor._current_proc and self.executor._current_proc.poll() is None:
            self.executor.terminate_current()
            self._output("Příkaz přerušen uživatelem (Ctrl+C).")
            self._speak("Příkaz přerušen.")
        else:
            self.input.clear()
            self._speak("Řádek vymazán.")

    def clear_output(self):
        self.output.clear()
        self._output("Výstup vymazán.")
        self._speak("Výstup vymazán.")
        self.input.setFocus()

    def _toggle_theme(self):
        self.theme.toggle()
        self.config["theme"] = "dark" if self.theme.dark_mode else "light"
        save_config(self.config)
        self.toggle_btn.setText(
            "Světlý režim" if self.theme.dark_mode else "Tmavý režim",
        )
        msg = "Tmavý režim zapnut." if self.theme.dark_mode else "Světlý režim zapnut."
        self._output(msg)
        self._speak(msg)
        self._announce_accessible(msg)
        self.input.setFocus()

    def _open_settings(self):
        from settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            # dialog ulozil do self.config primo
            save_config(self.config)
            self._apply_config_ui()
            # tema se mohlo zmenit v dialogu
            dark = self.config.get("theme", "light") == "dark"
            if dark != self.theme.dark_mode:
                self.theme.dark_mode = dark
                self.theme._apply()
                self.toggle_btn.setText("Světlý režim" if dark else "Tmavý režim")
            self._output("Nastavení uloženo.")
            self._speak("Nastavení uloženo.")
            self._announce_accessible("Nastavení uloženo")
        self.input.setFocus()

    def _announce_accessible(self, text: str):
        if HAS_ACCESSIBLE:
            try:
                # Pokus o live region oznameni – NVDA zachyti Alert
                from PyQt6.QtGui import QAccessibleEvent
                ev = QAccessibleEvent(self, QAccessible.Event.Alert)
                QAccessible.updateAccessibility(ev)
            except Exception:
                pass

    def _on_command_started(self, cmd: str):
        self.input.setEnabled(False)
        self.input.setAccessibleDescription("Příkaz běží, čekej na dokončení. Stiskni Ctrl+C pro přerušení.")
        self._announce_accessible(f"Spuštěn příkaz {cmd}")

    def _on_command_finished(self, code: int):
        self.input.setEnabled(True)
        self.input.setAccessibleDescription(
            "Zadej příkaz a stiskni Enter. Šipka nahoru a dolů prochází historii, Tab doplňuje složky po cd."
        )
        # Vratit fokus – QTimer aby se predchozi emit stihl zpracovat
        QTimer.singleShot(0, lambda: self.input.setFocus())

    def _on_greeting_ready(self, text: str, had_cmd: bool):
        # volano v GUI threadu pres signal
        self._output(text)
        self._speak(text)
        if not had_cmd:
            self._announce_location()

    def _show_greeting(self):
        greeting = self.config.get("greeting", "")
        has_cmd = "{cmd" in greeting
        if not greeting:
            greeting = f"Čau! Jsem tvůj přístupný terminál."
            self._output(greeting)
            self._speak(greeting)
            self._announce_location()
            return

        # Pokud greeting obsahuje {cmd ...}, expanduj asynchronne aby neblokoval GUI
        # Pro jednoduche {cmd} bez argumentu je to rychly cwd, nemusime cekat
        if has_cmd:
            # rychla synchronni expanze pokud je jen {cmd} (bez shell)
            if greeting.strip() == "{cmd}" or greeting.strip() == "{cmd }":
                expanded = os.getcwd()
                # nahrada primo
                greeting = greeting.replace("{cmd}", expanded).replace("{cmd }", expanded)
                self._output(greeting)
                self._speak(greeting)
                return
            # jinak async pres signal (bezpecne z jineho vlakna)
            self._output("Načítám uvítání…")
            threading.Thread(target=self._expand_greeting_async, args=(greeting, has_cmd), daemon=True).start()
        else:
            # rychla cesta – bez substituce
            self._output(greeting)
            self._speak(greeting)
            self._announce_location()

    def _expand_greeting_async(self, greeting: str, had_cmd: bool):
        expanded = self._expand_greeting_commands(greeting)
        # zpet na GUI thread pres signal (QTimer z worker by nefungoval)
        try:
            if self._greet_obj is not None:
                self._greet_obj.greet.emit(expanded, had_cmd)
            else:
                # fallback: QMetaObject
                from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(self, "_on_greeting_ready", Qt.ConnectionType.QueuedConnection, Q_ARG(str, expanded), Q_ARG(bool, had_cmd))
        except Exception:
            # posledni fallback – primo (risk, ale lepsi nez nic)
            QTimer.singleShot(0, lambda: self._on_greeting_ready(expanded, had_cmd))

    def _expand_greeting_commands(self, text: str) -> str:
        def replace(m):
            cmd = m.group(1)
            if cmd is None:
                return os.getcwd()
            cmd = cmd.strip()
            if not cmd:
                return os.getcwd()
            # bezpecnost: omezit delku a zakazat nebezpecne retezeni v greetingu
            if len(cmd) > 200:
                return "[příliš dlouhý příkaz]"
            try:
                proc = subprocess.Popen(
                    cmd, shell=True, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True,
                    encoding="utf-8", errors="replace",
                )
                out, _ = proc.communicate(timeout=2)
                return out.strip()
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                return f"[čas vypršel: {cmd}]"
            except Exception:
                return f"[nepovedlo se: {cmd}]"

        return re.sub(r"\{cmd(?:\s+(.+?))?\}", replace, text)

    def _announce_location(self):
        msg = f"Nacházíš se v: {os.getcwd()}"
        self._output(msg)
        self._speak(msg)

    def _show_help(self):
        lines = [
            "Můžeš používat tyhle příkazy:",
            "",
            "  ahoj / čau       – pozdrav, terminál odpoví",
            "  cd <cesta>       – změna adresáře",
            "  exit             – ukončení terminálu",
            "  set              – zobrazí aktuální nastavení",
            "  set <klíč> <hodnota> – změní nastavení",
            "  help / ? / F1    – tahle nápověda",
            "",
            "Klávesové zkratky:",
            "  Enter            – spustit příkaz",
            "  Šipka nahoru/dolů – historie příkazů",
            "  Tab / Shift+Tab  – doplnění složek po cd",
            "  Ctrl+Tab         – přepnout fokus (input ↔ tlačítka ↔ výstup)",
            "  Ctrl+C           – přerušit běžící příkaz nebo vymazat řádek",
            "  Ctrl+L           – vymazat výstup",
            "  Ctrl+T           – přepnout motiv",
            "  Ctrl+,           – otevřít nastavení",
            "  Escape           – vrátit fokus na příkazový řádek",
            "  F1               – nápověda",
            "",
            "Nastavení, která jde měnit (příkazem set nebo v dialogu Nastavení):",
            "  voice on/off         – hlasová odezva",
            "  fontsize <6-72>      – velikost písma",
            "  font <název>         – typ písma",
            "  emoji on/off         – zobrazování emoji",
            "  greeting <text>      – vlastní uvítání",
            "  alias <z> <příkaz>   – zkratka pro příkaz",
            "",
            "V uvítání můžeš použít {cmd příkaz}:",
            "  greeting Vítej v {cmd}",
            "  greeting Dnes je {cmd echo %date%}",
            "",
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
            "Všechna nastavení se mění přes set nebo v dialogu Nastavení přes Ctrl čárka. "
            "Historie funguje šipkami, Tab doplňuje složky. Fokus přepneš Ctrl Tab. "
            "Aktuální adresář se oznamuje automaticky. "
            "Cokoliv jiného jde do příkazové řádky."
        )

    # ---------- output helpers ----------

    def _output(self, text: str) -> None:
        if not text:
            return
        if not self.config.get("emoji_enabled", True):
            text = strip_emoji(text)
        # appendPlainText vzdy prida novy blok – zachovavame
        self.output.appendPlainText(text)
        # automaticky scroll jen kdyz uzivatel neprochazi historii (fokus neni v outputu)
        if not self.output.hasFocus():
            vsb = self.output.verticalScrollBar()
            vsb.setValue(vsb.maximum())
        else:
            # kdyz uzivatel cte stary vystup, neposouvat nasilne
            pass
        if HAS_ACCESSIBLE:
            try:
                from PyQt6.QtGui import QAccessibleEvent
                ev = QAccessibleEvent(self.output, QAccessible.Event.ValueChanged)
                QAccessible.updateAccessibility(ev)
            except Exception:
                pass

    def _speak(self, text: str, force: bool = False) -> None:
        if not text or not text.strip():
            return
        # respektuj voice_enabled, krome force (napr. Hlas zapnut)
        if not force and not self.config.get("voice_enabled", True):
            return
        # speak_mode: pokud je NVDA aktivni a rezim auto, omez dlouhe vystupy
        speak_mode = self.config.get("speak_mode", "auto")
        clean = truncate_for_speech(text)
        # kdyz je NVDA aktivni a text je dlouhy vystup, spolehame na live region, mluvime jen souhrn
        # Executor uz posila souhrn, takze tady jen pojistka proti spam
        if speak_mode == "off" and not force:
            return
        try:
            self.tts.stop()
        except Exception:
            pass
        # emoji uz odstraneno v truncate_for_speech
        self.tts.speak(clean)

    # ---------- event filter ----------

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mod = event.modifiers()
            # Ctrl+Tab / Ctrl+Shift+Tab – nechat projit na focusNextPrevChild
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and (mod & Qt.KeyboardModifier.ControlModifier):
                return False
            # Smerove klavesy – historie
            if key == Qt.Key.Key_Up:
                self._handle_history_back()
                return True
            elif key == Qt.Key.Key_Down:
                self._handle_history_forward()
                return True
            elif key == Qt.Key.Key_Tab:
                shift = bool(mod & Qt.KeyboardModifier.ShiftModifier)
                self._handle_tab(shift)
                return True
            elif key == Qt.Key.Key_Escape:
                self.input.clear()
                self._speak("Řádek vymazán.")
                return True
        elif obj is self.output and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.input.setFocus()
                return True
        return super().eventFilter(obj, event)

    def _handle_history_back(self):
        # uloz draft pri prvnim kroku zpet
        if self.history._index == len(self.history._items):
            self._draft_input = self.input.text()
        cmd = self.history.back()
        if cmd is not None:
            self.input.setText(cmd)
            self._speak(f"Historie: {cmd}")
        else:
            self._speak("Začátek historie.")
            if HAS_ACCESSIBLE:
                QApplication.beep()

    def _handle_history_forward(self):
        cmd = self.history.forward()
        if cmd is not None:
            self.input.setText(cmd)
            self._speak(f"Historie: {cmd}")
        else:
            # navrat na draft
            self.input.setText(self._draft_input)
            if self._draft_input:
                self._speak(f"Návrat: {self._draft_input}")
            else:
                self.input.clear()
                self._speak("Konec historie.")

    def _handle_tab(self, shift: bool):
        text = self.input.text()
        if not text.lower().startswith("cd "):
            self._speak("Doplňování funguje jen po cd.")
            QApplication.beep()
            return
        result = self.tab.complete_cd(text, shift)
        if result is not None:
            self.input.setText(result)
            # ziskej info o poctu shod pro oznameni
            try:
                info = self.tab.get_last_match_info()
                if info:
                    idx, total, name = info
                    self._speak(f"Doplněno: {name}, {idx} z {total}")
                else:
                    self._speak(f"Doplněno: {result[3:].strip()}")
            except Exception:
                self._speak(f"Doplněno: {result[3:].strip()}")
        else:
            self._speak("Žádná shoda.")
            QApplication.beep()

    # ---------- command execution ----------

    def run_command(self):
        cmd = self.input.text().strip()
        if not cmd:
            return

        if cmd.lower() in ["ahoj", "čau"]:
            self._output("Ahoj kámo! 😎 Jak se máš?")
            self._speak("Ahoj kámo! Jak se máš?")
            self.input.clear()
            self._draft_input = ""
            self.input.setFocus()
            return

        if cmd.lower() in ("help", "nápověda", "?"):
            self._show_help()
            self.input.clear()
            self._draft_input = ""
            self.input.setFocus()
            return

        if cmd.lower().startswith("set "):
            self._handle_set(cmd[4:].strip())
            self.input.clear()
            self._draft_input = ""
            self.input.setFocus()
            return

        if cmd.lower().startswith("greeting "):
            self._handle_set(f"greeting {cmd[9:].strip()}")
            self.input.clear()
            self._draft_input = ""
            self.input.setFocus()
            return

        if cmd.lower().startswith("cd "):
            raw = cmd[3:].strip().strip('"').strip("'")
            path = os.path.expanduser(raw)
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            try:
                os.chdir(path)
                msg = f"Super! Nový aktuální adresář: {os.getcwd()}"
                self._output(msg)
                self._speak(msg)
            except Exception as e:
                self._output(f"Ups, složku jsem nenašel 😅 {e}")
                self._speak(f"Ups, složku jsem nenašel. {e}")
            self.input.clear()
            self._draft_input = ""
            self.input.setFocus()
            return

        self._output(f"> {cmd}")
        self.history.add(cmd)
        self._draft_input = ""
        self.input.clear()

        if cmd.lower() == "exit":
            self._output("Ukončuji terminál… měj se fajn! 👋")
            self._speak("Ukončuji terminál, měj se fajn!")
            QTimer.singleShot(600, QApplication.quit)
            return

        if cmd.lower() == "clear" or cmd.lower() == "cls":
            self.clear_output()
            return

        cmd = self._expand_aliases(cmd)
        self.executor.execute(cmd)
        # fokus zustava, ale input je docasne disabled pres signal started

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
            self._announce_accessible("Nastavení změněno")
        else:
            self._output(f"Neznámé nastavení: {key}")
            self._speak(f"Neznámé nastavení: {key}")
        self.input.setFocus()

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
            f"  režim řeči: {self.config.get('speak_mode', 'auto')}",
            f"  limit historie: {self.config.get('history_limit')}",
            "  Tip: Nastavení změníš i v dialogu Ctrl+,",
        ]
        aliases = self.config.get("aliases", {})
        if aliases:
            lines.append("  aliasy:")
            for k, v in aliases.items():
                lines.append(f"    {k} => {v}")
        self._output("\n".join(lines))
        self._speak("Zobrazuji aktuální nastavení. Dialog otevřeš Ctrl čárka.")

    def _set_voice(self, value):
        if value in ("on", "1", "true", "yes", "zapnuto"):
            self.config["voice_enabled"] = True
            msg = "Hlas zapnut."
        elif value in ("off", "0", "false", "no", "vypnuto"):
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
            msg = f"Uvítací zpráva nastavena. V textu můžeš použít složený příkaz cmd."
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
