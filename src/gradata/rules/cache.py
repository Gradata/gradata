"""Session-scoped rule cache. Invalidated on correction."""

from __future__ import annotations

import hashlib


class RuleCache:
    """Caches formatted rule strings by scope key. Invalidated on brain.correct().

    Stores the output of ``format_rules_for_prompt`` (a ``str``) keyed by
    scope so re-applying the same scope is a dict lookup, not a re-rank.
    """

    def __init__(self):
        self._cache: dict[str, str] = {}
        self._dirty: bool = True

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def invalidate(self):
        self._dirty = True
        self._cache.clear()

    def get(self, scope_key: str) -> str | None:
        if self._dirty:
            return None
        return self._cache.get(scope_key)

    def put(self, scope_key: str, rules: str):
        self._cache[scope_key] = rules
        self._dirty = False

    @staticmethod
    def make_key(task_type: str = "", domain: str = "", audience: str = "") -> str:
        raw = f"{task_type}:{domain}:{audience}"
        return hashlib.md5(raw.encode()).hexdigest()
