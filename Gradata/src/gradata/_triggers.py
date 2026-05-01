"""
Trigger n-gram extractor — falsifiable test of T2.
====================================================

The Skeptic's open question from the council: do (verb, domain-noun) bigrams
extracted at correct() time give us deterministic rule routing with ≥70%
recall against held-out corrections? If yes, Gbrain-style zero-LLM self-wiring
generalises to behavioural rules. If not, we need a tiny classifier instead.

This module:
  1. Extracts trigger n-grams from a draft+final pair (regex only, no LLM).
  2. Stores ``(rule_id, trigger_ngram)`` edges as the rule graduates.
  3. Looks up candidate rules at apply-time given a fresh draft's n-grams.
  4. Provides a measurement harness that splits a corrections corpus
     train/test, builds the index from train, and reports recall@k on test.

Determinism: regex-only. No tokenizers with hidden state, no embedding model.
Two callers running on the same Python build get identical n-grams from the
same text. That's the whole load-bearing assumption.

Storage: lives in ``<brain>/triggers.jsonl`` — append-only event log of
``(rule_id, ngram, score, ts)`` tuples. Easy to rebuild from corrections,
easy to project to a SQLite index later if hot-path lookup becomes the
bottleneck. We keep it as JSONL for now to mirror events.jsonl's portability.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

_log = logging.getLogger("gradata.triggers")

# ─── Tokenisation ────────────────────────────────────────────────────────────
# A trigger is a (verb-ish word, content-word) pair within a small window.
# We intentionally use a tiny stop-list and case-fold; the goal is recall
# (does the n-gram fire on test corrections that touch the same rule?), not
# linguistic precision. A precision pass can come later via a tiny classifier
# if the recall harness shows we need it.

_WORD_RE = re.compile(r"[a-z][a-z0-9_'-]{1,}")

# Minimal English stoplist. Extending this is cheap; shrinking it is risky
# (you'd start picking up "a", "the" pairs that match every text).
_STOP = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on",
        "at", "by", "for", "with", "from", "as", "is", "are", "was", "were",
        "be", "been", "being", "this", "that", "these", "those", "it", "its",
        "i", "you", "he", "she", "we", "they", "me", "him", "her", "us",
        "them", "my", "your", "his", "their", "our", "what", "which", "who",
        "whom", "whose", "do", "does", "did", "have", "has", "had", "will",
        "would", "should", "could", "can", "may", "might", "must", "shall",
        "not", "no", "yes", "so", "than", "then", "there", "here", "very",
        "just", "only", "also", "too",
    }
)

# Window size for bigram extraction. 4 = "(verb [skip skip skip] noun)"
# tolerates short adverbial inserts ("write the very short email") without
# blowing up the ngram space.
_WINDOW = 4


def _tokens(text: str) -> list[str]:
    """Lowercase token stream, stopwords removed, deterministic order."""
    return [w for w in _WORD_RE.findall(text.lower()) if w not in _STOP]


def extract_ngrams(text: str, *, window: int = _WINDOW) -> list[tuple[str, str]]:
    """Extract co-occurrence bigrams within a sliding window.

    Returns deduplicated ``(left, right)`` tuples in canonical (sorted) form,
    so ``("write", "email")`` and ``("email", "write")`` collapse — order
    matters semantically but not for trigger lookup, and dedup keeps the
    index small.

    The window is small (4 tokens) because we want LOCAL phrasal triggers,
    not document-wide co-occurrence. Increasing the window inflates the
    index quadratically and adds noise faster than recall.
    """
    toks = _tokens(text)
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for i, left in enumerate(toks):
        for right in toks[i + 1 : i + 1 + window]:
            if left == right:
                continue
            pair = (left, right) if left < right else (right, left)
            if pair in seen:
                continue
            seen.add(pair)
            out.append(pair)
    return out


def extract_correction_triggers(draft: str, final: str) -> list[tuple[str, str]]:
    """Triggers derived from a correction event.

    We extract from BOTH the draft (what the AI produced) and the final
    (what the user wanted), then union. Why both: rules sometimes fire on
    surface tokens that only appear in the draft (rule = "don't say X"),
    sometimes only in the final (rule = "always include Y"). Union gives
    the best recall at the cost of mild over-indexing — which the
    measurement harness will catch if it hurts precision.
    """
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for source in (draft, final):
        for ng in extract_ngrams(source):
            if ng in seen:
                continue
            seen.add(ng)
            out.append(ng)
    return out


# ─── Index ───────────────────────────────────────────────────────────────────


@dataclass
class TriggerIndex:
    """In-memory bigram → rule_id map with score weighting.

    Score is just a frequency count in the current implementation. A future
    revision could swap in PMI or Bayesian smoothing if the measurement
    harness shows score-sensitive ranking (top-k vs. all-fired).
    """

    # ngram → {rule_id: weight}
    _table: dict[tuple[str, str], dict[str, int]] = field(default_factory=dict)
    # rule_id → set of ngrams (for rebuilds / pruning)
    _by_rule: dict[str, set[tuple[str, str]]] = field(default_factory=dict)

    def add(self, rule_id: str, ngrams: Iterable[tuple[str, str]]) -> None:
        for ng in ngrams:
            self._table.setdefault(ng, {})[rule_id] = self._table.get(ng, {}).get(rule_id, 0) + 1
            self._by_rule.setdefault(rule_id, set()).add(ng)

    def lookup(self, ngrams: Iterable[tuple[str, str]], *, top_k: int = 10) -> list[tuple[str, float]]:
        """Return rule_ids ranked by summed weight across matched ngrams.

        The score is the sum of edge weights for every fired ngram. Ties are
        broken by rule_id (stable, deterministic). top_k=0 returns all.
        """
        scores: Counter[str] = Counter()
        for ng in ngrams:
            row = self._table.get(ng)
            if not row:
                continue
            for rule_id, w in row.items():
                scores[rule_id] += w
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        if top_k > 0:
            ranked = ranked[:top_k]
        return [(rid, float(s)) for rid, s in ranked]

    def rules(self) -> list[str]:
        return sorted(self._by_rule.keys())

    def size(self) -> dict[str, int]:
        return {
            "ngrams": len(self._table),
            "rules": len(self._by_rule),
            "edges": sum(len(v) for v in self._table.values()),
        }


# ─── Persistence ─────────────────────────────────────────────────────────────


def save(index: TriggerIndex, path: Path) -> None:
    """Persist as JSONL — one ``(rule_id, ngram, weight)`` line per edge.

    JSONL chosen over a single JSON blob for the same reason events.jsonl is:
    appendable, line-recoverable on partial writes, easy to grep.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ng, rules in sorted(index._table.items()):
            for rule_id, w in sorted(rules.items()):
                fh.write(json.dumps({"rule_id": rule_id, "ngram": list(ng), "w": w}) + "\n")


