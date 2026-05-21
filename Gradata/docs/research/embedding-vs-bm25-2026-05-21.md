# GRA-1299: Embedding vs BM25 for Cross-Language Rule Injection

**Date:** 2026-05-21  
**Author:** analyst (claude_local, GRA-1299)  
**Harness:** `bench/cross_language_scoring.py`  
**Raw results:** `bench/results/cross-language-scoring-20260521T075538.md`  
**Upstream:** GRA-1292 (general scorer benchmark), GRA-1291 (injection survey)

---

## Problem Statement

BM25 ranks by term overlap.  A rule such as:

> "Write a one-line docstring for every public function."

…will score **zero** against a draft such as:

> "This method is missing inline documentation"

because the token sets are disjoint.  BM25 knows nothing about the fact that
`docstring` and `documentation` are synonyms, or that `function` and `method`
refer to the same concept.  This is the *cross-language* failure mode: the rule
is written in a formal, instructional register; the user's draft is informal and
action-oriented.

GRA-1292 benchmarked BM25 vs embedding on a general corpus where most probes
shared vocabulary with their target rules.  GRA-1299 isolates the cross-language
signal: 30 rule–draft pairs engineered to share **zero or near-zero vocabulary**,
testing whether embedding captures semantic equivalence even when lexical
matching fails completely.

---

## Method

### Corpus design

30 rules across 10 categories (PYTHON, SECURITY, DRAFTING, SALES, EMAIL,
DEPLOYMENT, FORMAT, OUTREACH, CODE_REVIEW, TONE) — 3 rules per category.

Rules are written in the typical Gradata lesson format: formal, instructional,
written in a third-person imperative register.

### Probe design

Each rule gets exactly one paired probe.  Probes are written in the register of
real user drafts: informal, first- or second-person, action-oriented, using
different vocabulary from the rule.  Construction rule: the probe must have a
Jaccard token similarity < 0.05 against its target rule (after applying the same
stopword list and tokenizer as `jit_inject.py`).

**Result:** 28 of 30 probes achieved J=0.00 (exact zero overlap); 2 probes
("sales" shared in probe 11, "email" shared in probe 12) landed at J=0.06–0.07.

### Scorers

| Scorer | Implementation | Notes |
|--------|---------------|-------|
| Jaccard | Word-unigram overlap | Same as jit_inject.py fallback |
| BM25 | Pure-Python Okapi k1=1.5, b=0.75 | Same as inject_scoring.py |
| Embedding | sentence-transformers/all-MiniLM-L6-v2, cosine | 84MB model, CPU |

### Metrics

- **P@1**: is the target rule ranked #1 by the scorer?
- **P@1(J=0)**: P@1 restricted to the 28 probes with exact zero token overlap
- **P@3**: is the target rule in the top 3?
- **Avg latency**: wall-clock time to score one probe against 30-doc corpus

---

## Results

### Headline numbers

| Scorer | P@1 (all 30) | P@1 (zero-overlap, n=28) | P@3 | Avg ms |
|--------|-------------|--------------------------|-----|--------|
| Jaccard | 0.033 | 0.036 | 0.133 | 0.13 |
| BM25 (current) | 0.033 | 0.036 | 0.133 | 0.08 |
| **Embedding** | **0.733** | **0.714** | **0.833** | 14.40 |

Random chance on a 30-document corpus is P@1 = 0.033 (1/30).  BM25 matches
random exactly — because on zero-overlap probes BM25 assigns identical (zero)
scores to every document, making selection arbitrary.  Embedding is **22× better
than random** and **22× better than BM25** on the same cross-language pairs.

### Per-category P@1 (embedding)

| Category | Embedding P@1 | Notes |
|----------|------------|-------|
| DEPLOYMENT | 1.000 | All 3 probes ranked #1 |
| EMAIL | 1.000 | All 3 probes ranked #1 |
| SALES | 1.000 | All 3 probes ranked #1 |
| SECURITY | 1.000 | All 3 probes ranked #1 |
| CODE_REVIEW | 0.667 | 1 miss: "route handler/permission" → ranked #5 |
| DRAFTING | 0.667 | 1 miss: "terminology/non-specialist" → ranked #2 |
| FORMAT | 0.667 | 1 miss: "punctuation mark" → ranked #4 |
| OUTREACH | 0.667 | 1 miss: "clichéd marketing language" → ranked #3 |
| PYTHON | 0.333 | 2 misses (detail below) |
| TONE | 0.333 | 2 misses (detail below) |

