"""Shared core for runtime middleware adapters.

This module is SDK-layer: it provides the :class:`RuleSource` (which reads
``lessons.md`` from a brain directory) and the injection / enforcement
primitives the per-framework adapters compose. It must not import any
third-party LLM SDK.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gradata._env import env_str
from gradata.enhancements.rule_to_hook import DeterminismCheck, classify_rule

if TYPE_CHECKING:  # pragma: no cover
    from gradata._types import Lesson

_log = logging.getLogger(__name__)

# Default cap matches the existing SessionStart hook (inject_brain_rules.py)
DEFAULT_MAX_RULES = 10
DEFAULT_MIN_CONFIDENCE = 0.60

# Regex block patterns derived from RULE-tier deterministic classifications.
# Each entry: (hook_template, compiled_regex, friendly_name)
# These apply post-call to detect rule violations in model output.
_BLOCK_PATTERNS: dict[str, tuple[re.Pattern[str], str]] = {
    "regex_replace": (re.compile(r"[\u2014\u2013]"), "em-dash"),
}


class RuleViolation(Exception):  # noqa: N818 — public API name specified in spec
    """Raised when an LLM output violates a RULE-tier deterministic pattern.

    Attributes:
        rule_description: The source rule's description text.
        pattern_name: Short label for which check fired (e.g. ``"em-dash"``).
        output: The offending model output text.
    """

    def __init__(self, rule_description: str, pattern_name: str, output: str) -> None:
        self.rule_description = rule_description
        self.pattern_name = pattern_name
        self.output = output
        super().__init__(
            f"RuleViolation: output matched '{pattern_name}' "
            f"(rule: {rule_description!r})"
        )


def is_bypassed() -> bool:
    """Return True if GRADATA_BYPASS=1 is set (kill switch for middleware)."""
    return env_str("GRADATA_BYPASS").strip() == "1"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Fetch ``key`` from a response-like object using attr-then-dict lookup.

    LLM SDK responses are inconsistently typed across versions — modern
    clients expose pydantic objects while older ones (and cassette fixtures)
    return plain dicts. Adapters would otherwise repeat
    ``getattr(x, k) or (x.get(k) if isinstance(x, dict) else None)``
    for every field they touch.
    """
    val = getattr(obj, key, None)
    if val is None and isinstance(obj, dict):
        return obj.get(key, default)
    return val if val is not None else default


# ---------------------------------------------------------------------------
# RuleSource
# ---------------------------------------------------------------------------


@dataclass
class _ScoredLesson:
    category: str
    description: str
    state: str  # "RULE" or "PATTERN"
    confidence: float


def _clamp_confidence(value: float) -> float:
    """Clamp a confidence value into the [0.0, 1.0] range.

    Out-of-range inputs are logged at debug level and clamped rather than
    raised — middleware must not fail on malformed lesson inputs.
    """
    if value < 0.0 or value > 1.0:
        _log.debug("Confidence %s out of [0.0, 1.0]; clamping", value)
    return max(0.0, min(value, 1.0))


