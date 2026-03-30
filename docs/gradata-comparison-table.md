# Gradata Competitive Comparison Table
## For gradata.ai landing page

### Three-Phase Learning Pipeline (adapted from EverMemOS lifecycle framing)

| Phase | EverMemOS (memory) | Gradata (learning) |
|-------|-------------------|-------------------|
| **Phase 1: Capture** | Episodic Trace Formation | Correction Capture (edit distance, severity classification) |
| **Phase 2: Consolidate** | Semantic Consolidation | Graduation Engine (INSTINCT → PATTERN → RULE) |
| **Phase 3: Apply** | Reconstructive Recollection | Context Injection (scope-matched rules, primacy/recency positioning) |

EverMemOS stores and retrieves. Gradata learns and improves.

---

### Direct Comparison Table (for landing page)

| Feature | Gradata | Mem0 | Letta | Zep | Hindsight | EverMemOS |
|---------|---------|------|-------|-----|-----------|-----------|
| **Learns from corrections** | Yes | No | Vague ("self-improvement") | No | No | No |
| **Graduation engine** | INSTINCT → PATTERN → RULE | No | No | No | No | No |
| **Quality proof (manifest)** | Correction rate, category extinction, compound score | No | No | No | No | No |
| **Ablation-tested rules** | Yes (causally verified) | No | No | No | No | No |
| **Memory recall** | Basic (SQLite FTS5) | Strong (vector + graph) | Strong (tiered) | Strong (temporal graph) | Best (91.4% LongMemEval) | Strong (92.3% LoCoMo) |
| **Knowledge graph** | No | Pro tier only | No | Yes (Graphiti) | Yes | No |
| **Multi-agent** | Yes (CARL rule transfer) | Yes | Yes (subagents) | Yes | Yes | Yes |
| **Cross-session persistence** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Session-type-aware decay** | Yes | No | No | No | No | No |
| **Severity-weighted confidence** | Yes (trivial → rewrite) | No | No | No | No | No |
| **Meta-rule emergence** | Yes (3+ related rules → principle) | No | No | No | "Reflect" (insights) | No |
| **Cost per request** | ~$0.004 (10 rules injected) | Varies (API calls) | Varies | Varies | Self-hosted | Varies |
| **Open source** | Yes (AGPL/Apache TBD) | Apache 2.0 | Apache 2.0 | MIT (Graphiti) | MIT | Apache 2.0 |
| **Self-hosted** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Cloud option** | Coming (gradata.ai) | Yes ($19-249/mo) | Yes | Yes ($25/mo+) | No | Coming |
| **GitHub stars** | Pre-launch | ~48K | ~21.8K | N/A | ~6.5K | ~3.3K |
| **Academic paper** | In progress (arXiv) | No formal paper | ICLR 2024 (MemGPT) | No | No | arXiv:2603.23516 (MSA) |

### The "Only We Can Say This" Claims

1. **"Your AI stops repeating mistakes."** No other system tracks corrections, measures severity, and graduates behavioral rules.
2. **"Prove your AI improved."** brain.manifest provides correction rate decay, category extinction count, and compound quality score. Nobody else has quality proof.
3. **"10 rules, not 10 million tokens."** Gradata distills 73 sessions of corrections into 10 behavioral rules. MSA needs 169GB of GPU memory for 100M tokens. We need a text file.

### Objection Handling

**"How is this different from Mem0?"**
Mem0 stores facts your AI told you. Gradata learns from mistakes your AI made. Mem0 remembers that you prefer Python. Gradata learns to stop using em dashes in emails after you corrected it 3 times. Different problem, different solution.

**"Can't I just use a long context window?"**
You can. It costs ~$175 per request at 100M tokens. Gradata injects 10 rules for $0.004. Also: having every email you ever wrote open in tabs doesn't mean you learned from them.

**"Letta says it self-improves too."**
Ask them: how? What's the mechanism? How do they measure improvement? Gradata: edit distance severity → confidence scoring → three-tier graduation → ablation verification. Published methodology, open source code, reproducible benchmark.

**"Why not just write a better system prompt?"**
You could. But you'd need to manually identify every pattern from every correction, decide which are real patterns vs one-offs, update the prompt continuously, and track whether each rule actually helps. Gradata automates all of this and proves it works.
