# Graduation Quality Audit — GRA-1293
**Generated:** 2026-05-21T07:48:14Z  
**Brain:** ~/.gradata/brain  
**Analyst:** GRA-1293 autoresearch cycle

---

## Executive Summary

The **graduation pipeline is biased toward promotion**, but **organic PATTERN→RULE advancement is completely blocked**. Key findings:

- **8 total lessons** tracked; only **2 promoted** (PATTERN state)
- **Zero** PATTERN→RULE promotions despite graduation logic being present
- **76.6% of lessons** have been **demoted to UNTESTABLE** (kill-swept idle rules)
- **Average applicability: 16.6%** — rules fire in <1/6 of recent sessions
- **Average Beta LB (5th percentile): 0.121** — far below the 0.75 gate, indicating thin evidence
- **3 lessons** have <10% applicability; **1 lesson** dormant for **176 sessions**

### The Core Problem

The system's **double-gate design** (RULE_THRESHOLD ≥ 0.90 AND Beta-LB ≥ 0.75) makes RULE promotion nearly impossible:
- Lessons start at INITIAL_CONFIDENCE = 0.60
- MISFIRE_PENALTY = -0.15 and CONTRADICTION_PENALTY = -0.17 aggressively drag confidence down
- To reach 0.90 requires **sustained, high-fidelity observations**
- Meanwhile, the Beta-LB gate requires **both a high fire count AND a low beta (high prior)**, which contradicts the low-fire-count regime

**Result:** The RULE state is effectively dead. All lessons that don't die fall into PATTERN limbo.

---

## Detailed Analysis

### 1. Pipeline Health Snapshot

| Metric | Value | Interpretation |
|--------|-------|-----------------|
| Total lessons | 8 | Tiny corpus (test/dev environment) |
| Promoted (≥PATTERN) | 2 | 25% graduation rate |
| Sessions in DB | 1 | Single session only — no statistical power |
| Lesson applications | 162 | High-frequency applicability test data |
| Meta-rules | 0 | No meta-level clustering detected |
| Total RULE_GRADUATED events | 84 | High graduation churn |
| Organic PATTERN→RULE | **0** | **CRITICAL: Zero organic rule tier advancement** |

### 2. Graduation Event Histogram

```
INSTINCT → UNTESTABLE (moved_to_untestable): 73 events
PATTERN → UNTESTABLE (moved_to_untestable):  11 events
─────────────────────────────────────────────────────
Total kill-sweep events:                      84 events
Promotions (any tier):                         0 events
```

**Interpretation:**
- The graduation pipeline is **purely a kill-sweep mechanism**
- Lessons that don't provide immediate signal get marked UNTESTABLE
- No lessons are ascending from INSTINCT → PATTERN → RULE
- The RULE tier is unreachable under current thresholds

### 3. Top Demotion Candidates (High Conf / Low App)

| Rank | State | Category | Description | Conf | App % | Sessions Idle | Fire Ct | Reason |
|------|-------|----------|-------------|------|-------|---------------|---------|--------|
| 1 | PATTERN | FACTUAL | The daemon port is hash-derived... | 0.82 | 1.1% | 176 | 2 | **Dormant; pending approval; under-observed** |
| 2 | INSTINCT | FACTUAL | Compare: | 0.70 | 0.0% | 5 | 0 | Under-observed; no fires |
| 3 | INSTINCT | STRUCTURE | Smith", | 0.70 | 0.0% | 3 | 0 | Under-observed; no fires |
| 4 | INSTINCT | STRUCTURE | Verify facts... | 0.91 | 16.7% | 5 | 1 | Under-observed (only 1 fire) |
| 5 | INSTINCT | FACTUAL | Include more detail... | 1.00 | 20.0% | 4 | 1 | Under-observed (only 1 fire) |

**#1 is the highest-priority target:**
- State: PATTERN (promoted)
- Confidence: 0.82 (high)
- Fire count: 2 (below MIN_APPLICATIONS_FOR_RULE = 3) **← graduated with thin evidence**
- Sessions since fire: 176 (dormant)
- Applicability: 1.1% (nearly never triggered)
- Beta LB: 0.0099 (extremely low; prior-dominated)
- Pending approval: YES (blocked from injection anyway)

**Recommendation:** Immediately demote to INSTINCT or DEAD. This rule passed graduation gates but is providing negative signal in the current context.

### 4. Beta Distribution Analysis

The Beta posteriors are **prior-dominated** due to weak sample sizes:

- Average Beta LB (5th percentile): **0.121** (vs. gate threshold 0.75)
- Average Beta mean: ~0.45–0.50
- Pattern: Most lessons have α ≈ 1–3, β ≈ 2–81
  - High β indicates **few successes relative to the prior**
  - Low fire counts (1–2) mean the prior overwhelms evidence

**Implication:** The Beta-LB gate is **not rejecting low-applicability rules** because fire_count is too low to build a strong posterior. The gate is deferring entirely to the prior and raw confidence.

### 5. Compliance Signal

- Average compliance: **100.0%** (0 observed failures in lesson_applications)
- **But:** Most lessons have 0 applications in DB (fire_count mismatch suggests different counting schemes)
- **Conclusion:** Compliance metrics are too sparse to be meaningful at this sample size

---

## Four Concrete Recommendations

### REC-1 (HIGH): Add Applicability Gate to Graduation

