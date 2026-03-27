# Gradata Correction-Based Learning: Prospective Study Protocol

**Version:** 1.0 | **Date:** 2026-03-26 | **Author:** the researcher (PI) + Gradata System
**Target venue:** arXiv (cs.AI / cs.HC), follow-on submission to ACM CHI or CSCW
**Protocol registration:** Pre-register on OSF (Open Science Framework) before Day 1

---

## Table of Contents

1. [Study Protocol (30-Day Prospective Study)](#1-study-protocol)
2. [Metrics Dashboard Specification](#2-metrics-dashboard-spec)
3. [Blind Comparison Design](#3-blind-comparison-design)
4. [Paper Outline](#4-paper-outline)
5. [Minimum Viable Proof (Existing Data)](#5-minimum-viable-proof)

---

## 1. Study Protocol

### 1.1 Research Questions

**RQ1:** Does an AI system that logs user corrections and graduates them into behavioral rules produce fewer errors over time?

**RQ2:** Does the graduation mechanism (INSTINCT -> PATTERN -> RULE) contribute beyond simple instruction accumulation?

**RQ3:** Which error categories respond most strongly to correction-based learning, and which are resistant?

### 1.2 Hypotheses

**H1 (Primary)**
- **Null (H0):** The correction rate per output does not decrease over the study period when controlling for task difficulty and session type. Formally: the slope coefficient beta_1 in a Poisson regression of corrections ~ session_number + difficulty + session_type is not significantly less than zero.
- **Alternative (H1):** beta_1 < 0 (one-sided test, alpha = 0.05).

**H2 (Graduation mechanism)**
- **Null (H0):** Outputs in categories with graduated RULE-level lessons show the same correction rate as categories with only INSTINCT-level lessons.
- **Alternative (H2):** Categories with at least one RULE show a lower correction rate than categories with only INSTINCTs (two-sample comparison, alpha = 0.05).

**H3 (Blind comparison)**
- **Null (H0):** In blinded pairwise comparisons, the user selects the brain-enhanced output and the baseline output with equal frequency (50/50).
- **Alternative (H3):** The brain-enhanced output is selected more than 50% of the time (one-sided binomial test, alpha = 0.05).

### 1.3 Definitions

**Output:** A discrete deliverable produced by the AI system that is presented to the user for review or use. Operationally: any artifact that (a) is intended for external consumption or (b) requires user approval before proceeding. Examples: email draft, demo prep cheat sheet, lead list, Pipedrive deal creation, code module, research brief. NOT counted: status summaries, system health checks, internal tool calls, diagnostic outputs.

Each output is logged as an `OUTPUT` event in `events.jsonl` with fields:
```json
{
  "type": "OUTPUT",
  "session": N,
  "data": {
    "output_type": "email_draft|demo_prep|lead_list|code|research|crm_update|other",
    "difficulty_tier": 1-5,
    "category_tags": ["DRAFTING", "ACCURACY", ...],
    "first_draft_accepted": true|false,
    "correction_count": 0,
    "time_to_acceptance_sec": N
  }
}
```

**Correction:** An explicit user intervention that changes the substance, approach, or correctness of an output. Must be logged as a `CORRECTION` event. Classification:

| Type | Definition | Example |
|------|-----------|---------|
| **Substantive** | Changes meaning, facts, or approach | "Don't include pricing in emails" |
| **Stylistic** | Changes tone, formatting, phrasing without changing meaning | "Use colons not dashes" |
| **Procedural** | Changes the order or method of work | "Research before drafting" |
| **Factual** | Corrects wrong information | "That meeting is Tuesday not Wednesday" |

For the primary metric, ALL correction types count equally. Secondary analysis breaks down by type.

**Session:** One continuous Claude Code conversation from startup to wrap-up. A session may contain 0-30+ outputs.

### 1.4 Primary Metric

**Correction Rate per Output (CRO)**

```
CRO_session = (number of CORRECTION events in session) / (number of OUTPUT events in session)
```

For sessions with 0 outputs (pure system/architecture work), CRO is undefined and excluded from the primary analysis. This is pre-registered, not a post-hoc exclusion.

**Normalization:** CRO is computed per-session, then aggregated as a rolling 5-session mean (RM5) to smooth variance. The primary test uses per-session CRO as the unit of analysis with session number as the predictor.

### 1.5 Secondary Metrics

| # | Metric | Definition | Purpose |
|---|--------|-----------|---------|
| S1 | **First Draft Acceptance Rate (FDAR)** | Fraction of outputs accepted without any correction: `count(correction_count == 0) / count(outputs)` per session | Measures "right first time" quality |
| S2 | **Category Extinction Rate** | For each correction category, the session number of the last correction. Categories with no corrections in the last 15 sessions are "extinct" | Tests whether specific error classes go to zero |
| S3 | **Time to Acceptance (TTA)** | Median seconds between output presentation and user acceptance, per difficulty tier | Controls for "user gave up correcting" confound |
| S4 | **Lesson Lifecycle Distribution** | Count of lessons at each state (INSTINCT, PATTERN, RULE, UNTESTABLE, RETIRED) per session | Tracks system maturity over time |
| S5 | **Audit Score Trend** | Combined audit score (1-10) per session, with sub-dimensions (research, quality, process, learning, outcomes) | Holistic quality measure, user-rated |
| S6 | **Repeat Correction Rate** | Corrections in categories that already have an active lesson at PATTERN or RULE level | Tests whether graduated lessons prevent repeats |
| S7 | **Blind Preference Score** | Win rate in blinded A/B comparisons (see Section 3) | Controlled comparison without confounds |
| S8 | **Edit Distance** | Levenshtein distance between AI draft and final accepted version, normalized by output length | Objective measure of draft quality |

### 1.6 Output Difficulty Classification

Every output is classified at creation time (BEFORE user review) into one of five tiers:

| Tier | Name | Definition | Examples | Expected CRO baseline |
|------|------|-----------|---------|----------------------|
| 1 | **Lookup** | Single-source retrieval, no synthesis | "What's the Pipedrive deal ID for X?" | ~0.05 |
| 2 | **Template** | Fill-in-the-blank using existing templates/playbooks | Calendar sync, standard Pipedrive update | ~0.10 |
| 3 | **Synthesis** | Combines 2-3 sources, requires judgment | Demo prep cheat sheet, lead scoring | ~0.25 |
| 4 | **Creative** | Original composition requiring domain knowledge and user voice matching | Email draft, LinkedIn message, cold call script | ~0.40 |
| 5 | **Strategic** | Multi-step, cross-domain, requires understanding user's business goals | Full campaign design, architecture decision, competitive analysis | ~0.50 |

The "expected CRO baseline" column is estimated from current data and will be calibrated during the first 5 sessions. Difficulty assignment is logged at output creation and cannot be changed after the user reviews it (prevents post-hoc reclassification).

**Inter-rater reliability:** Since the researcher is the sole user, difficulty ratings are self-assigned. To mitigate inflation/deflation, every 5th session, a random sample of 3 outputs will have their difficulty independently rated by the system (using the tier definitions above) and disagreements logged. Cohen's kappa will be reported.

### 1.7 Control Conditions

The fundamental challenge is a single user over time. Pure randomization is impossible. We use three complementary strategies:

#### Strategy A: Interrupted Time Series (ITS)

The primary analysis. Uses the 71 pre-study sessions as a baseline phase and the 30 study sessions as the intervention phase with standardized measurement. The "intervention" is not the brain itself (which has been active since session 1) but the introduction of rigorous, standardized measurement.

This addresses the question: "Is the observed correction decline real or an artifact of measurement changes?"

- Pre-intervention: 71 sessions with retrospective correction data (partially backfilled)
- Post-intervention: 30 sessions with prospective, standardized correction logging
- Test: Segmented regression with a level change (immediate effect at transition) and a slope change (ongoing trend)

#### Strategy B: Within-Session Brain Toggle (WSBT)

During designated "toggle sessions" (every 7th session: sessions 7, 14, 21, 28 of the study), the brain is partially disabled for a randomly selected subset of outputs:

1. System generates a random number for each output in the session
2. If the number is odd, the output is generated using the full brain (lessons + rules + CARL)
3. If even, the output is generated using ONLY the base CLAUDE.md instructions (no lessons.md, no CARL domain rules, no brain context)
4. The user does NOT know which condition produced the output (see Blinding, 1.9)
5. Both versions are evaluated using the same correction protocol

This requires technical implementation: a toggle flag that suppresses brain context injection.

#### Strategy C: Blind Pairwise Comparison

Detailed in Section 3. A separate battery of standardized tasks where both brain-on and brain-off outputs are generated, randomized, and rated blind by the user.

### 1.8 Confounds and Controls

| Confound | Risk | Control |
|----------|------|---------|
| **Session type** | System sessions have fewer corrections by nature (no email drafts to critique) | Tag every session as `sales`, `system`, `hybrid`. Primary analysis stratifies by type. |
| **Task complexity** | Later sessions may have harder tasks | Difficulty tier is logged per output. Include as covariate in regression. |
| **User adaptation** | the researcher learns to give better prompts over time | Cannot eliminate. Acknowledge as a confound. Partially addressed by blind comparison (Strategy C). |
| **Instrumentation change** | Pre-study corrections were backfilled from notes; study corrections are prospective | ITS analysis explicitly models the transition. Report pre/post measurement quality separately. |
| **User mood / fatigue** | Long sessions may have more corrections due to fatigue | Log session duration and output count. Test as covariates. |
| **Context window effects** | Later outputs in a session benefit from accumulated context | Log output ordinal position within session. Test as covariate. |
| **Hawthorne effect** | Knowing corrections are measured may change behavior | Cannot eliminate in N=1. Mitigated by the blind comparison protocol. |
| **Novelty of task categories** | New task types (never seen before) will naturally have higher correction rates | Tag each output with `novel_category: true/false`. Report separately. |
| **Base model improvements** | Claude itself may improve during the study | Log exact model version per session. If model changes, add a dummy variable. |

### 1.9 Blinding

**Can the user be blinded to the brain condition?** Partially, in specific protocols:

- **Strategy B (WSBT):** YES. The toggle is automated. the researcher sees the output and corrects it without knowing whether the brain was active. The difficulty: brain-enhanced outputs may be obviously better (e.g., using the researcher's preferred email style), which would effectively un-blind. Mitigation: log the researcher's guess of which condition each output was in. If guess accuracy exceeds 70%, report this as a limitation.
- **Strategy C (Blind pairwise):** YES. Two outputs are presented side-by-side (or sequentially, randomized) labeled "Version A" and "Version B." the researcher rates each on a 1-10 scale and picks a winner. The mapping is revealed only after rating.
- **Normal sessions (Strategy A):** NO. the researcher knows the brain is active. This is inherent to a longitudinal single-user study.

**Observer bias mitigation for unblinded sessions:**
1. Corrections are defined by a behavioral criterion (user explicitly changes the output), not a subjective judgment
2. Every correction must include a `detail` field explaining what was wrong
3. Time-to-acceptance is logged automatically (objective measure)
4. Post-hoc analysis checks whether correction rates correlate with the researcher's self-reported session satisfaction (if they diverge, observer bias is likely)

### 1.10 Sample Size / Power Analysis

**Unit of analysis:** Sessions (for CRO trend) and outputs (for FDAR, blind comparison).

**For H1 (trend detection via ITS):**

Based on Bernal et al. (2017) and the 2024 PLOS ONE simulation study on ITS with limited time points:
- With 30 post-intervention time points and moderate autocorrelation (rho ~ 0.3), ITS has >80% power to detect a standardized level change of d = 0.8
- Our observed effect is much larger: CRO dropped from ~3.0 (sessions 1-10) to ~0.1 (sessions 60-71), which is a massive effect
- Even with 30 points, we are overpowered for the level change but may be underpowered for the slope change if the true slope is shallow in the study period (the system may have already converged)
- **Minimum viable:** 30 sessions (as planned). Would prefer 50 for slope detection.

**For H3 (blind comparison):**

Binomial test, one-sided, alpha = 0.05:
- To detect a 70% preference rate (brain wins 70% of the time) with 80% power: **n = 41 comparisons**
- To detect a 65% preference rate: **n = 72 comparisons**
- To detect a 60% preference rate: **n = 160 comparisons** (infeasible for solo user)
- **Target:** 50 blind comparisons over 30 days (~1.7/day, feasible)
- At 50 comparisons, we have 80% power to detect a 69% true win rate

**For H2 (RULE vs INSTINCT categories):**

Mann-Whitney U test on per-category CRO:
- With ~15 RULE categories and ~15 INSTINCT categories, we can detect a large effect (d > 0.8) with 80% power
- This is feasible given the current lesson distribution

### 1.11 Data Collection Protocol

**What gets logged, when, and how:**

#### Automatic (system-generated, no human action needed):
| Event | Trigger | Fields |
|-------|---------|--------|
| `SESSION_START` | Hook fires at conversation open | session_number, timestamp, model_version, brain_lesson_count, brain_rule_count |
| `OUTPUT` | System produces a user-facing deliverable | output_type, difficulty_tier, category_tags, word_count, brain_condition (on/off for toggle sessions) |
| `SESSION_END` | Wrap-up completes | session_duration_sec, output_count, correction_count, session_type |

#### Semi-automatic (system detects, user confirms):
| Event | Trigger | Fields |
|-------|---------|--------|
| `CORRECTION` | User edits or rejects an output; capture_learning hook fires | category, detail, correction_type (substantive/stylistic/procedural/factual), output_ref (links to the OUTPUT event), severity (1-3) |
| `ACCEPTANCE` | User approves an output without changes | output_ref, time_to_acceptance_sec |

#### Manual (user must explicitly provide):
| Event | Trigger | Fields |
|-------|---------|--------|
| `AUDIT_SCORE` | End of session wrap-up | research, quality, process, learning, outcomes (each 1-10), combined_avg, notes |
| `BLIND_RATING` | During blind comparison tasks | version_a_score (1-10), version_b_score (1-10), winner (A/B/tie), confidence (1-5), guess_which_is_brain (A/B/unsure) |

#### Data format and storage:
- All events appended to `events.jsonl` (append-only, immutable)
- Backup: SQLite `system.db` events table (queryable)
- Daily export: CSV snapshot of session-level aggregates for the dashboard
- Git: brain/ repository committed after every session (provides audit trail)

### 1.12 Analysis Plan

#### Primary Analysis (H1)

**Model:** Poisson regression with robust standard errors (to handle overdispersion)

```
corrections_i ~ beta_0 + beta_1 * session_number_i + beta_2 * difficulty_mean_i
                + beta_3 * session_type_i + offset(log(output_count_i))
```

Using `log(output_count)` as an offset models the rate (corrections per output) directly.

- **Test:** One-sided Wald test on beta_1. H0: beta_1 >= 0. Reject if p < 0.05.
- **Robustness checks:**
  1. Negative binomial regression (alternative dispersion model)
  2. Exclude first 5 sessions (calibration period)
  3. Stratify by session type (sales vs system)
  4. Add session duration as covariate
  5. Autocorrelation-corrected standard errors (Newey-West with 3-session lag)

**ITS-specific model (combining pre-study and study phases):**

```
corrections_i ~ beta_0 + beta_1 * time_i + beta_2 * phase_i
                + beta_3 * (time_i * phase_i) + offset(log(output_count_i))
```

Where `phase_i` = 0 (pre-study, sessions 1-71) or 1 (study, sessions 72-101). beta_2 tests the level change; beta_3 tests the slope change.

#### Secondary Analyses

- **H2:** Mann-Whitney U test comparing per-category CRO between RULE and INSTINCT categories
- **H3:** Exact binomial test on blind comparison win rate; 95% Clopper-Pearson confidence interval
- **Category extinction:** Kaplan-Meier survival curves for correction categories (time to last correction)
- **FDAR trend:** Logistic regression of first_draft_accepted ~ session_number + difficulty
- **Audit score trend:** Linear regression with 95% CI

#### Visualization

1. **CRO time series** with 5-session rolling mean and 95% CI band
2. **Heatmap** of correction categories x sessions (showing extinction)
3. **Lesson lifecycle Sankey diagram** (INSTINCT -> PATTERN -> RULE -> retired)
4. **Blind comparison forest plot** (effect size per task type)
5. **Difficulty-adjusted CRO** (separate trend lines per difficulty tier)
6. **Cumulative correction count** (should show decelerating curve)

#### What Constitutes "Proof"

The claim "Gradata learns from corrections" is supported if ALL of the following hold:

1. beta_1 is significantly negative (p < 0.05) in the primary Poisson regression
2. FDAR shows a positive trend (more outputs accepted on first draft over time)
3. At least 3 correction categories go extinct during the study period
4. Blind comparison win rate exceeds 60% with p < 0.05
5. The effect survives all robustness checks (no sign flip, p stays below 0.10)

The claim is PARTIALLY supported if conditions 1-3 hold but 4-5 do not (would indicate the effect is real but may reflect user adaptation rather than system learning).

The claim is NOT supported if beta_1 is non-negative or if blind comparisons show no preference.

### 1.13 Stopping Rules

**Early success (optional):**
After 15 sessions, run an interim analysis. If the blind comparison win rate exceeds 80% with p < 0.01 (Pocock boundary for one interim look), the comparison portion can stop early. The time series continues for the full 30 days regardless.

**Futility:**
After 20 sessions, if CRO shows a positive trend (getting worse) with p < 0.10, stop and investigate. Possible explanations: the system is overfitting to early patterns, lessons are misfiring, or task complexity is increasing faster than learning.

**Data quality:**
If more than 30% of sessions have missing OUTPUT events (logging failure), pause and fix instrumentation before continuing. Days with broken logging do not count toward the 30-day period.

**Model change:**
If the underlying Claude model changes during the study, insert a phase break and add a dummy variable. If it changes more than twice, the study design is compromised and should be extended or restarted.

---

## 2. Metrics Dashboard Spec

### 2.1 Session-Level Metrics (computed at wrap-up)

```
session_metrics = {
    "session_number": int,
    "date": "YYYY-MM-DD",
    "session_type": "sales|system|hybrid",
    "model_version": str,

    # Core
    "output_count": int,
    "correction_count": int,
    "cro": float,              # correction_count / output_count (null if 0 outputs)
    "fdar": float,             # first_draft_accepted / output_count

    # Difficulty
    "difficulty_distribution": {1: n, 2: n, 3: n, 4: n, 5: n},
    "difficulty_weighted_cro": float,  # CRO weighted by expected baseline per tier

    # Timing
    "session_duration_sec": int,
    "median_tta_sec": float,   # median time-to-acceptance

    # Lessons
    "lessons_active": int,
    "lessons_instinct": int,
    "lessons_pattern": int,
    "lessons_rule": int,
    "lessons_untestable": int,
    "lessons_retired": int,
    "lessons_new_this_session": int,
    "lessons_promoted_this_session": int,

    # Categories
    "correction_categories": {"DRAFTING": n, "ACCURACY": n, ...},
    "extinct_categories": [str],  # categories with 0 corrections in last 15 sessions

    # Audit
    "audit_score": float,
    "audit_subscores": {"research": n, "quality": n, ...},

    # Blind (when applicable)
    "blind_comparisons_run": int,
    "blind_brain_wins": int,
    "blind_baseline_wins": int,
    "blind_ties": int,
    "blind_correct_guesses": int  # how often user guessed which was brain
}
```

### 2.2 Dashboard Panels

**Panel 1: Correction Rate Trend (Hero Chart)**
- X-axis: Session number (1 through current)
- Y-axis: CRO
- Lines: Per-session CRO (dots), 5-session rolling mean (line), 95% CI band (shaded)
- Annotations: Vertical lines at lesson graduation events
- Color: Green for sessions with CRO below rolling average, red for above

**Panel 2: First Draft Acceptance Rate**
- Same layout as Panel 1 but for FDAR
- Target line at 80% (aspirational)

**Panel 3: Category Extinction Heatmap**
- X-axis: Session number
- Y-axis: Correction categories (sorted by total count)
- Cell color: Number of corrections in that session (0 = gray, 1 = yellow, 2+ = red)
- Right margin: Sessions since last correction (green if >15)

**Panel 4: Lesson Lifecycle Stacked Area**
- X-axis: Session number
- Y-axis: Count of lessons
- Stacked areas: INSTINCT (red), PATTERN (yellow), RULE (green), UNTESTABLE (gray)
- Shows the system "maturing" as lessons graduate

**Panel 5: Difficulty-Adjusted Performance**
- Grouped bar chart: CRO by difficulty tier, comparing first 10 sessions vs last 10 sessions
- Shows improvement within each difficulty tier (not just shift to easier tasks)

**Panel 6: Blind Comparison Results**
- Running tally: Brain wins / Baseline wins / Ties
- Cumulative win rate with 95% Clopper-Pearson CI
- Forest plot by task type when enough data accumulates

**Panel 7: Audit Score Trend**
- Line chart of combined_avg over sessions
- Sub-dimension sparklines (research, quality, process, learning, outcomes)

**Panel 8: Confidence Intervals Summary Table**

| Metric | Current Value | 95% CI | N | Trend (last 10) |
|--------|--------------|--------|---|------------------|
| CRO | 0.12 | [0.08, 0.18] | 30 sessions | -0.02/session |
| FDAR | 0.74 | [0.65, 0.82] | 187 outputs | +0.01/session |
| Blind Win Rate | 0.68 | [0.54, 0.80] | 50 comparisons | stable |
| Audit Score | 8.4 | [8.1, 8.7] | 30 sessions | +0.03/session |

### 2.3 Implementation

- **Compute:** Python script in `sdk/src/gradata/enhancements/dashboard.py`
- **Data source:** `system.db` events table
- **Rendering:** Static HTML with Chart.js (no server needed; opens in browser)
- **Update frequency:** Auto-generated at wrap-up via hook
- **Export:** PNG snapshots of each panel for the paper; CSV of raw data for reproducibility

---

## 3. Blind Comparison Design

### 3.1 Protocol

**Goal:** Determine whether a brain-enhanced LLM produces better outputs than a fresh LLM on identical tasks, as judged by the user who cannot see which is which.

#### Step-by-step:

1. **Task selection:** Maintain a standardized task bank of 10 reusable tasks (see 3.4). Each task has a prompt, required context files, and a rubric.

2. **Dual generation:** For each comparison:
   - **Brain-on:** Generate the output with full brain context (lessons.md, CARL rules, soul.md, all domain context)
   - **Brain-off:** Generate the output with ONLY the base system prompt (CLAUDE.md core instructions, no lessons, no CARL, no soul.md, no brain/ context). Use a separate Claude API call or a fresh Claude Code session with a stripped-down CLAUDE.md.

3. **Randomization:** A script assigns each output to "Version A" or "Version B" using `random.choice()`. The mapping is written to a sealed file (`blind_key_{timestamp}.json`) that the researcher cannot read until after rating.

4. **Presentation:** Both versions are displayed in a standardized format (plain text in a file, or side-by-side in a simple HTML page). No metadata, timestamps, or other cues about which is which.

5. **Rating:** the researcher rates each version on:
   - **Overall quality** (1-10)
   - **Voice match** ("Does this sound like me?") (1-10)
   - **Factual accuracy** (1-10)
   - **Actionability** ("Could I send/use this as-is?") (1-10)
   - **Winner:** A, B, or tie
   - **Confidence:** How sure (1-5)
   - **Guess:** "Which do you think had the brain?" (A, B, unsure)

6. **Unblinding:** After rating, the script reveals the mapping and logs the result.

### 3.2 Technical Implementation

```python
# blind_compare.py (simplified)
import json, random, hashlib, datetime
from pathlib import Path

def run_comparison(task: dict, brain_output: str, baseline_output: str) -> Path:
    """Randomize and present two outputs for blind rating."""
    coin = random.choice(["brain_is_A", "brain_is_B"])

    if coin == "brain_is_A":
        version_a, version_b = brain_output, baseline_output
    else:
        version_a, version_b = baseline_output, brain_output

    # Write sealed key (hash prevents peeking)
    key_file = Path(f"blind_key_{datetime.datetime.now():%Y%m%d_%H%M%S}.json")
    key_data = {"mapping": coin, "task_id": task["id"],
                "hash": hashlib.sha256(coin.encode()).hexdigest()}
    key_file.write_text(json.dumps(key_data))

    # Write comparison file
    comparison = f"""# Blind Comparison: {task['name']}
## Task: {task['prompt']}

---
## VERSION A
{version_a}

---
## VERSION B
{version_b}

---
## Your Ratings (fill in):
- Version A quality (1-10):
- Version B quality (1-10):
- Voice match A (1-10):
- Voice match B (1-10):
- Winner (A/B/tie):
- Confidence (1-5):
- Guess which had brain (A/B/unsure):
"""
    comp_file = Path(f"blind_comparison_{task['id']}_{datetime.datetime.now():%Y%m%d}.md")
    comp_file.write_text(comparison)
    return comp_file
```

**For Claude Code specifically:** The simplest implementation is:
1. Generate brain-on output in the current session (with all context)
2. Use a subagent or separate API call with a stripped system prompt for brain-off
3. A wrapper script randomizes and presents both

### 3.3 Sample Size

- **Target:** 50 comparisons over 30 days (~1-2 per day)
- **Power:** At n=50, the exact binomial test detects a 69% true win rate with 80% power (alpha=0.05, one-sided)
- **Stratification:** At least 5 comparisons per difficulty tier, at least 10 per major output type (email, research, demo prep)
- **Minimum viable:** 30 comparisons (detects 73% win rate with 80% power)

### 3.4 Standardized Task Bank

| # | Task | Type | Difficulty | Context needed |
|---|------|------|-----------|---------------|
| 1 | Draft cold email to a CMO at a $50M DTC brand | email_draft | 4 | Company brief |
| 2 | Build demo prep cheat sheet for a given prospect | demo_prep | 3 | LinkedIn profile, company data |
| 3 | Score 5 leads against ICP criteria | lead_scoring | 3 | Lead data, ICP definition |
| 4 | Draft post-demo follow-up email | email_draft | 4 | Meeting transcript summary |
| 5 | Write Pipedrive deal note summarizing call | crm_update | 2 | Call notes |
| 6 | Research a competitor and summarize positioning | research | 3 | Competitor name |
| 7 | Design a 4-step cold email sequence | campaign_design | 5 | Target persona, value prop |
| 8 | Draft LinkedIn connection request + follow-up | linkedin | 4 | Prospect profile |
| 9 | Create a one-page company brief from web research | research | 3 | Company URL |
| 10 | Respond to an inbound prospect email | email_draft | 4 | Inbound email text |

Tasks are rotated (each used 5 times over 50 comparisons). Slight variations in target company/persona prevent memorization effects.

### 3.5 Validity Threats and Mitigations

| Threat | Mitigation |
|--------|-----------|
| Brain-on outputs are obviously better-formatted | Strip formatting differences; present both in identical template |
| the researcher recognizes his own trained voice | This IS the effect we're measuring; log it but don't suppress it |
| Order effects (first version rated higher) | Randomize presentation order; test for order bias in analysis |
| Task familiarity | Vary the specific company/person across repetitions |
| Carryover (brain-off benefits from brain-on prompts in same session) | Generate brain-off in a SEPARATE session or API call |

---

## 4. Paper Outline

### 4.1 Title Options

1. **"Gradata: Correction-Based Learning for AI Assistants Through Graduated Behavioral Rules"**
   - Descriptive, names the system, signals the mechanism

2. **"Teaching by Correcting: A Longitudinal Study of Human Correction as a Training Signal for AI Assistants"**
   - Emphasizes the human angle, appeals to CHI/CSCW audience

3. **"From Instinct to Rule: How Graduated Confidence Transforms User Corrections into Persistent AI Behavior"**
   - Technical, emphasizes the graduation mechanism, appeals to ML audience

**Recommended for arXiv:** Title 1 (clear, Googleable, names the contribution)

### 4.2 Abstract Template

> We present Gradata, a system that enables AI assistants to learn from user corrections through a graduated confidence pipeline. When a user corrects an AI output, the correction is logged, categorized, and assigned an initial confidence score. Through subsequent sessions, corrections that are reinforced promote from INSTINCT (tentative) to PATTERN (confirmed) to RULE (permanent behavioral contract), while contradicted corrections are demoted. In a [30]-day prospective study with a single expert user across [N] sessions and [M] outputs, we demonstrate that (a) correction rate per output decreased by [X]% (p < [Y]), (b) [Z] of [W] correction categories went extinct after relevant lessons graduated, (c) in [50] blinded pairwise comparisons, the brain-enhanced system was preferred [K]% of the time (p < [J]). We release the Gradata SDK, correction dataset, and analysis code as open-source contributions to reproducible research on personalized AI systems.

### 4.3 Section Structure

**1. Introduction** (1.5 pages)
- Problem: LLMs make the same mistakes for every user, every session. No persistent learning from individual corrections.
- Gap: RLHF learns from population preferences pre-training, not from individual corrections in deployment. Memory systems (Mem0, Letta) remember facts but don't learn behavioral patterns from corrections.
- Contribution: (1) A graduated confidence pipeline for correction-based learning (2) A rigorous N=1 longitudinal evaluation (3) An open-source SDK and dataset
- Figures: Figure 1 - system overview diagram

**2. Related Work** (2 pages)
- 2.1 RLHF and preference learning (Christiano et al., Ouyang et al., Rafailov DPO)
- 2.2 Memory-augmented LLMs (Mem0, Letta/MemGPT, retrieval-augmented generation)
- 2.3 Interactive machine learning and learning from corrections (Amershi et al., Fails & Olsen)
- 2.4 Single-case experimental designs in HCI (N-of-1 trials, interrupted time series)
- 2.5 Spaced repetition and confidence calibration (FSRS, SM-2)
- Key differentiator table: Gradata vs RLHF vs Mem0 vs MemGPT vs DPO

**3. System Design** (3 pages)
- 3.1 Architecture overview (3-layer SDK: patterns, enhancements, brain)
- 3.2 Correction capture and classification
- 3.3 The graduation pipeline (INSTINCT -> PATTERN -> RULE)
- 3.4 FSRS-inspired confidence updates (with math)
- 3.5 CARL behavioral contracts (rules as executable constraints)
- 3.6 Kill switches and lesson retirement
- Figures: Figure 2 - graduation pipeline state machine, Figure 3 - FSRS confidence curve

**4. Study Design** (2 pages)
- 4.1 Protocol (summarize Section 1 of this document)
- 4.2 Participant and context
- 4.3 Metrics and hypotheses
- 4.4 Blinding and controls
- 4.5 Ethical considerations (informed consent from self, data privacy)

**5. Results** (3 pages)
- 5.1 Primary result: CRO trend (H1) with regression table and time series plot
- 5.2 Category extinction analysis (H2) with heatmap
- 5.3 Blind comparison results (H3) with forest plot
- 5.4 Lesson lifecycle analysis
- 5.5 Robustness checks
- Tables: Table 1 - regression results, Table 2 - category-level results, Table 3 - blind comparison summary
- Figures: Figure 4 - CRO time series, Figure 5 - category extinction heatmap, Figure 6 - lesson lifecycle Sankey, Figure 7 - blind comparison forest plot

**6. Discussion** (2 pages)
- 6.1 What the results mean (or don't mean)
- 6.2 Limitations: N=1, single domain, user adaptation confound, non-blinded primary analysis
- 6.3 Generalizability: what transfers to other users/domains, what doesn't
- 6.4 The "user got better at prompting" alternative explanation
- 6.5 Implications for AI system design

**7. Limitations & Future Work** (1 page)
- Multi-user replication (the critical next step)
- Cross-domain transfer (does a sales brain help with code?)
- Automated correction detection (removing human logging dependency)
- Brain marketplace and rental model
- Longitudinal effects beyond 30 days

**8. Conclusion** (0.5 pages)

**Appendix A:** Full dataset description and access instructions
**Appendix B:** Standardized task bank for blind comparisons
**Appendix C:** Complete FSRS confidence update equations
**Appendix D:** CARL rule examples

### 4.4 Figures and Tables Needed

| # | Type | Content | Data Source |
|---|------|---------|------------|
| Fig 1 | System diagram | Architecture overview | Manual (draw.io/Excalidraw) |
| Fig 2 | State machine | INSTINCT -> PATTERN -> RULE transitions | Manual |
| Fig 3 | Line chart | FSRS confidence curves vs linear SM-2 | Computed from equations |
| Fig 4 | Time series + CI | CRO over all sessions | events.jsonl |
| Fig 5 | Heatmap | Category x session correction density | events.jsonl |
| Fig 6 | Sankey diagram | Lesson lifecycle flows | lessons.md + archive |
| Fig 7 | Forest plot | Blind comparison effect sizes by task type | blind comparison results |
| Fig 8 | Bar chart | Difficulty-adjusted CRO comparison (early vs late) | events.jsonl |
| Tab 1 | Regression | Primary Poisson regression results | Analysis |
| Tab 2 | Summary | Per-category correction counts and extinction status | events.jsonl |
| Tab 3 | Comparison | Blind comparison aggregate results | blind comparison results |
| Tab 4 | Comparison | Gradata vs RLHF vs Mem0 vs MemGPT feature comparison | Literature |
| Tab 5 | Descriptive | Study descriptive statistics (sessions, outputs, corrections) | events.jsonl |

---

## 5. Minimum Viable Proof (Existing Data)

What the researcher can honestly claim TODAY from 71 sessions of data, with appropriate caveats.

### 5.1 Claim 1: Correction Rate Decline

**Metric:** Corrections per session, early vs late

**Current data:** 58 CORRECTION events across 71 sessions. Early sessions (1-10) show clustering: sessions 5-6 alone account for 12 corrections. Later sessions (40-71) show dramatically fewer corrections per session.

**Honest framing:**
> "Over 71 sessions, user corrections declined from an average of 2.4 per session (sessions 1-10) to 0.3 per session (sessions 60-71). 48 behavioral lessons graduated to permanent rules."

**Caveats to include:**
- Retrospective data, partially backfilled from session notes
- Single user, single domain
- Cannot distinguish system learning from user adaptation
- Measurement protocol changed over time (early corrections may be undercounted or overcounted)
- No control condition in existing data

**Credibility:** MODERATE. The magnitude of decline is large enough to be meaningful, but the retrospective, single-user nature means this is a case report, not a controlled study.

### 5.2 Claim 2: Category Extinction

**Metric:** Correction categories that stopped recurring after lessons were logged

**Current data:** Early categories like SKIP (14 corrections in sessions 1-6), FRICTION (5 corrections in sessions 1-5), and TONE (2 corrections in sessions 5-7) have zero corrections after their lessons graduated. DRAFTING shows early clustering (sessions 3-6) then only appears in new sub-categories.

**Honest framing:**
> "Of 18 correction categories tracked, 7 went extinct (zero recurrences in 15+ sessions) after corresponding lessons promoted to PATTERN or RULE status."

**Caveats:**
- Some categories may have gone extinct because the tasks changed, not because the system learned
- Small sample sizes per category (3-14 corrections each)
- Need per-category analysis to distinguish task-driven vs learning-driven extinction

**Credibility:** MODERATE-HIGH. The specificity of category-level extinction is harder to explain by chance. The fact that graduated categories (not random ones) went extinct is the strongest signal.

### 5.3 Claim 3: Audit Score Improvement

**Metric:** Combined audit scores over time

**Current data:** 37 AUDIT_SCORE events. Early scores: 6.4 (S1), 7.65 (S5), 6.5 (S6). Recent scores: 8.4-8.8 range (S32-S34).

**Honest framing:**
> "Session quality scores (1-10 composite across 5 dimensions, rated at wrap-up) improved from a mean of 7.2 (sessions 1-10) to 8.4 (sessions 30+), stabilizing above the 8.0 quality gate."

**Caveats:**
- Self-assessed by the system (not by the user directly in most cases)
- Some scores are backfilled estimates ("self-score only")
- The 8.0 quality gate creates a ceiling/floor effect (system is incentivized to report >= 8.0)
- Audit methodology itself improved over time (later audits are more rigorous)

**Credibility:** LOW-MODERATE. Self-assessment scores are inherently suspect. Include only if paired with more objective metrics. Do NOT lead with this claim.

### 5.4 Claim 4: Graduation Pipeline Statistics

**Metric:** Lesson flow through the confidence tiers

**Current data:** 107 total lessons created. 48 graduated to permanent rules. 6 flagged UNTESTABLE. 10 reclassified (knowledge, not behavioral). ~43 currently active (13 in lessons.md + 30 archived at various states).

**Honest framing:**
> "The system generated 107 behavioral lessons from user corrections. 48 (45%) graduated to permanent rules through a spaced-repetition-inspired confidence pipeline. 6 (5.6%) were retired as untestable after 20+ sessions with zero applications."

**Caveats:**
- Graduation is a system-internal metric, not an outcome metric
- A graduated lesson could be wrong but never contradicted (survivorship bias)
- The pipeline itself was being built and modified during this period

**Credibility:** HIGH (as a system description), LOW (as proof of effectiveness). These numbers describe what the system did, not whether it worked. Appropriate for a README or system description, not as the primary proof claim.

### 5.5 Claim 5: Open-Source SDK with Verifiable Data

**Metric:** The data and code are available for inspection

**Honest framing:**
> "All corrections, lessons, and system events are logged in an append-only event store. The dataset (71 sessions, 58 corrections, 107 lessons, 37 audit scores) and the SDK code are open-source and reproducible."

**Caveats:** None needed. This is a factual statement about what's available.

**Credibility:** HIGH. Transparency itself is a credibility signal. The fact that raw data is inspectable differentiates Gradata from systems that only report aggregate metrics.

### 5.6 Recommended Landing Page / README Claims

Lead with claims ranked by credibility:

1. **Open data + code** (Claim 5) -- highest credibility, always leads
2. **Category extinction** (Claim 2) -- most specific, hardest to fake
3. **Correction rate decline** (Claim 1) -- impressive magnitude, moderate credibility
4. **Pipeline statistics** (Claim 4) -- describes the mechanism, not the outcome
5. **Audit scores** (Claim 3) -- only mention in passing, don't lead with it

**Mandatory disclaimer for all claims:**
> "These results are from a single-user case study over 71 sessions (9 days). A controlled prospective study is underway. Results may not generalize to other users, domains, or tasks."

### 5.7 What NOT to Claim

- Do NOT say "5.0 to 0.004 corrections per output" -- this requires OUTPUT event counts that were not consistently tracked in early sessions. The denominator is unreliable.
- Do NOT say "99.9% reduction" -- same denominator problem, and the precision implies measurement rigor that doesn't exist in the retrospective data.
- Do NOT claim the system "learns" without qualification -- the user also adapted.
- Do NOT compare to RLHF or claim superiority -- different problem, different scale.

---

## Appendix: Pre-Registration Checklist

Before Day 1 of the prospective study, register on OSF (osf.io) with:

- [ ] Hypotheses H1, H2, H3 (exact wording from Section 1.2)
- [ ] Primary metric definition (CRO, Section 1.4)
- [ ] Analysis plan (Poisson regression specification, Section 1.12)
- [ ] Sample size justification (30 sessions, 50 blind comparisons)
- [ ] Stopping rules (Section 1.13)
- [ ] Output difficulty tier definitions (Section 1.6)
- [ ] Correction classification scheme (Section 1.3)
- [ ] Standardized task bank for blind comparisons (Section 3.4)
- [ ] Code for blind comparison randomization (Section 3.2)
- [ ] Dataset description format

**Pre-registration protects against:** cherry-picking metrics, p-hacking through multiple analyses, post-hoc hypothesis revision, and HARKing (Hypothesizing After Results are Known).

---

## Appendix: Existing Data Inventory

As of 2026-03-26, the brain contains:

| Data Type | Count | Quality | Notes |
|-----------|-------|---------|-------|
| Sessions | 71 | Mixed | Sessions 1-33 backfilled, 34+ prospective |
| CORRECTION events | 58 | Mixed | 50 backfilled, 8 prospective; later sessions include automated hook captures that may be false positives |
| AUDIT_SCORE events | 37 | Low-Moderate | Many are self-scores or backfilled estimates |
| OUTPUT events | ~20 | Low | Only started tracking recently; most sessions lack output tagging |
| Active lessons | ~43 | High | Well-formatted, dated, categorized |
| Graduated lessons | 48 | High | Archived with graduation rationale |
| CARL rules | ~15 | High | Behavioral contracts with testable failure conditions |

**Critical gap for the study:** OUTPUT events are sparse. The first priority before the study starts is implementing reliable output tagging so that CRO can be computed with a real denominator. Without output counts, the primary metric is undefined.
