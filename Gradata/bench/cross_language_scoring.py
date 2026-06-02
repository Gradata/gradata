"""cross_language_scoring.py — GRA-1299: does embedding beat BM25 for cross-language rules?

The core question: BM25 ranks by term overlap.  A rule "always use snake_case for
Python" won't match a draft "rename myVar to my_var" unless the terms overlap.
Embedding scoring captures semantic similarity regardless of vocabulary.

Benchmark design
----------------
1. Build 30 cross-language (rule, draft) pairs across 10 categories.
   Each pair is deliberately constructed so Jaccard token overlap is < 0.10 —
   i.e., the rule and draft share no significant vocabulary.
2. Place all 30 rules in the corpus; each draft's ground truth is exactly 1 rule.
3. Run three scorers: Jaccard, BM25 (pure-Python), Embedding (all-MiniLM-L6-v2).
4. Report: P@1 overall, P@1 on truly-zero-overlap probes (Jaccard == 0.0),
   and per-category breakdown.  The delta on zero-overlap probes isolates the
   cross-language gain attributable purely to semantic representation.

Run
---
    python -m bench.cross_language_scoring
    python -m bench.cross_language_scoring --no-embed   # skip embedding
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

RESULTS_DIR = HERE / "results"

# ---------------------------------------------------------------------------
# Tokenizer (identical to inject_scoring.py / jit_inject.py)
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "have", "i", "in", "is", "it", "its", "of", "on", "or",
        "that", "the", "this", "to", "was", "were", "will", "with",
        "you", "your", "we", "our",
    }
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2]


def _tokenize_set(text: str) -> frozenset[str]:
    return frozenset(_tokenize(text))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Cross-language corpus
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    category: str
    description: str


@dataclass
class CrossLangProbe:
    """A (rule_idx, draft) pair where the draft is deliberately paraphrased
    so that it shares ≤1 content token with the target rule.
    """
    rule_idx: int            # index into CORPUS
    draft: str
    category: str


# 30 rules across 10 categories — each rule is written in formal,
# instructional language.  The paired draft uses different vocabulary
# while conveying the same scenario.
CORPUS: list[Rule] = [
    # --- PYTHON (0–2) ---
    Rule("PYTHON", "Write a one-line docstring for every public function."),
    Rule("PYTHON", "Name private helpers with a leading underscore."),
    Rule("PYTHON", "Use pathlib.Path instead of os.path for filesystem operations."),

    # --- SECURITY (3–5) ---
    Rule("SECURITY", "Never log API tokens, passwords, or secret keys."),
    Rule("SECURITY", "Store secrets in environment variables, never in source code."),
    Rule("SECURITY", "Enforce HTTPS; reject plain HTTP in production configs."),

    # --- DRAFTING (6–8) ---
    Rule("DRAFTING", "Use active voice in all user-facing copy."),
    Rule("DRAFTING", "Lead with the conclusion, then the supporting detail."),
    Rule("DRAFTING", "Replace jargon with concrete plain-English equivalents."),

    # --- SALES (9–11) ---
    Rule("SALES", "Qualify every deal against MEDDPICC before forecasting."),
    Rule("SALES", "Include a concrete ROI metric in every proposal summary."),
    Rule("SALES", "Always reference prior Apollo conversations before outreach."),

    # --- EMAIL (12–14) ---
    Rule("EMAIL", "Subject line must be under 50 characters and action-oriented."),
    Rule("EMAIL", "Open with the prospect's first name, never 'Dear' or 'Hey'."),
    Rule("EMAIL", "Verify attachment is attached before clicking Send."),

    # --- DEPLOYMENT (15–17) ---
    Rule("DEPLOYMENT", "Use zero-downtime rolling deploy; never restart all pods at once."),
    Rule("DEPLOYMENT", "Tag every release commit with a semver tag before pushing."),
    Rule("DEPLOYMENT", "Document a rollback plan before merging a deploy PR."),

    # --- FORMAT (18–20) ---
    Rule("FORMAT", "Write dates as Month DD, YYYY (e.g., April 30, 2026)."),
    Rule("FORMAT", "Avoid bold headers inside body paragraphs."),
    Rule("FORMAT", "Never use em dashes in user-facing or marketing copy."),

    # --- OUTREACH (21–23) ---
    Rule("OUTREACH", "Personalise the first sentence with a specific company detail."),
    Rule("OUTREACH", "Avoid buzzwords like 'synergy', 'leverage', or 'disruptive'."),
    Rule("OUTREACH", "Send cold emails between 7–9 am local time of the recipient."),

    # --- CODE_REVIEW (24–26) ---
    Rule("CODE_REVIEW", "Flag magic numbers; require named constants instead."),
    Rule("CODE_REVIEW", "Check that new code paths are covered by at least one unit test."),
    Rule("CODE_REVIEW", "Audit new endpoints for authentication and authorisation checks."),

    # --- TONE (27–29) ---
    Rule("TONE", "Remove hedging phrases such as 'might', 'possibly', or 'could perhaps'."),
    Rule("TONE", "Never use exclamation marks in professional writing."),
    Rule("TONE", "Avoid starting sentences with 'So,' 'Actually,' or 'Basically,'."),
]

# 30 probes — each uses different vocabulary from its target rule.
# The "paraphrase register" is intentionally informal and action-oriented
# (as real user drafts are) while the rule is formal and instructional.
PROBES: list[CrossLangProbe] = [
    # PYTHON
    CrossLangProbe(0,  "This method is missing inline documentation",                                      "PYTHON"),
    CrossLangProbe(1,  "Internal utility functions should be prefixed to signal they are not in the public API", "PYTHON"),
    CrossLangProbe(2,  "Convert the file handling code to the object-oriented directory API",               "PYTHON"),

    # SECURITY
    CrossLangProbe(3,  "The JWT bearer credential is being printed to stdout in the exception handler",     "SECURITY"),
    CrossLangProbe(4,  "The database connection string is hardcoded directly in the configuration file",    "SECURITY"),
    CrossLangProbe(5,  "The service is running without TLS on port 80; switch to encrypted transport",      "SECURITY"),

    # DRAFTING
    CrossLangProbe(6,  "The document was completed by the team — it reads in a passive register throughout", "DRAFTING"),
    CrossLangProbe(7,  "Put the key insight at the start before expanding on the rationale",                "DRAFTING"),
    CrossLangProbe(8,  "Simplify the technical terminology for a non-specialist audience",                   "DRAFTING"),

    # SALES
    CrossLangProbe(9,  "Have you confirmed the buyer's decision criteria and identified the economic champion?", "SALES"),
    CrossLangProbe(10, "Add a quantified business outcome to the executive brief to justify the investment", "SALES"),
    CrossLangProbe(11, "Review the account history in your sales database to understand past touchpoints",   "SALES"),

    # EMAIL
    CrossLangProbe(12, "The email header is way too long and does not tell the reader what to do",          "EMAIL"),
    CrossLangProbe(13, "Do not use formal greetings or casual slang in the opening — address them personally", "EMAIL"),
    CrossLangProbe(14, "Make sure the file is included when you submit the message",                        "EMAIL"),

    # DEPLOYMENT
    CrossLangProbe(15, "Gradually shift traffic to the new containers without taking the whole service offline", "DEPLOYMENT"),
    CrossLangProbe(16, "Label the revision with a version number in the expected format prior to publishing", "DEPLOYMENT"),
    CrossLangProbe(17, "Write down how to undo this change in the ticket prior to getting approval",         "DEPLOYMENT"),

    # FORMAT
    CrossLangProbe(18, "Convert the numeric date string to the long-form textual representation",           "FORMAT"),
    CrossLangProbe(19, "Do not use emphasized titles within the main text — keep the hierarchy flat",       "FORMAT"),
    CrossLangProbe(20, "Remove the long horizontal punctuation mark between these clauses",                 "FORMAT"),

    # OUTREACH
    CrossLangProbe(21, "Add something unique about their recent funding round to open the message",          "OUTREACH"),
    CrossLangProbe(22, "Remove the cliched marketing language that every vendor uses",                       "OUTREACH"),
    CrossLangProbe(23, "Schedule the sequence to arrive in their inbox just before business hours start",   "OUTREACH"),

    # CODE_REVIEW
    CrossLangProbe(24, "The value 86400 appears three times with no context — give it a meaningful identifier", "CODE_REVIEW"),
    CrossLangProbe(25, "This branch has no assertions verifying the behavior at all",                       "CODE_REVIEW"),
    CrossLangProbe(26, "The route handler has no verification that the caller has permission to access this resource", "CODE_REVIEW"),

    # TONE
    CrossLangProbe(27, "This sounds too uncertain — commit to the recommendation instead of qualifying everything", "TONE"),
    CrossLangProbe(28, "The proposal has three enthusiasm indicators — strip them out for a formal register", "TONE"),
    CrossLangProbe(29, "The response opens with a filler transition — delete the first word",               "TONE"),
]


# ---------------------------------------------------------------------------
# Overlap analysis
# ---------------------------------------------------------------------------

def token_overlap(rule: Rule, draft: str) -> tuple[float, frozenset[str]]:
    """Return (jaccard, shared_tokens) between rule text and draft."""
    rule_toks = _tokenize_set(f"{rule.category} {rule.description}")
    draft_toks = _tokenize_set(draft)
    shared = rule_toks & draft_toks
    j = _jaccard(rule_toks, draft_toks)
    return j, shared


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------

ScorerFn = Callable[[str, list[Rule]], list[float]]


def _jaccard_scorer(draft: str, corpus: list[Rule]) -> list[float]:
    draft_toks = _tokenize_set(draft)
    return [
        _jaccard(draft_toks, _tokenize_set(f"{r.category} {r.description}"))
        for r in corpus
    ]


class _BM25:
    """Pure-Python Okapi BM25 (k1=1.5, b=0.75)."""

    def __init__(self, corpus_texts: list[str]) -> None:
        self.tokenized = [_tokenize(t) for t in corpus_texts]
        N = len(self.tokenized)
        self.avgdl = sum(len(d) for d in self.tokenized) / max(N, 1)
        df: dict[str, int] = defaultdict(int)
        for doc in self.tokenized:
            for term in set(doc):
                df[term] += 1
        self.idf: dict[str, float] = {
            term: math.log((N - df[term] + 0.5) / (df[term] + 0.5) + 1.0)
            for term in df
        }
        self.k1 = 1.5
        self.b = 0.75

    def score(self, query: str) -> list[float]:
        q_toks = _tokenize(query)
        scores: list[float] = []
        for doc in self.tokenized:
            dl = len(doc)
            tf_map: dict[str, int] = defaultdict(int)
            for t in doc:
                tf_map[t] += 1
            s = 0.0
            for term in q_toks:
                if term not in self.idf:
                    continue
                tf = tf_map[term]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1))
                s += self.idf[term] * (numerator / denominator)
            scores.append(s)
        max_s = max(scores) if scores else 0.0
        if max_s > 0:
            scores = [s / max_s for s in scores]
        return scores


def make_bm25_scorer(corpus: list[Rule]) -> ScorerFn:
    texts = [f"{r.category} {r.description}" for r in corpus]
    bm25 = _BM25(texts)

    def _s(draft: str, _corpus: list[Rule]) -> list[float]:
        return bm25.score(draft)

    return _s


def make_embedding_scorer(corpus: list[Rule]) -> ScorerFn | None:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        return None

    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [f"{r.category} {r.description}" for r in corpus]
    embs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    embs_norm = embs / norms

    def _s(draft: str, _corpus: list[Rule]) -> list[float]:
        q = model.encode([draft], convert_to_numpy=True, show_progress_bar=False)[0]
        qn = np.linalg.norm(q)
        if qn > 0:
            q = q / qn
        sims = embs_norm @ q
        sims = (sims + 1.0) / 2.0
        return sims.tolist()

    return _s


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    probe_idx: int
    category: str
    target_rule_idx: int
    draft_snippet: str
    jaccard_overlap: float
    shared_tokens: frozenset[str]
    hit_at_1: bool
    ranked_target_pos: int   # 1-based position of the target rule in the ranking
    latency_ms: float


@dataclass
class ScorerReport:
    name: str
    precision_at_1: float
    precision_at_1_zero_overlap: float   # only probes with Jaccard == 0.0
    precision_at_3: float
    avg_latency_ms: float
    p95_latency_ms: float
    per_category: dict[str, float]       # category → P@1
    probe_results: list[ProbeResult] = field(default_factory=list)


def _evaluate(
    name: str,
    scorer_fn: ScorerFn,
    corpus: list[Rule],
    probes: list[CrossLangProbe],
) -> ScorerReport:
    results: list[ProbeResult] = []
    latencies: list[float] = []

    for pi, probe in enumerate(probes):
        rule = corpus[probe.rule_idx]
        jac, shared = token_overlap(rule, probe.draft)

        t0 = time.perf_counter()
        scores = scorer_fn(probe.draft, corpus)
        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed)

        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        target_pos = ranked.index(probe.rule_idx) + 1  # 1-based
        hit1 = target_pos == 1
        hit3 = target_pos <= 3

        results.append(ProbeResult(
            probe_idx=pi,
            category=probe.category,
            target_rule_idx=probe.rule_idx,
            draft_snippet=probe.draft[:70],
            jaccard_overlap=round(jac, 4),
            shared_tokens=shared,
            hit_at_1=hit1,
            ranked_target_pos=target_pos,
            latency_ms=round(elapsed, 3),
        ))

    n = len(results)
    p1 = sum(1 for r in results if r.hit_at_1) / n
    p3 = sum(1 for r in results if r.ranked_target_pos <= 3) / n

    zero_overlap = [r for r in results if r.jaccard_overlap == 0.0]
    p1_zero = (
        sum(1 for r in zero_overlap if r.hit_at_1) / len(zero_overlap)
        if zero_overlap else float("nan")
    )

    by_cat: dict[str, list[ProbeResult]] = defaultdict(list)
    for r in results:
        by_cat[r.category].append(r)
    per_cat = {
        cat: round(sum(1 for r in rs if r.hit_at_1) / len(rs), 3)
        for cat, rs in sorted(by_cat.items())
    }

    avg_lat = sum(latencies) / len(latencies)
    p95_lat = sorted(latencies)[int(0.95 * len(latencies))]

    return ScorerReport(
        name=name,
        precision_at_1=round(p1, 3),
        precision_at_1_zero_overlap=round(p1_zero, 3),
        precision_at_3=round(p3, 3),
        avg_latency_ms=round(avg_lat, 3),
        p95_latency_ms=round(p95_lat, 3),
        per_category=per_cat,
        probe_results=results,
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _write_report(
    reports: list[ScorerReport],
    corpus: list[Rule],
    probes: list[CrossLangProbe],
    run_date: str,
    total_s: float,
) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = RESULTS_DIR / f"cross-language-scoring-{tag}.md"

    lines: list[str] = []
    a = lines.append

    a(f"# cross-language-scoring benchmark — {run_date}")
    a("")
    a(f"**GRA-1299**: embedding vs BM25 on zero-term-overlap probes  ")
    a(f"**Corpus**: {len(corpus)} rules (30 cross-language pairs, 10 categories)  ")
    a(f"**Probes**: {len(probes)} | **Wall time**: {total_s:.1f}s")
    a("")

    # Overlap analysis
    overlaps = [token_overlap(corpus[p.rule_idx], p.draft)[0] for p in probes]
    zero_n = sum(1 for j in overlaps if j == 0.0)
    low_n = sum(1 for j in overlaps if 0.0 < j < 0.05)
    med_n = sum(1 for j in overlaps if j >= 0.05)
    a("## Corpus overlap analysis")
    a("")
    a("| Overlap tier | n probes | Jaccard range |")
    a("|-------------|---------|--------------|")
    a(f"| Zero (J=0.00) | {zero_n} | exactly 0 |")
    a(f"| Low (J<0.05) | {low_n} | 0.01–0.04 |")
    a(f"| Medium (J≥0.05) | {med_n} | 0.05+ |")
    a("")

    a("## Summary — P@1 overall vs zero-overlap subset")
    a("")
    a(f"*(Zero-overlap n={zero_n} probes — pure semantic matching, no shared vocabulary)*")
    a("")
    a("| Scorer | P@1 (all 30) | P@1 (zero-overlap) | P@3 (all 30) | Avg ms |")
    a("|--------|-------------|---------------------|-------------|--------|")
    for rep in reports:
        a(
            f"| {rep.name} "
            f"| {rep.precision_at_1:.3f} "
            f"| {rep.precision_at_1_zero_overlap:.3f} "
            f"| {rep.precision_at_3:.3f} "
            f"| {rep.avg_latency_ms:.2f} |"
        )
    a("")

    a("## Per-category P@1")
    a("")
    cats = sorted({p.category for p in probes})
    hdr = "| Category |" + "".join(f" {r.name} |" for r in reports)
    sep = "|----------|" + "----------|" * len(reports)
    a(hdr)
    a(sep)
    for cat in cats:
        row = f"| {cat:12} |"
        for rep in reports:
            v = rep.per_category.get(cat, float("nan"))
            row += f" {v:.3f}    |"
        a(row)
    a("")

    a("## Per-probe detail")
    a("")
    a("Columns: Jaccard overlap | shared tokens | target rank per scorer (1=top)")
    a("")
    hdr2 = "| # | Cat | Draft snippet | J | Shared | " + " | ".join(f"{r.name} rank" for r in reports) + " |"
    a(hdr2)
    a("|---|-----|---------------|---|--------|" + "----------|" * len(reports))
    for pi, probe in enumerate(probes):
        jac, shared = token_overlap(corpus[probe.rule_idx], probe.draft)
        row = (
            f"| {pi:2d} | {probe.category:12} "
            f"| {probe.draft[:52]:<52} "
            f"| {jac:.2f} "
            f"| {','.join(sorted(shared)) or '—'} "
        )
        for rep in reports:
            pr = rep.probe_results[pi]
            mark = "✓" if pr.hit_at_1 else f"#{pr.ranked_target_pos}"
            row += f"| {mark:<8} "
        row += "|"
        a(row)
    a("")

    a("## Recommendation")
    a("")
    reports_by_name = {r.name: r for r in reports}
    bm25 = reports_by_name.get("BM25")
    emb = reports_by_name.get("Embedding")

    if bm25 is not None and emb is not None:
        delta_all = emb.precision_at_1 - bm25.precision_at_1
        delta_zero = emb.precision_at_1_zero_overlap - bm25.precision_at_1_zero_overlap

        a(f"**BM25 P@1 (all):** {bm25.precision_at_1:.3f}  ")
        a(f"**Embedding P@1 (all):** {emb.precision_at_1:.3f}  (Δ = {delta_all:+.3f})")
        a("")
        a(f"**BM25 P@1 (zero-overlap):** {bm25.precision_at_1_zero_overlap:.3f}  ")
        a(f"**Embedding P@1 (zero-overlap):** {emb.precision_at_1_zero_overlap:.3f}  (Δ = {delta_zero:+.3f})")
        a("")

        if delta_zero >= 0.30:
            verdict = "REPLACE"
            body = (
                f"Embedding shows a dominant gain on zero-overlap probes "
                f"(Δ={delta_zero:+.3f}).  BM25 is structurally blind to cross-language "
                f"rules; embedding should become the primary scorer with BM25 as the "
                f"no-dep fallback via `GRADATA_JIT_SCORER=embedding`."
            )
        elif delta_zero >= 0.15:
            verdict = "AUGMENT"
            body = (
                f"Embedding shows a meaningful gain on zero-overlap probes "
                f"(Δ={delta_zero:+.3f}).  Add embedding as an optional tier "
                f"(`GRADATA_JIT_SCORER=embedding`) while keeping BM25 as the default."
            )
        elif delta_zero >= 0.05:
            verdict = "AUGMENT (optional)"
            body = (
                f"Embedding shows a moderate gain on zero-overlap probes "
                f"(Δ={delta_zero:+.3f}).  The cross-language advantage exists but is "
                f"not decisive at this corpus size.  Opt-in tier is appropriate."
            )
        else:
            verdict = "SKIP"
            body = (
                f"Embedding shows negligible gain on zero-overlap probes "
                f"(Δ={delta_zero:+.3f}).  The latency cost is not justified.  "
                f"Keep BM25 as default and re-evaluate at 500+ rule corpus."
            )

        a(f"**Verdict: {verdict}**")
        a("")
        a(body)
    else:
        a("*(Embedding scorer not available — install sentence-transformers to compare)*")
    a("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(include_embedding: bool = True) -> list[ScorerReport]:
    t0 = time.perf_counter()
    run_date = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    corpus = CORPUS
    probes = PROBES

    print(f"[cross-lang] corpus: {len(corpus)} rules | probes: {len(probes)}", file=sys.stderr)

    # Overlap stats
    overlaps = [token_overlap(corpus[p.rule_idx], p.draft)[0] for p in probes]
    zero_n = sum(1 for j in overlaps if j == 0.0)
    print(
        f"[cross-lang] overlap: {zero_n}/{len(probes)} probes have J=0.0 (true zero-overlap)",
        file=sys.stderr,
    )

    scorers: list[tuple[str, ScorerFn]] = [
        ("Jaccard", _jaccard_scorer),
        ("BM25", make_bm25_scorer(corpus)),
    ]
    if include_embedding:
        emb = make_embedding_scorer(corpus)
        if emb:
            scorers.append(("Embedding", emb))
            print("[cross-lang] embedding scorer ready (all-MiniLM-L6-v2)", file=sys.stderr)
        else:
            print("[cross-lang] sentence-transformers not found — skipping", file=sys.stderr)

    reports: list[ScorerReport] = []
    for name, fn in scorers:
        print(f"[cross-lang] evaluating {name}…", file=sys.stderr)
        rep = _evaluate(name, fn, corpus, probes)
        reports.append(rep)
        print(
            f"[cross-lang]   {name}: P@1={rep.precision_at_1:.3f}  "
            f"P@1(zero)={rep.precision_at_1_zero_overlap:.3f}  "
            f"P@3={rep.precision_at_3:.3f}  {rep.avg_latency_ms:.2f}ms",
            file=sys.stderr,
        )

    total = time.perf_counter() - t0
    out = _write_report(reports, corpus, probes, run_date, total)
    print(f"[cross-lang] saved: {out}", file=sys.stderr)

    # Stdout summary
    print()
    print("cross-language-scoring — GRA-1299")
    print(f"  corpus={len(corpus)} rules  probes={len(probes)}  zero-overlap={zero_n}  wall={total:.1f}s")
    print()
    print(f"  {'Scorer':12}  {'P@1':>6}  {'P@1(J=0)':>8}  {'P@3':>6}  {'ms':>6}")
    print("  " + "-" * 48)
    for rep in reports:
        p1z = f"{rep.precision_at_1_zero_overlap:.3f}" if not math.isnan(rep.precision_at_1_zero_overlap) else "  n/a"
        print(
            f"  {rep.name:12}  {rep.precision_at_1:.3f}  {p1z:>8}  "
            f"{rep.precision_at_3:.3f}  {rep.avg_latency_ms:>6.2f}"
        )
    print()

    return reports


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--no-embed", action="store_true", help="Skip embedding scorer")
    args = p.parse_args()
    run(include_embedding=not args.no_embed)


if __name__ == "__main__":
    main()
