# S103 Validation Report

In April 2026 we ran a validation sprint on Gradata's core architecture. The goal: find out whether our design choices hold up when a large panel of domain experts is asked to solve the same problem without knowing Gradata exists.

This page documents the methodology, what the panel validated, what they missed, what gaps they exposed, and the limits of the exercise.

## Methodology

- **Panel size:** 200 simulated experts across two parallel sims (100 agents each)
- **Domains:** 10 research areas including ML systems, continual learning, retrieval, distributed systems, privacy, and alignment
- **Format:** 15 rounds of structured debate per sim, with distinct personas and positions seeded per agent
- **Blinding:** Zero knowledge of Gradata. Experts were asked to design a system that compounds user corrections over time, not to review ours.
- **Volume:** ~900 substantive posts across the two sims
- **Comparison:** Panel proposals were categorized and cross-referenced against Gradata's 14 core features

Two additional workstreams ran alongside:

- **Stat replication experiment:** N=100 synthetic users across 4 cohorts (consistent, sporadic, evolving, adversarial) run through 20 sessions x 5 corrections
- **JTBD experiment:** 50 job-to-be-done statements generated and scored on specificity, measurability, and customer resonance

## The 10 Validated Features

These are the features the blind panel independently converged on. Independent convergence across diverse expert personas is the strongest form of design validation short of user studies.

| Feature | Panel convergence |
|---|---|
| Correction storage as structured objects | 100/100 experts insisted on decomposing corrections into typed knowledge units, not raw text |
| Error type taxonomy (Rosch 6-category) | Universal 4-category consensus (Tone, Factual, Structural, Judgment). Gradata's Rosch taxonomy is a superset. |
| Rule abstraction from raw corrections | ~70/100 proposed synthesizing corrections into abstract rules. The graduation pipeline (INSTINCT -> PATTERN -> RULE) is this synthesis. |
| Prompt injection with prioritization | Universal endorsement of `[System Directives] + [Retrieved Corrections] + [Current Context]` |
| Decay / temporal weighting | ~25/100 championed spaced repetition and forgetting curves. Gradata's `temporal_decay()` and FSRS-inspired scheduling match. |
| Max injection limit | Engineers noted that injecting too many corrections degrades performance. Gradata's `max_rules=5` matches. |
| Severity-weighted confidence | Multiple agents proposed severity weights. Gradata's SEVERITY_WEIGHTS dict (trivial=0.20 through rewrite=1.30) matches. |
| Contradiction handling | Agents flagged preference-contradiction loops as a known failure mode. Gradata's contradiction detector handles polarity, negation, and opposite-action patterns. |
| Three-tier distribution architecture | Sim B experts proposed Edge / Aggregation / Knowledge layers. Gradata's cloud sync uses three tiers (metrics / rules / events). |
| Middleware wrapping the LLM | 100% agreed: all learning is externalized, the LLM stays stateless. Gradata is middleware: hooks, context injection, rule engine. |

Validation score: 10 of 14 core features independently confirmed.

## The 7 Novel Features (The Moat)

These are the features Gradata has that nobody on the panel proposed, even after 15 rounds of debate.

| Feature | Why it matters |
|---|---|
| **Graduation pipeline (INSTINCT -> PATTERN -> RULE)** | No expert proposed a multi-stage confidence pipeline with explicit state-machine transitions. They proposed flat rule abstraction, not graduated maturity. This is the primary differentiator. |
| **Fire / misfire tracking with correction attribution** | No expert proposed tracking when rules fire correctly vs incorrectly and attributing corrections back to the rules that failed. Enables self-healing. |
| **Auto-climb / scope generalization** | No expert proposed rules automatically broadening their scope when proven across contexts. Scope was assumed static. |
| **Meta-rules from rule clusters** | No expert proposed automatically discovering higher-order principles from 3+ related graduated rules. Emergent hierarchy. |
| **Rule suppression tracking** | Only 1 of 50 in a separate simulation identified the denominator-bias problem in confidence scoring. Almost nobody sees this. |
| **Brain manifest / quality proof** | Nobody proposed a machine-readable quality proof that demonstrates a brain's competence. |
| **Sharing graduated rules (not gradients)** | ALL 100 distribution experts defaulted to federated learning / gradient sharing. Multiple experts then criticized gradient approaches as inadequate for discrete symbolic knowledge like "never use em dashes." Gradata sidesteps the entire gradient-to-symbolic gap by sharing discrete rules. |

## The 7 Gaps (And What We Shipped to Close Them)

The panel also surfaced 7 genuine gaps in Gradata. Five were closed during the same session.

