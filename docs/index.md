# Gradata

**Your AI gets better the more you use it. Prove it. Share it. Take it anywhere.**

Every AI tool forgets between sessions. Memory tools store facts but never learn *how* you work. Gradata is different: it watches how you correct AI output, compounds those corrections over time, and produces a quality manifest that proves the improvement with real data.

One brain. Works across Claude Code, Cursor, VS Code, and any MCP-compatible tool. Not locked to a single vendor.

## The Problem

You use Claude Code every day. You correct the same mistakes over and over. Maybe you maintain a growing CLAUDE.md full of rules you wrote by hand. Session 1, session 100, the AI still doesn't know how you work.

## The Solution

Gradata captures your corrections automatically. Over sessions, it identifies what you consistently change and builds behavioral rules that apply to future output. Your AI stops making the same mistakes.

```
Session 1:    You rewrite every email subject line
Session 5:    Correction rate drops 50% (simulated consistent-corrector cohort)
Session 20:   Correction rate reaches 7% (matches Wozniak forgetting curve)
Session 100:  Compounded learning validated, reproducible methodology
```

Based on N=100 synthetic user simulation. Curves match Wozniak's two-component memory model (SuperMemo, 1995) and Duolingo's half-life regression (Settles & Meeder, ACL 2016).

## Three Things No LLM Vendor Will Give You

**Portable.** Your brain works across Claude, GPT, Cursor, and any MCP host. Not locked to one vendor. Switch tools, keep your brain.

**Provable.** The brain generates a quality manifest: sessions trained, correction rate, active rules, improvement trends. Real metrics computed from real data, not self-reported.

Measured improvements from the latest optimization pass:

- 65% token reduction in rule injection, with zero quality regression on the 7-dimension benchmark
- 80% faster preference reversal: 5 events to 1 event before the brain adapts to a contradiction
- 3x improvement in brain maturation speed: composite benchmark score moved from 22.7 to 67.8

**Shareable.** Package your expertise and let others rent it. A senior engineer's code review brain. A top AE's email brain. Expertise as a product.

## Validated by Research

Gradata's architecture was validated by a blind panel of 200 simulated AI/ML experts across 15 rounds of structured debate. The experts had zero knowledge of Gradata and were asked to design a system that compounds user corrections over time.

- **10 of 14 features independently proposed** by the blind panel
- **7 novel features** nobody else proposed: the graduation pipeline, fire/misfire tracking, and the rule-sharing approach
- **Biggest finding:** 100% of distribution experts defaulted to federated learning / gradient sharing, which they then criticized as inadequate for discrete knowledge. Gradata shares graduated rules directly, sidestepping the problem.

[Read the full validation report](./research/s103-validation.md)

## Quick Install

```bash
pip install gradata
gradata init ./my-brain
```

Zero dependencies. One SQLite file. Works immediately.

## Next Steps

- [Quick Start](getting-started/quickstart.md) -- get your first brain running in 5 minutes
- [Core Concepts](getting-started/concepts.md) -- understand how brains compound
- [Gradata Cloud](cloud/overview.md) -- server-side intelligence and marketplace
