# GRA-1294: Patch Acceptance — Do Agents Behave Differently After a Rule Rewrite?

**Status:** INSTRUMENTED — telemetry live, behavioral data pending  
**Date:** 2026-05-21  
**Author:** analyst (claude_local / sonnet-4-6)  
**Branch:** GRA-1291-prompt-injection-survey

---

## Problem Statement

`enhancements/self_healing.py` rewrites failing rules via `auto_heal_failures()`. The
patch pipeline gates each candidate through `retroactive_test`, which checks whether
the text added by the patch is semantically relevant to the correction that triggered
the failure. But passing the gate is not the same as changing behavior: a rule is only
effective if an agent *follows* it in subsequent sessions. This doc investigates whether
agents actually accept patched rules.

---

## Research Design

### Measurement framework (added this session)

`enhancements/self_improvement/_patches.py` provides three functions:

| Function | What it does |
|---|---|
| `observe_patch(brain, category, old, new)` | Emits `rule_patch_observed` event at patch time; counts RULE_FAILURE events for the old rule in the last 3 sessions (`observed_compliance_before`) |
| `resolve_patch_compliance(brain)` | Called 3+ sessions later; measures RULE_FAILURE count for the new rule text; emits resolved event with `observed_compliance_after_3_sessions` |
| `patch_acceptance_rate(brain)` | Computes % of resolved observations where compliance improved |

`brain.patch_rule()` now calls `observe_patch()` automatically after every patch.

### Acceptance definition

A patch is **accepted** if `observed_compliance_after_3_sessions < observed_compliance_before`.

- `observed_compliance_before` = count of `RULE_FAILURE` events for the *old* rule text in the 3 sessions before the patch
- `observed_compliance_after_3_sessions` = count of `RULE_FAILURE` events for the *new* rule text in the 3 sessions following the patch
- Lower failure count = better compliance

---

## Pre-Telemetry Analysis: N=29 Synthetic Patch Scenarios

Before behavioral data is available, we ran the deterministic patch pipeline against 29
synthetic (rule, correction) pairs. This tests the retroactive gate but not behavioral
compliance. Results establish the baseline the empirical phase will compare against.

### Standard scenarios (N=25) — realistic corrections

| # | Category | Original rule | Correction | Gate score | Pass |
|---|---|---|---|---|---|
| 1 | TONE | Never use exclamation marks | Removed exclamation marks from email draft | 0.600 | YES |
| 2 | TONE | Keep responses neutral and professional | Avoided emotional language in Slack reply | 0.600 | YES |
| 3 | FORMAT | Always include a summary section | Added missing summary to design doc | 0.671 | YES |
| 4 | FORMAT | Use bullet points for lists | Reformatted list from prose to bullets in report | 0.600 | YES |
| 5 | EMAIL | Add a clear next-step label in follow-ups | Added action items to follow-up email | 0.600 | YES |
| 6 | EMAIL | Keep subject lines under 60 characters | Shortened verbose subject line in campaign draft | 0.600 | YES |
| 7 | CODE | Add docstrings to all public functions | Added missing docstring to process_data function | 0.600 | YES |
| 8 | CODE | Use snake_case for Python variables | Renamed camelCase variable to snake_case | 0.775 | YES |
| 9 | SECURITY | Mask sensitive values before logging | Removed plaintext password from debug log | 0.600 | YES |
| 10 | SECURITY | Validate all user inputs at boundaries | Added input validation to API endpoint handler | 0.600 | YES |
| 11 | DRAFTING | Prefer precise command verbs | Replaced vague verb with specific action verb | 0.632 | YES |
| 12 | DRAFTING | Avoid passive voice in technical docs | Rewrote passive sentence to active voice | 0.600 | YES |
| 13 | SALES | Confirm assumptions before suggesting changes | Verified client budget before proposing solution | 0.600 | YES |
| 14 | SALES | Lead with customer value not product features | Rewritten pitch to focus on ROI not functionality | 0.600 | YES |
| 15 | CONCISENESS | Limit responses to 3 paragraphs maximum | Trimmed verbose 5-paragraph response to 3 | 0.671 | YES |
| 16 | TONE | Be concise and avoid jargon | Simplified technical acronyms for non-technical audience | 0.750 | YES |
| 17 | FORMAT | Start sections with a clear heading | Added missing heading to prerequisites section | 0.671 | YES |
| 18 | CODE | Handle exceptions explicitly | Added try/except for FileNotFoundError in importer | 0.671 | YES |
| 19 | SECURITY | Rotate credentials regularly | Flagged hardcoded API key for rotation | 0.600 | YES |
| 20 | DRAFTING | Use Oxford comma in lists | Added Oxford comma to enumeration in announcement | 0.600 | YES |
| 21 | TONE | Keep responses neutral | Avoided sycophantic opener in proposal | 0.671 | YES |
| 22 | EMAIL | Follow up within 24 hours | Sent delayed reply; missed 24-hour window | 0.600 | YES |
| 23 | CODE | Write tests for all new functions | Added unit test for validate_config function | 0.577 | YES |
| 24 | FORMAT | Use consistent date format ISO 8601 | Standardized date strings to YYYY-MM-DD | 0.671 | YES |
| 25 | SALES | Ask discovery questions before pitching | Paused pitch to ask about customer pain points | 0.600 | YES |

**Gate pass rate: 25/25 (100%)**

### Edge / degenerate cases (N=4) — retroactive gate should reject

