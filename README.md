<div lang="cs">

# Přístupný příkazový řádek

Přístupný terminál pro Windows postavený na **PyQt6**, optimalizovaný pro **NVDA** a klávesové ovládání. Zachovává přátelské hlášky, historii, Tab doplňování a přitom neblokuje GUI.

**Vstupní bod:** `python main.py` → `terminal_ui.FriendlyTerminal` (`main.py:1`)

---

## Spuštění

```bash
pip install -r requirements.txt
python main.py
```

Vyžaduje Python 3.10+ a Windows (NVDA). Na Linuxu/macOS běží bez NVDA, hlas jde přes SAPI5 fallback v `accessible_output2`.

Konfigurace se ukládá do `terminal_config.json` v adresáři aplikace. Geometrie okna a volby se automaticky obnoví.

---

## Ovládání

### Příkazový řádek (`QLineEdit` – *Příkazový řádek*)
* **Enter** – spustí příkaz.
* **Šipka nahoru / dolů** – historie. Zachovává rozepsaný text (draft): když píšeš `git st` a šipkou odjedeš do historie, návratem dolů se vrátí `git st`. Na hranicích se ozve *„Začátek historie“ / „Konec historie“*.
* **Tab / Shift+Tab** – doplnění složek po `cd `. Opakovaným Tabem cykluješ mezi shodami. Ozve se *„Doplněno: Název, 2 z 5“*, při žádné shodě *„Žádná shoda“* + pípnutí. Funguje jen po `cd `, jinde zahlásí nápovědu.
* **Ctrl+Tab / Ctrl+Shift+Tab** – přepne fokus mezi *příkazový řádek → tlačítka → výstup* (Tab samotný neopouští vstup, aby nebyla past na klávesnici).
* **Ctrl+C** – pokud běží příkaz, přeruší ho (`taskkill /T /F` + `terminate`). Pokud neběží, vymaže řádek.
* **Escape** – vymaže řádek (v inputu) nebo vrátí fokus z výstupu na příkazový řádek.
* **Ctrl+L** – vymaže výstup.

### Výstup (`QPlainTextEdit` – *Výstup terminálu*, readOnly)
* Prochází se šipkami, když má fokus (ClickFocus). Text lze vybírat klávesnicí (`Shift+šipky`) a kopírovat `Ctrl+C`.
* Nové řádky se přidávají průběžně (streaming), starší zůstávají. Automatické scrollování jen když **nemá fokus** – když čteš starší výstup, aplikace tě nevrátí násilně na konec.
* Každý nový řádek vyvolá `QAccessible.Event.ValueChanged` – NVDA ho zachytí jako live region.

### Tlačítka a menu
* **Přepnout motiv** (`Ctrl+T`) – přepíná světlý/tmavý (tmavý `#2b2b2b` s kontrastním tlačítkem `#555`). Stav se oznámí hlasem i live regionem.
* **Nastavení…** (`Ctrl+,`) – otevře dialog (viz níže).
* **Hlavní nabídka** (`Alt`) – *Soubor → Nastavení, Nápověda (F1), Vymazat výstup, Ukončit*.

### Příkazy

```
ahoj / čau          – pozdrav
cd <cesta>          – změna adresáře (podporuje ~, relativní, cesty s mezerami v uvozovkách)
exit                – ukončení (s 600ms prodlevou pro dočtení hlasu)
clear / cls         – vymazat výstup
help / ? / F1       – nápověda (vypíše se i přečte)
set                 – zobrazí aktuální nastavení
set voice on/off    – hlas
set fontsize 6-72   – velikost písma
set font <název>    – rodina písma
set emoji on/off    – emoji ve výstupu
set greeting <text> – uvítání, může obsahovat {cmd} nebo {cmd příkaz}
set alias <z> <cmd> – zkratka, např. set alias g git
greeting <text>     – alias pro set greeting
```

Uvítání: `greeting` z `terminal_config.json` se expanduje při startu. `{cmd}` bez argumentu vloží `cwd` synchronně, `{cmd echo %date%}` se spustí asynchronně (timeout 2 s) aby neblokoval GUI. Výchozí je `Čau! Jsem tvůj přístupný terminál.` + *Nacházíš se v: …*

Aliasy: první slovo se nahradí, např. `g status` → `git status`.

---

## Klávesové zkratky – přehled

| Zkratka | Kde | Akce |
|---|---|---|
| `Enter` | input | spustit |
| `↑` / `↓` | input | historie |
| `Tab` / `Shift+Tab` | input | doplnění `cd` |
| `Ctrl+Tab` | kdekoli | další fokus |
| `Ctrl+Shift+Tab` | kdekoli | předchozí fokus |
| `Ctrl+C` | kdekoli | přerušit příkaz / vymazat řádek |
| `Escape` | input/output | vymazat / vrátit fokus |
| `Ctrl+L` | kdekoli | vymazat výstup |
| `Ctrl+T` | kdekoli | přepnout motiv |
| `Ctrl+,` | kdekoli | nastavení |
| `F1` | kdekoli | nápověda |
| `Ctrl+Q` | menu | ukončit |

Všechny prvky mají `accessibleName` a `accessibleDescription`, `placeholderText` a `ToolTip` – NVDA čte *„Příkazový řádek, Zadej příkaz…“* místo *„Edit“*.

---

## Historie a Tab

* `command_history.py:4` – `CommandHistory` s `maxlen` z config `history_limit`, ukládá jen úspěšně odeslané příkazy (`> cmd`).
* Historie se neztrácí při procházení, draft se obnoví.
* `tab_completer.py:6` – hledá složky v `os.listdir(search_dir)`, filtruje `isdir` a `startswith(prefix)`, řadí case-insensitive, cykluje bez ztráty původního prefixu (i když se input změní na `cd C:\…\AlfaBeta`, další Tab stále cykluje mezi původními `A*`).

