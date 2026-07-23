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
    result.update(data)
    return result


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