| # | Category | Original rule | Correction | Score | Pass | Reason |
|---|---|---|---|---|---|---|
| 26 | TONE | Keep it professional | Be more and in the of to for from with | 0.000 | NO | Delta irrelevant — only stopwords in correction |
| 27 | FORMAT | Use bullet points for all lists always | use bullet points always for lists | 0.000 | NO | Patch identical to original — no new words |
| 28 | CODE | Write docstrings | write docstrings | 0.000 | NO | Patch identical to original |
| 29 | EMAIL | Follow up promptly | follow up promptly | 0.000 | NO | Patch identical to original |

**Gate pass rate: 0/4 (0%)**

---

## Key Findings from Synthetic Analysis

### 1. The retroactive gate clears nearly all realistic patches

For typical corrections (those containing informative nouns and verbs beyond the
rule text), the deterministic patch heuristic appends a qualifying clause that always
passes the 0.20 delta-score threshold. Gate scores cluster at 0.600 for standard cases
and reach 0.775 for high-overlap cases.

**Implication:** The gate is a useful filter for degenerate patches (identical or stopword-only
corrections) but does NOT discriminate among the realistic cases. A second-stage behavioral
filter is needed — which is exactly what `_patches.py` provides.

### 2. The patch heuristic produces syntactically correct but semantically shallow rewrites

The `_generate_deterministic_patch` template always produces:

```
<original_rule> (especially in context: word1 word2 word3)
```

The appended clause is the top-3 new words from the correction, extracted without stemming
or ranking beyond set difference. This makes the patches legible but formulaic. An agent
seeing this rule receives marginally more specific guidance — the question is whether that
marginal specificity changes behavior.

### 3. Expected behavioral acceptance rate: ~50–70% (hypothesis)

Based on the patch structure:

- **Cases where behavior changes (expected accepted):** When the qualifying clause adds a domain
  or medium the agent was previously applying the rule too broadly. Example: adding "email" to a
  TONE rule means the rule no longer fires on Slack messages where it didn't apply. Clearer scope
  → fewer false positives → fewer RULE_FAILUREs.

- **Cases where behavior does NOT change (expected rejected):** When the clause adds
  context words the agent's rule injection already handles via category matching. The new
  rule text appears in the injected prompt at approximately the same semantic position as
  the original; the model's in-context interpretation does not materially change.

The hypothesis is that ~60% of patches produce measurable RULE_FAILURE reduction.
This is the null hypothesis for the empirical phase.

---

## Empirical Measurement Plan

The telemetry is now live. Behavioral data will accumulate as follows:

1. **Session 0 (now):** `observe_patch()` is called for every future `brain.patch_rule()` invocation.
   `rule_patch_observed` events appear in `events.jsonl` with `observed_compliance_before` filled and
   `observed_compliance_after_3_sessions: null`.

2. **Session 3+:** `resolve_patch_compliance()` fills in the after count. Call it from the
   `auto_heal()` loop or from a scheduled CLI job.

3. **Dashboard:** `cloud/dashboard/src/components/brain/SelfHealing.tsx` renders the acceptance rate
   once resolved events exist.

### Triggering conditions

Patches fire when `auto_heal_failures()` is called and RULE_FAILURE events are present. To
accelerate observation accumulation:

```bash
# Manually trigger auto_heal on a brain with rule failures
gradata auto-heal --brain <path>

# Or from Python
from gradata.brain import Brain
b = Brain.open("<path>")
b.auto_heal()
```

### Query for current observations

```bash
gradata events --type rule_patch_observed --limit 100
```

Expected event schema:
```json
{
  "type": "rule_patch_observed",
  "source": "_patches.observe_patch",
  "data": {
    "category": "TONE",
    "old_rule_text": "Never use exclamation marks",
    "new_rule_text": "Never use exclamation marks (especially in context: email removed draft)",
    "applied_at": "2026-05-21T12:00:00+00:00",
    "observed_compliance_before": 3,
    "observed_compliance_after_3_sessions": null
  },
  "tags": ["category:TONE", "self_healing", "patch_telemetry"]
}
```

---

## Caveats and Limitations

1. **Session granularity vs. wall time.** A "session" in Gradata is one agent invocation. A brain
   used infrequently might not accumulate 3 sessions for weeks. The `resolve_patch_compliance`
   3-session window needs to be tunable per deployment.

2. **Zero-failure baselines.** If `compliance_before = 0` (rare — means the RULE_FAILURE that
   triggered the patch was from an earlier sweep not in the 3-session lookback), the patch cannot
   "improve" by this metric. These cases should be flagged as `baseline_unavailable`, not rejected.

3. **Confounders.** Compliance may improve for reasons unrelated to the patch (the category's
   correction rate naturally declined, or the user changed behavior). A control group (rules that
   were NOT patched) would give a cleaner signal. This is a v2 addition.

4. **Deterministic patch quality ceiling.** The `_generate_deterministic_patch` heuristic has a
   design ceiling: LLM-generated patches (Phase 2 in the self_healing roadmap) may show
   substantially higher acceptance rates. The telemetry framework is designed to handle both.

---

## Next Steps

| Action | Owner | Timeline |
|---|---|---|
| Accumulate 20+ resolved observations | auto (live telemetry) | 2–4 weeks of production sessions |
| Call `resolve_patch_compliance()` from `auto_heal()` loop | engineer | next sprint |
| File GRA-1295: LLM-assisted patch generation (Phase 2) | analyst | after first acceptance rate data |
| Update this doc with empirical acceptance rate | analyst | when N_resolved >= 20 |
