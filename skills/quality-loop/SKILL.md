---
name: quality-loop
description: Use when user wants to Run every 5 sessions to evaluate and improve the entire Sprites sales ops system. Reads session summaries, grades workflow execution, identifies degradation, and auto-fixes skills, CARL domains, and rules. Use this skill when Oliver says "run quality check", "quality loop", "evaluate the system", "how are we doing", "system health", or when the session counter in brain/sessions/ hits a multiple of 5. Also trigger proactively if you notice repeated mistakes or skipped steps across sessions.
---

# Quality Loop — Self-Improving Sales Ops

## Why This Exists
Without periodic evaluation, skills drift, notebooks go stale, and bad habits compound. This skill runs an evaluator that grades recent performance, then an improver that fixes what's broken. The result: every 5 sessions, the system gets measurably better.

## When to Run
- Every 5 sessions (count files in `C:/Users/olive/SpritesWork/brain/sessions/`)
- When Oliver explicitly asks for a quality check
- When you notice the same mistake appearing in `lessons.md` more than twice

## Phase 1: Gather Evidence

Read these data sources to understand what happened in the last 5 sessions:

1. **Session summaries** — `C:/Users/olive/SpritesWork/brain/sessions/` (last 5 files)
2. **Lessons log** — `.claude/lessons.md` (any new entries since last quality loop)
3. **Notebook feed directory** — `docs/Exports/notebook-feeds/` (what was actually fed back)
4. **Brain prospect notes** — `C:/Users/olive/SpritesWork/brain/prospects/` (were they updated?)
5. **Google Sheets** (if connected) — NotebookLM Feed Log sheet (was call data fed back?), Weekly Metrics sheet (emails sent, demos booked, deals progressed), Campaign tracking sheets (funnel progression per campaign)
5. **Pipeline snapshot** — `C:/Users/olive/SpritesWork/brain/pipeline/` (latest file)
6. **docs/startup-brief.md** — is it current?
7. **Gmail drafts** — any approved but unsent?
8. **Calendar** — any demos that happened without prep docs?

## Phase 2: Score — The Quality Scorecard

Grade each dimension on a 1-5 scale with specific evidence:

### Workflow Execution (did we follow the process?)
| Metric | How to Measure | Target |
|--------|---------------|--------|
| Brain update rate | % of prospects touched that got a brain note updated | 100% |
| Notebook feed rate | % of calls/demos that fed data back to notebooks | 100% |
| Research depth | Did we use NotebookLM + web research, or just Apollo? | Always multi-source |
| Email quality | Did emails reference real call data + NotebookLM case studies? | Always personalized |
| Research order followed | Did we check brain → free web → Apollo → Clay? | Always in order |
| CARL domains loaded | Were the right domains activated for each task? | Always matched |

### System Health (is the infrastructure working?)
| Metric | How to Measure | Target |
|--------|---------------|--------|
| Notebook freshness | When was each notebook last fed? Any >2 weeks stale? | Fed every session |
| Brain completeness | Do all active pipeline prospects have brain notes? | 100% coverage |
| lessons.md growth | Are new lessons being added? Are old ones being fixed? | Growing + pruning |
| startup-brief accuracy | Does it match actual pipeline state? | Always current |
| Stale files | Any orphaned CSVs, duplicate prep docs, wrong-folder files? | Zero stale files |

### Output Quality (are we producing good work?)
| Metric | How to Measure | Target |
|--------|---------------|--------|
| Demo prep completeness | Did prep docs include NotebookLM intelligence? | Always enhanced |
| Email personalization | Did every email have a prospect-specific element? | 100% |
| Follow-up speed | Time from call end to follow-up email draft | Same session |
| Case study match | Did we use the right case study for the prospect profile? | Always profile-matched |

## Phase 3: Diagnose — Pattern Analysis

Look for these failure patterns:

**Regression** — A metric that was good 5 sessions ago is now bad. Why?
**Plateau** — A metric that should be improving isn't. What's blocking it?
**Skip pattern** — A step that keeps getting skipped (check lessons.md for repeats)
**Tool failure** — An API or MCP that's consistently failing (check for logged errors)
**Stale knowledge** — Notebooks or brain notes that haven't been updated despite activity

## Phase 4: Fix — The Improver

For each diagnosed issue, apply the fix immediately:

| Issue Type | Fix Location | Action |
|------------|-------------|--------|
| Skipped step | CARL domain or skill | Add the step explicitly, or strengthen the instruction |
| Wrong data flow | Skill or CARL domain | Fix the notebook ID, path, or tool call |
| Stale notebook | NotebookLM | Feed new data from recent sessions |
| Missing brain note | Obsidian brain | Create the note now from available data |
| Repeated mistake | lessons.md + CLAUDE.md | Promote from lesson to permanent rule |
| Dead reference | Any file | Fix the path or remove the reference |
| Contradicting rules | CARL vs CLAUDE.md | Align to CLAUDE.md (source of truth) |

## Phase 5: Report — Present to Oliver

Output a scorecard:

```
## Quality Loop Report — [Date]
Sessions evaluated: [N]

### Scores (1-5)
- Workflow Execution: X/5
- System Health: X/5
- Output Quality: X/5
- Overall: X/5

### What's Working
- [specific wins from last 5 sessions]

### What Degraded
- [metrics that got worse, with evidence]

### Fixes Applied
1. [what was fixed] → [which file was changed]
2. ...

### Recommendations for Oliver
- [things that need his input or decision]

### Next Quality Loop
- Due after session [N+5]
```

## Phase 6: Track

After running, log the quality loop:
- Save report to `C:/Users/olive/SpritesWork/brain/sessions/[date] — Quality Loop.md`
- Update `docs/startup-brief.md` with any system changes
- If any skills were modified, run a quick integration check (do all notebook IDs still match? do all file paths exist?)

## Session Counter
To know when to trigger, count files in `brain/sessions/`. If the count is a multiple of 5 (or close to it), suggest running the quality loop at the start of the session.
