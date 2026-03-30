# Gradata Learning Engine — Prioritized Fix Plan

**Date:** 2026-03-27 | **Source:** AUDIT-REPORT.md (S75)
**Workflow:** Plan → Adversary Review → Implement → Test

---

## Priority 1: Ship Blockers (Must fix before any public release)

### P1.1 — Port Graduation Logic to Open-Source SDK
**Track:** 2 (Graduation Logic)
**Files to create:**
- `sdk/src/gradata/enhancements/self_improvement.py`
- `sdk/src/gradata/enhancements/edit_classifier.py`
- `sdk/src/gradata/enhancements/pattern_extractor.py`

**Approach:**
- Extract core logic from `gradata_cloud_backup/graduation/` into open-source versions
- Keep advanced features (agent graduation, gate graduation, upward distillation) cloud-only
- Open-source gets: parse_lessons, update_confidence, graduate, format_lessons, compute_learning_velocity
- Open-source gets: classify_edits (keyword + regex based), summarize_edits
- Open-source gets: extract_patterns (diff-based), merge_patterns, patterns_to_lessons

**Test plan:**
- Unit tests for each function
- Integration test: synthetic correction → lesson creation → confidence update → graduation
- Regression: existing 450 SDK tests must still pass

**Adversary questions:**
- Does open-sourcing basic graduation expose competitive moat? → No, moat is data + marketplace
- Can a competitor clone graduation logic? → Yes, but without correction data it's useless
- Does this break cloud sync? → No, cloud overrides local via shim priority

### P1.2 — Fix Data Integrity Anomalies
**Track:** 1 (Data Integrity)
**Action:** Fix 3 anomalous session_metrics records

| Session | Current | Fix |
|---------|---------|-----|
| S35 | density=0.0, outputs=0, corrections=2 | Recompute: density=None (no outputs to divide by) |
| S36 | density=0.8, outputs=0, corrections=0 | Delete row or set density=None |
| S69 | density=0.0, outputs=70, corrections=5 | Recompute: density=0.071 |

**Also fix:**
- S64, S67, S68: compute density from events table (corrections/outputs)
- Backfill severity for all 60 corrections (run edit_distance retroactively where draft/final text exists)

### P1.3 — Remove Hardcoded Paths from SDK
**Track:** 12 (Security)
**File:** `sdk/src/gradata/enhancements/rule_canary.py` (lines 56, 64, 197, 239)
**Fix:** Replace all `Path("C:/Users/olive/SpritesWork/brain/...")` with:
```python
def _resolve_db_path(ctx=None):
    if ctx and ctx.db_path:
        return ctx.db_path
    env = os.environ.get("BRAIN_DIR")
    if env:
        return Path(env) / "system.db"
    return None
```

### P1.4 — Add Input Validation to brain.correct()
**Track:** 3 (MCP Tool Binding)
**File:** `sdk/src/gradata/brain.py`
**Validations to add:**
1. Reject if `draft == final` (no-op correction)
2. Reject if `draft` or `final` is empty string
3. Reject if `len(draft) + len(final) > 100_000` (prevent abuse)
4. Validate session is int > 0 if provided
5. Rate limit: max 50 corrections per session

---

## Priority 2: High Impact (Fix before beta)

### P2.1 — Reduce API Surface
**Track:** 10 (SDK API Surface)
**File:** `sdk/src/gradata/__init__.py`
**Action:** Move pattern exports to `gradata.patterns` subpackage import
```python
# __init__.py exports only:
__all__ = ["Brain", "BrainContext", "Lesson", "LessonState", "__version__"]

# Users who want patterns:
# from gradata.patterns import Pipeline, Stage, ...
```

### P2.2 — Fix Correction Detection False Positives
**Track:** 9 (Correction Detection)
**File:** `sdk/src/gradata/correction_detector.py`
**Changes:**
- Lower confidence on "actually" pattern from 0.65 → 0.45
- Add context window: only flag "actually" if preceded by agent output in same turn
- Add negation context: "but however" only counts if followed by correction verb

### P2.3 — Implement Automated Decay Sweep
**Track:** 8 (Decay & Retirement)
**New function in `enhancements/self_improvement.py`:**
```python
def sweep_stale_lessons(lessons, current_session):
    """Kill lessons with sessions_since_fire > UNTESTABLE_SESSION_LIMIT."""
    for lesson in lessons:
        if lesson.sessions_since_fire > UNTESTABLE_SESSION_LIMIT:
            lesson.transition("kill")
    return lessons
```
- Call at wrap-up after confidence updates
- Session-type-aware: only count testable sessions

