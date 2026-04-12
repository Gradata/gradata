# Your AI Keeps Making the Same Mistakes. We Fixed That.

75% of marketers spend 30+ minutes editing every AI output ([HubSpot, 2024](https://blog.hubspot.com/marketing/state-of-ai-marketing)). 72% of knowledge workers correct AI regularly, burning a quarter of their AI time on corrections ([Writer.com, 2024](https://writer.com/blog/ai-survey-2024)). The AI does not learn from any of it. Every correction you make today will be made again tomorrow.

Today we are launching Gradata, an open source SDK that makes AI agents learn from corrections.

## The Problem

You correct your AI. It forgets. You correct it again. You open the CLAUDE.md file, add a new rule by hand, save it, and hope you remember the phrasing the next time you hit the same bug. Three weeks later you have 50 rules, most of them contradicting each other, and no idea which ones the model is actually following.

Forrester reports 60% of teams abandon AI tools because they "do not understand context" ([Forrester, 2023](https://www.forrester.com/)). GitClear measured a 39% spike in code churn in Copilot-heavy repos ([GitClear, 2024](https://www.gitclear.com/)). Asana found AI saves roughly two hours a week on drafts and costs 1.5 hours a week on edits ([Asana Work Innovation Lab, 2024](https://asana.com/resources/research-ai-work)). The net gain is real but thin, because the feedback loop is broken at the bottom.

## The Insight

Every correction is a teaching moment. Existing tools throw them away. Memory systems like Mem0 and Letta store what the AI said; they do not store what you fixed. A system prompt full of hand-written rules is a static snapshot of what you thought mattered last Tuesday. Neither one closes the loop.

Gradata closes it. Capture every correction, classify it, graduate the ones that prove themselves, kill the ones that do not, and inject the survivors into every future prompt. The AI stops making the same mistakes.

## How it Works

When you call `brain.correct(draft, final)`, a diff engine computes edit distance and severity. An edit classifier categorizes the correction across five dimensions: tone, content, structure, factual, and style. A new lesson is created at INSTINCT state with a starting confidence of 0.30.

From there, the lesson earns its keep. Every future prompt where it applies and does not cause a contradiction is a fire, and confidence rises. Every time it misfires, causing a new error, confidence drops. Fire and misfire attribution is per-lesson, scaled by severity. A trivial survival adds 0.03. A major survival adds 0.12. A major misfire subtracts 0.20.

Lessons that survive repeated application graduate from INSTINCT (0.30) to PATTERN (0.60) to RULE (0.90). Lessons that keep misfiring or sit idle for 20 relevant sessions are killed automatically. When three or more graduated rules share a pattern, a meta-rule emerges and becomes portable across sub-agents.

At inference time, `brain.apply_brain_rules(task)` pulls the survivors scoped to the task type, caps the injection at five rules, and formats them as XML for the LLM. Everything is event-sourced in a single SQLite file. The brain is a directory. Copy it, version it, move it between machines.

## Validation

The architecture was stress-tested by 200 simulated AI/ML expert personas in two blind debates (15 rounds each, 10 research domains, zero knowledge of Gradata). We compared their consensus proposals against Gradata's feature set.

Ten of 14 features were independently proposed by the blind panel, including structured correction storage, error type taxonomy, rule abstraction, and temporal decay. Seven features were classified as novel: the multi-stage graduation pipeline, fire and misfire attribution, auto-climb scope generalization, meta-rules from rule clusters, rule suppression tracking, and the brain manifest quality proof. Zero of 200 experts proposed a multi-stage confidence pipeline with explicit state transitions.

The most telling finding came from the 100 distribution experts. All of them defaulted to federated learning or gradient sharing. Several then criticized gradient-based approaches as inadequate for discrete symbolic knowledge ("never use em dashes" does not translate to a gradient). None proposed sharing discrete human-readable rules directly. Gradata's approach sidesteps the gradient-to-symbolic gap the experts themselves flagged as a primary failure mode.

Synthetic benchmark results from the same sprint:

- 65% token reduction on rule injection with no quality regression (measured by brain_benchmark.py)
- 80% faster preference reversal: 5 events to flip down to 1 on synthetic contradiction scenarios
- 3x faster brain maturation: composite score moved from 22.7 to 67.8 after a bug fix and graduation pipeline tuning

These numbers are from synthetic events and simulated panels, not real users. Multi-user validation is next.

## Who it is For

The JTBD research points to four verticals where the pain is sharpest: legal professionals (compliance and citation correctness), developers (style, naming, API accuracy), support agents (tone, policy adherence), and marketers (brand voice, factual claims). Anyone who corrects AI output daily and keeps fixing the same mistakes. If you maintain a CLAUDE.md longer than 30 lines, Gradata is for you.

## Get Started

```bash
pip install gradata
```

Zero required dependencies. Python 3.11+. AGPL-3.0. Your app code and brain data stay yours.

```python
from gradata import Brain

brain = Brain.init("./my-brain", domain="Engineering")
brain.correct(draft="inline SQL in the API", final="repository pattern in the API")
rules = brain.apply_brain_rules("write API design")
```

Code: [github.com/gradata-systems/gradata](https://github.com/gradata-systems/gradata). Early users can book time with me directly: [calendly.com/oliver-spritesai/30min](https://calendly.com/oliver-spritesai/30min).

Mem0 remembers. Gradata learns.
