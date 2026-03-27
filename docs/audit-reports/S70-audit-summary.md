# Pre-Launch Audit Summary — Session 70

## Fixes Applied (Phase 2-3)

| Fix | Status | Impact |
|-----|--------|--------|
| LICENSE → Gradata Systems | DONE | Legal |
| .gitignore + git rm --cached 19 sensitive files | DONE | IP protection |
| ChromaDB removed from onboard.py | DONE | Broken onboarding fix |
| "sprites" domain removed from _config.py | DONE | Scope leak |
| README QuickStart KeyError fixed | DONE | First-run UX |
| --dangerously-skip-permissions removed from start.py | DONE | Security |
| Skill router expanded: 14 → 116 skills | DONE | Automation coverage |
| Oliver/Anna/Siamak stripped from SDK (14 instances) | DONE | IP/professionalism |
| SQLite context managers (8 call sites in _events.py) | DONE | Windows DB lock fix |
| CLI tests (22 new) | DONE | Coverage: CLI tested |
| Integration tests (31 new) | DONE | Coverage: all 4 adapters tested |
| conftest.py shared fixtures | DONE | Test infrastructure |
| Package rename: aios-brain → gradata | DONE | Brand consistency |
| Tests: 752 → 805 passing, 0 failures | DONE | Quality proof |
| Behavior triggers hook (13 rules) | DONE | Proactive skill firing |

## Agent Reports

### 1. SDK Code Quality — 7/10
**HIGHs:**
- 11 unguarded SQLite connections in `_events.py` (no `with` context managers, connections leak on exception)
- `__import__('sys')` in error handlers instead of normal import

**MEDIUMs:**
- Brain.py god class (30+ methods, 934 lines, 6 concerns)
- `_events.py` mixed responsibilities (683 lines, 5 concerns including 300-line compute_brain_scores)
- embed() catches Exception and returns -1 instead of raising
- Pattern extraction failure silently swallowed with bare `pass`
- 18 bare `except Exception` blocks in `_context_packet.py`
- Type hints missing on public API params (Brain.init domain/name/company)
- `_emit_direct()` zero type annotations
- `patch_anthropic(client: Any)` loses type info

**LOWs:**
- ChromaDB references persist (onboard.py, _paths.py, _doctor.py, _data_flow_audit.py)
- "sprites" domain-specific config in _config.py
- Magic numbers for truncation (2000, 5000) not configurable
- MD5 used for file hashing (compliance flag)

**POSITIVEs:**
- Zero required dependencies
- No eval/exec/pickle/shell=True
- PII sanitization in export
- Zip Slip protection in installer

### 2. SDK Test Coverage — 4/10
**BLOCKERs:**
- CLI (cli.py) completely untested — primary user entry point
- 55% module coverage, ~40% real behavioral (20+ tests are importable-only stubs)

**HIGHs:**
- All 4 integration adapters untested (anthropic, openai, langchain, crewai)
- Cloud client untested (monetization path)
- Sidecar watcher untested (own docs call it "highest-risk gap")
- context_wrapper.py untested ("one-line adaptation" mechanism)
- _doctor.py untested (what users run when broken)
- _installer.py untested (marketplace install)
- _embed.py untested beyond integration
- _context_compile.py untested
- No conftest.py (fixtures copy-pasted 4x)
- reports.py, calibration.py, contextual_bandit.py untested
- edit_classifier: only 2 tests, no category assertions
- pattern_extractor: callable check only
- quality_gates: instantiation only, evaluate() untested
- Error paths not exercised

**Well covered:** brain.correct(), self_improvement (graduation), mcp_server, agent_graduation, loop_intelligence, decay/distill, call/tone profiles

### 3. SDK Architecture — 5/10
**HIGHs:**
- F1: Layer violation — patterns/rule_engine.py imports from enhancements via shim
- F7: Global mutable state in _paths.py — blocks multi-brain marketplace vision

**MEDIUMs:**
- F2: patterns/rule_tracker.py imports _events (I/O in Layer 0)
- F3: Brain is 30+ method god object
- F4: _events.py doing 5 unrelated things
- F5: 3 competing event emit paths (_events.emit, _emit_direct, sidecar fallback)
- F6: __init__.py exports Layer 1 internals (graduate, update_confidence)
- F8: 8 backward-compat shims launder layer violations
- F10: No ARCHITECTURE-SPEC.md, no enforcement mechanism

**LOWs:**
- F9: Integration adapters swallow all errors silently

