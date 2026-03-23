# AIOS Brain SDK + Marketplace — MVP Roadmap

## Vision

Open-source SDK that lets anyone build, train, and share personal AI brains. Marketplace where trained brains are rented (not sold) — streaming access keeps brains improving, prevents cloning, and creates recurring revenue for creators. The WordPress/Spotify hybrid for AI expertise.

## What's Built

### Core SDK (aios_brain/)
- [x] Brain class with full API surface (init, search, emit, embed, manifest, export, context_for, stats)
- [x] CLI (`aios-brain`) with 10 subcommands (init, search, embed, manifest, stats, audit, export, context, validate, install)
- [x] Onboarding wizard with interactive and non-interactive modes
- [x] pyproject.toml with hatchling build, pip-installable as `aios-brain`
- [x] `__init__.py` with clean public API (`Brain`, `onboard`, `__version__`)
- [x] `_paths.py` module for brain directory resolution
- [x] `_config.py` configuration module
- [ ] Published to PyPI
- [ ] Automated CI/CD pipeline for releases
- [ ] Type stubs / py.typed marker for IDE support

### Retrieval (semantic search + context)
- [x] Local embeddings via sentence-transformers (all-MiniLM-L6-v2, 384d, no API key)
- [x] ChromaDB vector store integration (`_embed.py`)
- [x] FTS5 full-text search (`_query.py` with `brain_search`, `fts_rebuild`)
- [x] Hybrid search (vector + keyword, auto-selects best mode)
- [x] Context compiler (`_context_compile.py`) — auto-injects relevant brain knowledge
- [x] Context packet builder (`_context_packet.py`)
- [x] Delta embedding with hash tracking (`.embed-manifest.json`)
- [x] Fact extractor (`_fact_extractor.py`) — structured facts from knowledge files
- [ ] Gemini embedding provider option (declared in config, not tested in SDK standalone)
- [ ] Embedding provider plugin architecture (swap models without code changes)

### Quality System
- [x] Event emitter with dual-write (SQLite + JSONL) (`_events.py`)
- [x] Tag taxonomy with closed vocabulary and auto-enrichment (`_tag_taxonomy.py`)
- [x] Data flow audit (`_data_flow_audit.py`) — end-to-end pipe verification
- [x] Brain stats module (`_stats.py`)
- [ ] Self-improvement pipeline (INSTINCT -> PATTERN -> RULE) — exists in brain/scripts, not promoted to SDK
- [ ] Lesson graduation tracking — exists in brain/scripts, not in SDK
- [ ] Judgment decay — exists in brain/scripts, not in SDK
- [ ] Session scorer — exists in brain/scripts, not in SDK
- [ ] Correction rate computation — manifest references it but SDK doesn't compute it standalone

### Manifest & Packaging
- [x] brain.manifest.json v1.0.0 schema (metadata, quality, RAG, behavioral_contract, tag_taxonomy, bootstrap, compatibility)
- [x] Manifest generator (`_brain_manifest.py`)
- [x] Export with PII sanitization (`_export_brain.py`) — redacts emails, phones, names, API keys, paths
- [x] Export modes: full, no-prospects, domain-only
- [x] Prospect anonymization (name -> `[PROSPECT_N]`, company -> `[COMPANY_N]`)
- [x] Memory type classification (episodic, semantic, procedural, strategic)
- [ ] Manifest schema validation (JSON Schema definition file that external tools can validate against)
- [ ] Manifest versioning/migration (v1 -> v2 upgrade path)

### Installation
- [x] Brain installer (`brain_install.py`) — extracts from zip, validates compatibility, runs bootstrap
- [x] Install metadata tracking (`.install-meta.json`)
- [x] `--list` to show installed brains (stored in `~/.aios/brains/`)
- [x] `--dry-run` preview mode
- [x] Compatibility checker (Python version, chromadb dependency)
- [x] CLI wiring (`aios-brain install`)
- [ ] Uninstall command
- [ ] Upgrade command (install newer version of existing brain)

### Validation & Trust
- [x] 5-dimension brain validator (metric integrity, training depth, learning signal, data completeness, behavioral coverage)
- [x] Trust grading: A-F with verdicts (TRUSTED/VERIFIED/PROVISIONAL/CAUTION/UNTRUSTED)
- [x] Weighted scoring (metric integrity 30%, learning signal 25%, training depth 20%, data completeness 15%, behavioral coverage 10%)
- [x] CLI wiring (`aios-brain validate`, `--strict`, `--json`)
- [x] Validation report saving to `brain/validations/`
- [ ] Validator runs as SDK-native code (currently imports from brain/scripts via sys.path hack)