### Embedding failure cases

**PYTHON (P@1=0.33):**

- Probe 0: "This method is missing inline documentation" → rule: "Write a one-line
  docstring for every public function." → ranked **#4**, not #1.
  Root cause: the three PYTHON rules are semantically close; the embedding space
  doesn't distinguish strongly between "documentation missing" (probe 0) and
  "naming convention" (rule 1) or "pathlib" (rule 2).  The 30-doc corpus creates
  a hard-rank problem when intra-category distances are small.

- Probe 1: "Internal utility functions should be prefixed to signal they are not in
  the public API" → rule: "Name private helpers with a leading underscore." →
  ranked **#3**.  "Prefixed / not in the public API" and "leading underscore" are
  semantically adjacent but `all-MiniLM-L6-v2` doesn't specialise in Python
  naming conventions.  A fine-tuned model would likely close this.

**TONE (P@1=0.33):**

- Probe 27: "This sounds too uncertain — commit to the recommendation instead of
  qualifying everything" → rule: "Remove hedging phrases such as 'might',
  'possibly', or 'could perhaps'." → ranked **#8**.
  Root cause: "uncertain / qualifying" and "hedging phrases / might / possibly"
  are semantically close but the general-purpose model doesn't strongly associate
  them.

- Probe 28: "The proposal has three enthusiasm indicators — strip them out for a
  formal register" → rule: "Never use exclamation marks in professional writing."
  → ranked **#16**.
  Root cause: "enthusiasm indicators" is indirect domain jargon for exclamation
  marks; the embedding model has no basis for this mapping.  This is a genuinely
  hard case — even humans may not make the connection without domain context.

**Implication:** Failures cluster in cases where (a) intra-category rules are
very similar, making rank-1 difficult even with correct semantic retrieval, or
(b) the probe uses opaque domain jargon that the general-purpose model cannot
resolve.  Both are expected weaknesses of a non-fine-tuned 84MB model.

---

## Structural analysis: why BM25 fails here

BM25 computes a weighted term-frequency score over a query–document vocabulary
intersection.  When the query and document share **zero terms**, every document
receives a score of zero.  Scores are normalized to [0, 1] by dividing by the
max; when all scores are zero the normalization collapses and ranking is
undefined (implementation: returns uniform 0.0 → arbitrary ranking).

This is not a tunable failure.  No value of k1, b, or IDF weighting fixes it.
Cross-language retrieval requires a representation that generalizes beyond the
observed vocabulary.  BM25 is not that representation.

