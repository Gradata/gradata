# X Thread — Launch Day

10 tweets. 280 chars each. Drop all at once as a native thread. No link in tweet 1 (X suppresses reach).

---

**1/10 — Hook**

Your AI forgets how you work every single session.

You correct the same em dash Monday. Correct it Tuesday. Correct it Wednesday.

I built the layer that fixes this. Open sourced it today. Here's what it does and why 200 simulated AI researchers couldn't beat the design.

---

**2/10 — The problem, with receipts**

HubSpot 2024: 75% of marketers spend 30+ minutes editing AI output per piece.

Writer.com (n=1600): 72% correct AI regularly. 25% of saved time goes back into corrections.

Forrester: 60% abandon AI tools because "it didn't understand context."

AI has a memory problem.

---

**3/10 — What Gradata actually is**

Gradata is a learning layer that sits under your LLM.

Every correction you make becomes an event. Severity, category, diff, all logged.

Patterns that repeat get promoted to rules. Rules get injected into every future session automatically. No fine-tuning.

---

**4/10 — The graduation pipeline**

Correction fires once → INSTINCT (confidence 0.40).

Fires three times without you reversing it → PATTERN (0.60).

Fires five times with survival proof → RULE (0.90).

Only graduated rules get injected. Low-signal noise gets decayed out.

---

**5/10 — Rule injection**

Max 10 rules per session. XML format. Scope-matched to the task type.

Our autoresearch loop (28 iterations) cut injection tokens 65% with zero quality regression. 478 tokens → 166 tokens on our benchmark.

1,934 tests pass. Measured, not vibes.

---

**6/10 — Validation: 200 simulated experts**

I ran a blind debate. 100 AI researcher personas per sim × 2 sims. 15 rounds each. Zero knowledge of Gradata. 3000 posts.

Then I compared their independent consensus against my feature set.

10 of my 14 features were independently proposed.

---

**7/10 — The novel part**

Zero of 200 experts proposed the graduation pipeline. They all said "store and retrieve." Gradata adds "store, test, graduate, and prove."

Distribution experts defaulted to federated learning. Multiple then argued gradients can't carry symbolic rules. We just share the rules.

---

**8/10 — Measured outcomes (synthetic)**

65% fewer tokens injected (benchmark).
3x faster brain maturation (22.7 → 67.8 on our composite).
80% faster preference reversal (5 events → 1 event to flip).
100% correction drop by session 5 for consistent users (synthetic cohort).

---

**9/10 — What's free and what's paid**

Open source SDK, AGPL-3.0: graduation pipeline, rule injection, correction tracking, brain manifest. Runs locally, works with Claude Code today.

Paid cloud tier: brain sync across machines, team-shared rules with k-anonymity and transfer_scope controls.

---

**10/10 — Try it**

SDK: github.com/Gradata/gradata

Book 30 min if you want to talk enterprise deployment (legal, dev teams, marketing ops): calendly.com/oliver-spritesai/30min

Built in the open. I'll post the full 200-expert methodology next.

---

## Notes

- Numbers are from synthetic benchmarks. Tweet 8 says so explicitly. Never imply real-user data.
- Tweet 1 has no link so the algorithm doesn't suppress it.
- Tweet 10 is where all the links land.
- First reply: quote-tweet with the TikTok demo video.
- Second reply: pinned thread of install steps.
