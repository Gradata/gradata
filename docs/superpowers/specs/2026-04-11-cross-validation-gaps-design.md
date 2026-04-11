# Cross-Validation Gap Features — Design Spec

**Date:** 2026-04-11
**Goal:** Build the 6 features that 200 blind experts converged on but Gradata doesn't have yet.
**Source:** S103 cross-validation matrix (GAPS section)

---

## Gap 1: LLM-Powered Batch Synthesis

**Problem:** Meta-rules currently use keyword clustering to group 3+ related graduated rules. This produces shallow groupings that miss semantic relationships.

**Solution:** Add `llm_synthesize_rules()` that sends recent graduated lessons to the LLM provider and gets back synthesized high-level directives. Called during session_close consolidation alongside tree climb evaluation.

**Files:**
- Modify: `src/gradata/enhancements/meta_rules.py` — add `llm_synthesize_rules()`
- Use: `src/gradata/enhancements/llm_synthesizer.py` (existing LLM call infrastructure)
- Test: `tests/test_llm_synthesis.py`

**Interface:**
```python
def llm_synthesize_rules(
    lessons: list[Lesson],
    provider: str = "anthropic",
    max_rules_per_synthesis: int = 10,
) -> list[dict]:
    """Synthesize graduated lessons into high-level directives via LLM.
    
    Returns list of {"directive": str, "source_lessons": list[str], "confidence": float}
    """
```

**Constraints:**
- LLM call is optional — falls back to keyword clustering if no API key
- Max 10 lessons per synthesis call (context budget)
- Cache synthesis results — don't re-synthesize if lessons haven't changed
- Use existing `llm_synthesizer.py` patterns for the API call

---

## Gap 2: Knowledge Graph for Rule Relationships

**Problem:** Rules exist in isolation. No way to query "what rules support this one?" or "what rules contradict this one?" `rule_graph.py` exists but only tracks basic conflicts.

**Solution:** Extend `RuleGraph` with typed relationships: REINFORCES, CONTRADICTS, SPECIALIZES, GENERALIZES. Auto-detect relationships when rules graduate. Store in SQLite.

**Files:**
- Modify: `src/gradata/rules/rule_graph.py` — add relationship types and detection
- Modify: `src/gradata/_migrations.py` — add `rule_relationships` table
- Test: `tests/test_rule_graph_relationships.py`

**Interface:**
```python
class RuleRelationType(Enum):
    REINFORCES = "reinforces"      # Both push same direction
    CONTRADICTS = "contradicts"    # Push opposite directions
    SPECIALIZES = "specializes"    # More specific version of another rule
    GENERALIZES = "generalizes"    # Broader version of another rule

def detect_relationship(rule_a: Lesson, rule_b: Lesson) -> RuleRelationType | None:
    """Detect the relationship between two rules based on category, scope, and description."""

def get_related_rules(rule_id: str, rel_type: RuleRelationType | None = None) -> list[dict]:
    """Query rules related to a given rule, optionally filtered by relationship type."""
```

**Relationship detection heuristics:**
- REINFORCES: same category, same scope direction, different wording
- CONTRADICTS: same category, opposite polarity (reuse contradiction_detector.py patterns)
- SPECIALIZES: same category, child scope of the other rule's scope (tree path is a prefix)
- GENERALIZES: same category, parent scope (tree path is a suffix)

**Storage:**
```sql
CREATE TABLE IF NOT EXISTS rule_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_a_id TEXT NOT NULL,
    rule_b_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    detected_at TEXT NOT NULL
);
```

---

## Gap 3: Privacy Threat Model + Differential Privacy

**Problem:** The correction log is a psycho-linguistic profile (Prof. Monika Novak, 4 likes). No formal threat model. No DP on shared rules.

**Solution:** 
1. Privacy threat model document (not code — a markdown file in security/)
2. Laplace noise on aggregated statistics before cloud export
3. Minimum k-anonymity threshold for marketplace rules

**Files:**
- Create: `src/gradata/security/privacy_model.py` — DP noise functions
- Create: `src/gradata/security/THREAT_MODEL.md` — formal threat model document
- Modify: `src/gradata/_export_brain.py` — apply DP before export
- Test: `tests/test_privacy_model.py`

**Interface:**
```python
def add_laplace_noise(value: float, sensitivity: float = 1.0, epsilon: float = 1.0) -> float:
    """Add calibrated Laplace noise to a value for differential privacy."""

def sanitize_for_sharing(lesson: Lesson, epsilon: float = 1.0) -> dict:
    """Prepare a lesson for cloud sharing with DP noise on statistics.
    
    Noise applied to: fire_count, misfire_count, sessions_since_fire.
    NOT applied to: description (text), category, confidence (needed for ranking).
    Strips: example_draft, example_corrected (PII risk), correction_event_ids.
    """

MIN_K_ANONYMITY = 5  # Rule must exist in 5+ brains before marketplace listing
```

