# Gradata Marketing & Positioning Strategy
**Version:** 1.0 | **Date:** 2026-03-27 | **Stage:** Pre-launch, zero public users

---

## 1. Positioning Framework

### The Core Insight

Memory tools and Gradata are solving different problems. Mem0 solves: "my agent doesn't remember what we talked about." Gradata solves: "my agent keeps making the same mistakes." These look adjacent but are not. One is retrieval. One is behavioral adaptation. They serve the same developer at different points of maturity.

Positioning Gradata as better memory is a losing fight (Mem0 has 48K stars, $24M, enterprise trust). Positioning Gradata as the only tool that measures and proves improvement over time is a fight nobody else is having.

---

### The One-Liner

**"Mem0 remembers. Gradata learns."**

This is 3 words of positioning carrying all the differentiation. It's memorable, it doesn't attack unfairly, and it names the exact delta. Use this in every channel.

Alternative one-liners for A/B testing:
- "The only AI SDK that proves your agent is getting smarter."
- "Track, graduate, and prove AI improvement from corrections."
- "Your AI stops making the same mistake twice."

---

### The "Only We Can Say This" Claims

1. **"We are the only framework with a correction graduation pipeline."** No competitor has INSTINCT → PATTERN → RULE with confidence-weighted scoring. Mem0 has memory. Letta has LLM-decided recall. Nobody has behavioral rule graduation from edit distance analysis.

2. **"We can show you a chart of your AI getting better."** The compound score, correction rate decay, and category extinction are auditable, generated from real event logs — not self-reported. The brain.manifest is cryptographically tied to events. No competitor has this.

3. **"We can prove a brain's quality before you deploy it."** The 5-dimension trust audit (metric integrity, training depth, learning signal, data completeness, behavioral coverage) grades A-F. No competitor publishes a trust score tied to verifiable data.

---

### Messaging Hierarchy

**Headline (gradata.ai hero):**
> Your AI keeps making the same mistakes. Gradata fixes that.

**Subhead:**
> Open-source SDK that tracks corrections to your AI agents, graduates them into behavioral rules, and proves improvement over time. Your brain gets smarter with every session — and we can show you the chart.

**Proof Points (ordered by trust-building value):**

1. **Behavioral graduation, not just memory.**
   Every correction your AI receives is analyzed by severity, tracked across sessions, and — when the pattern is confirmed — graduated into a permanent behavioral rule. INSTINCT → PATTERN → RULE. The rules travel with the brain.

2. **Quality proof you can ship.**
   The `brain.manifest.json` auto-generates every session: correction rate, graduated rule count, confidence scores, first-draft acceptance rate. Computed from real events, not self-reported. Present it in a demo. Put it in a proposal. The numbers are real.

3. **Open source core, hosted intelligence.**
   The local SDK is Apache-2.0 and fully capable standalone with BYOK. What happens on gradata.ai is where the brain compounds: team workspaces, the corrections corpus (cross-user network effect), brain marketplace, and a managed LLM option. Install locally. Plug into the hosted tier when you want team features, corpus signal, or a marketplace of rule sets.

---

### Objection Handling

**"How is this different from Mem0?"**

Direct answer (do not hedge):
> Mem0 solves retrieval — making sure your agent remembers what happened. Gradata solves adaptation — making sure your agent changes its behavior when it gets something wrong. They operate at different layers. You could use both.
>
> Specifically: Mem0 stores and surfaces facts. It does not analyze the severity of a correction, does not track whether the same mistake recurs, does not graduate behavioral patterns into rules, and does not produce a compound quality score. We do all four. If you care that your agent is measurably improving, Mem0 doesn't answer that question. We do.

**"Can't I just use LangChain memory?"**

Direct answer:
> LangChain's memory modules store context in a buffer or vector store — that's retrieval, not learning. None of them track whether your agent made the same mistake twice, compute the severity of a correction, or produce a behavioral rule. LangMem (their prompt optimization layer) is closer but it's locked to LangChain and doesn't expose graduation metrics or quality proofs. Gradata works alongside any framework, including LangChain. You don't have to choose.

**"Why Apache-2.0?"**

Direct answer:
> Maximum adoption. Apache-2.0 is the license enterprise procurement teams approve without thinking — same as LangChain, Mem0, Letta, and most modern AI infra. No copyleft. No linking obligations. You can use Gradata in internal tools, commercial products, hosted SaaS, or research — and keep your modifications private if you want to.
>
> Our moat is not the SDK code. The moat is the hosted tier: team workspaces, the corrections corpus (cross-user network effect that nobody else has), the brain marketplace, and managed infrastructure. The more the SDK spreads, the stronger those network effects get. Apache-2.0 is the distribution multiplier.

