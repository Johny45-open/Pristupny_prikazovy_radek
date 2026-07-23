import json
import os

CONFIG_FILE = "terminal_config.json"


def save_theme(dark_mode: bool) -> None:
    data = {"theme": "dark" if dark_mode else "light"}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_theme() -> bool:
    if not os.path.exists(CONFIG_FILE):
        return False
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("theme", "light") == "dark"
    except Exception:
        return False
