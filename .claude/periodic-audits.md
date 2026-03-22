# Periodic Audit Schedule
# Checked at session start (Phase 0.5). Run audits when their trigger fires.
# Session number comes from brain/loop-state.md or startup-brief.md header.

## How It Works
At session start, read the `last_run` values below. If the trigger condition is met,
queue the audit to run at an appropriate time (noted per audit). After running, update
the `last_run` session number here immediately.

---

## /sdk-audit — SDK Boundary Enforcement
- **Frequency:** Every 5 sessions, OR immediately after modifying: CLAUDE.md, agents/registry.md, any hook file, any RAG script
- **When to run:** During session, after startup completes (not blocking)
- **Last run:** S0
- **Trigger:** Also fires when changelog entry mentions core architecture changes
- **Action:** Run /sdk-audit. Report to Oliver. No auto-edits.

## Memory Index Cleanup
- **Frequency:** Every 10 sessions
- **When to run:** During wrap-up (step 7, anti-bloat)
- **Last run:** S0
- **Action:** Read MEMORY.md index. For each memory file: (1) does it still exist? (2) is it still accurate? (3) is it duplicated by CLAUDE.md or lessons.md? Remove dead pointers, flag stale content, merge duplicates. Report changes.

## RAG Freshness Check
- **Frequency:** Every 3 sessions
- **When to run:** During session start (Phase 0.5)
- **Last run:** S0
- **Action:** Run `python brain/scripts/embed.py --stats` and compare chunk count to brain file count. If delta embed has >10 unembedded files, flag it. If manifest is >3 sessions stale, run delta embed automatically.

## Self-Audit — Compounding Intelligence Review
- **Frequency:** Every 10 sessions
- **When to run:** Reminder surfaces at wrap-up. Run before closing or first thing next session.
- **Last run:** S0
- **Action:** Run skills/self-audit/SKILL.md. Three lenses: error pattern analysis, outcome retrospective, judgment calibration. Each lens can run independently. Outputs append to brain/vault/outcome-retrospectives.md and brain/vault/judgment-calibration.md. Never auto-edits core files. All promotions require Oliver's approval.

## Config Bloat Scan
- **Frequency:** Every 10 sessions
- **When to run:** During wrap-up (step 7, anti-bloat)
- **Last run:** S0
- **Action:** Check total token weight of always-loaded files: CLAUDE.md + context-manifest.md + .carl/global + domain/carl/global + lessons.md. If combined exceeds 12k tokens (estimated via word count * 1.3), flag specific files that grew and suggest pruning. Also check settings.json hook count — flag if >10 hooks (complexity creep).