### 4. Brain Scripts — 6/10
**Must fix for launch:**
- S-1: `--dangerously-skip-permissions` baked into start.py launcher
- D-1: Zero `with` context managers across all 24 SQLite-using files
- P-1: paths.py defaults to Oliver's machine, no validation on missing env vars

**High priority:**
- Q-1: `_detect_session()` duplicated 5x with different logic (api_sync off by one)
- P-3: events.py:270 reconstructs WORKING_DIR via string replacement
- E-1: 136 silent exception swallows across 33 scripts

**Overall:** Security clean (no eval/exec/pickle/shell=True, parameterized SQL, env-var credentials). Architecture sound (proper SDK delegation). Portability poor.

### 5. Hook System — 5/10
**BLOCKERs:**
- config-validate.js NOT dispatched — config corruption undetected
- ECC config-protection.js completely dead — zero security value

**HIGHs:**
- secret-scan.js warns but never blocks writes (security theater)
- brain-maintain.js internal timeouts (108s) exceed dispatcher slot (30s)
- qwen-lint.js async HTTP in sync dispatcher — 15-20s on every Write if Ollama down
- implicit-feedback.js uses console.log instead of JSON protocol (output silently swallowed)
- implicit-feedback.js uses bare `python` instead of cfg.PYTHON
- implicit-feedback.js wrong events.py CLI syntax

**MEDIUMs:**
- Timeout budgets overflow in 3/6 dispatchers (post-tool 132>120, user-prompt 37>30, pre-tool 16>15)
- File contention on agent-written-files.json across 3 hooks
- cost-tracking.js receives no useful data, logs $0.00 entries
- cache-warmer.js hardcodes `python`
- session-init-data has 30s internal timeout in 10s dispatcher slot

### 6. Skills Audit — 93.7% healthy (133/142)
**Critical gap:** Only 14/142 skills are in the skill-router. 128 skills have no automatic routing.

**Broken (4):**
- marketing-skills/ — no SKILL.md
- mcp-builder/ — no SKILL.md (mcp-server-builder exists)
- minimalist-entrepreneur/ — no root SKILL.md (has sub-skills)
- sales-playbooks/ — no YAML frontmatter

**Dead (3):** sequence-engine (deprecated), content-creator (redirect), mcp-builder (empty)

**Redundancies (5 pairs):**
- marketing-skill vs marketing-ops (keep marketing-ops)
- test-driven-development vs tdd-guide (merge into tdd-guide)
- cold-email vs cold-email-manifesto (consolidate)
- code-reviewer-team vs requesting/receiving-code-review (different purposes, keep all)
- 6 CRO skills (keep all, different scopes)

**Should be agents:** overnight-agent, quality-loop, self-audit, one-step-better, verification-before-completion

### 7. Release Readiness — 4/10 (FIX FIRST)
**BLOCKER:**
- Package name identity crisis: code says `aios-brain`, plan says `gradata`. Import, CLI, GitHub URLs, pyproject.toml all inconsistent.

**HIGHs:**
- `oliver`, `anna`, `siamak` hardcoded in production source (agent_graduation.py line 217 has their names in a regex)
- SPEC.md + AUDIT.md tracked in git — expose exact graduation algorithm parameters (your moat)
- system.db + brain.manifest.json tracked in git — empty now but will leak data on push
- LICENSE says "Sprites AI" but publishing as "Gradata"
- Clone URL in install.md points to non-existent `sprites-ai` org

**MEDIUMs:**
- Public docs expose exact confidence deltas (+0.10/-0.15) — competitors can clone in an afternoon
- `instantly` and `pipedrive` hardcoded as first-class concepts in SDK core
- Three different GitHub org/repo name variants across files
- README H1 brand inconsistency
- First-run quickstart gives no health confirmation
- carl.py comments reference internal `.carl/` directory

**POSITIVEs:**
- Quickstart is honest, clear, functional
- Zero deps is genuine differentiator
- Docs structure well-organized
- Cloud positioned as acceleration not dependency
- Marketplace docs detailed and credible
- Mature Python toolchain (hatchling, ruff, pyright, bandit)

## Cross-Cutting Issues (appear in 3+ audits)

1. **SQLite connection leaks** — SDK + brain scripts, zero `with` context managers anywhere
2. **Silent error swallowing** — 136 bare excepts in brain, 18 in context_packet, all adapters
3. **ChromaDB ghosts** — 4+ files still reference killed dependency
4. **Path portability** — hardcoded Oliver paths in brain scripts, scheduled tasks, _paths.py
5. **Timeout math** — 3/6 dispatchers have budget overflows
6. **Skill routing gap** — 128/142 skills unreachable by automatic routing
