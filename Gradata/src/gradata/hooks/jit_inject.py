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

from gradata.hooks._base import extract_message, resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

if TYPE_CHECKING:
    from gradata._types import Lesson

try:
    from gradata.enhancements.self_improvement import is_hook_enforced, parse_lessons
except ImportError:
    parse_lessons = None  # type: ignore[assignment]
    is_hook_enforced = None  # type: ignore[assignment]

try:  # BM25 is optional — SDK must stay zero-required-deps.
    # Suppress bm25s stdout noise on Windows (benchmark.py prints to stdout).
    import io as _io
    import sys as _sys

    _bm25_stdout = _sys.stdout
    _sys.stdout = _io.StringIO()
    try:
        import bm25s  # type: ignore[import-not-found]
    finally:
        _sys.stdout = _bm25_stdout
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
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "i",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "you",
        "your",
        "we",
        "our",
    }
)

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


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _bm25_scores_for_draft(
    candidates: list[tuple[Lesson, str, str]],
    draft_text: str,
) -> list[float] | None:
    """Return BM25 scores (normalized to [0,1]) aligned to candidates, or None.

    candidates is ``[(lesson, category, description), ...]``. Returns None when
    bm25s isn't installed or scoring fails — callers fall back to Jaccard.
    """
    if not _BM25_AVAILABLE or bm25s is None or not candidates:
        return None
    corpus = [f"{cat} {desc}".strip() for _, cat, desc in candidates]
    if not any(corpus):
        return None
    try:
        retriever = bm25s.BM25()
        corpus_tokens = bm25s.tokenize(corpus, stopwords="en", show_progress=False)
        retriever.index(corpus_tokens, show_progress=False)
        query_tokens = bm25s.tokenize(
            [draft_text],
            stopwords="en",
            show_progress=False,
        )
        doc_ids, scores = retriever.retrieve(
            query_tokens,
            k=len(corpus),
            show_progress=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        _log.debug("bm25 scoring failed (%s) — falling back to Jaccard", exc)
        return None

    aligned = [0.0] * len(corpus)
    row_ids = doc_ids[0]
    row_scores = scores[0]
    max_score = max((float(s) for s in row_scores), default=0.0)
    if max_score <= 0:
        return None
    for j in range(len(row_ids)):
        aligned[int(row_ids[j])] = float(row_scores[j]) / max_score
    return aligned


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

    bm25_scores = _bm25_scores_for_draft(
        [(lesson, cat, desc) for lesson, cat, desc, _ in candidates],
        draft_text,
    )

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


def _emit_event(brain_dir: str, payload: dict) -> None:
    """Append a JIT_INJECTION event to events.jsonl. Silent on failure.

    We write directly instead of going through Brain() because hooks run
    as short-lived subprocesses and a full Brain init is ~100 ms of
    overhead we'd pay on every user prompt.
    """
    try:
        events_path = Path(brain_dir) / "events.jsonl"
        line = json.dumps(
            {
                "type": "JIT_INJECTION",
                "ts": time.time(),
                **payload,
            },
            ensure_ascii=False,
        )
        with events_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        # Telemetry must never break the hook contract.
        pass


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
    try:
        from gradata._config import BrainConfig

        max_prompt_chars = BrainConfig.load(brain_dir).max_recall_tokens * 4
    except ImportError:
        max_prompt_chars = 2000 * 4

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

    k = _int_env("GRADATA_JIT_MAX_RULES", DEFAULT_MAX_RULES)
    min_conf = _float_env("GRADATA_JIT_MIN_CONFIDENCE", DEFAULT_MIN_CONFIDENCE)
    min_sim = _float_env("GRADATA_JIT_MIN_SIMILARITY", DEFAULT_MIN_SIMILARITY)

    ranked = rank_rules_for_draft(
        lessons,
        message,
        k=k,
        min_confidence=min_conf,
        min_similarity=min_sim,
    )

    if not ranked:
        return None

    _emit_event(
        brain_dir,
        {
            "draft_len": len(message),
            "candidates": len(lessons),
            "injected": len(ranked),
            "k": k,
            "min_similarity": min_sim,
        },
    )

    # Dedup against the session wisdom block: skip JIT rules that are already
    # substantially covered by the session-start wisdom block (brain_prompt.md).
    # Threshold 0.25 Jaccard: "playbooks from the start" ↔ "always consult playbooks"
    # scores ~0.33, so covered rules skip. Saves ~11 tok/turn avg on typical sessions.
    wisdom_lines: list[str] = []
    bp_path = Path(brain_dir) / "brain_prompt.md"
    if bp_path.is_file():
        try:
            bp_text = bp_path.read_text(encoding="utf-8")
            wisdom_lines = [ln[2:].strip() for ln in bp_text.splitlines() if ln.startswith("- ")]
        except OSError:
            pass

    _WISDOM_DEDUP_THRESHOLD = 0.25

    def _already_in_wisdom(desc: str) -> bool:
        if not wisdom_lines:
            return False
        desc_words = set(desc.lower().split())
        for wl in wisdom_lines:
            wl_words = set(wl.lower().split())
            if not desc_words or not wl_words:
                continue
            j = len(desc_words & wl_words) / len(desc_words | wl_words)
            if j >= _WISDOM_DEDUP_THRESHOLD:
                return True
        return False

    # Dedup by normalized description AND by overlap with session wisdom block.
    # Emit as `[P83] description` — state abbreviation (P=PATTERN, I=INSTINCT,
    # R=RULE) + confidence percent. Keeps state+confidence signal for the model
    # while remaining compact (~3 tok/rule overhead).
    _STATE_ABBREV = {"PATTERN": "P", "INSTINCT": "I", "RULE": "R"}
    seen_descs: set[str] = set()
    lines = []
    for r, _sim in ranked:
        norm_desc = r.description.strip().lower()
        if norm_desc in seen_descs:
            continue
        seen_descs.add(norm_desc)
        if _already_in_wisdom(r.description):
            continue
        prefix = f"[{_STATE_ABBREV.get(r.state.name, r.state.name)}{round(r.confidence * 100):02d}]"
        lines.append(f"{prefix} {r.description}")
    if not lines:
        return None
    rules_block = "\n".join(lines)
    if len(rules_block) > max_prompt_chars:
        rules_block = rules_block[:max_prompt_chars].rstrip()
    return {"result": rules_block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
