---
name: adversarial-review
description: Adversarial debate between Draft and Critic agents before sending prospect-facing output. Two agents argue — one attacks, one defends — until they converge on a verdict. Not a one-sided review. A real debate with evidence.
---

# Adversarial Pre-Send Review

## When to Trigger
Before ANY prospect-facing output leaves the system:
- Emails (cold, follow-up, proposal)
- LinkedIn messages
- Demo scripts / talking points
- Proposals / pricing documents

Do NOT trigger for:
- Internal notes, session notes, system changes
- CRM updates, Pipedrive notes
- Draft revisions (only final versions)

## Architecture: Two-Agent Debate

### Agent 1: CRITIC (Adversarial)
**Role:** "You are the prospect. You received this. Why do you delete it?"

**Attacks along 5 axes:**
1. **Relevance** — Does this address MY actual problem, or is it generic?
2. **Proof** — Are claims backed by evidence, or just assertions?
3. **Ask** — Is the CTA clear, low-friction, and justified?
4. **Voice** — Does this sound like a human who knows my world, or an AI template?
5. **Timing** — Based on what we know about this prospect's stage, is this the right message right now?

**Output format:**
```
VERDICT: KILL | REVISE | PASS
WEAKEST AXIS: [which of the 5]
ATTACK: [specific, concrete objection — not vague]
EVIDENCE: [what data supports this objection]
```

### Agent 2: DEFENDER (Draft Agent)
**Role:** Responds to the Critic's attack with evidence or concedes and revises.

**Response format:**
```
RESPONSE: REBUT | CONCEDE
EVIDENCE: [if rebutting — specific data/context that answers the objection]
REVISION: [if conceding — the specific change made]
```

### Convergence Rules
- **Max 3 rounds.** If no convergence by round 3, escalate to Oliver.
- **PASS:** Critic gives PASS verdict, or Defender rebuts with evidence Critic accepts.
- **REVISE:** Critic gives REVISE, Defender concedes and rewrites. New version gets one more Critic pass.
- **KILL:** Critic gives KILL with evidence. Defender cannot rebut. Draft is blocked. Oliver decides.
- **Convergence = both agents agree on the same verdict.** Not one agent winning.

## Execution Flow

```
1. Draft agent produces output
2. Quality gate self-score (existing flow)
3. IF prospect-facing AND self-score >= 7:
     a. Spawn CRITIC subagent with:
        - The draft
        - Prospect context (from brain/prospects/*.md)
        - Last 3 interactions with this prospect
        - Known objections/patterns from PATTERNS.md
     b. CRITIC returns verdict
     c. IF KILL → block + notify Oliver
     d. IF REVISE → Draft agent revises, CRITIC reviews revision (1 round)
     e. IF PASS → proceed to send
4. Log debate to events.jsonl:
     emit("GATE_RESULT", "adversarial-review", {
         "prospect": name,
         "output_type": type,
         "rounds": N,
         "final_verdict": verdict,
         "critic_attacks": [...],
         "defender_responses": [...],
         "convergence": true/false
     })
```

## CRITIC Agent Prompt

```
You are the prospect who just received this message. Your job is to find the
weakest point and attack it. You are not mean — you are busy, skeptical, and
have seen 50 cold emails today.

Context about you (the prospect):
{prospect_context}

Last interactions:
{interaction_history}

The message you received:
{draft}

Evaluate along 5 axes (score 1-10 each):
1. RELEVANCE: Does this address my actual situation?
2. PROOF: Are claims backed by evidence I can verify?
3. ASK: Is the CTA clear and worth my time?
4. VOICE: Does this sound like someone who knows my world?
5. TIMING: Is this the right message given where I am in the process?

Your verdict:
- KILL if any axis scores 3 or below (fatal flaw)
- REVISE if any axis scores 4-5 (fixable weakness)
- PASS if all axes score 6+ (good enough to send)

Be specific. "This feels generic" is not an attack. "You mention AI efficiency
but my LinkedIn shows I just posted about reducing headcount, not adding AI
tools" IS an attack.
```

## DEFENDER Agent Prompt

```
The Critic found a weakness in your draft. You have two options:

1. REBUT — present specific evidence that answers their objection
   (prospect data, past interactions, pattern match, industry context)
2. CONCEDE — acknowledge the weakness and revise the specific section

You cannot:
- Dismiss the objection without evidence
- Add fluff to compensate for a weak point
- Change the subject

The attack:
{critic_verdict}

Your original draft:
{draft}

Available evidence:
{prospect_context}
{patterns}
```

## Token Budget
- CRITIC: max 500 tokens per round
- DEFENDER: max 500 tokens per round
- Max 3 rounds = 3,000 tokens total worst case
- This is ~$0.02-0.04 per review at current Sonnet pricing

## Measuring Value
Track in events.jsonl:
- Debate outcomes (PASS/REVISE/KILL rates)
- Post-debate reply rates vs pre-debate baseline
- Oliver override rate (did Oliver disagree with the verdict?)
- If Oliver overrides KILL → the Critic was wrong. Adjust.
- If Oliver agrees with KILL → the Critic saved a bad send. Valuable.

After 20+ debates, compute:
- Fisher's exact test: reply rate WITH debate vs WITHOUT
- If not significant → debate adds cost without value → kill the feature
- If significant → promote to mandatory gate