---

## Hlas a NVDA

* `tts_engine.py:4` – `TtsEngine` nad `accessible_output2.outputs.auto.Auto`. Na Windows s NVDA vybere NVDA, jinak SAPI5.
* **Oddělení:** `terminal_ui._speak` ořezává na 500 znaků, odstraňuje emoji a volá `tts.stop()` před novým. `command_executor` posílá do TTS jen **souhrn** (`Výstup 5 řádků… Začátek: …`) místo plného `stdout` – zamezí zahlcení NVDA fronty. Plný výstup jde jen do `QPlainTextEdit` (UIA).
* `speak_mode` v `terminal_config.json`:
  * `auto` (výchozí) – zkracuje dlouhé výstupy, respektuje `voice_enabled`.
  * `full` – čte vše (nedoporučeno s NVDA).
  * `off` – nemluví, jen live region (pro uživatele, co čte jen NVDA).
* `voice_enabled` lze přepnout `set voice off` nebo v dialogu. `force=True` použito jen pro potvrzení *„Hlas zapnut“*.

> **Poznámka:** Statická analýza prošla (0× `accessibleName` → nyní 7×). Reálné chování NVDA je potřeba ověřit ručně – automatický test NVDA nenahradí.

---

## Vykonávání příkazů

* `command_executor.py:32` – `CommandExecutor` s `ExecutorSignals(QObject)` (`output`, `speak`, `started`, `finished`) – **žádné** `QPlainTextEdit.appendPlainText` z worker threadu, vše přes `QueuedConnection`.
* Streaming: `Popen(bufsize=1)` + dvě vlákna `readline` pro `stdout`/`stderr`, každý řádek hned `emit` do GUI. `stderr` s `fatal`/`error` se označí `Hmm, tady je problém:`.
* `wait()` + `join(timeout=2)` – neblokuje GUI navždy (`communicate()` bez timeoutu odstraněno). `terminate_current()` volá `taskkill /PID /T /F` + `terminate`/`kill` – `Ctrl+C` funguje i pro `ping`, `flutter run` apod.
* Středník `;` mimo uvozovky se nahrazuje `&` pro `cmd.exe`.
* Návratový kód se překládá na lidskou hlášku (`_exit_message`), `git commit` bez `-m` se odmítne před spuštěním.

---

## Nastavení

* **Dialog** `settings_dialog.py:6` (`QDialog`, `QFormLayout`, `QCheckBox`, `QComboBox`, `QSpinBox`, `QFontComboBox`) – otevřeš `Ctrl+,` nebo menu. Všechna pole mají `accessibleName/Description`.

  * Motiv, písmo, velikost, emoji, hlas, režim řeči, limit historie, uvítání.
* **Příkazem** `set` – zpětně kompatibilní, po změně `save_config` + `„Nastavení změněno“` + live region.
* `config_manager.py:6` – `DEFAULTS` s validací (`speak_mode`, `font_size 6-72`, `window_geometry` kontrola vůči `QScreen.availableGeometry()`).

---

## Vzhled pro slabozraké

* `theme_manager.py:4` – `_DARK` (`#2b2b2b`/`#f0f0f0`, tlačítko `#555` s hover `#666` a focus `#4a90e2`) a `_LIGHT` s vysokým kontrastem na focus. Připraven `_HIGH_CONTRAST` (černá/žlutá/bílá) – lze zapnout programově.
* Písmo a velikost se mění živě, `setMaximumBlockCount` respektuje `history_limit`.
* Žádná informace není sdělena jen barvou.

---

## Architektura

```
main.py → FriendlyTerminal (QWidget)
  ├─ config_manager ↔ terminal_config.json
  ├─ ThemeManager
  ├─ CommandHistory
  ├─ TabCompleter
  ├─ TtsEngine (accessible_output2)
  ├─ ExecutorSignals ──► CommandExecutor (thread + Popen streaming)
  ├─ SettingsDialog (QDialog)
  └─ QPlainTextEdit (output) + QLineEdit (input) + QPushButtony + QMenuBar
```

`Radek.py` byl **odstraněn** (byl legacy monolit před rozdělením v `cd92526`). Zachován je pouze archiv `_legacy_Radek.py` pro historii – aktivní kód ho neimportuje. Obnova možná přes `git log` / `git checkout`.

---

## Testování

```bash
# syntaxe a importy
python -m py_compile *.py
QT_QPA_PLATFORM=offscreen python -c "from PyQt6.QtWidgets import QApplication; app=QApplication([]); from terminal_ui import FriendlyTerminal; t=FriendlyTerminal(); print('ok')"

# ruční
python main.py
# v aplikaci vyzkoušet:
# echo hello, neexistující příkaz, ping -n 10 127.0.0.1 + Ctrl+C, Up/Down, cd + Tab, help, set, Ctrl+T, Ctrl+,
```

Automatické testy lze spustit offscreen (`QT_QPA_PLATFORM=offscreen`). NVDA nutno ověřit ručně.

---

## Známé limity

* `shell=True` – uživatelský vstup jde do `cmd.exe`; greeting `{cmd …}` je omezen na 200 znaků a timeout 2 s.
* Dlouhé příkazy bez newline (např. `flutter run` bez ukončení) streamují, ale `taskkill` je potřeba pro přerušení.
* Skutečné chování NVDA (dvojí čtení, live region) bylo ověřeno statickou analýzou a offscreen testy, ne přímo s NVDA – doporučeno ruční otestování.

---

## Licence

Interní projekt – viz git log.

</div>
