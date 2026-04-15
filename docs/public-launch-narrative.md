# Public-Launch Narrative — Draft for Review

This PR prepares Gradata's marketing + credits narrative before going public. It is separate from the cleanup PR so the voice/framing decisions can be reviewed without noise from refactors.

## Why this PR exists

Going public invites two predictable reactions:

1. *"This is just Mem0 / Letta / a prompt library."*
2. *"You didn't invent any of this. You copied X."*

Both reactions dissolve if we lead with transparent attribution. The goal of this PR is to turn potential "you copied X" accusations into credited prior art, and to sharpen the one-sentence pitch so it lands for three different buyers (founder-engineer, OSS believer, enterprise).

## Pieces shipped in this PR

### 1. `CREDITS.md` (new, repo root)

Transparent-synthesis narrative. Credits:

- Research foundations (Constitutional AI, Duolingo half-life regression, Generative Agents, MT-Bench, SuperMemo, Copilot RCT, Grammarly ROI, Persona Transparency Checklist)
- Architectural inspirations (Mem0, Letta, EverMind, 15 agentic patterns)
- Research methodology (MiroFish, Mann-Kendall, OASIS, Karpathy autoresearch)
- Open-source dependencies (summary + pointers to `pyproject.toml` and `package.json`)
- "What's new here" — the graduation pipeline + correction tracking + compound proof

All citations are real papers (Park et al., Settles/Meeder Duolingo, Peng Copilot RCT, Zheng MT-Bench, Wozniak SuperMemo, Anthropic Constitutional AI). No invented citations.

### 2. `README.md` (rewritten top, new section)

**Before:** H1 was `# Gradata — AI that learns your judgment`, then a descriptive paragraph.

**After:**

- Cleaner H1: `# Gradata`
- Tagline H2: `## AI that learns your judgment, not just your preferences.`
- Three-bullet product pitch targeting three buyers at once:
  - Founder-engineer: pragmatic ROI framing ("use Claude or GPT like you already do")
  - OSS believer: AGPL-3.0 + local-first framing
  - Enterprise: "simulation-validated" + "honest metrics, not vanity"
- New `## Intellectual lineage` paragraph pointing to `CREDITS.md`

Preserved: all badges, install instructions, Quick Start, mermaid diagrams, ablation table, CLI, architecture, Community, Contributing, License. Nothing removed beyond the original opening paragraphs, which were absorbed into the new framing.

### 3. `docs/public-launch-narrative.md` (this file)

Explains what changed and why, for review before merge.

## What this PR does NOT do

- Does not change product pricing or feature claims.
- Does not touch `marketing/` — that has its own narrative track.
- Does not invent citations — every paper listed is one Oliver approved.
- Does not remove existing README scaffolding (install, quick start, diagrams, license).

## Suggested review checklist

- [ ] Does the one-sentence pitch in README land for all three buyer profiles?
- [ ] Is `CREDITS.md` generous enough that "you copied X" arguments feel tired on arrival?
- [ ] Are there any sources we should add (papers, systems) before public launch?
- [ ] Is AGPL-3.0 framing in CREDITS the right voice (confident, not apologetic)?

## Follow-ups (not in this PR)

- Marketing site lineage page (separate work under `marketing/`).
- `RESEARCH.md` with longer-form academic framing once the paper is ready.
- Hacker News / launch-post alignment with this same vocabulary.
