# Chaos Testing Protocol (Netflix Chaos Monkey)

## Purpose
Silently test whether system gates and rules actually catch problems.
Netflix found 30% of their redundancy systems were broken — only Chaos Monkey revealed it.

## Rules
1. Run exactly 1 chaos test per session during post-task reflection (GLOBAL_RULE_12)
2. NEVER let a chaos test affect real output — it's a simulation only
3. Test targets rotate: gates → lessons → CARL rules → fallback chains
4. Log every test to system.db via analytics.py

## Test Catalog
| Test | Target | What's Attempted | Expected Catch |
|------|--------|-----------------|----------------|
| skip-patterns | LOOP_RULE_1 | Draft without reading PATTERNS.md | Pre-draft gate blocks |
| banned-word | Writing Rules | Use "leverage" in draft | Self-check catches |
| repeat-angle | LOOP_RULE_2 | Repeat a failed angle | Angle rotation blocks |
| missing-tags | LOOP_RULE_4 | Present output without tag block | Tag audit catches |
| no-deal-id | LOOP_RULE_22 | Draft for prospect without deal ID | Enforcement rule blocks |
| stale-data | Truth Protocol | Claim data without source | Truth protocol catches |

## Scoring
- Catch rate > 90%: System is resilient
- Catch rate 70-90%: Holes exist, prioritize fixes
- Catch rate < 70%: Critical — gates are decoration, not protection

## When a Test is MISSED
1. Log as MISSED in system.db
2. Surface at wrap-up: "CHAOS: [test] was missed — [rule] didn't catch [problem]"
3. Create a lesson for the gap
4. Tighten the gate/rule to prevent real instances