def load(path: Path) -> TriggerIndex:
    """Load from JSONL. Missing file → empty index (caller decides if that's
    an error)."""
    idx = TriggerIndex()
    if not path.exists():
        return idx
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ng = tuple(row["ngram"])
            rid = row["rule_id"]
            w = int(row.get("w", 1))
            for _ in range(w):
                # Replay weight by re-adding; cheap on reasonable corpus sizes.
                idx.add(rid, [ng])
    return idx


# ─── Measurement harness ─────────────────────────────────────────────────────


@dataclass
class RecallResult:
    """Outcome of a recall@k evaluation against held-out corrections.

    A recall pass = true rule_id appears in the top_k results returned by
    ``TriggerIndex.lookup`` for the test draft+final's ngrams. We report:
      - hits  : test cases where recall succeeded
      - total : test cases evaluated
      - recall: hits / total (0..1)
      - top_k : k used
      - empty_lookups: cases where lookup returned [] (separately tracked,
        because "no candidates at all" is a different failure mode from
        "wrong candidate ranked higher")
    """

    hits: int
    total: int
    top_k: int
    empty_lookups: int
    by_rule: dict[str, dict[str, int]]  # rule_id → {hits, total}

    @property
    def recall(self) -> float:
        return self.hits / self.total if self.total else 0.0

    def as_dict(self) -> dict:
        return {
            "recall": round(self.recall, 4),
            "hits": self.hits,
            "total": self.total,
            "top_k": self.top_k,
            "empty_lookups": self.empty_lookups,
            "by_rule": self.by_rule,
        }


@dataclass(frozen=True)
class CorrectionExample:
    """One labelled correction: draft + final + the rule_id it should fire."""

    rule_id: str
    draft: str
    final: str


def measure_recall(
    train: Sequence[CorrectionExample],
    test: Sequence[CorrectionExample],
    *,
    top_k: int = 5,
) -> RecallResult:
    """Build an index from ``train`` and measure recall@k on ``test``.

    The threshold the architecture rests on: ``recall ≥ 0.70`` at
    ``top_k=5`` validates T2 (zero-LLM routing is good enough). Below that,
    we need a tiny classifier in the path.

    Per-rule breakdown surfaces tail rules that the index can't index well
    (e.g. rules with very short or generic descriptions). Those are exactly
    the cases where you'd want to fall back to embedding lookup.
    """
    idx = TriggerIndex()
    for ex in train:
        idx.add(ex.rule_id, extract_correction_triggers(ex.draft, ex.final))

    by_rule: dict[str, dict[str, int]] = defaultdict(lambda: {"hits": 0, "total": 0})
    hits = 0
    empty = 0
    for ex in test:
        candidates = idx.lookup(
            extract_correction_triggers(ex.draft, ex.final), top_k=top_k
        )
        by_rule[ex.rule_id]["total"] += 1
        if not candidates:
            empty += 1
            continue
        if any(rid == ex.rule_id for rid, _ in candidates):
            hits += 1
            by_rule[ex.rule_id]["hits"] += 1

    return RecallResult(
        hits=hits,
        total=len(test),
        top_k=top_k,
        empty_lookups=empty,
        by_rule=dict(by_rule),
    )


__all__ = [
    "CorrectionExample",
    "RecallResult",
    "TriggerIndex",
    "extract_correction_triggers",
    "extract_ngrams",
    "load",
    "measure_recall",
    "save",
]
