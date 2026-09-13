import json
import os

CONFIG_FILE = "terminal_config.json"

DEFAULTS = {
    "theme": "light",
    "font_size": 12,
    "font_family": "Consolas",
    "voice_enabled": True,
    "emoji_enabled": True,
    "greeting": "",
    "history_limit": 100,
    "aliases": {},
    "window_geometry": None,
    "speak_mode": "auto",  # auto | full | off – jak mluvit pri NVDA
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        save_config(dict(DEFAULTS))
        return dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dict(DEFAULTS)
    result = dict(DEFAULTS)
    # jen zname klice, aby neznama data nerozbila aplikaci
    for k, v in data.items():
        if k in DEFAULTS or k in ("window_geometry", "aliases", "speak_mode"):
            result[k] = v
        else:
            # povol i nove klice pro zpetnou kompatibilitu
            result[k] = v
    # validace
    if result.get("speak_mode") not in ("auto", "full", "off"):
        result["speak_mode"] = "auto"
    try:
        result["font_size"] = int(result.get("font_size", 12))
        if not 6 <= result["font_size"] <= 72:
            result["font_size"] = 12
    except Exception:
        result["font_size"] = 12
    return result


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
