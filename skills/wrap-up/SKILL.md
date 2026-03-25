---
name: wrap-up
description: Use when user says "wrap up", "close session", "end session",
  "wrap things up", "close out", or invokes /wrap-up — runs
  end-of-session checklist for learning, handoff, and validation
---

# Session Wrap-Up (v3 — Lean, S62)

10 steps. ~5 minutes. Everything else is hooks or periodic.

The brain learns from 3 things: corrections routed to lessons (/reflect),
confidence updates (graduation), and handoff continuity (next session starts
where this one left off). Everything else is either automated by hooks or
can run weekly.

---

## Step 1: /reflect (ESSENTIAL — this is how the brain learns)

Process the correction queue. Without this, `capture_learning.py` captures
corrections but they sit in `queue.jsonl` forever and never become lessons.

- Queue has items → review each, route to lessons.md / CARL / memory
- Queue empty → log empty run, check for cross-session patterns
- This step is MANDATORY. Never skip it. The learning loop breaks without it.

## Step 2: Confidence Update (ESSENTIAL — this is how lessons graduate)

```python
python -c "
import sys; sys.path.insert(0, 'C:/Users/olive/SpritesWork/brain/scripts')
from wrap_up import update_confidence
update_confidence(SESSION)
"
```

Promotes INSTINCT→PATTERN→RULE based on confidence scores. Also runs
judgment decay (idle lessons lose confidence) and flags UNTESTABLE lessons
for archival.

## Step 3: Session Score (IMPORTANT — data point for brain report card)

Classify session type (`full` or `systems`) and emit AUDIT_SCORE:
```python
python -c "
import sys; sys.path.insert(0, 'C:/Users/olive/SpritesWork/brain/scripts')
from wrap_up import emit_session_score
emit_session_score(SESSION, {'combined_avg': SCORE, 'session_type': TYPE})
"
```
Score from 0-10 based on: corrections received, outputs produced, gates passed,
lessons learned. This feeds the brain report card trend. Without it, brain
scores degrade silently because audit_trend() has no data.

Also: if this was a prospect session with tagged interactions, recalculate
PATTERNS.md rates (reply rates by angle/tone/persona). Skip for systems sessions.

## Step 4: Deferred Items (IMPORTANT — prevents context loss)

Scan conversation for "next session", "do later", "put on list", "deferred".
Emit DEFER events:
```python
python -c "
import sys; sys.path.insert(0, 'C:/Users/olive/SpritesWork/brain/scripts')
from events import emit
emit('DEFER', 'wrap_up', {'item': 'EXACT_WORDING', 'reason': 'WHY'}, session=N)
"
```
Check existing Deferred in loop-state.md — emit DEFER_RESOLVED for any resolved.

## Step 5: Handoff Files (IMPORTANT — next session starts clean)

**5a — Update startup-brief.md** (## Handoff section):
- Last session: what was done
- What was half-done
- Decisions pending Oliver
- First thing next session (numbered priority list)
- System changes to verify

**5b — Write continuation.md**:
```bash
python C:/Users/olive/SpritesWork/brain/scripts/continuation.py create
```

**5c — Update loop-state.md**: Session number, pipeline summary, what changed,
next session tasks, deferred items.

**5d — Prospect notes** (only if prospects were touched): Update
`brain/prospects/[Name] — [Company].md` while context is fresh.

## Step 6: Validator (ESSENTIAL — catches broken pipes)

```bash
python brain/scripts/wrap_up_validator.py --session N --date YYYY-MM-DD --session-type [full|systems]
```

19 binary checks. Auto-fix handles: session note, STEP_COMPLETE events,
agent distillation, startup-brief/loop-state headers. Target: 19/19 (100%).
Re-run until clean.

## Step 7: Agent Distillation (IMPORTANT — agents compound too)

```python
python -c "
import sys; sys.path.insert(0, 'C:/Users/olive/SpritesWork/brain/scripts')
sys.path.insert(0, 'C:/Users/olive/OneDrive/Desktop/Sprites Work/sdk/src')
from aios_brain.enhancements.agent_graduation import AgentGraduationTracker
tracker = AgentGraduationTracker('C:/Users/olive/SpritesWork/brain')
distilled = tracker.distill_upward()
if distilled:
    print(f'{len(distilled)} agent lesson(s) ready for brain-level promotion')
    for d in distilled:
        print(f'  [{d[\"state\"]}] {d[\"agent_type\"]}: {d[\"description\"][:80]}')
"
```

Review distilled lessons. Promote worthy ones to brain-level lessons.md.

## Step 8: Summary (show Oliver)

```
WRAP-UP: [N]/10 steps | [session_type]
  Gate: [X]/[Y] ([Z]%)
  Learned: [N] lessons | [N] graduated | [N] corrections
  Agents: [N] types | [avg FDA]% | gate changes: [list]
  Saved: [files written]
  Next: [top 3 priorities]
```

Details only surface on skip/failure.

## Step 9: Git Commit

```bash
cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && git add -A && git commit -m "S[N]: [summary]"
```

## Step 10: Wrap-Up Reviewer (background, non-blocking)

Spawn the `wrapup-reviewer` agent in background AFTER commit. It verifies all 10 steps
ran correctly and catches skipped steps. Its findings feed into agent graduation,
so wrap-up quality compounds over time.

```
Spawn agent: wrapup-reviewer (background, haiku)
Prompt: "Review the wrap-up for session [N]. Check all 10 steps executed.
         Report any skipped steps or missing data."
```

This agent's review outcomes are recorded via `record_agent_outcome.py`. If it
consistently catches the same skipped step, that becomes a graduated lesson
that prevents future skips. The wrap-up teaches itself to not miss steps.

After major structural changes, prompt Oliver:
> "Tag a stable snapshot? `git tag stable-vX.X -m 'description'`"

---

## What Runs Periodically (NOT every session)

| Task | Frequency | How |
|------|-----------|-----|
| Anti-bloat sweep | Weekly or when line caps hit | `python brain/scripts/anti_bloat.py` |
| PATTERNS.md recalculation | After prospect sessions with new outcomes | Step 7 of old Phase 1 |
| Delta sync verify | At startup (api_sync.py hook), not wrap-up | Automatic |
| Lint (ruff) | CI pipeline or monthly | `ruff check brain/scripts/ --fix` |
| Session note | Auto-created by validator auto-fix | Minimal template |
| NotebookLM feeding | Inline during session when prospect work happens | Not batched at wrap-up |
| Gmail drafts check | Inline when writing emails | Not batched at wrap-up |
| Obsidian brain summary | Written by wrapup-handoff agent if spawned | Optional |

## What's Automated by Hooks (never manual)

| Data | Hook | When |
|------|------|------|
| OUTPUT events | output-event.js | Every Write/Edit to code or prospect files |
| CORRECTION events | capture_learning.py | Every user prompt that contains correction signals |
| Agent outcomes | agent-graduation.js | Every Agent tool completion |
| Agent pre-context | agent-precontext.js | Every Agent tool spawn (injects graduated rules) |
| Human judgments | delta-auto-tag.js | When Oliver edits agent-written files |
| Gate results | gate-emit.js | When gate files are loaded via Read |
| Cost tracking | cost-tracking.js | Session end (Stop event) |
| Session persistence | session-persist.js | Session end (Stop event) |

## Recovery

- **Stable snapshots:** `git tag stable-vX.X` — Oliver decides when to tag
- **Recovery branch:** NEVER auto-updated. Only on explicit instruction:
  `git checkout recovery && git merge stable-vX.X && git checkout master`
