"""
Instruction Cache — caches LLM-extracted behavioral instructions.

Key = hash of (category + added_words + removed_words).
Value = behavioral instruction string.
Persisted as JSON in the brain directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class InstructionCache:
    """Simple JSON-file cache for behavioral instructions."""

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._data: dict[str, str] = {}
        if cache_path.is_file():
            try:
                self._data = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def put(self, key: str, instruction: str) -> None:
        self._data[key] = instruction
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    @staticmethod
    def make_key(category: str, added_words: list[str], removed_words: list[str]) -> str:
        raw = f"{category}|+{','.join(sorted(added_words))}|-{','.join(sorted(removed_words))}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
