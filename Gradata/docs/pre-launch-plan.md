# Gradata — Pre-Launch Plan

_Source: gap-analysis Card 8 (sessions/2026-04-20-pipeline-revamp/gradata-gap-analysis.md). Canonical; update here only._

---

## 1. The Five Post-Launch Metrics

### 1.1 Activation Rate

**Definition:** Percentage of installs that log at least one correction event within 7 days of first `gradata init`.

- Numerator: installs with `CORRECTION_LOGGED` event timestamp ≤ install + 7 days.
- Denominator: all installs (unique `tenant_id` values).
- Measurement: anonymous opt-in telemetry. Collected via `brain.telemetry_summary` hook at session close.

**Why it matters:** Proxy for "reached the aha moment." An install that never logs a correction got zero value from Gradata's core promise.

---

### 1.2 D7 Retention

**Definition:** Percentage of installers who run at least one Gradata-instrumented session on day 7 (±1 day window) after install.

- Detected via `SESSION_CLOSE` event present in the D7 window.
- Measurement: same telemetry pipeline as activation; anonymized per `tenant_id`.

**Why it matters:** Activation is a one-time gate. Retention says "they came back." Day 7 is early enough to act on before users fully churn.

---

### 1.3 Time-to-First-Graduation

**Definition:** Median wall-clock hours from install to the first `RULE_GRADUATED` event at any tier (INSTINCT, PATTERN, or RULE).

- Measured from `tenant_id` creation timestamp to earliest `RULE_GRADUATED` event in `brain/events.jsonl`.
- Reported as a cohort median (p50), tracked weekly.

**Why it matters:** Graduation is the compound-quality proof. A long time-to-first-graduation means the correction-loop is too slow or the threshold is too high — users leave before they see the payoff.

---

### 1.4 Free → Pro Conversion Rate

**Definition:** Percentage of free-tier active users (≥1 session in trailing 14 days) who upgrade to a paid plan in any given 30-day window.

- Denominator: free users who were active in the window.
- Numerator: upgrades (Stripe webhook `customer.subscription.created`, tier ≥ Pro).
- Tracked monthly once cloud billing is live.

**Why it matters:** This is the revenue signal. Conversion below 3% in month 2 means the free tier is too generous or the paywall is in the wrong place.

---

### 1.5 Correction-Rate Decay

**Definition:** For users with ≥30 days of data, the per-session correction count trend over time.

- Compute: linear regression slope of `corrections_per_session` vs. session ordinal for each cohort.
- Negative slope = corrections decreasing = AI is learning = product is working.
- Flat or positive slope = no compound improvement = core thesis is broken.
- Reported as a cohort-level aggregate (% of users with negative slope).

**Why it matters:** This is the one metric that cannot be faked by good onboarding or a flashy dashboard. If correction rate is not decaying, Gradata does not do what it says it does.

---

## 2. Decision Triggers

### 2.1 Pivot Trigger

**Condition:** Activation rate < 20% AND correction-rate-decay slope is flat (≤ 0 users with negative slope) across all cohorts at day 30 post-launch.

**Interpretation:** Users are installing but not correcting, and when they do correct, the rules are not compounding. The behavioral-rules-as-a-product thesis is not landing.

**Response:** Pivot positioning toward memory-plus-guardrails (reduce, don't eliminate, graduation machinery; lead with "your AI won't leak secrets or drift on tone" rather than "your AI gets smarter").

---

### 2.2 Kill Trigger

**Condition:** Fewer than 100 installs in the 60 days following the HN launch post.

**Interpretation:** The distribution event ran and the pain is not real to enough people. No amount of feature work closes a zero-demand gap.

**Response:** Shut down or pivot entirely. Do not extend the runway by building more features. The decision date is day 60 post-HN-launch — pre-commit to it now to prevent rationalization.

---

### 2.3 Scale Trigger

**Condition:** More than 1,000 installs AND free-to-Pro conversion ≥ 5% within 90 days post-launch.

**Interpretation:** Demand is real, the paywall placement is working, unit economics are viable.

**Response:** Raise a seed round, hire one additional engineer, productize the cloud (multi-tenant dashboard, team tier, enterprise SLA). Begin corpus opt-in network-effect flow design.

---

## 3. Weekly Retro Format

**When:** Every Monday, 30 minutes, first thing.

**Attendees:** Oliver (solo pre-seed — this is a solo retro until the first hire).

**Agenda (strict 30-min time box):**

| # | Item | Time |
|---|------|------|
| 1 | Pull the 5 metrics dashboard — review numbers vs. prior week. | 8 min |
| 2 | Top 3 user comments (verbatim, from telemetry free-text or user calls). | 7 min |
| 3 | "Biggest surprise this week" — one sentence, written before the retro starts. | 5 min |
| 4 | One decision carried into next week — written, time-boxed, owner named. | 5 min |
| 5 | Check: are we past a trigger threshold? If yes, execute the trigger — no debate. | 5 min |

**Output:** One paragraph in `sessions/YYYY-MM-DD-retro.md` covering the decision from item 4. No other documentation required.

**Rule:** If any metric is missing (telemetry gap, no data yet), log "MISSING" — do not skip the retro. Missing data is a decision (fix the telemetry) not an excuse to defer.

---

## 4. Pre-Launch Checklist (Gate Before HN Launch)

- [ ] Anonymous telemetry instrumented and tested locally (activation + D7 events).
- [ ] `RULE_GRADUATED` event emitted by pipeline and confirmed in `events.jsonl`.
- [ ] Stripe webhook configured for conversion tracking (Pro tier).
- [ ] Baseline cohort dashboard exists (even a local SQLite query + CSV is acceptable).
- [ ] This file committed and reviewed by Oliver — triggers are not rationalized away.
- [ ] Kill-decision date written in calendar: _60 days from HN launch date_.

---

_Last updated: 2026-04-20. Owner: Oliver Le._
