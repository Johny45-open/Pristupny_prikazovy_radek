from __future__ import annotations

import os


class TabCompleter:
    def __init__(self):
        self._index = -1  # index posledni zobrazene polozky
        self._last_partial = ""  # puvodni partial pro cyklovani
        self._last_matches: list[str] = []
        self._last_search_dir: str = ""
        self._last_prefix: str = ""

    def complete_cd(self, text: str, shift_pressed: bool) -> str | None:
        if not text.lower().startswith("cd "):
            return None
        partial = text[3:].strip()
        search_dir = os.path.dirname(partial) if os.path.dirname(partial) else os.getcwd()
        prefix = os.path.basename(partial)

        # Detekce cyklovani: pokud je partial uz jednou z predchozich matches, povazuj za stejny puvodni dotaz
        is_cycling = False
        if self._last_matches and self._last_search_dir == search_dir:
            # zkontroluj zda partial (basename) je v predchozich matches
            # nebo zda cela partial cesta je presne jedna z matches
            completed_paths = [os.path.join(self._last_search_dir, m) for m in self._last_matches]
            if partial in completed_paths or prefix in self._last_matches:
                # uzivatel jen cykluje mezi doplnenymi – pouzij puvodni prefix/matches
                is_cycling = True
                # obnov puvodni prefix pro hledani, at se nemeni seznam
                # ale ponech search_dir stejny
                prefix = self._last_prefix
                # matches zustavaji stejne jako minule
                matches = self._last_matches
                # neprovadej novy listing
                if shift_pressed:
                    self._index = (self._index - 1) % len(matches)
                else:
                    self._index = (self._index + 1) % len(matches)
                result = f"cd {os.path.join(search_dir, matches[self._index])}"
                # _last_partial zustava puvodni
                return result

        try:
            all_dirs = [
                d for d in os.listdir(search_dir)
                if os.path.isdir(os.path.join(search_dir, d))
            ]
            matches = sorted([d for d in all_dirs if d.startswith(prefix)], key=str.lower)
            if not matches:
                self._last_matches = []
                self._last_search_dir = search_dir
                self._last_prefix = prefix
                self._index = -1
                self._last_partial = partial
                return None
            # nova partial -> reset cyklu
            if not is_cycling and self._last_partial != partial:
                self._index = -1
            self._last_matches = matches
            self._last_search_dir = search_dir
            self._last_prefix = prefix
            self._last_partial = partial

            if shift_pressed:
                self._index = (self._index - 1) % len(matches)
            else:
                self._index = (self._index + 1) % len(matches)

            result = f"cd {os.path.join(search_dir, matches[self._index])}"
            return result
        except Exception:
            self._last_matches = []
            self._index = -1
            return None

    def get_last_match_info(self) -> tuple[int, int, str] | None:
        """Vrati (index 1-based, total, name) pro posledni doplneni, nebo None."""
        if not self._last_matches or self._index == -1:
            return None
        try:
            name = self._last_matches[self._index]
            return (self._index + 1, len(self._last_matches), name)
        except Exception:
            return None
