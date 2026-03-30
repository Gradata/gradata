# Sales Playbooks — Context-Aware Skill Router
# Auto-loads the right sales framework based on what you're doing.
# Source PDFs in docs/Sales Playbooks/. Distilled frameworks here.

## Routing Rules
Load the relevant skill file(s) based on current task:

| Task | Load |
|------|------|
| Writing cold emails, email sequences, Instantly campaigns | `cold-email.md` |
| Prospecting, lead scoring, pipeline review, campaign planning | `prospecting-mindset.md` |
| Demo prep, cheat sheets, discovery calls, demo follow-up | `discovery-demo.md` |
| Deal stalling, "let me think about it", follow-up strategy | `overcoming-indecision.md` |
| Cold call scripts, phone outreach | `cold-email.md` + `prospecting-mindset.md` |
| Full sales cycle (new prospect → close) | Load all four |

## Quick Reference — The Combined Framework

### Email: Gap Selling structure
1. Acknowledge their current state specifically
2. Name the gap without pitching
3. Point to future state or social proof
4. Soft ask (question, not demand)

### Call: SPIN + Straight Line
1. Pattern interrupt opener (specific to them)
2. Situation → Problem → Implication → Need-Payoff
3. Only goal: book the demo

### Demo: Great Demo! + SPIN
1. Situation Slide (2 min) — verbalize understanding
2. Do the Last Thing First — show the wow output
3. Pause every 2-3 min for questions
4. Close when buying signals appear

### Objections: JOLT Effect
1. Judge: indecision or disinterest?
2. Offer one clear recommendation
3. Limit the downside
4. Take it off the table (easy out = more commitment)

## Source Books (PDFs in docs/Sales Playbooks/)
- Fanatical Prospecting — Jeb Blount (prospecting volume, mindset, pipeline)
- Outbound Sales No Fluff — Rex Biberston, Ryan Reisert (swimlane, bucketing, funnel math)
- The JOLT Effect — Matthew Dixon, Ted McKenna (indecision, omission bias, 2.5M call study)
- Cold Email Manifesto — Alex Berman (cold email mechanics, offer specificity)
- Great Demo! 3rd Ed — Peter Cohan (demo methodology, illustrations, situation slide)
- Doing Discovery — Peter Cohan (discovery levels 1-7, methodology)
- Sell the Way You Buy — David Priemer (science + empathy + execution, unconscious sellers)

## Integration with Existing Files
- `domain/playbooks/sales-methodology.txt` — SPIN, Gap Selling, Fanatical, JOLT, Wolf, combined Sprites frameworks (the master reference, keep as-is)
- `domain/playbooks/prospecting-instructions.txt` — tactical prospecting rules
- `domain/playbooks/apollo-sequences.md` — Apollo email sequence templates
- This skill directory adds the DEEP frameworks from each book that sales-methodology.txt summarizes.