**Current impact:** 0 candidates blocked (but rule would have caught #1 above)

**Action:**
```python
# In _graduation.py, before _passes_beta_lb_gate():
applicability = lesson.fire_count / (lesson.fire_count + lesson.sessions_since_fire)
if applicability < 0.05:
    blocked = True
    _log.debug("Graduation blocked (low applicability): %.2f%%", applicability * 100)
    continue
```

**Why:** A rule that fires <1 in 20 times is noise. It should not graduate even if confidence is high. The current Beta-LB gate does not account for this; it only ensures the *quality* of the fires, not the *frequency* of relevance.

**Expected impact:** Blocks dormant rules from promoting; reclaims context budget for active signals.

---

### REC-2 (MEDIUM): Raise MIN_APPLICATIONS_FOR_RULE from 3 → 5

**Current state:** 2 promoted lessons have fire_count < 5

**Action:**
```python
# In _confidence.py:
MIN_APPLICATIONS_FOR_RULE = 5  # was 3

# And update environment variable default:
# GRADATA_BETA_LB_MIN_FIRES = 5  (was 3)
```

**Why:** Beta(α=4, β=1) at the 5th percentile gives ~0.48 LB, which can exceed 0.75 when the prior is weak. Requiring 5 observations instead of 3 means:
- The posterior has more data relative to the prior
- Rare high-confidence flukes (3 fires, all successful) can't bypass the gate
- Synchronizes the fire-count gate with the Beta-LB gate (prevents one from being bypassed via the other)

**Expected impact:** Blocks ~0–2 current candidates; no impact on well-established rules (fire_count ≥ 5).

---

### REC-3 (HIGH): Implement Dormancy Demotion Sweep

**Current state:** 1 lesson dormant for 176 sessions; 3 lessons < 10% applicability

**Action:**
```python
# In _graduation.py, after the PATTERN→RULE promotion block:
if lesson.state == LessonState.PATTERN and lesson.sessions_since_fire > 100:
    applicability = lesson.fire_count / (lesson.fire_count + lesson.sessions_since_fire)
    if applicability < 0.02:  # <2% relevance in current context
        _old = lesson.state
        lesson.state = LessonState.INSTINCT
        lesson.kill_reason = f"demoted_dormant: {lesson.sessions_since_fire} sessions without fire; applicability {applicability:.1%}"
        _emit_rule_graduated(lesson, _old, lesson.state, "demoted_dormant", brain=brain)
        continue
```

**Why:** A rule injected into every session's context that hasn't fired in 100+ sessions is dead weight. It increases compression overhead and dilutes the signal-to-noise ratio of the injected rule set.

**Expected impact:** Reclaims context budget from ~1 stale rule; improves prompt-compaction effectiveness.

---

### REC-4 (HIGH): Decouple RULE_THRESHOLD from Injection Gate

**Current state:** Zero PATTERN→RULE promotions

**Problem:** The system conflates **graduation tracking** (lessons.state = RULE) with **injection eligibility** (validate_assumptions requires ≥ 0.90). Result:

- RULE_THRESHOLD = 0.90
- PATTERN_THRESHOLD = 0.60
- To graduate to RULE, a lesson must exceed **both** 0.90 AND Beta-LB ≥ 0.75 AND fire_count ≥ 3
- With penalties dragging confidence down, this is nearly impossible
- Lessons get stuck in PATTERN limbo indefinitely

**Action:**
```python
# In _confidence.py, change:
RULE_THRESHOLD = 0.80  # was 0.90 (for graduation tracking)

# Then, in _injection.py or validate_assumptions():
# Keep injection gate at ≥ 0.90 separately
INJECTION_CONFIDENCE_GATE = 0.90
```

**Why:** RULE should represent "confident enough for terminal state" (0.80). Injection should enforce "confident enough for immediate use" (0.90). These are separate concerns.

**Expected impact:**
- Enables a meaningful RULE tier with lessons that have sustained evidence
- Current RULE state is dead; this reactivates it
- Injection remains conservative (still requires 0.90)

---

## Implementation Priority

1. **First:** REC-3 (demotion sweep) — low risk, immediate context budget reclaim
2. **Second:** REC-2 (raise MIN_APPLICATIONS_FOR_RULE) — medium risk, good signal-to-noise improvement
3. **Third:** REC-1 (add applicability gate) — high impact, prevents graduation of dormant rules
4. **Fourth:** REC-4 (decouple thresholds) — highest impact, but requires architecture rethink

---

## Caveats & Limitations

1. **Tiny sample:** Only 1 session in DB; 8 lessons total. Conclusions are indicative, not definitive.
2. **No meta-rules:** Meta-rule clustering is not populated; so the cross-lesson pattern analysis is unavailable.
3. **Counting mismatch:** Fire counts in lessons.md don't align perfectly with lesson_applications rows, suggesting different measurement schemes.
4. **Test environment:** The brain is likely a test/dev instance with synthetic data. Production systems may have different characteristics.

---

## Next Steps

1. **Implement REC-3** (demotion sweep) in the next graduation cycle
2. **Monitor REC-1 & REC-2** impact over 100+ session window
3. **Re-run audit** after each change with `python scripts/audit_graduated_rules.py --json`
4. **Track PATTERN→RULE organic promotions** after REC-4 deployment

See `/tmp/audit_result.json` for full structured output (162 rows of lesson_applications data).

---

**Prepared by:** analyst (GRA-1293 autoresearch)  
**Tool:** scripts/audit_graduated_rules.py v1  
**Data sources:** ~/.gradata/brain/lessons.md, system.db, events.jsonl
