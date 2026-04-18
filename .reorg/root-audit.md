# Sprites Work Root — Bloat & Legacy Audit

**Date:** 2026-04-18 (Session S368, Phase A)
**Purpose:** Classify every top-level item into Gradata / Sprites / Hausgem / Root / Delete, so Phase B + a cleanup pass can execute deterministically.
**Constraint (from S11 note):** `CLAUDE.md` must stay at root — claude hooks resolve it relative to `WORKING_DIR`.

---

## A. Stays at Root (git-repo essentials, cannot move)

| Item | Why |
|------|-----|
| `.git/` | Git repo root. |
| `.gitignore`, `.gitattributes` | Git config. |
| `.github/` | Unused after S367 (`PR #104` deleted all workflows) — verify empty then DELETE. |
| `CLAUDE.md` | Must stay at WORKING_DIR root. |
| `.env`, `.mcp.json` | Secrets, gitignored. Stay where hooks expect. |
| `.claude/` | Per-project claude config (worktrees live here). |
| `.agentignore`, `.claudeignore` | Ignore files read at root. |
| `.vscode/`, `.obsidian/`, `.codex/` | Editor/tool state, gitignored. |

## B. Move to `Gradata/` (public product/SDK — Phase B script handles)

| Item | Notes |
|------|-------|
| `src/` → `Gradata/src/` | SDK package source |
| `tests/` → `Gradata/tests/` | |
| `docs/` → `Gradata/docs/` | Strip private docs (see section E) before move |
| `pyproject.toml`, `uv.lock`, `.venv/` | Python project root follows SDK |
| `README.md`, `CHANGELOG.md`, `LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CREDITS.md` | Public docs |
| `AGENTS.md` | Public agent docs — move to `Gradata/` |
| `mkdocs.yml`, `Dockerfile`, `docker-compose.yml`, `.dockerignore` | Deploy config |
| `packages/`, `gradata-install/`, `gradata-plugin/` | npm distribution |
| `examples/`, `scripts/`, `hooks/` | Public SDK tooling (audit first — some `scripts/*` may be sales-only) |
| `design-system/` | UI design tokens (SDK website uses it) |
| `package.json`, `package-lock.json`, `node_modules/` | Docs/website npm |

## C. Move to `Sprites/` (sales + 9-5 + dogfood)

| Item | Notes |
|------|-------|
| `.forge/` → `Sprites/.forge/` | Sales persona config (ex-`.carl/`) |
| `domain/` → `Sprites/domain/` | Persona content (ex-`domain/carl/`) |
| `Leads/` → `Sprites/Leads/` | Active lead CSVs (`apollo-leads-*.csv`) |
| `sessions/` → `Sprites/sessions/` | S114-S116 handoff notes (private, gitignored) |
| `C:/Users/olive/SpritesWork/brain/` → `Sprites/brain/` | **CROSS-DRIVE MOVE** — the real brain runtime. Phase B script handles. |

## D. Move to `Hausgem/`

Currently empty. No content to move yet — placeholder scaffold only.

## E. DELETE (bloat / legacy / regenerable)

### E1 — Regenerable caches (delete now, no risk)

| Item | Size | Why delete |
|------|------|-----------|
| `.coverage` | 114 KB | pytest coverage artifact, regenerates on `pytest --cov` |
| `.pytest_cache/` | — | pytest cache |
| `.ruff_cache/` | — | ruff linter cache |
| `.code-review-graph/` | — | graph cache (regenerable via `code-review-graph update`) |
| `graphify-out/` | — | graphify tool output (already gitignored) |
| `.graphify_analysis.json`, `.graphify_ast.json`, `.graphify_auto_labels.json`, `.graphify_cached.json`, `.graphify_chunks.json`, `.graphify_chunks_in/`, `.graphify_chunks_out/`, `.graphify_detect.json`, `.graphify_extract.json`, `.graphify_labels.json`, `.graphify_python`, `.graphify_semantic.json`, `.graphify_semantic_new.json`, `.graphify_uncached.txt` | — | Graphify intermediates. **ADD to .gitignore** then delete. |
| `.graphify_autolabel.py`, `.graphify_relabel.py`, `.graphify_viz.py` | — | One-off python helpers for graphify. If reusable, move to `scripts/`. Else DELETE. |
| `brain.manifest.json` | 10 KB | Regenerates from brain |
| `system.db` at root | 106 KB | **Likely a stray** — real `system.db` is inside `brain/`. Verify then DELETE the root copy. |
| `run.log` | 141 B | Ephemeral |
| `vendor/` | — | Pre-bundled deps, already gitignored, regenerable via install |
| `.tmp/` | Large | Has `ablation_s105/`, `archon-plans/`, `audits/`, `autoresearch/` — most are experiment leftovers. AUDIT each subdir before purge. |
| `.venv/` | Large | Regenerate via `uv sync` |
| `node_modules/` | Large | Regenerate via `npm install` |

### E2 — Dead tool installs (likely abandoned)

| Item | Last modified | Check & delete if unused |
|------|--------------|--------------------------|
| `.agents/` | 2026-04-05 | Old agent registry — superseded by `.claude/agents/` |
| `.archon/` | 2026-04-14 | Archon plugin state |
| `.claude-flow/` | 2026-04-05 | Claude-flow data (config says data dir ignored) |
| `.claude-plugin/` | 2026-04-15 | Plugin marketplace metadata — KEEP if publishing skills |
| `.gstack/` | 2026-04-09 | Gstack tool state |
| `.gitnexus/` | 2026-04-12 | Gitnexus tool state |
| `.wrangler/` | 2026-04-15 | Cloudflare wrangler state — keep if deploying workers |
| `.opencli/` | 2026-04-18 | Opencli state (regenerates on session) |
| `.superpowers/` | 2026-04-09 | Superpowers plugin state |
| `.planning/` | 2026-04-14 | Gitignored — dev notes |

### E3 — Sessions' stale worktrees

From `git worktree list` — 3 inner worktrees under `.claude/worktrees/`. Per S367 loop-state line 19: "56+ orphaned worktrees... safe to prune". Prune list:
```
git worktree list --porcelain | grep -B1 "branch " | ...  # (manual review recommended)
git worktree prune
```

## F. Deferred decisions (need Oliver input)

1. **`.github/workflows/` deletion** — all workflows were removed in PR #104. Is `.github/` dir still needed for ISSUE templates, etc.?
2. **`docs/research/` vs `research/`** — .gitignore excludes `research/` but includes `docs/research/`. Which is canonical?
3. **`brain/` at Sprites Work root** — only contains `scripts/`. Is this a leftover shim? Real brain is `C:/Users/olive/SpritesWork/brain/`. Safe to delete?
4. **`system.db` at root** — is this a test artifact or a second brain instance? If test: delete. If real data: move to brain/.
5. **`.venv/` location** — should it be inside `Gradata/` (next to pyproject.toml) post-Phase-B?

---

## Proposed execution order

1. **Pre-Phase-B (safe now):** Delete section E1 regenerable caches + section E2 items Oliver confirms abandoned.
2. **Phase B (offline):** Run `.reorg/phase-b.ps1` to execute sections B + C + part of D.
3. **Post-Phase-B:** Answer section F questions, then targeted cleanup.

## Not covered here

- CARL framework scrub (done in Phase A, S368) — see commit history
- Desktop-level orphan deletes (done in Phase A: 6 deleted, 1 deferred to Phase B for OneDrive reasons)
- Eventual `Sprites Work` → `Claude Code` rename (deferred — other terminals reference the old name)
