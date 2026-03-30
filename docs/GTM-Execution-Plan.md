# Gradata GTM Execution Plan
**Date:** 2026-03-27 | **Author:** Strategy analysis for Oliver | **Status:** Draft for review

---

## Executive Summary

Gradata has a defensible technical moat (correction-based learning with graduation) and zero distribution. Every competitor in the AI memory space (Mem0 48K stars, Letta 21.8K, Hindsight 6.5K) does memory retrieval but none does behavioral adaptation from corrections. The window is closing: Claude shipped persistent memory in March 2026, and the "Adaptation of Agentic AI" survey (arXiv:2512.16301) is mapping the entire design space. The plan: ship the SDK in Week 1 with a 3-line hello world, publish a Correction Learning Benchmark that reframes the competitive conversation from "memory recall" to "behavioral improvement," dual-license to MIT+proprietary to remove the AGPL adoption blocker, and submit an arXiv preprint by Week 4. Every action serves one goal: get 100 GitHub stars and 10 active users in 90 days, which validates the correction-learning thesis with external data.

---

## 90-Day Roadmap

### Week 1 (Mar 28 - Apr 3): Ship or Die
| Day | Milestone | Owner |
|-----|-----------|-------|
| 1 | Secrets audit (grep for API keys, tokens, paths containing `olive`) | Automated (bandit + grep) |
| 1 | Remove all Oliver-specific paths, Sprites references, brain vault references | Oliver |
| 1 | Strip `gradata_cloud_backup/`, `brain/`, `.carl/`, personal leads from repo | Automated (.gitignore + clean) |
| 2 | Simplify `__init__.py` to expose only: `Brain`, `Brain.init`, `brain.correct`, `brain.search`, `brain.manifest` | Oliver |
| 2 | Write 3-line quickstart that actually runs end-to-end (test it cold on a fresh venv) | Oliver |
| 3 | Push to `github.com/gradata-systems/gradata` (public) | Oliver |
| 3 | `pip install gradata` working on PyPI (test install from clean machine) | Oliver |
| 4 | Publish on PyPI via `uv build && twine upload` | Oliver |
| 5 | Write HN "Show HN" post (see launch copy below) | Oliver |
| 6 | Post to r/MachineLearning, r/LocalLLaMA, r/ClaudeAI, AI Twitter | Oliver |
| 7 | Monitor, respond to every issue/comment within 2 hours | Oliver |

### Week 2-3 (Apr 4 - Apr 17): Benchmark + Paper Draft
| Milestone | Owner |
|-----------|-------|
| Design CLB v0.1 (50 scenarios, 3 metrics) | Oliver |
| Implement CLB runner as standalone repo | Oliver + Claude Code |
| Run CLB against Gradata, baseline (no memory), and raw-context-stuffing | Automated |
| Draft arXiv preprint sections 1-4 (intro, related work, method, experiments) | Oliver + Claude Code |
| Open issues for community contributions (good first issues) | Oliver |

### Week 3-4 (Apr 11 - Apr 24): Paper + Benchmark Publication
| Milestone | Owner |
|-----------|-------|
| Publish CLB repo with Gradata scores and reproduction instructions | Oliver |
| Complete arXiv preprint draft | Oliver |
| Submit to arXiv (cs.AI + cs.CL) | Oliver |
| Announce benchmark with "challenge" framing on Twitter/HN | Oliver |
| License decision finalized and applied | Oliver |

### Week 5-8 (Apr 25 - May 22): Community Building
| Milestone | Owner |
|-----------|-------|
| Discord server live, linked from README | Oliver |
| Respond to first external issues/PRs | Oliver |
| gradata.ai landing page (static, not dashboard yet) | Oliver |
| Blog post: "What 71 sessions of correction data taught us" | Oliver |
| Interactive playground (Colab notebook, not custom infra) | Automated |

### Week 9-12 (May 23 - Jun 25): Dashboard MVP + Workshop Submission
| Milestone | Owner |
|-----------|-------|
| gradata.ai dashboard MVP (Next.js + Supabase) | Oliver |
| Cloud sync API: POST /api/sync for correction events | Oliver |
| Submit to CHI 2027 workshop (Sep 2026 deadline) or NeurIPS 2026 workshop | Oliver |
| Target: 100 stars, 10 active users, 3 external correction datasets | Metric |

