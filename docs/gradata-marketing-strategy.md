# Gradata Marketing & Positioning Strategy
**Version:** 2.0 | **Date:** 2026-04-05 | **Stage:** Pre-launch, zero public users

**Core repositioning:** "Procedural memory for AI agents" (infrastructure pitch) replaced with "AI that learns your judgment" (personalized intelligence pitch).

---

## 1. Positioning Framework

### The Core Insight

The AI isn't getting generally smarter. It's converging on the user's judgment. Every correction encodes expertise. Meta-rules emerging = the AI predicting your patterns across domains. To the user, that IS intelligence.

This changes everything about how we talk about Gradata. We are not selling infrastructure. We are selling personalized intelligence with proof.

---

### The One-Liner

**"Mem0 remembers. Gradata learns."**

Unchanged. Still carries all the differentiation in 3 words.

---

### The Tagline

**"AI that learns your judgment."**

Alternative taglines for A/B testing:
- "Your AI stops making the same mistake twice."
- "The only SDK that proves your AI is getting smarter for you."
- "Train an AI brain on your judgment. Rent it to your team."

---

### The "Only We Can Say This" Claims

1. **"We extract behavioral instructions from corrections."** Not diff fingerprints. Actual instructions like "Use casual tone in emails." The correction pipeline doesn't just detect that something changed — it extracts what the human intended.

2. **"We can show you a convergence curve."** Corrections-per-session declining over time. When it flattens, your AI has learned your style. No competitor has this metric because no competitor tracks correction patterns at this granularity.

3. **"Trained brains are rentable."** A brain calibrated to a sales leader's judgment can be shared with new team members. The brain carries the leader's patterns, not generic instructions.

---

### Messaging Hierarchy

**Hero headline (gradata.ai):**
> AI that learns your judgment.

**Subhead:**
> Every correction teaches your AI something. Gradata extracts the behavioral instruction, graduates it into a rule, and proves your AI is converging on your style. Not generally smarter. Smarter for you.

**Proof Points (ordered by trust-building value):**

1. **Behavioral extraction from corrections.**
   Not diff fingerprints — real instructions. When you change "Hey team" to "Hi everyone," the system extracts "Use inclusive, slightly formal greetings" not "Content change (added: Hi everyone)." This is the core technical differentiator.

2. **Convergence metric.**
   Corrections-per-session declining over time. This is the chart that sells the product. When the curve flattens, the AI has learned your style. Every session generates this data automatically.

3. **Meta-rules = personalized intelligence.**
   When your email tone preferences start aligning with your code review style and your process preferences — that's a meta-rule. The AI predicting your behavioral patterns across domains. To the user, this IS the AI "getting" them.

4. **Ablation experiment: +13.2% quality improvement.**
   Driven by preference adherence. Not general intelligence gains. The AI got better at matching what the specific user wanted. This is the proof point for every skeptic.

---

### Objection Handling

**"How is this different from Mem0?"**

Direct answer:
> Mem0 stores context. Gradata evolves behavior. Mem0 doesn't track whether the same mistake recurs, doesn't graduate behavioral rules, doesn't prove convergence. You could use both — they solve different problems. Mem0 makes your agent remember. Gradata makes your agent learn.

**"Can't I just use a good system prompt?"**

Direct answer:
> System prompts are static. Gradata's rules are dynamic. They graduate, decay, and evolve based on your corrections. A good system prompt is where you start. Gradata is how it gets better. After 93 sessions, the system has extracted 39 graduated rules that no human would have thought to put in a system prompt — because they emerged from actual usage patterns.

**"Why would someone rent a brain?"**

Direct answer:
> A sales leader trains a brain over 200 sessions. Their patterns, style, judgment — encoded. A new SDR rents that brain and writes in the leader's voice on day one. The brain isn't smarter. It's calibrated. The alternative is 3 months of the new hire learning the leader's style through trial and error.

**"You have zero users."**

Direct answer:
> 93 sessions of production data. Ablation experiment showing +13.2% improvement. 39 graduated rules. 6 category extinctions. The data is auditable. The events.jsonl is public. The methodology is documented. This isn't a promise — it's a track record with verifiable numbers.

---

## 2. Competitive Positioning

### Comparison Table

| Competitor | What they do | Our advantage |
|---|---|---|
| Mem0 | Stores context for retrieval | We evolve behavior from corrections |
| Letta (MemGPT) | LLM-decided memory recall | We graduate rules with measurable confidence |
| LangChain Memory | Buffer/vector context storage | We track correction patterns, not just context |
| Fine-tuning | Permanent model modification | We adapt at inference time, no retraining |
| System prompts | Static instructions | Our rules graduate, decay, and evolve dynamically |

**Key differentiator:** None of these extract behavioral instructions from corrections, graduate them through confidence tiers, or prove convergence with a measurable metric.

---

## 3. Launch Content Plan

### Blog Post #1: Problem-Aware

**Title:** "Your AI Doesn't Know You Yet"