class RuleSource:
    """Reads lessons from the same brain directory Claude Code hooks use.

    The source loads ``<brain_path>/lessons.md`` on demand and returns the
    top-N highest-priority lessons. Parsing delegates to the same
    :func:`gradata.enhancements.self_improvement.parse_lessons` the
    SessionStart hook uses, so behaviour is identical across environments.

    A :class:`RuleSource` can also be constructed directly from a list of
    lesson dicts — useful for tests and for callers that source rules from
    somewhere other than the default lessons file.
    """

    def __init__(
        self,
        brain_path: str | Path | None = None,
        *,
        lessons: list[dict] | None = None,
        max_rules: int = DEFAULT_MAX_RULES,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self._brain_path = Path(brain_path) if brain_path else None
        self._static_lessons = lessons
        self.max_rules = max_rules
        self.min_confidence = min_confidence

    # -- loading ----------------------------------------------------------

    def _load_from_brain(self) -> list[_ScoredLesson]:
        if self._brain_path is None:
            return []
        path = self._brain_path / "lessons.md"
        if not path.is_file():
            return []
        try:
            from gradata.enhancements.self_improvement import parse_lessons
        except ImportError:  # pragma: no cover
            _log.debug("parse_lessons unavailable; returning no rules")
            return []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem edge
            _log.warning("Could not read %s: %s", path, exc)
            return []
        parsed = parse_lessons(text)
        return [_lesson_to_scored(lesson) for lesson in parsed]

    def _load_from_dicts(self) -> list[_ScoredLesson]:
        out: list[_ScoredLesson] = []
        for lesson in self._static_lessons or []:
            state = str(lesson.get("state") or lesson.get("status") or "").upper()
            raw_conf = lesson.get("confidence", 0.0)
            try:
                conf = _clamp_confidence(float(raw_conf) if raw_conf is not None else 0.0)
            except (TypeError, ValueError):
                # Malformed caller-supplied lessons (e.g. confidence="high")
                # must not abort the whole injection/enforcement path.
                _log.debug(
                    "Skipping lesson with non-numeric confidence %r", raw_conf,
                )
                continue
            category = str(lesson.get("category", "") or "")
            description = str(lesson.get("description", "") or "")
            if not description:
                continue
            out.append(
                _ScoredLesson(
                    category=category,
                    description=description,
                    state=state,
                    confidence=conf,
                )
            )
        return out

    def load(self) -> list[_ScoredLesson]:
        """Return eligible lessons (RULE/PATTERN only, above min_confidence)."""
        lessons = (
            self._load_from_dicts() if self._static_lessons is not None
            else self._load_from_brain()
        )
        return [
            l for l in lessons
            if l.state in ("RULE", "PATTERN") and l.confidence >= self.min_confidence
        ]

    # -- selection --------------------------------------------------------

    def select(self) -> list[_ScoredLesson]:
        """Return up to ``max_rules`` lessons ranked for injection.

        RULE beats PATTERN, ties broken by confidence descending. This matches
        the priority scheme used by ``inject_brain_rules.py``.
        """
        lessons = self.load()
        lessons.sort(
            key=lambda l: (1 if l.state == "RULE" else 0, l.confidence),
            reverse=True,
        )
        return lessons[: self.max_rules]

    # -- enforcement ------------------------------------------------------

    def rule_tier_blockers(self) -> list[tuple[_ScoredLesson, re.Pattern[str], str]]:
        """Return (lesson, compiled_pattern, name) tuples for RULE-tier blockers.

        Uses :func:`gradata.enhancements.rule_to_hook.classify_rule` to find
        rules whose descriptions map to a deterministic regex template, then
        resolves that template to a compiled pattern. PATTERN-tier lessons are
        skipped — only RULE-tier rules (confidence >= 0.90) are enforced.
        """
        out: list[tuple[_ScoredLesson, re.Pattern[str], str]] = []
        for lesson in self.load():
            if lesson.state != "RULE":
                continue
            try:
                candidate = classify_rule(lesson.description, lesson.confidence)
            except ValueError:
                continue
            if candidate.determinism == DeterminismCheck.NOT_DETERMINISTIC:
                continue
            spec = _BLOCK_PATTERNS.get(candidate.hook_template)
            if spec is None:
                continue
            pattern, name = spec
            out.append((lesson, pattern, name))
        return out


def _lesson_to_scored(lesson: Lesson) -> _ScoredLesson:
    state_name = lesson.state.name if hasattr(lesson.state, "name") else str(lesson.state)
    return _ScoredLesson(
        category=lesson.category,
        description=lesson.description,
        state=state_name,
        confidence=_clamp_confidence(float(lesson.confidence)),
    )


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------


def build_brain_rules_block(source: RuleSource) -> str:
    """Render the ``<brain-rules>`` XML block for a given :class:`RuleSource`.

    Matches the format produced by :mod:`gradata.hooks.inject_brain_rules`
    so injection is identical across Claude Code and direct-SDK agents.
    Returns ``""`` when no rules are eligible.
    """
    if is_bypassed():
        return ""
    selected = source.select()
    if not selected:
        return ""
    lines = [
        f"[{l.state}:{l.confidence:.2f}] {l.category}: {l.description}"
        for l in selected
    ]
    return "<brain-rules>\n" + "\n".join(lines) + "\n</brain-rules>"


def inject_into_system(system: str | None, block: str) -> str:
    """Append the ``<brain-rules>`` block to an existing system prompt."""
    if not block:
        return system or ""
    if not system:
        return block
    return f"{system}\n\n{block}"


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------


def check_output(source: RuleSource, text: str, *, strict: bool = False) -> list[RuleViolation]:
    """Scan ``text`` for RULE-tier pattern violations.

    When ``strict`` is True, the first violation is raised. Otherwise the
    full list of violations is returned (empty if clean).
    """
    if is_bypassed() or not text:
        return []
    violations: list[RuleViolation] = []
    for lesson, pattern, name in source.rule_tier_blockers():
        if pattern.search(text):
            v = RuleViolation(
                rule_description=lesson.description,
                pattern_name=name,
                output=text,
            )
            if strict:
                raise v
            _log.warning(
                "Gradata rule violation (%s): %s", name, lesson.description,
            )
            violations.append(v)
    return violations