| Gap | Status |
|---|---|
| Knowledge graph for correction relationships | **Shipped.** REINFORCES / CONTRADICTS / SPECIALIZES / GENERALIZES edges between rules. |
| Contrastive / directional embeddings | **Shipped.** Cosine-distance semantic delta for correction representation. |
| Batch synthesis via dedicated LLM call | **Shipped.** LLM batch synthesis in `meta_rules.py` replaces keyword-only clustering. |
| Constitutional principles format | **Shipped (experimental, opt-in).** Alongside the default imperative format. |
| Context budget awareness | **Shipped.** 5-level budget-aware injection with context compression. |
| Privacy / profiling risk mitigation | **Shipped.** Laplace DP + k-anonymity + sanitization + `THREAT_MODEL.md` covering 5 attack vectors and 10 mitigations. |
| User trust / credibility scoring | **Deferred.** Relevant for multi-tenant deployments. Tracked for a later session. |

## Published Stats (Problem Validation)

These are external, published numbers we cite to validate the problem space. They are not Gradata's own results.

| Stat | Source |
|---|---|
| 75% of marketers spend 30+ minutes editing AI output | HubSpot State of AI (2024) |
| 72% correct AI regularly; 25% of their time goes to corrections | Writer.com, n=1,600 (2024) |
| 60% abandon AI tools because the tool "didn't understand context" | Forrester (2023) |
| Code churn up 39% in Copilot-heavy repos | GitClear (2024) |
| AI saves ~2 hr/week on drafts, costs ~1.5 hr/week on edits | Asana Work Innovation Lab (2024) |
| 52% more concerned than excited about AI | Pew Research (2023) |
| Explainability increases AI trust | MIT Sloan / BCG, n=2,000 (2024) |

## Measured Internal Improvements

Three optimization loops ran during the same sprint. All numbers are measured against `brain_benchmark.py` (a 7-dimension composite) replaying 2,000 events.

- **Conciseness:** Token count for injected rules reduced from 478 to 166 (65.3% reduction). Composite quality score unchanged at 22.74/100. Key change: `max_rules` 10 -> 5 and compressed formatting.
- **Cold start:** Composite benchmark moved from 22.7 to 67.8 (+198%). Root cause was a bug: survival events were not incrementing `fire_count`, so lessons rarely graduated. The fix affects all deployed brains.
- **Reversal:** Events-to-flip reduced from 5.0 to 1.0 (80% reduction) on synthetic contradiction scenarios. Mechanisms: contradiction streak tracking, FSRS quadratic penalty scaling, cooling period after contradictions.

## Stat Replication

We mapped Duolingo's half-life regression and Wozniak's two-component memory model onto Gradata's graduation pipeline, then ran N=100 synthetic users through 20 sessions x 5 corrections each across 4 cohorts.

- Consistent correctors: 100% correction reduction by session 5 (exponential decay, matches Wozniak)
- Sporadic correctors: 93% reduction, noisy convergence (partial match)
- Evolving correctors: 100% reduction with a step-function spike at the preference reversal (matches predicted curve)
- Adversarial correctors: -42% (worse than baseline) -- correctly never converges

Citations:

- Settles and Meeder, "A Trainable Spaced Repetition Model for Language Learning," ACL 2016 (12M sessions, 9.5% retention increase)
- Wozniak, "Two-Component Model of Long-Term Memory," SuperMemo, 1995

## Named Limitations

We do not want to overclaim. Every finding on this page has caveats.

- **Simulated experts are LLM personas, not humans.** Consensus may reflect training-data bias rather than true expert judgment. Results should be validated against real user interviews.
- **All replication data is synthetic.** The 100-user simulation is not a substitute for real user studies. Do not extrapolate the curves directly to real users.
- **Benchmark-measured quality is a proxy.** The 7-dimension composite is a reasonable proxy for learning quality, but it does not directly measure user satisfaction.
- **Consistent-corrector cohort may converge too fast.** 0% correction rate by session 5 is likely faster than real users. The shape matches Wozniak; the exact constants need real-world calibration.
- **Preference-reversal optimum is synthetic.** 1-event flip may be too aggressive for production, because one-off contradictory corrections could cause instability.
- **Absence of evidence is weak evidence.** "Nobody on the panel proposed X" suggests non-obvious, not correct.
- **Discrete rule sharing is not privacy-free.** Graduated rules may still leak information if not filtered by transfer_scope. Sharing rules avoids gradient inversion, but does not avoid the need for sanitization and DP on aggregated data.
- **JTBD verticals are synthetic.** Legal and developer scored highest in a Gemma4-judged experiment. Validate against real customer conversations before making positioning decisions.

## Source Documents

The full per-experiment reports live in the brain vault:

- `SIM_A_LEARNING_ARCH_S103.md` -- learning-architecture sim, 581 substantive posts, 15 rounds, 100 agents
- `SIM_B_DISTRIBUTION_ARCH_S103.md` -- distribution-architecture sim, 319 substantive posts, 15 rounds, 100 agents
- `S103_CROSS_VALIDATION.md` -- the validated / gap / questionable / novel matrix
- `S103_JTBD_EXPERIMENT.md` -- 50 JTBD statements, legal and developer verticals
- `S103_STAT_REPLICATION.md` -- curves matched against Wozniak and HLR
- `S103_MARKETING_CLAIMS.md` -- claims, methodology, citations, limitations
