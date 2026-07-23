from __future__ import annotations


class CommandHistory:
    def __init__(self):
        self._items: list[str] = []
        self._index = -1

    def add(self, cmd: str) -> None:
        self._items.append(cmd)
        self._index = len(self._items)

    def back(self) -> str | None:
        if self._items and self._index > 0:
            self._index -= 1
            return self._items[self._index]
        return None

    def forward(self) -> str | None:
        if self._items and self._index < len(self._items) - 1:
            self._index += 1
            return self._items[self._index]
        self._index = len(self._items)
        return None
