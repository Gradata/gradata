"""
Tests for gradata._triggers — n-gram extraction + recall@k harness.

The most important tests in this file are the recall measurements at the
bottom: they're the falsifiable claim from the council's Step 4. If
``recall < 0.70`` on a synthetic-but-realistic corpus, the architecture's
"deterministic routing is good enough" assumption is empirically wrong and
the design needs a tiny classifier in the path.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from gradata._triggers import (
    CorrectionExample,
    TriggerIndex,
    extract_correction_triggers,
    extract_ngrams,
    load,
    measure_recall,
    save,
)


# ─── n-gram extraction ───────────────────────────────────────────────────────


def test_extract_ngrams_is_deterministic():
    """Same text in → same tuples out, in the same order. No hidden hash
    randomisation, no ordering drift across runs."""
    text = "Always write short subject lines for cold emails to founders"
    out1 = extract_ngrams(text)
    out2 = extract_ngrams(text)
    assert out1 == out2
    # Shape check: it's a list of (str, str) tuples, dedup'd, canonical-sorted.
    for ng in out1:
        assert isinstance(ng, tuple) and len(ng) == 2
        assert ng[0] < ng[1]


def test_extract_ngrams_drops_stopwords():
    """`the` and `a` must NOT appear in any ngram, otherwise every text
    matches every other text and recall collapses."""
    out = extract_ngrams("write the email to a founder")
    flat = [w for ng in out for w in ng]
    assert "the" not in flat
    assert "a" not in flat
    # Content words survived.
    assert "write" in flat
    assert "email" in flat
    assert "founder" in flat


def test_extract_ngrams_window_bounds():
    """Tokens further than the window apart must NOT co-occur. Otherwise the
    bigram space explodes and noise drowns signal."""
    text = "alpha beta gamma delta epsilon zeta eta theta"
    pairs = set(extract_ngrams(text, window=2))
    assert ("alpha", "beta") in pairs
    assert ("alpha", "gamma") in pairs
    # alpha → epsilon is 4 tokens away, beyond window=2.
    assert ("alpha", "epsilon") not in pairs


def test_extract_correction_triggers_unions_draft_and_final():
    """Triggers from BOTH draft and final must surface — some rules fire on
    surface tokens that only exist in one or the other."""
    draft = "really excited to share our awesome product"
    final = "share our product"
    triggers = extract_correction_triggers(draft, final)
    flat = {w for ng in triggers for w in ng}
    # "excited", "awesome" (only in draft) → present
    assert "excited" in flat
    assert "awesome" in flat
    # "share", "product" (in both) → present
    assert "share" in flat
    assert "product" in flat


# ─── TriggerIndex ────────────────────────────────────────────────────────────


def test_index_add_and_lookup():
    """Trivial round trip: add a rule's triggers, query with same triggers,
    that rule wins."""
    idx = TriggerIndex()
    idx.add("R1", [("write", "email"), ("short", "subject")])

    hits = idx.lookup([("write", "email")], top_k=5)
    assert hits[0][0] == "R1"
    assert hits[0][1] >= 1.0


def test_index_ranks_by_summed_weight():
    """A query that fires multiple ngrams against the same rule must rank
    that rule above one that fires only once. Sum-of-weights, not max."""
    idx = TriggerIndex()
    idx.add("R_voice", [("write", "email"), ("short", "subject"), ("cold", "outreach")])
    idx.add("R_decision", [("verify", "pricing")])

    # Query fires 2 of R_voice's 3 ngrams, 0 of R_decision's.
    ranked = idx.lookup([("write", "email"), ("short", "subject")], top_k=5)
    assert ranked[0][0] == "R_voice"
    # R_decision shouldn't even appear (zero score).
    assert all(rid != "R_decision" for rid, _ in ranked)


def test_index_empty_query_returns_nothing():
    idx = TriggerIndex()
    idx.add("R1", [("a_word", "b_word")])
    assert idx.lookup([], top_k=5) == []


def test_index_unknown_query_returns_nothing():
    """A query whose ngrams nobody indexed must return [] — that's the
    `empty_lookup` failure mode the recall harness tracks separately."""
    idx = TriggerIndex()
    idx.add("R1", [("write", "email")])
    assert idx.lookup([("totally", "unrelated")], top_k=5) == []


def test_index_top_k_bounds_results():
    idx = TriggerIndex()
    common = [("shared", "word")]
    for i in range(20):
        idx.add(f"R{i}", common)
    ranked = idx.lookup(common, top_k=3)
    assert len(ranked) == 3


def test_index_persistence_roundtrip(tmp_path: Path):
    """save + load must reconstruct an equivalent index — same ngrams,
    same rules, same lookups. Critical for `gradata project`-style flows
    where the index is built once and queried many times."""
    idx = TriggerIndex()
    idx.add("R1", [("write", "email"), ("short", "subject")])
    idx.add("R2", [("verify", "pricing")])

    p = tmp_path / "triggers.jsonl"
    save(idx, p)
    assert p.exists()

    reloaded = load(p)
    assert set(reloaded.rules()) == {"R1", "R2"}
    assert reloaded.lookup([("write", "email")], top_k=5)[0][0] == "R1"
    assert reloaded.lookup([("verify", "pricing")], top_k=5)[0][0] == "R2"


def test_load_missing_file_returns_empty_index(tmp_path: Path):
    idx = load(tmp_path / "nope.jsonl")
    assert idx.size()["edges"] == 0


# ─── Recall@k harness — the falsifiable architectural claim ──────────────────


def _synthetic_corpus(seed: int = 42) -> tuple[list[CorrectionExample], list[CorrectionExample]]:
    """Build a small but lexically-distinct corpus.

    The point is NOT to prove production-grade recall — it's to verify the
    harness fires correctly and the trivial case (where rules have
    distinguishable trigger vocabulary) achieves the stated threshold.
    Real-corpus recall measurement happens in the offline benchmark, not
    here.

    Each rule has a distinct vocabulary "signature" (3-4 anchor words),
    plus 4-6 surface variations per rule, train/test split 60/40.
    """
    rng = random.Random(seed)
    rules: dict[str, list[str]] = {
        "R_voice_email_short": [
            "write a short cold email to the prospect about pricing",
            "draft a brief outreach email mentioning short subject",
            "compose a concise email subject for cold outreach today",
            "short subject line on the cold email please",
            "keep the cold email subject brief and direct",
            "send a short outreach email to the founder right now",
            "we should write a brief email subject for prospects",
            "compose short subject email outreach pitch line",
        ],
        "R_decision_pricing_verify": [
            "verify the pricing tier before quoting any number",
            "always confirm the pricing on the contract before sending",
            "check pricing accuracy in the quote document carefully",
            "confirm pricing data with the source before publishing",
            "verify pricing numbers before quoting on the call",
            "double-check pricing tier accuracy ahead of the proposal",
            "validate pricing on the contract before signing today",
            "ensure pricing accuracy in the quote totals",
        ],
        "R_relation_acme_formal": [
            "use formal tone with acme bob the executive sponsor",
            "acme prefers formal language in all bob exec emails",
            "formal addressing for acme corp executives like bob",
            "bob at acme expects formal tone in client emails",
            "always formal voice when emailing acme exec bob today",
            "acme exec bob requires formal style email greetings",
            "formal greetings for acme bob in client emails",
            "acme bob prefers formal exec email tone",
        ],
        "R_process_pr_review": [
            "all changes must go through pr review before merge",
            "pr review required before any merge to main branch",
            "every commit needs pr review approval before merge",
            "no direct merges always pr review on main always",
            "code review required pr before main branch merge",
            "pr review approval required before merge to main",
            "always pr review every change before merge to main",
            "pr review gate before merge to main branch always",
        ],
    }
    train: list[CorrectionExample] = []
    test: list[CorrectionExample] = []
    for rid, examples in rules.items():
        rng.shuffle(examples)
        # 60/40 split.
        cutoff = int(len(examples) * 0.6)
        for ex in examples[:cutoff]:
            # draft = the example, final = a slight variation. Keeps the
            # bigram signal strong in both.
            train.append(CorrectionExample(rule_id=rid, draft=ex, final=ex))
        for ex in examples[cutoff:]:
            test.append(CorrectionExample(rule_id=rid, draft=ex, final=ex))
    return train, test


def test_measure_recall_meets_council_threshold():
    """The architectural T2 claim: deterministic n-gram routing achieves
    recall@5 ≥ 0.70 on rules with distinguishable vocabulary. If this fails,
    the hybrid plan needs a classifier in the path — which is fine, but
    must be flagged before we build more on top.

    NB: this is a SYNTHETIC corpus where rules have curated, lexically-
    distinct vocab. It's a sanity check on the harness, not a production
    claim. Real-corpus recall on Oliver's actual brain is the next test.
    """
    train, test = _synthetic_corpus()
    result = measure_recall(train, test, top_k=5)
    assert result.recall >= 0.70, (
        f"recall@5 = {result.recall:.2%} < 70% threshold. "
        f"Triggers alone may not be enough; consider classifier fallback. "
        f"by_rule={result.as_dict()}"
    )


def test_measure_recall_top_k_monotonic():
    """Recall@k must be non-decreasing in k — adding more candidates can
    never lose a true positive that was already in the set."""
    train, test = _synthetic_corpus()
    r1 = measure_recall(train, test, top_k=1).recall
    r3 = measure_recall(train, test, top_k=3).recall
    r10 = measure_recall(train, test, top_k=10).recall
    assert r1 <= r3 <= r10


def test_measure_recall_breakdown_per_rule():
    """Per-rule breakdown must add up to total. This is how we'll spot
    'rule X has terrible recall' in real corpora and reach for a smarter
    fallback only for those rules."""
    train, test = _synthetic_corpus()
    result = measure_recall(train, test, top_k=5)
    total_from_breakdown = sum(v["total"] for v in result.by_rule.values())
    hits_from_breakdown = sum(v["hits"] for v in result.by_rule.values())
    assert total_from_breakdown == result.total
    assert hits_from_breakdown == result.hits


def test_measure_recall_handles_empty_test_set():
    """No test examples → recall undefined but no crash. Returns 0.0 (the
    safe default) rather than a divide-by-zero."""
    result = measure_recall([CorrectionExample("R1", "x y z", "x y z")], [], top_k=5)
    assert result.total == 0
    assert result.recall == 0.0