**"You're a solo founder with zero users. Why should I trust this?"**

Direct answer:
> 73 sessions of production data. Correction rate declining measurably. 142+ rules graduated at 0.90+ confidence. First-draft acceptance rate trackable session over session. We're not shipping a thesis — we're shipping data. The brain.manifest is verifiable. The events.jsonl is auditable. You can clone the repo and run ablation tests yourself. This isn't a promise. It's a track record.

---

## 2. Launch Content Plan

### Blog Post #1: Problem-Aware

**Title:** "Why Your AI Agent Keeps Making the Same Mistakes"

**Target reader:** Developer who has built an AI agent and is frustrated that it doesn't improve.

**Outline:**

Opening hook (don't bury it):
> You corrected your AI agent last Tuesday. You corrected it for the same thing yesterday. It will do the same thing tomorrow. This is not a model problem. This is an infrastructure problem — and nobody is solving it.

Section 1: The retrieval-vs-learning gap
- Memory tools remember what was said. They do not change behavior.
- The difference: "remember this fact" vs "don't do this thing again"
- Example: agent recommends the wrong email format. You correct it. Memory tool logs the correction. Next week, same mistake. Why? Because the correction wasn't graduated into a rule.

Section 2: Why this happens
- No severity analysis (trivial typo vs structural mistake treated the same)
- No pattern detection (one correction vs confirmed pattern)
- No graduation mechanism (observation never becomes rule)
- No quality proof (no way to know if things are getting better)

Section 3: What graduation actually looks like
- Walk through a real correction: wrong tone in an email
- Edit distance: moderate severity
- Session 2: same pattern reappears — INSTINCT
- Session 4: confirmed again — PATTERN
- Session 6: 0.90 confidence — RULE
- The rule now travels with the agent permanently

Closing CTA: "This is the problem Gradata was built to solve. [link to GitHub]"

---

### Blog Post #2: Solution-Aware

**Title:** "How Correction-Based Learning Works: The Graduation Pipeline Explained"

**Target reader:** Developer who understands the problem and wants the mechanism.

**Outline:**

Section 1: The three-tier graduation model
- INSTINCT (0.30): observed once, low confidence
- PATTERN (0.60): confirmed across sessions, medium confidence
- RULE (0.90): graduated — this is now a behavioral contract

Why thresholds matter: a single correction could be context-specific. Three confirmations is a pattern. Five confirmations at high confidence is a rule. We do not graduate noise.

Section 2: Edit distance severity
- The five severity levels (trivial/minor/moderate/major/rewrite)
- Why they matter: a trivial correction should contribute less confidence than a rewrite
- Confidence delta formulas (show the math — developers trust math)

Section 3: The brain.manifest
- What it auto-generates every session
- Correction rate, graduated rule count, severity distribution, category extinction
- Why "computed from events" matters more than "self-reported"
- Show a real manifest snippet (redact if needed, but make it real)

Section 4: What this looks like in a dashboard
- Correction rate trending down: good signal
- Category extinction: topics where errors have been eliminated
- Compound score: single number that tracks overall brain quality

CTA: "Install in 5 minutes. [pip install gradata] [link to docs]"

---

### Blog Post #3: Benchmark Results

**Title:** "73 Sessions, 142 Graduated Rules: What We Learned About AI Agent Learning Curves"

**Target reader:** Technical skeptic. Researcher. Someone who needs proof before trusting a new tool.

This post is the most important one for long-term credibility. Do not publish it until the numbers are real and the methodology is clean.

**Outline:**

Section 1: The dataset
- 73 production sessions (Oliver's actual workflow)
- Not curated. Not cherry-picked. Every correction logged.
- Methodology: what counts as a correction, how edit distance is computed, how severity is assigned

Section 2: What the data shows
- Correction rate over time (chart: should show declining trend)
- Severity distribution (most corrections are minor — shows the system isn't over-triggering)
- Category extinction timeline (which topic areas improved first and why)
- First-draft acceptance rate progression

Section 3: The graduation curve
- How many observations become instincts, patterns, rules
- The natural filter ratio (e.g., 600 observations → 280 instincts → 142 rules)
- Why false positives are rare (confidence-weighted, not count-weighted)

Section 4: Comparison context
- How this differs from what Mem0/Letta expose (no correction rate, no graduation, no quality audit)
- What Hindsight gets right (retrieval accuracy) and what it misses (behavioral adaptation)
- What this paper would look like as a formal study

CTA: Link to arXiv preprint when published. Link to GitHub. Link to dashboard.

---

### Twitter/X Launch Thread

**Tweet 1 (hook):**
> You corrected your AI agent yesterday.
>
> You'll correct it for the same thing tomorrow.
>
> This is not a model problem. This is an infrastructure problem.
>
> We built the fix. 🧵

**Tweet 2:**
> Memory tools remember what happened.
>
> They don't change behavior.
>
> There's a difference between:
> "Remember I prefer bullet points"
> and
> "Never use em dashes in email prose ever again"
>
> Gradata tracks corrections, measures severity, and graduates patterns into permanent rules.

**Tweet 3:**
> The graduation pipeline:
>
> INSTINCT (0.30) — observed once
> PATTERN (0.60) — confirmed across sessions
> RULE (0.90) — behavioral contract
>
> A single correction could be context. Three confirmations is a pattern. Five at 90% confidence is a rule.
>
> We don't graduate noise.

**Tweet 4:**
> After 73 sessions:
>
> • 142 graduated rules at 0.90+ confidence
> • Correction rate declining measurably session over session
> • Category extinction in 6 topic areas
> • First-draft acceptance rate improving
>
> Computed from events.jsonl. Not self-reported. Auditable.

**Tweet 5:**
> Every session auto-generates a brain.manifest.json:
>
> • correction_rate
> • graduated_rule_count
> • severity_distribution
> • compound_quality_score
>
> It's a track record, not a promise.
>
> You can present it in a demo. Put it in a proposal. It's real data.

**Tweet 6:**
> Mem0 remembers. Letta recalls. Neither learns.
>
> No correction tracking.
> No pattern graduation.
> No quality proof.
>
> Gradata is the first framework that can show you a chart of your AI getting better.

**Tweet 7 (CTA):**
> Open source (Apache-2.0).
> Python SDK.
> pip install gradata
>
> Cloud dashboard (gradata.ai) coming soon — see your brain's compound score, correction rate, graduation history.
>
> GitHub: [link]
> Docs: [link]
>
> If you build agents and you're tired of the same mistakes — this is for you.

---

### Hacker News Show HN Post

**Title:**
> Show HN: Gradata — open-source SDK that tracks AI agent corrections and graduates them into behavioral rules

**Opening paragraph:**
> I've been running an AI agent for my own workflow for 73 sessions. The agent kept making the same mistakes — not because the model was bad, but because there was no mechanism to turn corrections into permanent behavioral rules. I built Gradata to fix that.
>
> The core mechanism: every correction is analyzed by edit distance severity (trivial/minor/moderate/major/rewrite). Corrections accumulate as INSTINCT (confidence 0.30). When the pattern recurs across sessions, it graduates to PATTERN (0.60), then RULE (0.90). Rules travel with the brain and inject at session start. Every session generates a brain.manifest.json — correction rate, graduated rule count, compound quality score — computed from raw event logs, not self-reported.
>
> After 73 sessions: 142 rules at 0.90+ confidence, correction rate declining, six categories where errors have been fully eliminated. The code is Apache-2.0, the SDK is pip-installable, and the hosted tier (gradata.ai) adds team workspaces, a corrections corpus, and a brain marketplace on top.
>
> What I'm looking for: developers who are frustrated that their agents don't improve, and who want to install this and tell me what breaks. Happy to answer questions about the graduation algorithm, the manifest spec, or the architecture tradeoffs.

**Notes for HN:**
- Post on a Tuesday or Wednesday morning (9-11am ET) — highest HN traffic
- Be present to reply for the first 3 hours — HN rewards engagement velocity
- If someone mentions Mem0/Letta, use the exact objection handling language above
- If someone says "this is just prompt engineering" — that's a real objection worth a full thread reply (prepare it in advance)

---

### Reddit r/MachineLearning Post

**Title:**
> Correction-based behavioral adaptation in AI agents: 73 sessions of data on the graduation pipeline

**Tone:** Research framing, not product pitch. Link to the benchmark blog post.

**Opening:**
> I want to share some data from a small longitudinal experiment: what happens when you systematically track and analyze every correction made to an AI agent across 73 production sessions, weight them by edit distance severity, and graduate confirmed patterns into permanent behavioral rules.
>
> Short version: the correction rate declines measurably, category extinction is observable, and first-draft acceptance rate improves. The mechanism — INSTINCT (0.30) → PATTERN (0.60) → RULE (0.90) — filters noise without over-triggering.
>
> I built the tooling for this and open-sourced it as Gradata. But this post is more about the data and methodology than the product. Interested in thoughts from the community, especially on the confidence thresholds and severity calibration.

**What works on r/ML:**
- Data first, product second
- Invite critique — the community will engage if they think they can find a flaw
- Don't use any marketing language
- Respond to every top-level comment in the first hour

---

### Dev.to Technical Tutorial

**Title:** "Building an AI Agent That Learns From Its Mistakes: A Step-by-Step Guide with Gradata"

**Format:** Long-form with working code blocks

**Structure:**

1. The problem (2 paragraphs, plain language)
2. How the graduation pipeline works (visual diagram + explanation)
3. Installation: `pip install gradata`
4. Basic setup: wrapping an existing LLM call with `with brain_context():`
5. Logging a correction: `brain.correct(original, edited, context)`
6. Viewing graduation status: `brain.status()`
7. Reading the manifest: `brain.manifest.json` walkthrough
8. Connecting to gradata.ai dashboard (when live)
9. Common pitfalls: what counts as a correction, why edit distance matters

**Tone:** Like documentation with personality. No marketing. Assume the reader is a mid-level developer who has built at least one LLM-powered tool before.

---

## 3. Community Strategy

### Discord Server Structure

**Category: Getting Started**
- #announcements (locked, Oliver only)
- #welcome-and-intros
- #install-help

**Category: Using Gradata**
- #show-your-brain (share manifests, graduation stats, interesting rules)
- #integrations (Claude Code, Cursor, VS Code, LangChain, CrewAI)
- #prompting-for-corrections (how to structure workflows that generate good training signal)

**Category: Building with Gradata**
- #sdk-development (technical contributors)
- #feature-requests
- #bug-reports (with template: version, OS, reproduction steps)

**Category: Research**
- #graduation-algorithm (discussion on confidence thresholds, severity calibration)
- #benchmarks (share your correction rate data)
- #paper-discussion (link to arXiv preprint when live)

**Category: Early Adopters** (private, invite-only)
- #early-access-cohort
- #weekly-check-in
- #direct-feedback-to-oliver

**Moderation rules:**
- No "how do I use ChatGPT" questions (redirect to #install-help, close if unrelated)
- Share your manifest or it didn't happen (encourage data sharing)
- Critique of the graduation algorithm is welcome and will get a direct response from Oliver

---

### GitHub Community Health Files

**CONTRIBUTING.md key sections:**
- Where corrections and bugs go (GitHub Issues, not Discord)
- How to run the test suite (pytest sdk/tests/, pytest brain/gradata_cloud_backup/tests/)
- Contribution scope: SDK is open (PRs welcome). Cloud graduation engine is proprietary (not in repo).
- Graduation algorithm changes require: data supporting the change (not just intuition)
- Code style: ruff, type hints required, no magic numbers (document thresholds with comments)
- PR checklist: tests pass, manifest auto-generates correctly, no new dependencies without discussion

**CODE_OF_CONDUCT.md:**
Use the Contributor Covenant as the base. Add one Gradata-specific clause:
> We value data over opinion. If you're arguing for a change to the graduation thresholds or severity calibration, bring numbers.

**SECURITY.md:**
- Do not open public issues for security vulnerabilities
- Email: security@gradata.ai (set up before launch)
- Response SLA: 48 hours for acknowledgment, 7 days for initial assessment

**Issue templates:**
1. Bug report: version, OS, command run, expected behavior, actual behavior, stack trace
2. Feature request: what are you trying to do, what did you try first, why doesn't the current approach work
3. Benchmark submission: methodology, session count, correction rate data, graduated rule count

---

### Early Adopter Program

**Size:** 10-15 people (small enough to give real attention, large enough to get variance)

**What they get:**
- Direct Discord channel with Oliver (#early-access-cohort)
- Brain.manifest reviewed personally once per week for the first month
- gradata.ai Pro free for 6 months
- Named in the arXiv paper acknowledgments section
- Input on graduation threshold calibration (their data feeds the research)
- First access to composable skills marketplace when it launches

**What Oliver gets:**
- Real correction event data from diverse use cases (not just one workflow)
- Bugs found before public launch
- Testimonials that are grounded in actual metrics (not vibes)
- Case studies for the benchmark post and the paper

**Selection criteria (explicit, not vague):**
- Already building with LLMs in production (not learning)
- Willing to share their brain.manifest weekly (anonymized if needed)
- Has a workflow with enough LLM interactions to generate meaningful training signal (10+ interactions/day minimum)
- Not at a competitor (Mem0, Letta, Zep, Hindsight, Langchain team)

**Application process:**
Short form: name, what you're building, estimated daily LLM interactions, one-line answer to "what mistake does your agent keep making." No referrals. No follower count. No social proof required. Technical substance only.

**Timeline:**
- Applications open at launch
- 48-hour response
- Onboarding call (30 min) within first week
- First group check-in at week 2

---

### Dev Advocate / Champion Program

**Do not build this until you have 50+ active community members.** Before that, there is no community to advocate into.

When the time comes:

**Tier 1: Brain Builder** (informal, 5-10 people)
- Criteria: active in Discord, shared their manifest, helped someone else install
- Perks: early access to features, shoutout in monthly update
- Ask: answer questions in Discord, share their brain stats publicly

**Tier 2: Gradata Champion** (formal, 2-3 people)
- Criteria: shipped a project using Gradata, willing to write about it
- Perks: Pro free indefinitely, co-authored case study on gradata.ai, speaking slot if we ever do an event
- Ask: write one technical post per quarter, give feedback on docs

**Tier 3: Integration Partner** (paid or rev-share, 1-2 orgs)
- Criteria: building a product on top of Gradata SDK
- Structure: negotiate individually — could be rev-share on dashboard referrals, could be co-marketing

---

## 4. Comparison Table

### Table Copy for gradata.ai

Place this below the hero section, above pricing. The goal is to make a developer who just Googled "gradata vs mem0" stop scrolling.

**Headline above table:**
> How Gradata compares

**Subhead:**
> Memory tools and Gradata are solving different problems. Here's the exact difference.

---

| Feature | Gradata | Mem0 | Letta | Zep | Hindsight |
|---|---|---|---|---|---|
| **Learns from corrections** | Yes — tracks every correction, analyzes severity, graduates into rules | No — stores corrections as memories but does not adapt behavior | Claimed — LLM decides what to remember; no graduation mechanism | No | No |
| **Correction severity analysis** | Yes — edit distance severity (trivial/minor/moderate/major/rewrite) | No | No | No | No |
| **Graduation engine** | Yes — INSTINCT (0.30) → PATTERN (0.60) → RULE (0.90) with confidence scoring | No | No | No | No |
| **Quality proof / manifest** | Yes — brain.manifest.json auto-generated, computed from events | No | No | No | No |
| **Ablation testing** | Yes — verify rules causally, not just correlatively | No | No | No | No |
| **Correction rate tracking** | Yes — session-over-session chart | No | No | No | No |
| **Category extinction** | Yes — shows which error types have been eliminated | No | No | No | No |
| **Multi-agent support** | Yes — scope-matched rule injection per agent | Partial | Yes | Partial | No |
| **MCP compatible** | Yes | Yes | No | No | No |
| **Framework agnostic** | Yes | Yes | No (own runtime) | Partial | Yes |
| **Open source** | Yes (Apache-2.0) | Yes (Apache 2.0) | Yes (Apache 2.0) | Partial | Yes (MIT) |
| **Retrieval accuracy** | Good (FTS5 + sqlite-vec) | Good (hybrid vector+graph) | Good | Good (temporal graphs) | Best-in-class (91.4%, TAO) |
| **Self-hosted** | Yes | Yes | Yes | Partial | Yes |
| **Cloud dashboard** | Yes — gradata.ai | Yes | Yes | Yes | No |
| **Pricing (cloud)** | Free / $9-29/mo | $19-249/mo | $0-custom | Enterprise | Free |
| **Funded** | Bootstrapped | $24M (YC S24) | $10M seed | Undisclosed | Undisclosed |
| **Stars** | New | 48K | 21.8K | ~3K | 6.5K |

**Notes below table (important — do not skip):**

> Retrieval accuracy: Hindsight leads at 91.4%. If retrieval accuracy is your primary concern, Hindsight is worth evaluating. Gradata prioritizes behavioral adaptation over retrieval benchmarks — these are different problems.
>
> Letta's "self-improvement" claim: Letta allows LLMs to decide what to store. This is LLM-directed recall, not correction-based graduation. There is no published mechanism for pattern confirmation, confidence scoring, or quality proof.
>
> License alignment: Gradata, Mem0, and Letta are all Apache-2.0. No license-driven friction for enterprise procurement or SaaS redistribution. See the FAQ.

---

**Visual treatment recommendations:**
- Gradata column gets a subtle background highlight (not garish — just a very light tint)
- "Yes" cells in the top 8 rows (the behavioral rows): green text or checkmark icon
- "No" cells in the top 8 rows for competitors: gray, not red (red reads as hostile)
- The "Learns from corrections" row should be the first row and visually bolder than the others — it's the whole positioning in one line
- On mobile: collapse to a card per competitor with just the top 5 rows

---

## 5. Growth Funnel

### AARRR Framework for Gradata

---

**AWARENESS**

Goal: Put "correction-based learning" in front of developers who are frustrated that their agents don't improve.

Channels ranked by leverage:

1. **Hacker News Show HN** — single highest-leverage launch moment. One good HN post can drive 2,000-5,000 unique visitors. This is the priority.

2. **arXiv preprint** — post "Behavioral Adaptation from Corrections in AI Agents: A 73-Session Longitudinal Study" before the public launch or simultaneously. Academic framing gets shared by researchers. Gets cited. Creates permanent credibility. Mem0 did this. Letta's MemGPT paper drove thousands of stars.

3. **Twitter/X thread** — use the thread drafted above at launch. Tag relevant developers in the agent space (not competitors). Reply to threads about agent limitations.

4. **r/MachineLearning** and r/LocalLLaMA — the benchmark post works for both. r/LocalLLaMA specifically because local brain with sqlite-vec is a perfect story for that community.

5. **Dev.to / Hashnode** — the technical tutorial drives organic search traffic over time. Not launch-day wins but important for sustained awareness.

6. **AI Discord servers** (not your own) — identify 5-7 developer Discord servers where agent builders hang out. Drop in the benchmark post when relevant. Not spam — answer questions first, share when genuinely useful.

7. **GitHub Trending** — this is not a tactic you control, but a good README, a clear use case, and HN/Twitter traffic all feed it. Make the README great.

**What to avoid in awareness:**
- ProductHunt at launch — saves it for when you have a working dashboard and some testimonials. PH works best when you have users to upvote it.
- Paid ads — zero ROI at this stage.
- Newsletter cold outreach — not yet.

---

**INTEREST (turning visitors into readers)**

Goal: Someone lands on gradata.ai or the GitHub. Get them to understand the graduation pipeline in under 90 seconds.

Tactics:

1. **README as the product pitch.** The README is the most-read document in open source. It should have: one-liner, the graduation pipeline diagram (even a text diagram), one working code example, and a link to the benchmark data. Length: medium. Not a wall of text, not a one-liner.

2. **Demo GIF on the README.** Show the correction rate chart declining. Show a rule graduating. No narration needed. Visual proof.

3. **gradata.ai homepage.** Three sections: hero (one-liner + the "Mem0 remembers, Gradata learns" contrast), how it works (the graduation pipeline in 3 steps with icons), the comparison table. Clean. No padding.

4. **The benchmark blog post.** This is your "interesting story" content. People who land here from HN or r/ML will spend 5+ minutes. It's the deepest funnel content at the top.

---

**ACTIVATION (first value moment)**

Goal: Developer installs, logs their first correction, sees it tracked.

The critical path:
```
pip install gradata
→ brain = Brain()
→ with brain_context(): [LLM call]
→ brain.correct(original, edited, context="why")
→ brain.status() → shows correction logged, severity: moderate, confidence: 0.30
```

Time to first value: under 10 minutes. This is the activation metric. If it takes longer than 10 minutes, fix that before doing more marketing.

Tactics:

1. **Dead simple install.** One command. No configuration required for basic mode. sqlite-vec is optional — FTS5 works out of the box.

2. **Onboarding email sequence** (for gradata.ai signups):
   - Day 0: "You're in. Here's how to log your first correction." (include the 5-line code snippet)
   - Day 3: "Your first correction has been logged. Here's what the severity analysis found."
   - Day 7: "Check your brain's current status." (link to dashboard)
   - Day 14: "Your first graduation is coming. Here's what to watch for."

3. **Example corrections pre-loaded.** When someone first runs `brain.status()`, show example data so the dashboard isn't empty. (Clear indication it's demo data, not theirs.)

4. **MCP trojan horse.** This is the passive activation channel — the one that works without any user intentionally trying Gradata.

**MCP Trojan Horse Strategy (detailed):**

The MCP server (`gradata-mcp`) installs alongside Claude Code, Cursor, VS Code, or any MCP-compatible host. The developer adds it to their MCP config once.

```json
{
  "mcpServers": {
    "gradata": {
      "command": "uvx",
      "args": ["gradata-mcp"]
    }
  }
}
```

From that point: every LLM interaction the developer has in their MCP host generates potential training signal. They don't have to remember to call `brain.correct()` manually. The sidecar file watcher captures edit patterns passively.

Why this is powerful distribution:
- Zero behavioral change required from the user after install
- Brain builds passively across any workflow (coding, writing, research)
- The dashboard becomes interesting in days, not weeks
- Natural upsell trigger: "Your brain has 12 corrections logged. Sign in to gradata.ai to see your compound score."

MCP integration sequence:
1. User installs `gradata-mcp`
2. Works locally, no account required
3. After 10 corrections, surfaces: "Connect to gradata.ai to see your brain's growth chart"
4. They sign up (free)
5. Dashboard hooks them — they see the chart
6. Pro features become obviously valuable

---

**RETENTION**

Goal: Get developers to keep using Gradata across sessions. The product needs to be stickier than "I installed this once."

Key insight: retention is tied to whether the brain visibly improves. If correction rate doesn't decline in the first 3 weeks, they churn. The product must surface this clearly.

Tactics:

1. **Weekly brain digest email.** Every Monday: "Your brain this week — X corrections logged, Y at PATTERN status, 1 rule graduated." Short. Data. One CTA: "See your full dashboard."

2. **Category extinction notifications.** When a correction category hits zero for 3 consecutive sessions: "Your brain hasn't made a [writing tone] mistake in 3 sessions. That category may be extinct." This is a win worth celebrating. Make it visible.

3. **Rule graduation notifications.** When a rule graduates from PATTERN to RULE: "New behavioral rule graduated: [rule summary]. Confidence: 0.91." Push this to Discord too (opt-in).

4. **The streak mechanic.** "Your brain has improved for 14 consecutive sessions." Simple, visible in the dashboard.

5. **Comparison against your own baseline.** "Your correction rate is 40% lower than when you started." Self-referential benchmarking (not vs other users) is privacy-safe and motivating.

6. **Brain staleness indicator.** If no corrections logged in 7 days, dashboard shows: "Your brain needs sessions to grow." This is both a retention prompt and honest product behavior — the brain doesn't improve without input.

---

**REVENUE**

Goal: Convert active users to paid. The conversion trigger should be obvious — they should feel it when they hit the free tier limit.

Key insight: charge for the intelligence layer, not the storage. Storage is cheap. The graduation engine, quality proof, and compound scoring are the value.

(See Pricing Strategy section below for full detail.)

Tactics at this stage:

1. **Upgrade prompt on dashboard** at specific triggers:
   - Trying to export the manifest
   - Trying to view severity trend chart
   - Trying to run ablation test
   - Brain crosses 50 graduated rules

2. **The "show this to your team" moment.** When the manifest is compelling, the user wants to share it. Make sharing require an account. Make the full shared manifest require Pro.

3. **Startup program** (see below).

---

### Startup Program Design

**Modeled on Mem0's 3-month Pro, but sharper:**

**Gradata Brain Builder Program**

Offer: gradata.ai Pro free for 6 months (not 3 — you need a longer window to show graduation data)

Eligibility:
- Building an AI-powered product (not just experimenting)
- Less than $1M ARR or seed-stage and under
- Accepted into an accelerator OR referred by an existing Brain Builder member
- Agree to share anonymized brain.manifest data for research (opt-out available)

What they get:
- Full Pro dashboard access
- Priority support (Discord #early-access channel)
- Named in the arXiv paper
- 1 onboarding call with Oliver
- First access to composable skills marketplace when it launches

What you get:
- Brain data diversity for the study
- Testimonials grounded in metrics
- Case studies with real numbers
- A reason to talk to 30 early-stage AI founders

Application: simple form, 5 questions, 48-hour response. Accept 15-20 per cohort. Run 2 cohorts before public launch.

---

## 6. Pricing Strategy

### Tier Design

**Free tier — "Local Brain"**

Included:
- Full SDK (Apache-2.0) — 100% capable standalone with BYOK
- Local SQLite brain
- MCP server
- Correction logging
- Basic graduation (INSTINCT/PATTERN/RULE)
- brain.manifest.json auto-generation
- FTS5 search
- `brain.status()` in terminal

Not included (creates pull toward Pro):
- gradata.ai dashboard
- Severity trend charts
- Category extinction view
- Compound quality score (visible on web UI with history; terminal still shows the current value locally)
- Manifest export to PDF / shareable link
- Ablation testing UI (the engine runs locally; Pro adds the UI)
- Cross-tenant corpus insights (opt-in rule donation; visible once ≥100 donors)
- Team / shared brains (later phase)

Philosophy: free is functionally complete. Graduation, meta-rule synthesis (via your own Anthropic key or Claude Code Max OAuth), ablation, quality manifest — all run locally with zero cloud dependency. Pro is visualization, history, export, and eventually the community corpus. A developer running Gradata locally without a dashboard account has the full product; they just don't have the chart.

---

**Pro tier — "Brain Dashboard"**

Price: **$19/month or $180/year ($15/mo)**

Why $19:
- Anchors below Mem0's $19/mo entry tier
- Round number, memorable
- For a developer doing serious agent work, this is obviously worth it
- Annual discount creates commitment

Included:
- Everything in Free
- Full gradata.ai dashboard
- Severity trend analysis
- Category extinction charts
- Compound quality score with history
- Graduation optimization (cloud engine)
- Manifest export (PDF + shareable link)
- Ablation testing UI
- Weekly brain digest email
- Priority Discord channel
- 3 brains (for different projects/agents)

Upgrade trigger language:
> "Your brain has 23 graduated rules. See the full quality picture on gradata.ai Pro."

---

**Team tier — "Shared Brain"**

Price: **$49/month** (up to 5 seats)

Why: Teams running multiple agents with shared correction standards. Agencies. AI dev shops.

Additional inclusions:
- Shared brain across team members
- Correction attribution (who made which correction)
- Conflict resolution UI (when two team members correct the same behavior differently)
- Team dashboard with per-member contribution
- 10 brains

---

**Enterprise tier — "Custom"**

Custom pricing (starting at $500/month, likely $1K-5K).

Target: companies running AI agents at scale, where behavioral consistency is a compliance or quality requirement.

Additional inclusions:
- Self-hosted graduation engine (not open source, licensed binary)
- SSO / SAML
- SOC2 audit trail (correction log + graduation history is already the audit trail — surface it)
- SLA
- Private Slack channel
- Custom brain limits
- API access for programmatic manifest generation
- Legal: dedicated MSA, DPA, and indemnification for enterprise procurement

---

### Price Anchoring Vs Competitors

| Tier | Gradata | Mem0 | Letta |
|---|---|---|---|
| Free | Full SDK + local brain | API access, limited calls | Open source only |
| Pro | $19/mo | $19/mo | Not public |
| Team | $49/mo | $99/mo | Not public |
| Graph memory | Included (graduation = structural knowledge) | $249/mo (paywalled) | N/A |
| Quality proof | Included in Pro | Not offered | Not offered |

Talking point: "Mem0's graph memory is $249/mo. Our graduation engine — which does more — is $19."

---

### "Why Apache-2.0?" Messaging

Put this in the FAQ on gradata.ai. Do not bury it.

**Headline:** Apache-2.0, no strings attached

**Body:**

> The Gradata SDK is Apache-2.0. That means:
>
> - Use it in any product, commercial or otherwise.
> - Modify it, fork it, bundle it.
> - Ship it as part of your own SaaS without sharing modifications.
> - Keep your application code, your fork, and your brain data fully private.
>
> No copyleft obligations. No linking constraints. Same license as LangChain, Mem0, and Letta — the license enterprise procurement already approves.
>
> Why not copyleft? Our moat is not the SDK code. The moat is the hosted tier: team workspaces, the corrections corpus (cross-user network effect that compounds with every user), the brain marketplace, and managed infrastructure. The more the SDK spreads, the stronger those network effects get. Apache-2.0 is the distribution multiplier.
>
> Paid cloud plans exist for teams that want shared brains, observability, marketplace access, or a managed LLM tier without BYOK plumbing. The SDK stays free forever.

---

## Strategic Priorities (ordered)

These are the things that matter before any other marketing work:

1. **Ship the GitHub.** Nothing else is real until the repo is public.
2. **README quality.** The README is the most-read marketing document you will ever write. Get it right.
3. **10-minute install path.** If it takes longer than 10 minutes to see a correction logged, fix that before anything else.
4. **arXiv preprint.** This is the credibility anchor for every channel.
5. **HN Show HN post.** This is the launch.
6. **Early adopter cohort.** 15 people with real data is more valuable than 1,000 passive installs.
7. **gradata.ai dashboard MVP.** This is the retention mechanism and the revenue engine.

Everything else in this document comes after those seven things exist.

---

## What Not To Do

- Do not launch on ProductHunt before you have a working dashboard and 5+ testimonials with real numbers.
- Do not position against Mem0 aggressively in public. "Mem0 remembers. Gradata learns" is the line — it's competitive but not hostile. The comparison table is direct, not derogatory.
- Do not claim anything in the benchmark post that isn't computed from the real events.jsonl. Academic framing makes the numbers matter more, not less.
- Do not open the Discord until the GitHub is live. A Discord with no product is worse than no Discord.
- Do not build the marketplace before you have users. Cold start kills marketplaces. The SDK must be useful standalone first.
- Do not add pricing tiers before you understand what people actually want to pay for. The pricing above is a hypothesis — validate it with the early adopter cohort before publishing it publicly.