### Shim Architecture (SDK canonical, brain/scripts as wrappers)
- [x] SDK modules are canonical: `_embed.py`, `_query.py`, `_events.py`, `_brain_manifest.py`, `_export_brain.py`, `_context_compile.py`, `_fact_extractor.py`, `_tag_taxonomy.py`, `_data_flow_audit.py`
- [x] `brain/scripts/export_brain.py` imports from SDK (`from aios_brain._export_brain import *`) and adds brain-only overrides
- [ ] Most brain/scripts still standalone, not shimmed to SDK (embed.py, query.py, events.py, context_compile.py, fact_extractor.py, brain_manifest.py all have their own implementations)
- [ ] brain_validator.py is standalone, not shimmed to SDK
- [ ] brain_install.py is standalone, not shimmed to SDK

### Tests
- [x] Test suite exists (`sdk/tests/test_brain.py`) with 7 test classes
- [x] Tests cover: init, duplicate detection, event emission, tag enrichment, keyword search, manifest generation, validator, export PII redaction
- [ ] No CI/CD running tests automatically
- [ ] No tests for: semantic search, context compilation, fact extraction, install flow, embed delta logic
- [ ] No tests for error paths (missing dependencies, corrupt DB, bad manifest)

---

## MVP Milestones

### Phase 1: SDK Hardening (S40-S50)

The goal is a self-contained SDK that works on any machine without Oliver's brain directory. Currently, `aios-brain validate` does a `sys.path.insert` into `brain/scripts/` — that cannot ship.

**Function Promotion (brain-only -> SDK)**
- [ ] Promote `brain_validator.py` logic into `aios_brain/_validator.py` (remove sys.path hack from cli.py)
- [ ] Promote `brain_install.py` logic into `aios_brain/_installer.py` (remove sys.path hack from cli.py)
- [ ] Shim remaining brain/scripts to import from SDK (embed.py, query.py, events.py, brain_manifest.py, context_compile.py, fact_extractor.py)
- [ ] Self-improvement pipeline: extract core graduation logic into SDK (instinct -> pattern -> rule state machine)

**Test Suite Completion**
- [ ] Tests for semantic search (embed a file, search by meaning)
- [ ] Tests for context compilation (message -> relevant context)
- [ ] Tests for install flow (zip -> installed brain -> usable)
- [ ] Tests for embed delta (modify file, re-embed, verify only changed file re-embedded)
- [ ] Tests for error paths: missing chromadb, corrupt system.db, malformed manifest
- [ ] Tests for stats output structure
- [ ] Target: 90%+ coverage on SDK public API

**Error Handling**
- [ ] Graceful error when chromadb not installed (currently crashes on import)
- [ ] Graceful error when sentence-transformers not available
- [ ] Helpful error messages for common problems (wrong Python version, missing DB tables, manifest schema mismatch)
- [ ] `aios-brain doctor` command: checks environment, dependencies, brain health

**Documentation**
- [ ] README rewrite for external developers (current README is accurate but assumes context)
- [ ] Inline docstrings audit (every public method documented with Args, Returns, Raises)
- [ ] CONTRIBUTING.md with brain-layer vs runtime-layer classification rules

**First External Validation**
- [ ] Oliver installs SDK on a second machine via `pip install ./sdk`
- [ ] Run `aios-brain init ./test-brain --domain Testing --no-interactive`
- [ ] Verify full cycle: init -> add files -> embed -> search -> emit events -> manifest -> validate -> export -> install on third location
- [ ] Document every failure and fix it

**Estimated effort:** 8-10 sessions (S40-S50)

### Phase 2: Marketplace Foundation (S50-S70)

**Rent Protocol Spec**
- [ ] Design doc: how streaming access works (API layer? Local proxy? Encrypted runtime?)
- [ ] Define brain access tiers: preview (manifest + sample search), trial (time-limited full access), rent (ongoing access)
- [ ] Define what "renting" means technically: does the renter get the brain files? Or do queries route through the creator's hosted instance?
- [ ] Security model: how to prevent brain file extraction during rental
- [ ] Write the spec as a markdown doc with protocol diagrams

**brain-publish Command**
- [ ] `aios-brain publish` — validates brain, exports, uploads to registry
- [ ] Pre-publish checklist: trust grade >= C, manifest valid, no PII in export, at least 10 sessions trained
- [ ] Publish metadata: pricing, description, sample queries, trust grade, domain, session count
- [ ] Versioned publishing (v1.0.0, v1.1.0 — renters get latest)

