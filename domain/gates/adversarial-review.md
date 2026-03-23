---
name: adversarial-review
description: Mandatory adversarial two-agent debate before any prospect-facing output is marked done. Fires after draft + self-score, before send/delivery.
skill: skills/adversarial-review/SKILL.md
---

# Adversarial Pre-Send Review Gate (MANDATORY)

**No prospect-facing output may be considered "done" until this gate passes.**

## When This Gate Fires
After the draft is written AND self-scored >= 7, before presenting as final to Oliver. Applies to writes targeting:
- `prospects/`, `emails/`, `templates/`, `demos/`
- `Email Templates/`, `messages/`
- Any file explicitly identified as prospect-facing (cold email, follow-up, proposal, LinkedIn message, demo script)

## When This Gate Does NOT Fire
- Internal notes, session notes, system files
- CRM/Pipedrive updates
- Draft iterations mid-revision (only the version presented as "final")
- Self-score below 7 (fix the draft first, then gate)

## Gate Flow

```
1. Draft written to prospect-facing path
2. Self-score (quality-rubrics.md) — must be >= 7
3. >>> ADVERSARIAL REVIEW GATE <<<
   a. Run skills/adversarial-review/SKILL.md
   b. CRITIC + DEFENDER debate (max 3 rounds)
   c. Verdict: PASS / REVISE / KILL
4. If PASS  → present to Oliver as ready
5. If REVISE → revise per Critic feedback, re-run one Critic pass
6. If KILL  → block output, escalate to Oliver with Critic evidence
7. Log debate to events.jsonl (GATE_RESULT event)
```

## Proof Block (append below self-score block)
```
ADVERSARIAL REVIEW: [prospect name]
ROUNDS: [1-3]
VERDICT: [PASS / REVISE / KILL]
WEAKEST AXIS: [relevance / proof / ask / voice / timing]
SCORE: [avg of 5 axes, 1-10]
```

## Failure Mode
If adversarial review cannot run (e.g., no prospect context in vault), flag as:
```
ADVERSARIAL REVIEW: SKIPPED — no prospect context
```
Oliver must explicitly approve sending without review.
