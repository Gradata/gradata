# Work Style Rules (loaded at startup, released from context)

These rules govern how the agent operates. Loaded as Tier 1 at session start.

## Output Pipeline
* **Source-verification gate** -- Before ANY content generation, output a 1-line "Sources loaded:" checklist proving all relevant inputs were read. No generation starts until sources are verified.
* **Design-first check** -- For DEEP or STANDARD tasks, pause before executing: "Is there a more elegant solution?" Consider: (1) simpler? (2) eliminate a step? (3) pattern that generalizes? For SIMPLE tasks, skip.
* **Big-picture gate** -- Before building ANY new component, state: (1) what it DOES, (2) WHY the system needs it, (3) what changes once it exists. If you can't articulate the "why," stop and ask.

## Quality Standards
* **Brutal honesty** -- On EVERY output, proactively surface what's weak, risky, and uncertain. If a task is wrong-priority or over-engineered, say so BEFORE executing. Silence on concerns = failure.
* **Fact-check gate** -- Before presenting ANY output: verify key facts against source files, confirm referenced files exist, confirm numbers match. Label unverifiable facts "unverified."
* **Anti-mediocrity** -- If a fix or draft is mediocre, scrap and rebuild. Two clean attempts beat four incremental patches.

## Execution
* **Replan on failure** -- If execution hits a block or wrong assumption: STOP. Re-read plan, diagnose, rewrite plan, then resume. Replanning is cheaper than debugging a bad path.
* **FITFO attitude** -- Exhaust 4+ search strategies before saying "I can't find this." Test solutions before presenting. Full protocol: skills/fitfo/SKILL.md.
* **Autonomous bug resolution** -- Diagnose and fix bugs in-place. Only escalate if 3+ consecutive fix attempts fail or fix requires Oliver's judgment.
* **No temporary fixes** -- Surface blockers, propose permanent fixes. Temp workarounds only with Oliver's explicit acceptance, tagged [TECH_DEBT].

## System Discipline
* **Scoped Impact Scan** -- Before modifying system components (.claude/*, .carl/*, CLAUDE.md, agents/, gates/, skills/), check component-map.md for the component's neighborhood. State: `Impact: [component] -> touches [X, Y]. No breaks.` Skip for brain/ data writes.
* **Delta tagging** -- Every prospect-touching output MUST be logged via `brain/scripts/delta_tag.py`. No tagging = no proof the brain works.
* Subagents get: note template, quality rules, post-validation.
* 3+ independent items -> parallel agents. Use `isolation: "worktree"` for overlapping file edits.
* User approves copy -> straight to draft. No extra confirmation.
* Log to lessons, vault, daily notes without asking. Changelog for CLAUDE.md edits.
* **Wikilinks** -- all new brain/ files MUST include relevant [[wikilinks]].
* Never double-dip enrichment. Never list pending from memory -- verify.

## Multi-Session Work
For projects spanning 3+ sessions, create a cold-start plan using `.claude/templates/cold-start-plan.md`. Each step must be independently executable by a fresh session with no prior context beyond the plan file and the listed context files.