### P2.4 — Implement Meta-Rule Discovery
**Track:** 6 (Evolution Rules)
**File:** `sdk/src/gradata/enhancements/meta_rules.py`
**Add function:**
```python
def discover_meta_rules(lessons, min_cluster=3):
    """Find 3+ lessons in overlapping categories that share a principle."""
    # Group by category, find cross-category clusters
    # Use rule_conflicts.detect_rule_conflict() DERIVES relation
    # Create MetaRule with deterministic ID from source lesson IDs
```

### P2.5 — Add Missing Manifest Metrics
**Track:** 4 (Quality Metrics)
**File:** `sdk/src/gradata/brain.py` (manifest method)
**Add:**
- `compound_score`: weighted sum of correction_rate, FDA, lessons_graduated
- `categories_extinct`: categories with zero corrections in last 10 sessions
- `improvement_curve`: correction_rate trend over sliding 5-session windows

---

## Priority 3: Important (Fix before GA)

### P3.1 — Fix Git Status (Hook Files)
**Track:** 5 (Hook Verification)
**Action:** Stage all hook files that are deleted in git but present on disk
**Command:** `git add .claude/hooks/`
**Note:** Do this AFTER reviewing which hooks are actually needed

### P3.2 — Build CLB (Correction Learning Benchmark)
**Track:** 13 (Benchmark)
**New file:** `sdk/tests/test_clb.py`
**Design:**
```python
def test_clb_zero_to_rule():
    """Brain.init() → 10 corrections → verify graduation timeline."""
    brain = Brain.init(tmp_path / "clb-brain")
    for i in range(10):
        brain.correct(draft=f"draft {i}", final=f"final {i}", category="DRAFTING")
    # Assert lesson exists, confidence increased, graduation possible
```

### P3.3 — Remove Personal References from SDK Code
**Track:** 12 (Security)
**Files:**
- `meta_rules.py`: Remove "Oliver", "anna" from examples
- `rule_engine.py`: "sprites" in _TEAM_SIGNALS → keep as generic example but add comment
- `GATE0-PROOF.md`: Remove Oliver-specific paths

### P3.4 — Remove Deprecated ChromaDB
**Track:** 12 (Security)
**Action:** Delete `sdk/src/gradata/.vectorstore/` directory

### P3.5 — Fix behavior-triggers.js Temp Path
**Track:** 5 (Hook Verification)
**File:** `.claude/hooks/post-tool/behavior-triggers.js`
**Fix:** Use `os.tmpdir()` instead of hardcoded `/tmp/`

### P3.6 — Design Bonus Rule Pattern
**Track:** 6 (Evolution Rules)
**Design:**
- Agent discovers gap → emits `GAP_DISCOVERY` event
- Gap event creates INSTINCT lesson with confidence=0.15 (lower than human corrections at 0.30)
- Requires human confirmation (correction that matches gap) to reach 0.30
- Then follows normal graduation pipeline
- Source attribution: `source: "agent:gap_discovery"` vs `source: "human:correction"`

### P3.7 — Fix first_draft_acceptance Metric
**Track:** 4 (Quality Metrics)
**Investigation:** FDA=0.0 means either:
1. Every output was edited (unlikely for 1,056 outputs)
2. Metric computation is broken
**Action:** Trace FDA computation in `learning_dashboard.py` and `wrap_up.py`

---

## Priority 4: Nice to Have (Post-launch)

### P4.1 — Multi-Turn Correction Detection
**Track:** 9 — Link "no" on turn 1 with "I mean X" on turn 2

### P4.2 — Semantic Rule Verification
**Track:** 6 — LLM-based rule verification instead of regex-only

### P4.3 — Vector Search (sqlite-vec)
**Track:** 10 — Semantic ranking for brain.search()

### P4.4 — Profile Real Prompt Lengths
**Track:** 9 — Validate MAX_PROMPT_LENGTH=2000 is sufficient

### P4.5 — Environment Portability Testing
**Track:** 5 — Test hooks on macOS/Linux (not just Windows)

---

## Implementation Order

```
Week 1: P1.1 (graduation port) + P1.2 (data fixes) + P1.3 (hardcoded paths)
Week 2: P1.4 (validation) + P2.1 (API surface) + P2.5 (manifest metrics)
Week 3: P2.2 (false positives) + P2.3 (decay sweep) + P2.4 (meta-rule discovery)
Week 4: P3.* (all Priority 3 items)
Post-launch: P4.* (nice to have)
```

## Test Target
- Current: 973 tests (450 SDK + 523 cloud)
- After P1.1: +50 tests (graduation logic)
- After P1.4: +10 tests (validation)
- After P2.3: +10 tests (decay)
- After P2.4: +15 tests (meta-rules)
- After P3.2: +20 tests (CLB)
- **Target: 1,078+ tests, 0 failures**