**Registry Design**
- [ ] Evaluate options: GitHub Packages, custom registry on Cloudflare/Vercel, PyPI-adjacent
- [ ] Registry API spec: list brains, get manifest, download, verify signature
- [ ] Brain discovery: search by domain, trust grade, session count, tag taxonomy
- [ ] Decision: start with GitHub Releases as MVP registry (free, version-controlled, no infrastructure)

**Auth & Access Control**
- [ ] API key generation for brain creators and renters
- [ ] Access token scoping: read-only (renter), read-write (creator), admin
- [ ] Revocation: creator can revoke renter access
- [ ] Usage tracking: queries per renter per brain per day

**Pricing Model**
- [ ] Define pricing tiers: free (preview), paid (monthly rental)
- [ ] Creator revenue split (e.g., 80% creator / 20% platform)
- [ ] Usage-based vs flat-rate evaluation
- [ ] Stripe integration spec (or alternative for MVP)

**Estimated effort:** 15-20 sessions (S50-S70)

### Phase 3: Beta Launch (S70-S90)

**Example Brains**
- [ ] Sales brain (Oliver's — sanitized, exported, published as reference implementation)
- [ ] Engineering brain (scaffold + 20 sessions of training on a real codebase)
- [ ] Support brain (scaffold + 20 sessions of training on a real helpdesk)
- [ ] Each brain must pass validator at Grade B or higher

**Creator Onboarding**
- [ ] `aios-brain create-brain` wizard with domain templates
- [ ] Training guide: how to produce high-quality training sessions
- [ ] Quality dashboard: live view of trust grade, correction trend, lesson graduation rate
- [ ] Publishing guide: from trained brain to listed marketplace brain

**Renter Onboarding**
- [ ] `aios-brain browse` — search and preview available brains
- [ ] `aios-brain rent <brain-id>` — subscribe and install
- [ ] `aios-brain try <brain-id>` — time-limited trial
- [ ] Tutorial: how to integrate a rented brain into your workflow

**Landing Page**
- [ ] Single-page site explaining the concept (brain training -> marketplace -> rental)
- [ ] Live demo: query a real brain, see results
- [ ] Creator signup form
- [ ] Renter waitlist

**Payment Integration**
- [ ] Stripe checkout for brain rental
- [ ] Creator payout dashboard
- [ ] Subscription management (upgrade, downgrade, cancel)

**Estimated effort:** 15-20 sessions (S70-S90)

### Phase 4: Public Launch (S90+)

**Open Source**
- [ ] GitHub repo: `spritesai/aios-brain` (repo URL already in pyproject.toml)
- [ ] MIT license (already declared)
- [ ] Clean git history (no Oliver-specific data in commits)
- [ ] GitHub Actions CI: tests, linting, type checking on every PR
- [ ] PyPI publishing workflow (GitHub Actions -> PyPI on tag)

**Marketplace Live**
- [ ] Registry operational with at least 3 brains
- [ ] Payment processing working
- [ ] Creator and renter accounts functional
- [ ] Brain update pipeline: creator publishes new version, renters auto-upgrade

**Documentation Site**
- [ ] Hosted docs (GitHub Pages, Mintlify, or similar)
- [ ] Guides: Getting Started, Training Your Brain, Publishing, Renting, API Reference
- [ ] Architecture deep-dive for contributors

**Community**
- [ ] Discord or GitHub Discussions for brain creators
- [ ] Brain showcase: featured brains with trust scores
- [ ] Contributor guidelines for SDK development
- [ ] First 10 external brain creators onboarded

**Estimated effort:** 10-15 sessions (S90-S105)

---

## Checklist

Every task needed to reach MVP, organized by phase. Completed items reference the session they were done in.

### Phase 1: SDK Hardening (S40-S50)

```
- [x] Brain class with init/search/embed/emit/manifest/export/context_for/stats (S39)
- [x] CLI with 10 subcommands (S39-S40)
- [x] Onboarding wizard, interactive + non-interactive (S39)
- [x] pyproject.toml pip-installable package (S39)
- [x] Local embeddings working without API key (S39)
- [x] FTS5 + ChromaDB hybrid search (S39)
- [x] Context compiler (S39)
- [x] Fact extractor (S39)
- [x] Tag taxonomy with auto-enrichment (S39)
- [x] brain.manifest.json v1.0.0 schema (S39)
- [x] Export with PII sanitization (S39)
- [x] Brain validator, 5 dimensions, trust grading (S40)
- [x] Brain installer with bootstrap (S40)
- [x] Data flow audit (S39)
- [x] Test suite: 7 test classes covering core flows (S40)
- [ ] Promote brain_validator into SDK (remove sys.path hack) ~1 session
- [ ] Promote brain_install into SDK (remove sys.path hack) ~1 session
- [ ] Shim all brain/scripts to import from SDK ~2 sessions
- [ ] Extract self-improvement state machine into SDK ~1 session
- [ ] Tests for semantic search ~0.5 session
- [ ] Tests for context compilation ~0.5 session
- [ ] Tests for install flow ~0.5 session
- [ ] Tests for embed delta logic ~0.5 session
- [ ] Tests for error paths (missing deps, corrupt data) ~1 session
- [ ] Graceful error handling for missing chromadb/sentence-transformers ~0.5 session
- [ ] `aios-brain doctor` environment check command ~0.5 session
- [ ] README rewrite for external developers ~1 session
- [ ] Docstring audit on all public methods ~0.5 session
- [ ] CONTRIBUTING.md ~0.5 session
- [ ] Second-machine install test (full cycle validation) ~1 session
- [ ] Fix every failure found in second-machine test ~1-2 sessions
```

### Phase 2: Marketplace Foundation (S50-S70)

```
- [ ] Rent protocol spec (design doc) ~2 sessions
- [ ] Brain access tiers definition (preview/trial/rent) ~1 session
- [ ] Security model for brain file protection ~2 sessions
- [ ] `aios-brain publish` command ~2 sessions
- [ ] Pre-publish validation checklist ~0.5 session
- [ ] Registry design decision (GitHub Releases for MVP) ~1 session
- [ ] Registry API spec ~2 sessions
- [ ] Brain discovery/search in registry ~1 session
- [ ] API key generation for creators and renters ~2 sessions
- [ ] Access token scoping and revocation ~2 sessions
- [ ] Usage tracking ~1 session
- [ ] Pricing model design ~1 session
- [ ] Stripe integration spec ~1 session
- [ ] `aios-brain uninstall` command ~0.5 session
- [ ] `aios-brain upgrade` command ~1 session
- [ ] Manifest schema JSON Schema file ~0.5 session
- [ ] Manifest migration (v1 -> v2) ~0.5 session
```

### Phase 3: Beta Launch (S70-S90)

```
- [ ] Sales brain exported and published ~1 session
- [ ] Engineering example brain (20 training sessions) ~20 sessions (background)
- [ ] Support example brain (20 training sessions) ~20 sessions (background)
- [ ] All 3 example brains pass validator at Grade B+ ~1 session
- [ ] Creator onboarding wizard ~2 sessions
- [ ] Training quality guide ~1 session
- [ ] Quality dashboard (terminal UI) ~2 sessions
- [ ] Publishing guide ~1 session
- [ ] `aios-brain browse` command ~1 session
- [ ] `aios-brain rent` command ~2 sessions
- [ ] `aios-brain try` command ~1 session
- [ ] Renter tutorial ~1 session
- [ ] Landing page ~2 sessions
- [ ] Live demo on landing page ~1 session
- [ ] Stripe checkout integration ~2 sessions
- [ ] Creator payout dashboard ~2 sessions
- [ ] Subscription management ~1 session
```

### Phase 4: Public Launch (S90+)

```
- [ ] GitHub repo created and cleaned ~1 session
- [ ] GitHub Actions CI (tests + lint + type check) ~1 session
- [ ] PyPI publishing workflow ~1 session
- [ ] First PyPI release (v0.1.0) ~0.5 session
- [ ] Registry operational with 3+ brains ~1 session
- [ ] Payment processing live ~1 session
- [ ] Brain auto-upgrade pipeline ~1 session
- [ ] Documentation site deployed ~2 sessions
- [ ] 5 guides written (Getting Started, Training, Publishing, Renting, API Reference) ~3 sessions
- [ ] Architecture deep-dive doc ~1 session
- [ ] Discord or GitHub Discussions set up ~0.5 session
- [ ] Brain showcase page ~1 session
- [ ] Contributor guidelines ~0.5 session
- [ ] First 10 external creators onboarded ~5 sessions (calendar time)
```

---

**Total estimated effort to public launch: ~90-110 sessions from S40.**
At current pace (high-output build sessions, ~2-3 per week), that puts public launch around late 2026 / early 2027.

**Critical path:** Phase 1 (SDK hardening) is the only blocker. Phases 2-4 can start before Phase 1 is 100% complete, but no external user should touch the SDK until the second-machine install test passes cleanly.
