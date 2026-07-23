from __future__ import annotations

import os


class TabCompleter:
    def __init__(self):
        self._index = 0
        self._last_partial = ""

    def complete_cd(self, text: str, shift_pressed: bool) -> str | None:
        if not text.lower().startswith("cd "):
            return None
        partial = text[3:].strip()
        search_dir = os.path.dirname(partial) if os.path.dirname(partial) else os.getcwd()
        prefix = os.path.basename(partial)
        try:
            all_dirs = [
                d for d in os.listdir(search_dir)
                if os.path.isdir(os.path.join(search_dir, d))
            ]
            matches = [d for d in all_dirs if d.startswith(prefix)]
            if not matches:
                return None
            if self._last_partial != partial:
                self._index = 0
            if shift_pressed:
                self._index = (self._index - 1) % len(matches)
            result = f"cd {os.path.join(search_dir, matches[self._index])}"
            if not shift_pressed:
                self._index = (self._index + 1) % len(matches)
            self._last_partial = partial
            return result
        except Exception:
            return None
