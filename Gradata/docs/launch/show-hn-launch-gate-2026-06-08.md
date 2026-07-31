# Show HN launch gate checklist — 2026-06-08

Paperclip issue: GRA-2509 (`014ba174-2314-4063-8bc2-a4dc2c3d955b`)

Verdict: NO-GO until the two blocker gates below are cleared.

This artifact is the launch gate checklist, not the launch approval. It separates verified proof from claims that still need implementation or removal before a Hacker News post.

## Gate summary

| Gate | Status | Evidence | Required before posting |
| --- | --- | --- | --- |
| Quickstart works offline | PASS | `env -u BRAIN_DIR -u GRADATA_BRAIN PYTHONPATH=src python3 examples/offline_quickstart_smoke.py` passed on `origin/main` checkout `2b12800`. It exercised CLI help, `init`, `install --agent claude-code --dry-run`, `correct`, `recall`, `stats`, and `audit`. | Keep this smoke command green in CI or rerun immediately before posting. |
| Unsupported public stats removed | BLOCKED | `README.md` still includes public benchmark claims: "Ablation v4 — 4 models × 6 conditions × 16 tasks × 3 iterations = 432 trials", per-model preference/correctness lift table, and random-label-control claims at `README.md:81-94`. Supporting research docs exist, but these are still claims a public launch reader will challenge. | Either link the underlying reproducible report from the README or replace the launch copy with qualitative/product proof only. Do not post unqualified lift numbers. |
| Telemetry measures WAU / active developers | BLOCKED | SDK activation telemetry currently emits one-shot opt-in events only: `brain_initialized`, `first_correction_captured`, `first_graduation`, `first_hook_installed` in `src/gradata/_telemetry.py:90-95`. Hook telemetry summary counts local hook calls/bytes/skips in `src/gradata/hooks/telemetry_summary.py`, not weekly active users/developers. | Add a privacy-preserving recurring active-developer heartbeat or define WAU from backend aggregation of hashed `user_id` events over a 7-day window, then verify with a production query/dashboard. |
| Post copy finalized | READY WITH CAVEATS | Copy below avoids unsupported lift percentages and WAU claims. | Use only after blocker gates are fixed or keep the copy's claims limited to verified install/local-first behavior. |

## Verified command output

Clean worktree source:

```text
/home/olive/work/gradata-sdk/worktrees/gra-2509-show-hn-checklist/Gradata
HEAD: 2b12800 test: cover stale Claude hook pruning (#271)
```

Quickstart smoke command:

```bash
env -u BRAIN_DIR -u GRADATA_BRAIN PYTHONPATH=src python3 examples/offline_quickstart_smoke.py
```

Result excerpt:

```text
✓ claude-code → /tmp/gradata-quickstart-z5f3r54c/home/.claude/settings.json (added)
Correction logged: severity=major, edit_distance=0.76
<brain-rules/>
Brain: /tmp/gradata-quickstart-z5f3r54c/my-brain
  Markdown files: 3
  Database: 0.21 MB
  Has manifest: True
Recall coverage: 0.0%
Agents configured: 1
✓ offline quickstart smoke passed
```

The first run without unsetting `BRAIN_DIR` / `GRADATA_BRAIN` resolved `stats` to `/home/olive/.gradata/brain`; the clean verification run above prevents live-agent environment contamination.

## Claim audit

### Safe launch claims today

- Gradata is local-first procedural memory for AI agents.
- The Python SDK installs and the offline quickstart smoke passes without cloud credentials.
- The installer can dry-run Claude Code hook wiring into an isolated fake home.
- Corrections can be logged locally and recalled through the CLI.
- Telemetry is opt-in and avoids correction text, lesson text, file paths, names, emails, stack traces, and environment variables.

### Claims to avoid until gated

- Any statement that Gradata already has `N` weekly active developers.
- Any claim that current telemetry measures WAU, unless backed by a backend 7-day distinct-user query.
- Unqualified benchmark lift claims in public launch copy unless linked to a reproducible report and methodology.
- "Works with every agent" as an absolute. Use the enumerated installer targets instead: `claude-code`, `codex`, `gemini`, `cursor`, `hermes`, `opencode`.

## Final Show HN copy draft

Title:

```text
Show HN: Gradata — local-first procedural memory for AI coding agents
```

Body:

```text
Hi HN — I’m building Gradata, a local-first SDK that turns corrections into reusable behavioral rules for AI coding agents.

The problem: you correct the same things across sessions — tone, repo conventions, test habits, PR format, safe deploy steps — and the agent forgets. Gradata records those corrections locally, promotes recurring patterns into rules, and injects only the relevant rules back into Claude Code, Codex, Gemini, Cursor, Hermes, or OpenCode.

Quickstart:

  pip install gradata
  gradata init ./my-brain
  gradata install --agent claude-code --brain ./my-brain
  gradata --brain-dir ./my-brain audit

It is Apache-2.0, Python 3.11+, local-first, and cloud credentials are not required for the core loop. The installer smoke test covers init, dry-run hook install, correction logging, recall, stats, and audit in an isolated temp home.

I’m especially interested in feedback from people who use multiple coding agents and keep re-teaching the same repo/team habits. What would make this trustworthy enough to leave running in your dev loop?
```

Do not add benchmark percentages or WAU numbers to the HN body until those gates are cleared.

## Pre-post checklist

- [ ] Re-run: `env -u BRAIN_DIR -u GRADATA_BRAIN PYTHONPATH=src python3 examples/offline_quickstart_smoke.py`
- [ ] Remove or qualify README benchmark stats with links to reproducible research artifacts.
- [ ] Define WAU measurement: 7-day distinct anonymous active developers, source table, query, owner, and dashboard link.
- [ ] Verify telemetry privacy copy still matches `src/gradata/_telemetry.py`.
- [ ] Publish a release tag or commit SHA to link from HN.
- [ ] Use the caveated Show HN copy above; no unsupported numbers.
