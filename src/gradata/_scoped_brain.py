"""ScopedBrain — domain-scoped view over a parent ``Brain``. ``brain.scope(D)``
proxies filter graduated rules by domain (case-insensitive match on
``scope_json.domain`` / ``applies_to``) and delegate the rest unchanged. No
category-as-domain fallback; migrate legacy via
``scripts/migrate_legacy_scopes.py``. SDK Layer 0.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._types import Lesson
    from .brain import Brain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain matching
# ---------------------------------------------------------------------------


def lesson_matches_domain(lesson: Lesson, domain: str) -> bool:
    """Return True if ``lesson`` is in-scope for ``domain``.

    Matching is STRICT (council verdict 4/4): only the stored
    ``scope_json`` is consulted. ``lesson.category`` is deliberately
    ignored. Empty ``domain`` matches everything (wildcard).
    """
    if not domain:
        return True
    d_norm = domain.strip().lower()
    if not d_norm:
        return True

    if not lesson.scope_json:
        return False
    try:
        scope_data = json.loads(lesson.scope_json)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(scope_data, dict):
        return False

    scope_domain = str(scope_data.get("domain", "") or "").strip().lower()
    if scope_domain == d_norm:
        return True
    applies_to = str(scope_data.get("applies_to", "") or "").strip().lower()
    return applies_to == d_norm or applies_to.startswith(f"{d_norm}:")


def filter_lessons_by_domain(lessons: list[Lesson], domain: str) -> list[Lesson]:
    """Return the subset of ``lessons`` that match ``domain``."""
    if not domain:
        return list(lessons)
    return [l for l in lessons if lesson_matches_domain(l, domain)]


# ---------------------------------------------------------------------------
# ScopedBrain proxy
# ---------------------------------------------------------------------------


class ScopedBrain:
    """A domain-scoped view over a :class:`Brain`.

    Attribute access is delegated to the parent brain for everything except
    the rule-reading APIs, which are filtered by domain. The parent brain's
    storage, event bus, and cloud connection are shared.
    """

    # Shared sentinel so sub-agents can detect they received a scoped brain
    _gradata_scoped: bool = True

    def __init__(self, parent: Brain, domain: str) -> None:
        if not domain or not str(domain).strip():
            raise ValueError("ScopedBrain requires a non-empty domain")
        self._parent = parent
        self._domain = str(domain).strip()

    # ── Identity helpers ───────────────────────────────────────────────

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def parent(self) -> Brain:
        return self._parent

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"ScopedBrain(domain='{self._domain}', parent={self._parent!r})"

    # ── Filtered reads ─────────────────────────────────────────────────

    def rules(self, *, include_all: bool = False, category: str | None = None) -> list[dict]:
        """List graduated rules filtered to this scope's domain."""
        all_rules = self._parent.rules(include_all=include_all, category=category)
        return [r for r in all_rules if self._rule_dict_matches(r)]

    def _rule_dict_matches(self, rule: dict) -> bool:
        """Domain-match a dict as returned by ``list_rules``.

        STRICT matching (council verdict 4/4): only ``scope_json.domain``
        or ``scope_json.applies_to`` are consulted. ``category`` is
        ignored. ``metadata.where_scope`` is preserved as a legitimate
        alternate serialization of the stored scope domain.
        """
        d_norm = self._domain.lower()

        # metadata.where_scope is how the inspection layer serialises
        # the stored scope_json.domain, so it counts as a domain match.
        meta = rule.get("metadata") or {}
        where = str(meta.get("where_scope", "")).lower() if isinstance(meta, dict) else ""
        if where == d_norm:
            return True

        # Walk raw scope dict if present
        for key in ("scope", "scope_json"):
            raw = rule.get(key)
            if not raw:
                continue
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(raw, dict):
                if str(raw.get("domain", "")).lower() == d_norm:
                    return True
                applies = str(raw.get("applies_to", "")).lower()
                if applies == d_norm or applies.startswith(f"{d_norm}:"):
                    return True

        return False

    def lessons(self) -> list[Lesson]:
        """Return parsed :class:`Lesson` objects filtered to this domain.

        Unlike :meth:`rules` (which returns dicts from the inspection layer),
        this returns the raw Lesson dataclasses — useful for tests and
        advanced filtering.
        """
        all_lessons = self._parent._load_lessons()
        return filter_lessons_by_domain(all_lessons, self._domain)

    def inject(self, task: str = "", *, max_rules: int = 10) -> str:
        """Return scoped rules formatted for prompt injection.

        Equivalent to :meth:`Brain.apply_brain_rules` but only rules whose
        stored scope matches this ScopedBrain's domain are included. The
        underlying relevance ranking is still applied on top of the filter.
        """
        context: dict[str, Any] = {"domain": self._domain}
        if task:
            context["task"] = task

        # Pull the full injection string then rebuild from filtered lessons.
        # We re-run the same ranking logic scoped to the filtered lesson set.
        from ._scope import build_scope
        from .rules.rule_engine import (
            apply_rules,
            format_rules_for_prompt,
        )

        scoped_lessons = self.lessons()
        if not scoped_lessons:
            return ""

        query_scope = build_scope({"domain": self._domain, "task": task or self._domain})
        try:
            from .rules.rule_engine import apply_rules_with_tree

            applied = apply_rules_with_tree(scoped_lessons, query_scope, max_rules=max_rules)
        except Exception:
            applied = apply_rules(scoped_lessons, query_scope, max_rules=max_rules)

        return format_rules_for_prompt(applied)

    def apply_brain_rules(
        self,
        task: str,
        context: dict | None = None,
        agent_type: str | None = None,
        max_rules: int = 10,
    ) -> str:
        """Scoped equivalent of :meth:`Brain.apply_brain_rules`."""
        ctx = dict(context or {})
        ctx["domain"] = self._domain  # force domain filter
        # Reuse inject() which already filters to the scoped lesson set
        return self.inject(task=task, max_rules=max_rules)

    def stats(self) -> dict:
        """Counts of rules in this scope."""
        scoped = self.lessons()
        return {
            "domain": self._domain,
            "total": len(scoped),
            "by_state": {
                state: sum(1 for l in scoped if l.state.value == state)
                for state in ("RULE", "PATTERN", "INSTINCT")
            },
        }

    # ── Scope composition ──────────────────────────────────────────────

    def scope(self, domain: str) -> ScopedBrain:
        """Nested scoping: returns a ScopedBrain for ``domain`` against the
        original parent brain. Nested scopes do not intersect (a scoped brain
        is always a view over its top-level parent)."""
        return ScopedBrain(self._parent, domain)

    # ── Write-through delegation ──────────────────────────────────────
    #
    # Corrections, events, memory, and other write operations delegate to
    # the parent brain. We annotate the correction with the scope's domain
    # so that rules graduating from scoped sessions inherit the binding.

    def correct(
        self,
        draft: str,
        final: str,
        category: str | None = None,
        context: dict | None = None,
        **kwargs: Any,
    ) -> dict:
        """Record a correction. The scope's domain is injected into
        ``context`` and (by default) ``applies_to`` so graduating rules
        carry the scope binding."""
        merged_context = dict(context or {})
        merged_context.setdefault("domain", self._domain)

        # Default applies_to to the domain if the caller didn't specify.
        kwargs.setdefault("applies_to", self._domain)
        kwargs.setdefault("scope", "domain")

        return self._parent.correct(
            draft=draft,
            final=final,
            category=category,
            context=merged_context,
            **kwargs,
        )

    # ── Transparent attribute delegation ──────────────────────────────

    def __getattr__(self, name: str) -> Any:
        """Forward anything we don't explicitly override to the parent.

        Python only calls __getattr__ for missing attributes, so the
        overridden methods above win automatically.
        """
        return getattr(self._parent, name)