**Hook:** Every correction you make is expertise your AI throws away. You fixed the tone yesterday. You'll fix it again tomorrow. Not because the model is bad — because nothing captures the behavioral instruction behind your edit and turns it into a permanent rule.

**Structure:**
- The correction waste problem (every edit = lost expertise)
- Why memory isn't learning (storing context vs changing behavior)
- What it would look like if your AI actually learned from corrections
- CTA: "This is what Gradata does. [link to GitHub]"

---

### Blog Post #2: Solution-Aware

**Title:** "How Your AI Learns Your Judgment"

**Target reader:** Developer who understands the problem and wants the mechanism.

**Structure:**
- Walk through the pipeline: correct -> extract -> graduate -> converge
- The three-tier graduation model (INSTINCT -> PATTERN -> RULE)
- Why behavioral extraction matters (real instructions, not diff fingerprints)
- The convergence curve: what it looks like when your AI has learned your style
- CTA: "Install in 5 minutes. pip install gradata"

---

### Blog Post #3: Proof

**Title:** "93 Sessions: My AI Stopped Needing Corrections in 6 Categories"

**Target reader:** Technical skeptic. Researcher. Someone who needs data before trusting a new tool.

**Structure:**
- The dataset (93 production sessions, unfiltered)
- Ablation experiment results (+13.2% quality improvement)
- Category extinction timeline (which error types disappeared first)
- The convergence curve (corrections-per-session declining)
- What meta-rules look like in practice
- CTA: Link to GitHub, link to arXiv preprint when published

---

### Show HN Post

**Title:**
> Show HN: I built a system that makes AI learn your personal judgment

**Strategy:**
- Lead with the ablation experiment (+13.2% quality improvement)
- Emphasize it's open source (AGPL-3.0)
- Show the convergence curve data
- Be present and engage for the first 3 hours
- If someone mentions Mem0/Letta, use the objection handling language above
- If someone says "this is just prompt engineering," explain the dynamic graduation pipeline

---

### Twitter/X Launch Thread (7 tweets)

**Tweet 1 (hook):**
> Your AI doesn't know you. It doesn't learn from your corrections. Every edit you make is expertise it throws away.

**Tweet 2:**
> We built Gradata: an open-source SDK that captures your corrections and turns them into behavioral rules.

**Tweet 3:**
> Not diff fingerprints. Real instructions: "Use casual tone in emails" not "Content change (added: hey)"

**Tweet 4:**
> Rules graduate through confidence tiers. INSTINCT -> PATTERN -> RULE. Meta-rules emerge when patterns cluster.

**Tweet 5:**
> We ran an ablation experiment: +13.2% quality improvement. All from preference adherence. The AI isn't smarter. It's smarter for you.

**Tweet 6:**
> Coming soon: rent trained brains. A sales leader's 200-session brain, available to new team members on day one.

**Tweet 7 (CTA):**
> pip install gradata. AGPL. Zero dependencies. Works with any LLM.

---

### Reddit r/MachineLearning

**Title:**
> Correction-based behavioral learning: extracting actionable instructions from human edits

**Framing:** Research, not product pitch. Emphasize the graduation pipeline and convergence metric. Invite critique on the confidence thresholds and severity calibration. Lead with data, not brand.

**What works on r/ML:**
- Data first, product second
- Invite critique — the community engages when they think they can find a flaw
- No marketing language
- Respond to every top-level comment in the first hour

---

## 4. Updated Proof Points

From S93 ablation experiment:

- **+13.2%** overall quality improvement with brain rules
- **+1.5** preference adherence score (the core value prop)
- **93** sessions of real production use
- **39** graduated rules at RULE confidence (1.00)
- **6** category extinctions (domains where corrections stopped)
- Corrections-per-session **declining measurably**

These numbers are computed from events.jsonl. Not self-reported. Auditable. The methodology is documented and reproducible.

---

## 5. Brain Rental Business Model (Future)

### The Rentable Asset

A trained brain calibrated to a specific human's judgment.

### Use Cases

- **Sales team:** Leader trains brain over 200 sessions. SDRs rent it. Write in the leader's voice on day one. No 3-month ramp.
- **Code review:** Senior engineer trains brain. Juniors get the senior's review patterns. Consistent standards without the senior reviewing every PR.
- **Customer support:** Best agent trains brain. New agents get their resolution style. Customer experience stays consistent through hiring cycles.

### Revenue Model

Free to train (open source SDK). Pay to rent.

Subscription per brain rental. The person who trains the brain owns it. The people who rent it pay a subscription. The trainer can monetize their expertise without being in the room.

---

## 6. Meta-Rules = Personalized Intelligence

This is the key insight for positioning. Meta-rules aren't just "grouped rules." They're the AI predicting your behavioral patterns across categories.

When your email tone preferences start aligning with your code review style and your process preferences — that's a meta-rule. The AI starts "getting" you across domains.

To the user, the AI IS smarter for them. Not generally more intelligent. Converged on their judgment. That's what we sell.

This is the difference between "AI with memory" and "AI with judgment." Memory stores what happened. Judgment predicts what you would do. Gradata builds judgment from corrections.