The GRA-1292 benchmark didn't expose this because its probes were written in
the same register as the rules (e.g., "Replace the .format() string interpolation
with an f-string" → rule "Use f-strings for string interpolation, not .format() or
%.").  Real user drafts frequently paraphrase rather than echo rule vocabulary.

---

## Decision

### Verdict: AUGMENT → embedding as primary scorer, BM25 as no-dep fallback

The cross-language evidence is decisive.  BM25 is structurally broken on
zero-overlap probes; embedding works.  The recommendation is to **promote
embedding to the primary scorer** and retain BM25 only as the fallback for
deployments where `sentence_transformers` is not installed.

This upgrades the GRA-1292 recommendation ("add embedding as optional tier") to
a stronger position: embedding should be the *default when the library is present*,
not merely an opt-in.

**Rationale:**

1. **The cross-language gap is 22×.** P@1 0.714 vs 0.036 on zero-overlap probes.
   This is not a marginal improvement — it is the difference between the scorer
   being functional and being random.

2. **Real drafts are frequently cross-language.** Users write "rename myVar to
   my_var" not "use snake_case naming convention"; they write "the JWT is printed
   to stdout" not "log API tokens".  The cross-language probe set represents the
   tail that BM25 fails on silently.

3. **GRA-1292 showed embedding also leads BM25 on same-language probes** (+5 pp
   P@1, +12.5 pp P@3).  So promoting embedding doesn't trade off same-language
   performance.

4. **Latency is acceptable.** 14.4ms avg vs 0.08ms for BM25 on a 30-rule corpus.
   In production (expected 100–500 rules), embedding latency will scale to
   ~20–50ms per call — still within the hook timeout of 5000ms and negligible
   relative to the LLM round-trip.  The model loads once per session and caches
   corpus embeddings; only the query encoding runs per prompt.

5. **The fallback chain remains safe.** If `sentence_transformers` is not
   installed: fall back to BM25.  If `bm25s` is not installed: fall back to
   Jaccard.  Zero-required-deps guarantee is preserved.

### Scope of change in jit_inject.py

```python
# Current:
#   try BM25 (bm25s library) → fallback Jaccard
# Proposed:
#   try Embedding (sentence_transformers) → try BM25 (bm25s) → fallback Jaccard

GRADATA_JIT_SCORER=embedding   # new default when library available
GRADATA_JIT_SCORER=bm25        # explicit BM25 selection (old default)
GRADATA_JIT_SCORER=jaccard     # explicit Jaccard
```

The env var dispatcher reads the scorer preference at module load and caches the
corpus embeddings on first call.  No API changes to `rank_rules_for_draft()`.

### What we are NOT recommending

- **Replace BM25 as the fallback.** BM25 remains the correct no-dep scorer.
- **Remove Jaccard.** Jaccard remains the zero-dep fallback.
- **Fine-tune the model.** At the current corpus size (4 real + 50 synthetic
  rules), fine-tuning is not justified.  Re-evaluate when real corpus ≥ 500 rules.

---

## Implementation checklist

Derived from GRA-1292 checklist, updated with this finding:

- [ ] Add `sentence_transformers` to optional dependencies (`pyproject.toml`)
- [ ] Add `_embedding_scores_for_draft()` to `jit_inject.py`
- [ ] Add env-var dispatcher: `embedding → bm25 → jaccard`
- [ ] **Change default when library available to `embedding`** (new vs GRA-1292)
- [ ] Lazy-load model + cache corpus embeddings on first call (avoid re-encoding)
- [ ] Unit tests: embedding code path + fallback chain
- [ ] Update README: document `GRADATA_JIT_SCORER` env var and auto-download

---

## Caveats

1. **Corpus size.** 30 rules is small.  At 500+ rules, intra-category confusion
   increases and embedding rank-1 precision will decline somewhat.  Re-run
   `bench/cross_language_scoring.py` with a larger real corpus when available.

2. **TONE and PYTHON weaknesses are real.** P@1=0.33 for these categories means
   1 in 3 cross-language tone/Python probes ranks the wrong rule first.  Operators
   who are heavy users of TONE or PYTHON rules should be aware of this.  Fine-
   tuning on domain-specific data would close the gap.

3. **Probe construction bias.** Probes were written by the analyst knowing the
   target rule.  This may introduce bias toward probes that the analyst thought
   were "semantically obvious" to an embedding model.  A blind probe construction
   process would be more rigorous.

4. **Model version.** `all-MiniLM-L6-v2` (84MB) was chosen for CPU-fast inference.
   Larger models (`all-mpnet-base-v2`, 420MB) would likely improve TONE/PYTHON
   accuracy at higher latency.  Not evaluated here.

---

## Context: reading GRA-1292 and GRA-1299 together

| Dimension | GRA-1292 (general corpus) | GRA-1299 (cross-language corpus) |
|-----------|--------------------------|----------------------------------|
| Probe style | Same vocabulary as rules | Different vocabulary from rules |
| BM25 P@1 | 0.800 | 0.033 (≈ random) |
| Embedding P@1 | 0.850 | 0.733 |
| Delta | +0.050 | **+0.700** |
| Recommendation | Optional tier | **Primary scorer** |

GRA-1292 suggested embedding as an optional upgrade (+5 pp).  GRA-1299 reveals
that the improvement is non-uniform: on vocabulary-matched probes the delta is
modest; on cross-language probes the delta is catastrophic for BM25.  The
appropriate update is to make embedding the default, because the production
workload includes both probe types and embedding dominates on the harder case
while being roughly equal on the easy case.

---

**[analyst-wiki]** Filed `docs/research/embedding-vs-bm25-2026-05-21.md`.  
Harness: `bench/cross_language_scoring.py`.  
Decision: **AUGMENT → embedding as primary scorer with BM25 fallback**.  
Next: open implementation issue (GRA-13xx) for `jit_inject.py` changes.