---

## Priority 1: Ship the SDK Publicly

### Pre-Push Checklist (Day 1-2)

**Secrets audit (CRITICAL, do first):**
```bash
# Run from sdk/ directory
grep -rn "olive" src/ tests/ --include="*.py" | grep -v "test_olive"
grep -rn "api_key\|token\|password\|secret" src/ tests/ --include="*.py"
grep -rn "C:/Users/olive" src/ tests/ --include="*.py"
grep -rn "sprites" src/ tests/ --include="*.py" -i
bandit -r src/ -ll
```

**Files to exclude from public repo:**
- `gradata_cloud_backup/` (proprietary graduation engine)
- `brain/` (Oliver's personal brain data)
- `.carl/` (personal behavioral contracts)
- `Leads/` (sales data)
- `docs/Session Notes/` (internal session logs)
- Any file referencing Sprites.ai internal systems

**Files to add before push:**
- `LICENSE` (AGPL-3.0 text, or MIT if license decision changes)
- `CONTRIBUTING.md` (minimal: how to run tests, PR expectations)
- `CHANGELOG.md` (v0.1.0 initial release)
- `.github/workflows/ci.yml` (pytest on push)
- `.gitignore` (cover brain data, .env, __pycache__)

### The 3-Line Hello World

Current quickstart in README requires 5+ lines. Target:

```python
from gradata import Brain

brain = Brain.init("./my-brain")
brain.correct(draft="REST endpoints", final="gRPC endpoints")  # learns from this
```

To make this work, `Brain.init()` must:
- Auto-create the directory
- Auto-initialize SQLite with schema
- Return a ready-to-use Brain object
- Not require `domain` parameter (make it optional with default)

**Current state:** `Brain.init("./my-brain", domain="Engineering")` exists and works. The `domain` parameter just needs a default value. This is close.

### Launch Copy (Show HN)

> **Show HN: Gradata -- open-source SDK that learns from your corrections**
>
> I built an SDK that watches when you correct your AI agent's output, logs the diff, and makes that knowledge searchable. Over 71 sessions, my correction rate dropped from 5.0 to 0.004 per output.
>
> How it works: you call brain.correct(draft, final) when you edit AI output. Gradata computes the diff, classifies the edit severity, stores it as an immutable event, and makes it retrievable via brain.search(). Your AI stops repeating the same mistakes.
>
> What makes this different from Mem0/Letta: those systems store facts and memories. Gradata tracks behavioral corrections and proves improvement over time via a quality manifest. "Mem0 remembers. Gradata learns."
>
> Zero dependencies. Pure Python + SQLite. Works as a library or MCP server.
>
> pip install gradata
>
> N=1 results (honest caveat): all metrics are from my own usage. The benchmark for multi-user validation is in progress. I'm looking for early users to validate the correction-learning thesis.

### Soft Launch vs. Big Bang

**Recommendation: Soft launch (Week 1) then amplify (Week 3).**

Rationale:
- Week 1: Push to GitHub, post on 1-2 subreddits, get first bug reports
- Fix any install/onboarding friction found in Week 1-2
- Week 3: HN Show HN post + benchmark announcement = two news hooks in one week
- A benchmark gives HN something to discuss beyond "another AI tool"

Solo founder cannot handle simultaneous launch day chaos + critical bug reports. Stagger the exposure.

### Where to Announce (ranked by ROI for solo founder)

| Channel | When | Why | Expected Impact |
|---------|------|-----|----------------|
| Hacker News (Show HN) | Week 3 (with benchmark) | Technical audience, high signal, one post | 20-50 stars if front page |
| r/LocalLLaMA | Week 1 | Local-first crowd, MCP interest | 5-15 stars |
| r/ClaudeAI | Week 1 | MCP server angle, direct user base | 5-10 stars |
| Twitter/X | Week 1 onward | Drip content, build profile | Long-tail |
| r/MachineLearning | Week 3 (with paper) | Needs academic credibility | 10-20 stars |
| AI Discord servers (Cursor, Claude) | Week 2 | Direct MCP users | 3-8 stars |
| Dev.to / Hashnode blog | Week 5 | SEO play, long-tail discovery | Slow burn |

---

## Priority 2: Correction Learning Benchmark (CLB)

### Why This Matters Strategically

Existing benchmarks (LoCoMo, LongMemEval) measure **memory recall**. Top scores: EverMemOS 92.3%, Hindsight 89.6%, Mem0 ~66.9%. Nobody measures **behavioral improvement from corrections**. Publishing CLB reframes the entire competitive conversation onto Gradata's home turf.

### Benchmark Design: CLB v0.1

**Structure:** 100 scenarios across 5 domains, each with a 3-turn correction loop.

| Domain | Scenarios | Example |
|--------|-----------|---------|
| Email drafting | 20 | Agent writes email with em dashes. User corrects to colons. Next email should use colons. |
| Code generation | 20 | Agent uses REST. User corrects to gRPC. Similar API task should use gRPC. |
| Data formatting | 20 | Agent uses commas in CSV. User corrects to tabs. Next export should use tabs. |
| Document style | 20 | Agent writes passive voice. User corrects to active. Next doc should be active. |
| Reasoning/logic | 20 | Agent makes flawed assumption. User corrects with evidence. Similar reasoning should avoid the flaw. |

**Each scenario has 3 phases:**
1. **Initial output** -- agent produces output with a known pattern
2. **Correction** -- user provides corrected version (the "training signal")
3. **Transfer test** -- agent faces a similar (not identical) situation

**Three metrics per scenario:**

| Metric | Definition | Ideal |
|--------|-----------|-------|
| **Repeat Rate (RR)** | % of scenarios where the exact same mistake recurs after correction | 0% |
| **Corrections-to-Fix (CTF)** | Average number of corrections before behavior changes permanently | 1.0 |
| **Transfer Score (TS)** | % of similar-but-different scenarios where correction transfers | 100% |

**Composite CLB Score:** `(1 - RR) * 0.3 + (1/CTF) * 0.3 + TS * 0.4`

Weighted toward transfer because that is where real learning shows up (not just caching the exact correction).

### Implementation Plan

```
gradata-benchmark/
  README.md           # What CLB measures, why it matters
  scenarios/           # 100 YAML files, one per scenario
    email_001.yaml     # initial_prompt, expected_mistake, correction, transfer_prompt, expected_transfer
  runner.py            # Runs any system against scenarios, outputs scores
  baselines/
    no_memory.json     # Score with no memory system
    context_stuff.json # Score with full conversation in context
    gradata.json       # Gradata scores
  METHODOLOGY.md       # Detailed metric definitions, statistical approach
```

**Scenario YAML format:**
```yaml
id: email_001
domain: email_drafting
description: Em dash correction transfers to new email
initial_prompt: "Write a cold email to a CTO about our analytics platform"
expected_pattern: "em dash usage"  # What mistake to look for
correction:
  draft: "Our platform — built for scale — handles..."
  final: "Our platform, built for scale, handles..."
transfer_prompt: "Write a follow-up email to the same CTO"
transfer_check: "no em dashes in output"
difficulty: easy  # easy/medium/hard
```

### Credibility Strategy

1. **Reproducible:** Runner is open source. Anyone can run it. Results include exact model versions, temperatures, timestamps.
2. **Baselines included:** "No memory" and "context stuffing" baselines establish floor and ceiling.
3. **Invite competitors:** Open GitHub issues tagging Mem0, Letta, Zep repos. "We built a benchmark for correction learning. Here's how to run it against your system."
4. **LLM-as-judge:** Use Claude 3.5 Sonnet as evaluator (explicit model version pinned). Include human-evaluated subset (20 scenarios) for calibration.
5. **Limitations section:** Acknowledge N=100 is small, scenarios are synthetic, real-world correction patterns are messier.

### Publication

- **GitHub repo:** `gradata-systems/correction-learning-benchmark`
- **Blog post:** "Why AI Memory Benchmarks Measure the Wrong Thing"
- **Paper appendix:** Include full CLB methodology + results in arXiv preprint
- **Challenge tweet:** "We scored X on our own benchmark. @mem0ai @laborai scored Y on LoCoMo. Different benchmarks measure different things. Here's ours."

---

## Priority 3: Simplify Onboarding to 3 Lines

### Current SDK Surface Audit

The `__init__.py` exports 35+ symbols. A new user sees: Brain, BrainContext, Lesson, LessonState, RuleTransferScope, Pipeline, Stage, GateResult, PipelineResult, ParallelBatch, ParallelTask, DependencyGraph, merge_results, EpisodicMemory, SemanticMemory, ProceduralMemory, MemoryManager, InputGuard, OutputGuard, Guard, GuardCheck, MCPBridge, MCPToolSchema, MCPServer, HumanLoopGate, CritiqueChecklist, Criterion, reflect, EvalDimension, evaluate_optimize_loop, AudienceTier, TaskType, classify_scope, Delegation, DelegationResult, orchestrate, SmartRAG, NaiveRAG, RuleApplication.

**Problem:** This is an internal SDK surface, not a public API. A new user needs exactly 4 things:
1. `Brain.init()` -- create a brain
2. `brain.correct()` -- log a correction
3. `brain.search()` -- retrieve knowledge
4. `brain.manifest()` -- see improvement proof

Everything else is power-user territory.

### Recommended API Tiers

**Tier 1 -- Getting Started (3 lines):**
```python
from gradata import Brain
brain = Brain.init("./my-brain")
brain.correct(draft="old text", final="new text")
```

**Tier 2 -- Daily Usage (additional methods):**
```python
brain.search("query")           # Find relevant knowledge
brain.log_output("text", output_type="email")  # Track outputs
brain.manifest()                # Quality proof
brain.apply_brain_rules("task") # Get learned rules
```

**Tier 3 -- Power Users (patterns, integrations):**
```python
from gradata.patterns import Pipeline, SmartRAG, GuardCheck
from gradata.integrations import AnthropicAdapter
```

### What Defaults Need Baking In

| Setting | Current | Should Be |
|---------|---------|-----------|
| `domain` param in `Brain.init()` | Required | Optional, default `"general"` |
| Edit classification | Requires explicit call | Auto-classify on `correct()` |
| Event storage | Manual emit | Auto on every `correct()` and `log_output()` |
| Search mode | Must specify `mode=` | Auto-detect (keyword vs semantic based on query length) |
| Graduation thresholds | Hardcoded constants | Sensible defaults, overridable via config |

### Documentation Strategy

| Doc | Purpose | Length | When |
|-----|---------|--------|------|
| README.md | Hook + install + 3-line quickstart + "how it works" diagram | 150 lines max | Week 1 |
| docs/quickstart.md | 5-minute tutorial: init, correct, search, manifest | 100 lines | Week 1 |
| docs/api-reference.md | Full Brain class API with examples | As needed | Week 2 |
| docs/mcp-setup.md | MCP server configuration for Claude Code/Cursor | 50 lines | Week 1 |
| docs/benchmarks.md | CLB methodology + results | 200 lines | Week 3 |

### Interactive Playground

**Do not build custom infrastructure.** Use Google Colab.

```
Open in Colab badge in README
  -> Pre-installed gradata
  -> 5 cells: init, correct, correct again, search, manifest
  -> User sees correction count go up, search returns relevant corrections
  -> Total time: 2 minutes
```

This costs nothing, requires no hosting, and lets people try before installing.

---

## Priority 4: License Decision

### Option Analysis

| Factor | AGPL-3.0 (current) | MIT + Proprietary Cloud | Apache-2.0 + CLA |
|--------|-------------------|------------------------|-------------------|
| Enterprise adoption | Blocked (Google bans AGPL, most corps need legal review) | No friction | No friction |
| Fork protection | Strong (forks must also be AGPL) | Weak (anyone can close-source a fork) | Moderate (patent grant deters some) |
| Cloud provider protection | Strong (SaaS must share source) | None (AWS could host it) | None |
| Community contribution | Deterred (contributors fear AGPL virality) | Encouraged | Encouraged (CLA gives you flexibility) |
| Competitor moat | Legal moat | Technical moat only (graduation engine) | Technical moat only |
| Relevant precedents | GitLab (AGPL, works for large company), Grafana (moved TO AGPL) | Mem0 (Apache-2.0, 48K stars), LangChain (MIT) | OpenAI SDK (Apache-2.0) |

### What GitLab, MongoDB, and Elastic Learned

**GitLab (AGPL from day one):** Works because GitLab is an application you deploy, not a library you embed. Users run it as a service. AGPL's virality clause doesn't infect their code.

**MongoDB (AGPL to SSPL):** Moved away from AGPL because cloud providers (AWS DocumentDB) could host MongoDB without contributing. SSPL was more restrictive than AGPL but achieved the goal.

**Elastic (Apache to SSPL to AGPL):** Went through three license changes in 4 years. Each change caused community trust damage. The lesson: pick once, stick with it.

**Key insight for Gradata:** Gradata is an **SDK/library** that gets embedded into user applications. This is the worst case for AGPL. Unlike GitLab (standalone application), using Gradata as a library could trigger AGPL's virality clause on the host application. This is the exact scenario that makes legal teams say no.

### Recommendation: Dual License

```
SDK (gradata package on PyPI):     Apache-2.0
Graduation engine:                  Proprietary (not in repo)
Cloud platform (gradata.ai):       Proprietary
Benchmark (CLB):                   MIT
```

**Rationale:**
1. The SDK is a library. AGPL on a library kills adoption. Mem0 (Apache-2.0) has 48K stars. Letta (Apache-2.0) has 21.8K. Both are permissive.
2. The moat is NOT the SDK code. The moat is: (a) graduation engine (proprietary, server-side), (b) cross-brain meta-learning data (only on gradata.ai), (c) correction benchmark leadership.
3. Apache-2.0 > MIT for one reason: patent grant. Protects contributors and deters patent trolls.
4. The "cloud provider could host it" fear is irrelevant at 0 users. You need distribution, not protection. If AWS hosts Gradata, that is a success signal.

**What stays proprietary regardless of SDK license:**
- Graduation engine (INSTINCT to PATTERN to RULE confidence scoring)
- Quality scoring algorithm (5-dimension trust audit)
- Meta-learning across brains (cross-brain pattern discovery)
- Brain marketplace infrastructure
- Context-dependent rule weighting

### Migration Path (if you choose to switch)

1. Create `LICENSE` file with Apache-2.0 text
2. Update `pyproject.toml` license field
3. Add `NOTICE` file (Apache-2.0 requirement)
4. Update README license badge
5. Add header to source files (optional but conventional)
6. Commit message: "License: AGPL-3.0 -> Apache-2.0 for library adoption"

This is a one-commit change. Do it before the public push, not after. Changing license post-launch damages trust.

---

## Priority 5: arXiv Paper

### Paper Structure

**Title:** "Bottom-Up Principle Discovery: Learning Hierarchical Behavioral Rules from Human Corrections in AI Agent Systems"

**Target length:** 8-10 pages (workshop format) or 4 pages (short paper)

```
1. Introduction (1 page)
   - Problem: AI agents repeat mistakes despite memory systems
   - Insight: Corrections are a supervision signal, not just data to store
   - Contribution: A system that graduates corrections into behavioral rules

2. Related Work (1 page)
   - Memory systems: Mem0, Letta/MemGPT, Zep, Hindsight
   - Constitutional AI (Bai et al., 2022) -- top-down principle specification
   - Inverse Constitutional AI (Findeis et al., ICLR 2025) -- our direct ancestor
   - AGM belief revision (Alchourron et al., 1985) -- theoretical foundation
   - Rosch categorization theory (1978) -- hierarchy formation
   - ATLAS (arXiv:2511.01093) -- online adaptation (closest contemporary work)

3. Method (2 pages)
   - Correction capture: edit distance, severity classification, category assignment
   - Three-tier graduation: INSTINCT (0.30) -> PATTERN (0.60) -> RULE (0.90)
   - Confidence dynamics: severity-weighted updates with survival bonuses
   - Meta-rule formation: clustering related graduated rules (Rosch basic-level)
   - Context-dependent injection: scope matching, recency/primacy positioning

4. Experimental Setup (1 page)
   - Longitudinal study: 1 user, 73+ sessions, 9+ days
   - Metrics: correction rate per output, category extinction count,
     graduation rate, CLB scores
   - Ablation: rules disabled vs enabled (paired comparison)
   - Baselines: no-memory, full-context-stuffing, Mem0-style fact extraction

5. Results (1.5 pages)
   - Correction rate: 5.0 -> 0.004 per output (99.9% reduction)
   - 13/14 correction categories extinguished
   - 48/107 lessons graduated to RULE status (45%)
   - CLB scores vs baselines
   - Ablation results (what breaks when rules are disabled)

6. Discussion (1 page)
   - Limitations: N=1, single domain (sales), confounds (user learning)
   - Generalizability: CLB synthetic scenarios as partial mitigation
   - Correction detection challenge (MCP protocol gap)
   - Ethics: correction data encodes human judgment and biases

7. Conclusion (0.5 page)
   - Corrections are an underexploited supervision signal
   - Graduation creates a hierarchy that scales (not just a growing list)
   - Open source SDK + benchmark available
```

### Key Academic Frames

| Frame | How Gradata Fits | Citation |
|-------|-----------------|----------|
| **Inverse Constitutional AI** | Constitutional AI writes principles top-down. Gradata discovers them bottom-up from corrections. | Findeis et al., ICLR 2025 (arXiv:2406.06560) |
| **Rosch Categorization Theory** | L0 corrections cluster into L1 meta-rules at the "basic level" of abstraction. | Rosch, 1978 |
| **AGM Belief Revision** | Confidence updates follow contraction (correction = revise belief) and expansion (survival = strengthen belief). | Alchourron, Gardenfors, Makinson, 1985 |
| **Continual Learning** | Unlike fine-tuning, Gradata adapts without gradient updates. Closer to ATLAS (arXiv:2511.01093). | Parisi et al., 2019; Gao et al., 2025 |
| **Agentic Adaptation Survey** | Gradata is "agent-output-signaled" adaptation per the taxonomy. | arXiv:2512.16301 |

### Data to Include

| Data Point | Source | Presentation |
|------------|--------|-------------|
| Correction rate over sessions | events.jsonl | Line chart, log scale |
| Category extinction timeline | events.jsonl by category | Heatmap (session x category) |
| Graduation funnel | lessons.md status counts | Sankey diagram: 107 INSTINCT -> 48 RULE |
| Confidence score distribution | lessons.md confidence values | Histogram |
| Severity distribution | events.jsonl edit_distance | Bar chart: 35 moderate, 24 major |
| CLB scores (Gradata vs baselines) | Benchmark output | Table with confidence intervals |
| Ablation: rules on vs off | Paired test results | Box plot |

### Target Venues (ranked by fit and timeline)

| Venue | Deadline | Format | Fit |
|-------|----------|--------|-----|
| **arXiv preprint** | Anytime (target Week 4) | No limit | Immediate credibility + citability |
| **NeurIPS 2026 Workshop** | ~Jun 2026 | 4-6 pages | High (agent learning track likely) |
| **EMNLP 2026 Workshop** | ~Jul 2026 | 4-8 pages | Medium (NLP focus but agent track exists) |
| **CHI 2027** | Sep 2026 | 10 pages | High (human-AI interaction angle) |
| **ICLR 2027 Workshop** | ~Oct 2026 | 4-6 pages | Highest (where Inverse CAI was published) |

**Recommendation:** arXiv preprint in Week 4, then extend for ICLR 2027 workshop submission.

### Timeline

| Week | Milestone |
|------|-----------|
| Week 2 | Outline + related work complete. Run CLB, collect data. |
| Week 3 | Method + results sections drafted. Figures generated. |
| Week 4 | Full draft complete. Internal review (read aloud, check every claim against data). Submit to arXiv. |
| Week 6 | Incorporate any feedback. Post to Twitter, r/MachineLearning. |
| Week 10-12 | Extend for workshop submission (add multi-user data if available). |

---

## Launch Week Checklist (Minimum Viable Launch)

This is the absolute minimum for a credible public push. Everything else is Week 2+.

### Must Have (Block launch if missing)

- [ ] `pip install gradata` works on clean Python 3.11+ venv (test on Windows + Mac if possible)
- [ ] 3-line quickstart runs without errors
- [ ] Zero secrets/personal data in repo (automated grep audit passes)
- [ ] `gradata_cloud_backup/`, `brain/`, `.carl/`, `Leads/` excluded from repo
- [ ] README with: problem statement, install, quickstart, "how it works" diagram, caveats section
- [ ] LICENSE file present and matching pyproject.toml
- [ ] CI running (GitHub Actions: pytest on Python 3.11 + 3.12)
- [ ] All 363 SDK tests pass (no skips that hide failures)
- [ ] `gradata init ./test && gradata search "hello"` CLI works

### Should Have (Ship without, add in Week 2)

- [ ] CONTRIBUTING.md
- [ ] CHANGELOG.md
- [ ] MCP server setup docs
- [ ] "Open in Colab" quickstart notebook
- [ ] 3+ "good first issue" GitHub issues
- [ ] Social media accounts (Twitter @gradata_ai or similar)

### Must Not Have (Remove before push)

- [ ] Any path containing `olive`, `sprites`, `anna`, `siamak`
- [ ] API keys, tokens, or credentials (Prospeo, LeadMagic, ZeroBounce, Apify, Pipedrive)
- [ ] Brain vault data (events.jsonl, system.db with personal data)
- [ ] Sales leads, prospect data, session notes
- [ ] References to employer (Sprites.ai) in code or comments

---

## Success Metrics

### 30 Days

| Metric | Target | "Working" Signal |
|--------|--------|-----------------|
| GitHub stars | 50 | People found it and bookmarked it |
| PyPI installs | 200 | People tried it |
| GitHub issues opened | 10 | People used it enough to hit edges |
| CLB benchmark published | Yes | Reframing narrative established |
| arXiv preprint submitted | Yes | Academic credibility seeded |
| External brain.correct() calls logged | 5 users | Correction thesis being tested |

### 60 Days

| Metric | Target | "Working" Signal |
|--------|--------|-----------------|
| GitHub stars | 150 | Organic discovery happening |
| Active users (>3 sessions) | 10 | People stuck around |
| External PRs/issues | 5 | Community forming |
| Blog post / tweet about Gradata by someone else | 1 | Word of mouth |
| HN front page | Yes | Distribution breakthrough |
| Competitor response to CLB | Any | Benchmark is being taken seriously |

### 90 Days

| Metric | Target | "Working" Signal |
|--------|--------|-----------------|
| GitHub stars | 300 | Trajectory toward relevance |
| Active users | 25 | Product-market signal |
| gradata.ai signups | 50 | Cloud pipeline validated |
| Correction datasets from external users | 3 | Multi-user data for paper v2 |
| Workshop paper accepted | Submitted | Academic trajectory |
| Revenue | $0 (intentional) | Focus is adoption, not monetization |

### Anti-Metrics (Things That Would Signal Failure)

- 0 issues opened after 30 days (nobody used it seriously)
- Stars but no installs (curiosity, not usage)
- Installs but no `correct()` calls (onboarding broken)
- No response to CLB challenge (benchmark not credible or not visible)

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Nobody cares (no stars, no installs) | Medium | Critical | Benchmark creates discussion hook. Paper creates citation surface. Both drive discovery independently of SDK quality. |
| Correction detection doesn't work outside Claude Code | High | High | Ship explicit `brain.correct()` API as primary interface. Don't depend on auto-detection for launch. MCP sidecar is Phase 2. |
| AGPL scares away first 50 users | Medium | High | Switch to Apache-2.0 before launch. One commit. |
| Competitor ships correction learning | Low (6mo) | Critical | Speed. First mover with benchmark + paper + working code = defensible position. |
| Solo founder burnout | Medium | Critical | Week 1 is the only crunch week. After that, 2-3 hours/day on community. Automate CI, issue templates, Colab. |
| N=1 data gets dismissed | High | Medium | CLB benchmark provides synthetic multi-scenario data. Acknowledge N=1 honestly. First external users provide N=2+. |
| Paper rejected from workshops | Medium | Low | arXiv preprint is the actual distribution. Workshop acceptance is bonus credibility. |

---

## Key Strategic Decisions (Requiring Oliver's Input)

1. **License: AGPL or Apache-2.0?** Recommendation is Apache-2.0, but this is irreversible post-launch. Decide before Week 1 push.

2. **GitHub org name:** `gradata-systems` is in the README. Is this created? Is `gradata` available as a PyPI package name?

3. **gradata.ai domain:** Is it registered? Landing page needed by Week 5.

4. **Brain data for paper:** The 71-session dataset is powerful evidence. Can anonymized event logs be published as supplementary material? (No prospect names, no email content, just event types + timestamps + categories.)

5. **Sprites.ai employer relationship:** Is there any IP assignment clause that affects publishing the SDK or paper? Verify before public push.
