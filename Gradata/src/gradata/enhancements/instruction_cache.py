"""
Instruction Cache — caches LLM-extracted behavioral instructions.

Key = hash of (category + added_words + removed_words).
Value = behavioral instruction string.
Persisted as JSON in the brain directory.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger("gradata")


class InstructionCache:
    """Simple JSON-file cache for behavioral instructions.

    Holds entries in memory and writes to disk only on flush().
    Designed to be held as a singleton on the Brain instance.
    """

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._data: dict[str, str] = {}
        self._dirty = False
        if cache_path.is_file():
            try:
                self._data = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def put(self, key: str, instruction: str) -> None:
        self._data[key] = instruction
        self._dirty = True

    def flush(self) -> None:
        """Write cache to disk if modified since last flush."""
        if not self._dirty:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._dirty = False
        except OSError as e:
            _log.debug("Instruction cache flush failed: %s", e)

    @staticmethod
    def make_key(category: str, added_words: list[str], removed_words: list[str]) -> str:
        raw = f"{category}|+{','.join(sorted(added_words))}|-{','.join(sorted(removed_words))}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