**Threat model covers:**
- Profile inversion attack (correction log → user cognitive model)
- Correction poisoning (adversarial corrections)
- Side-channel inference from rule statistics
- Re-identification from shared rules
- Mitigation: DP noise, k-anonymity, transfer_scope gating, PII stripping

---

## Gap 4: Contrastive Embeddings for Corrections

**Problem:** Correction similarity uses edit distance, which misses semantic changes ("allow"→"deny" is 2 chars but catastrophic semantically).

**Solution:** Compute embeddings for draft and final text of each correction. Store the cosine distance as `semantic_delta`. Use semantic_delta alongside edit distance for severity classification.

**Files:**
- Modify: `src/gradata/correction_detector.py` — compute embeddings on correction
- Modify: `src/gradata/_embed.py` — add `embed_pair()` function
- Test: `tests/test_contrastive_embeddings.py`

**Interface:**
```python
def embed_pair(draft: str, final: str) -> dict:
    """Compute embeddings for a correction pair and return semantic delta.
    
    Returns: {
        "draft_embedding": list[float] | None,
        "final_embedding": list[float] | None,
        "cosine_distance": float,  # 0.0 = identical, 1.0 = completely different
        "semantic_delta": float,   # normalized severity from embedding distance
    }
    
    Falls back gracefully: if no embedding model available, returns None fields
    and cosine_distance=0.0 (neutral — doesn't affect scoring).
    """
```

**Constraints:**
- Embedding is optional — must work without an embedding model installed
- Use existing `_embed.py` infrastructure (nomic-embed-text on Ollama)
- Don't block correction processing on embedding computation — compute async if possible
- Store embeddings in events table `data_json` field (no schema change)

---

## Gap 5: Constitutional Format for Rules

**Problem:** Rules are injected as imperative commands ("Be concise"). Constitutional AI research suggests framing as values ("You are an AI that values conciseness") may be more effective for model alignment.

**Solution:** Add a `constitutional` format option to rule injection. User configures preference. Both formats available.

**Files:**
- Modify: `src/gradata/rules/rule_engine.py` — add constitutional format
- Test: `tests/test_constitutional_format.py`

**Interface:**
```python
def format_rules_for_prompt(
    rules: list[AppliedRule],
    *,
    format_style: str = "imperative",  # "imperative" | "constitutional"
    max_tokens: int | None = None,
) -> str:
    """Format rules for prompt injection.
    
    imperative: "<rule>TONE: Be concise and direct</rule>"
    constitutional: "<principle>You are an AI that values conciseness and directness in communication</principle>"
    """
```

**Constitutional transformation:**
- "Be concise" → "You value conciseness — express ideas in the fewest words that preserve meaning"
- "Always cite sources" → "You value accuracy — you ground claims in verifiable sources"
- "No em dashes" → "You follow the user's punctuation preferences — avoid em dashes in prose"

The transformation is a simple template: `"You {value_verb} {principle} — {elaboration}"`. No LLM call needed for v1.

---

## Gap 6: User Credibility Scoring

**Problem:** All corrections are treated as ground truth. In multi-user deployments, inconsistent users (who contradict themselves frequently) should have less influence on rule confidence.

**Solution:** Track contradiction rate per correction source. Compute credibility score. Apply as a multiplier on confidence deltas.

**Files:**
- Modify: `src/gradata/enhancements/self_improvement.py` — credibility-weighted confidence
- Test: `tests/test_credibility_scoring.py`

**Interface:**
```python
def compute_credibility(
    total_corrections: int,
    self_contradictions: int,
    consistency_window: int = 20,
) -> float:
    """Compute user credibility score (0.0-1.0).
    
    1.0 = perfectly consistent (no self-contradictions)
    0.5 = moderate (25% self-contradiction rate)
    0.0 = completely inconsistent (all corrections contradict each other)
    
    Formula: 1.0 - (self_contradictions / total_corrections)
    Clamped to [0.1, 1.0] — even inconsistent users get 10% weight.
    """

# Applied in confidence math:
# delta = base_delta * credibility_score
```

**Constraints:**
- Only applies to multi-user brains (single-user credibility is always 1.0)
- Credibility is per-source, not per-rule
- Minimum credibility 0.1 — even bad corrections carry some signal
- Track in session_metrics table (existing), not a new table

---

## Success Criteria

1. LLM synthesis produces higher-quality meta-rules than keyword clustering (qualitative)
2. Rule graph detects REINFORCES/CONTRADICTS/SPECIALIZES/GENERALIZES relationships
3. Privacy model strips PII, adds Laplace noise, enforces k-anonymity threshold
4. Contrastive embeddings fall back gracefully when no model available
5. Constitutional format produces valid prompt text from any rule
6. Credibility score reduces confidence impact of self-contradicting users
7. All existing tests pass (1959+)
8. Each gap is independently testable and deployable
