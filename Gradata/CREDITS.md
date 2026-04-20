# Credits & Intellectual Lineage

Gradata synthesizes ideas from decades of research and engineering practice. Standing on the shoulders of giants isn't stealing — it's the whole point of an open ecosystem. This document credits the work that shaped Gradata.

## Research foundations

- **Constitutional AI** (Anthropic, 2022) — the self-critique + revision loop under `sdk/src/gradata/enhancements/rule_verifier.py` is inspired by the RLAIF methodology introduced in *"Constitutional AI: Harmlessness from AI Feedback"* (Bai et al., 2022).
- **Half-life regression** (Settles & Meeder, ACL 2016) — confidence decay curves in the graduation engine draw on *"A Trainable Spaced Repetition Model for Language Learning"* and the Wozniak/Duolingo two-component memory model.
- **Generative agents** (Park et al., Stanford 2023/2024) — *"Generative Agents: Interactive Simulacra of Human Behavior"* and *"Generative Agent Simulations of 1,000 People"* (2024) validate our simulation-first design methodology; the latter demonstrated generative agents are ~85% as accurate as humans on survey responses.
- **MT-Bench / LLM-as-judge** (Zheng et al., NeurIPS 2023) — scoring methodology in `brain/scripts/brain_benchmark.py` adapts the multi-judge consensus approach from *"Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"*.
- **Self-preference bias in LLM judges** (2024) — informs our anonymization step before judging to control known evaluator biases.
- **Grammarly ROI study** (2024) — the "19 days saved per year" framing informs our *Est. Time Saved* KPI.
- **Copilot RCT** (Peng et al., 2023) — *"The Impact of AI on Developer Productivity: Evidence from GitHub Copilot"* reported a 55.8% speedup on a controlled coding task and anchors our developer-impact benchmarks.
- **SuperMemo 2 / two-component memory** (Wozniak, 1995) — retrievability + stability decomposition underpinning our confidence decay model.
- **Persona transparency** (AAAI 2025) — persona documentation requirements for simulation research inform how we publish MiroFish panels.

## Architectural inspirations

- **Mem0** — shared memory-first framing for AI agents. Gradata's difference: we learn from corrections, not just recall facts.
- **Letta** (formerly MemGPT) — agent state persistence patterns. Gradata's difference: state is rules, graduated from evidence rather than stored conversations.
- **EverMind / EverMemOS** (TCCI, 2025) — reported 92.3% on the LoCoMo memory-recall benchmark. Gradata is complementary: it adds the correction-learning layer on top of memory recall.
- **The 15 agentic patterns** — orchestrator, reflection, memory, rule_engine, RAG, tree-of-thoughts, and the rest are standard LLM-app primitives. Gradata builds the *enhancements* layer (`diff_engine`, `quality_gates`, `truth_protocol`, `meta_rules`, `rule_verifier`) on top of these primitives.

## Research methodology

- **MiroFish expert-panel simulation** — multi-round structured debate across grounded personas. Our adaptation lives in `brain/scripts/mirofish_sim.py`. The methodology is our own synthesis of published simulation work (Park et al.; Anthropic's Constitutional AI).
- **Mann-Kendall trend test** — autocorrelation-aware statistical validation used in our convergence checks.
- **OASIS framework** — indirect influence on our batch-run pattern for stress tests.
- **Karpathy-style autoresearch** — iterative self-improvement with verification gates. Our optimization runner adopts this pattern.

## Open-source dependencies

Key libraries Gradata is built on: FastAPI, Next.js, Recharts, Supabase, Stripe, Pydantic, pytest, Vitest, Tailwind, Radix UI, React. Full dependency lists are in `pyproject.toml` and `package.json`.

## What's new here

Gradata's novel contribution is the **graduation pipeline + correction tracking + compound proof** — the data dynamics that make personal AI learning work. Not the patterns. Not the libraries. The loop.

## License

Gradata is **Apache-2.0** — use it, fork it, embed it. No copyleft restrictions on your application.
