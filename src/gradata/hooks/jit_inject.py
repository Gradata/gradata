"""UserPromptSubmit hook: just-in-time (JIT) rule injection.

Session-start injection (`inject_brain_rules.py`) picks the top-N rules once
for the whole session. JIT flips the axis: on every user prompt we score
each graduated rule against the draft text and inject only the top-k that
match THIS draft. Many-shot literature (Agarwal 2024) shows monotonic gains
to ~1000 shots; context budgets cap us at 10-20 rules. JIT spends that
budget on the most relevant rules per call instead of globally.

Gated by env var ``GRADATA_JIT_ENABLED`` (default false) so the existing
SessionStart behavior is untouched for anyone who hasn't opted in. When
both are active they complement: SessionStart = broad priors, JIT = tight
per-prompt overlay.

Similarity uses BM25 (via ``bm25s``) when available — it captures term
rarity that Jaccard can't — and falls back to Jaccard on word unigrams
when ``bm25s`` isn't installed, keeping the SDK zero-required-deps.
Deterministic and under a few ms per call for the rule-tier volumes we
see in practice (~100s of graduated rules max).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from ._base import extract_message, resolve_brain_dir, run_hook
from ._profiles import Profile

if TYPE_CHECKING:
    from .._types import Lesson

try:
    from ..enhancements.self_improvement import is_hook_enforced, parse_lessons
except ImportError:
    parse_lessons = None  # type: ignore[assignment]
    is_hook_enforced = None  # type: ignore[assignment]

try:  # BM25 is optional — SDK must stay zero-required-deps.
    import bm25s  # type: ignore[import-not-found]
    _BM25_AVAILABLE = True
except ImportError:  # pragma: no cover - import gate
    bm25s = None  # type: ignore[assignment]
    _BM25_AVAILABLE = False

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "UserPromptSubmit",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

# Defaults. All tunable by env var so operators can sweep without a code change.
DEFAULT_MAX_RULES = 5
DEFAULT_MIN_CONFIDENCE = 0.60
DEFAULT_MIN_SIMILARITY = 0.05
MIN_DRAFT_LEN = 10

# Tokens that appear in almost every draft and would swamp Jaccard similarity.
# Kept tight on purpose: overfitting this list defeats the per-draft signal.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "i", "in", "is", "it", "its", "of", "on", "or", "that", "the",
    "this", "to", "was", "were", "will", "with", "you", "your", "we", "our",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    """Lowercase word-unigrams minus a small stopword list."""
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _jit_enabled() -> bool:
    raw = os.environ.get("GRADATA_JIT_ENABLED", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _num_env(name: str, default, cast):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        return default


def rank_rules_for_draft(
    lessons: list[Lesson],
    draft_text: str,
    *,
    k: int = DEFAULT_MAX_RULES,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> list[tuple[Lesson, float]]:
    """Score each lesson against draft_text and return top-k above threshold.

    Uses BM25 (via ``bm25s``) when installed, falling back to Jaccard so the
    SDK stays zero-required-deps. Returns (lesson, similarity) tuples highest
    first. A rule must clear BOTH confidence and similarity floors; we'd
    rather inject zero rules than inject noise (same philosophy as the PR #45
    source-filter gate).
    """
    if not draft_text or not lessons or k <= 0:
        return []

    draft_tokens = _tokenize(draft_text)
    if not draft_tokens:
        return []

    candidates: list[tuple[Lesson, str, str, float]] = []
    for lesson in lessons:
        conf = getattr(lesson, "confidence", 0.0)
        if conf < min_confidence:
            continue
        state = getattr(lesson.state, "name", "")
        if state not in ("RULE", "PATTERN"):
            continue
        description = getattr(lesson, "description", "") or ""
        category = getattr(lesson, "category", "") or ""
        candidates.append((lesson, category, description, conf))

    if not candidates:
        return []

    bm25_scores: list[float] | None = None
    if _BM25_AVAILABLE and bm25s is not None and candidates:
        _corpus = [f"{cat} {desc}".strip() for _, cat, desc, _ in candidates]
        if any(_corpus):
            try:
                _retr = bm25s.BM25()
                _retr.index(bm25s.tokenize(_corpus, stopwords="en", show_progress=False), show_progress=False)
                _qt = bm25s.tokenize([draft_text], stopwords="en", show_progress=False)
                _ids, _scores = _retr.retrieve(_qt, k=len(_corpus), show_progress=False)
                _max = max((float(s) for s in _scores[0]), default=0.0)
                if _max > 0:
                    bm25_scores = [0.0] * len(_corpus)
                    for _j in range(len(_ids[0])):
                        bm25_scores[int(_ids[0][_j])] = float(_scores[0][_j]) / _max
            except Exception as _exc:  # pragma: no cover - defensive
                _log.debug("bm25 scoring failed (%s) — falling back to Jaccard", _exc)
                bm25_scores = None

    scored: list[tuple[Lesson, float]] = []
    for idx, (lesson, category, description, conf) in enumerate(candidates):
        if bm25_scores is not None:
            sim = bm25_scores[idx]
        else:
            rule_tokens = _tokenize(f"{category} {description}")
            sim = _jaccard(draft_tokens, rule_tokens)
        if sim < min_similarity:
            continue
        # Blend similarity with a small confidence tie-break so two equally
        # matched rules order by confidence.
        scored.append((lesson, sim + 0.001 * conf))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]


def main(data: dict) -> dict | None:
    if not _jit_enabled():
        return None
    if parse_lessons is None:
        return None

    message = extract_message(data)
    if not message or len(message) < MIN_DRAFT_LEN:
        return None
    if message.startswith("/"):
        return None

    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    lessons_path = Path(brain_dir) / "lessons.md"
    if not lessons_path.is_file():
        return None

    try:
        text = lessons_path.read_text(encoding="utf-8")
    except OSError:
        return None

    lessons = parse_lessons(text)
    # Phase 5: skip rules already enforced deterministically by an installed hook.
    if is_hook_enforced is not None:
        lessons = [lesson for lesson in lessons if not is_hook_enforced(lesson)]
    if not lessons:
        return None

    k = max(0, _num_env("GRADATA_JIT_MAX_RULES", DEFAULT_MAX_RULES, int))
    min_conf = _num_env("GRADATA_JIT_MIN_CONFIDENCE", DEFAULT_MIN_CONFIDENCE, float)
    min_sim = _num_env("GRADATA_JIT_MIN_SIMILARITY", DEFAULT_MIN_SIMILARITY, float)

    ranked = rank_rules_for_draft(
        lessons,
        message,
        k=k,
        min_confidence=min_conf,
        min_similarity=min_sim,
    )

    try:
        _ee_line = json.dumps({
            "type": "JIT_INJECTION", "ts": time.time(),
            "draft_len": len(message), "candidates": len(lessons),
            "injected": len(ranked), "k": k, "min_similarity": min_sim,
        }, ensure_ascii=False)
        with (Path(brain_dir) / "events.jsonl").open("a", encoding="utf-8") as _ee_f:
            _ee_f.write(_ee_line + "\n")
    except OSError:
        pass

    if not ranked:
        return None

    lines = [
        f"[{r.state.name}:{r.confidence:.2f}] {r.category}: {r.description}"
        for r, _sim in ranked
    ]
    rules_block = "<brain-rules-jit>\n" + "\n".join(lines) + "\n</brain-rules-jit>"
    return {"result": rules_block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
