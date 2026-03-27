# Gradata — Agent Operating System
Startup: skills/session-start/SKILL.md (mandatory). Wrap-up: skills/wrap-up/SKILL.md when Oliver says "wrap up".
Domain: domain/DOMAIN.md | CARL: .carl/ | Gates: domain/gates/ | Voice: domain/soul.md
Work style: .claude/work-style.md | Output flow: .claude/action-waterfall.md
Self-check: gate complete? self-score >= 10? fallback chain followed? Never skip steps. Never report unverified numbers.
Quality: .claude/quality-rubrics.md | Fallbacks: .claude/fallback-chains.md
Mode: OODA godmode. Observe-Orient-Decide-Act continuously. Never pause to ask. Keep building until told to stop.

## Architecture (open source SDK + proprietary cloud)
Open SDK (sdk/src/gradata/): patterns/, enhancements/ (diff_engine, quality_gates, truth_protocol, meta_rules, rule_verifier). AGPL-3.0.
Proprietary (gradata_cloud_backup/): graduation engine, scoring, profiling. NOT in public repo. Backed up to brain vault.
Brain vault: C:/Users/olive/SpritesWork/brain/ (events.jsonl, system.db, prospects/, sessions/).

## Learning Pipeline
Correction -> edit_distance (severity: trivial/minor/moderate/major/rewrite) -> event logged -> lesson created
Confidence: severity-weighted (+0.03 trivial survival to +0.12 rewrite survival, -0.02 trivial penalty to -0.20 rewrite penalty)
Graduation: INSTINCT (0.30) -> PATTERN (0.60) -> RULE (0.90). Meta-rules emerge from 3+ related graduated rules.
Injection: max 10 rules per session, XML <brain-rules> format, primacy/recency positioning, scope-matched per task type.
Sub-agents: meta-rules auto-injected via agent-precontext.js hook, max 5 per agent, scope-matched.
Verification: rule_verifier.py checks outputs against rules. Ablation tests validate rules causally.
Dashboard: brain/scripts/learning_dashboard.py (adaptation score, correction rate, category extinction, severity trends).

## Environment
Windows 11. Python: C:/Users/olive/AppData/Local/Programs/Python/Python312/. Node available.
Prospecting: enrich before tiering, CEO != auto-T1, counts in filenames. Rules: domain/playbooks/prospecting-instructions.txt
Truth protocol: .carl/global GLOBAL_RULE_0 + .claude/truth-protocol.md
Tests: pytest sdk/tests/ (363 pass, 23 skip) + brain/gradata_cloud_backup/tests/ (523 pass) = 886 total. Build: uv.
