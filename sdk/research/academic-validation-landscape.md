# Academic Validation Landscape: AI Memory & Personalization Systems
## Research for Gradata Paper Preparation
### Date: 2026-03-27 (updated S74)

---

## 0. KEY PRIOR ART: "Distilling Feedback into Memory-as-a-Tool" (ICLR 2026 Workshop)

### Paper: arXiv:2601.05960
**Author:** Victor Gallego
**Venue:** ICLR 2026 MemAgents Workshop (OpenReview: U51WxL382H)

### Why This Matters
This paper **independently validates Gradata's core approach.** It converts transient feedback into retrievable guidelines via a file-based memory system, matching the performance of test-time refinement pipelines while "drastically reducing inference cost."

### Key Findings
- Feedback distilled into persistent memory matches online refinement quality
- File-based storage (not vector DB) is sufficient
- Cost reduction is dramatic vs re-processing feedback each time
- Gradient-free approach (no fine-tuning needed)

### How Gradata Extends This
- Gallego stores feedback as flat guidelines. Gradata **graduates** feedback through confidence tiers (INSTINCT → PATTERN → RULE)
- Gallego treats all feedback equally. Gradata **severity-weights** corrections (trivial → rewrite)
- Gallego has no decay. Gradata has **session-type-aware decay**
- Gallego has no quality proof. Gradata has **brain.manifest** with correction rate tracking

### Citation for Paper
```
@article{gallego2026distilling,
  title={Distilling Feedback into Memory-as-a-Tool},
  author={Gallego, Victor},
  journal={ICLR 2026 MemAgents Workshop},
  year={2026},
  url={https://arxiv.org/abs/2601.05960}
}
```

---

## 0b. EverMind / MSA: Memory Sparse Attention (arXiv:2603.23516, March 2026)

### Paper: "MSA: Memory Sparse Attention for Efficient End-to-End Memory Model Scaling to 100M Tokens"
**Authors:** Yu Chen, Runkai Chen, et al. (EverMind / Shandong Group / Peking University)
**Backing:** Tianqiao Chen (Shanda Group, $2B+ AI investment)

### Architecture
- Sparse attention with document-wise RoPE (position IDs reset per document)
- Offline corpus encoding into compressed K/V chunks (64-token segments)
- Online routing: top-k document selection via learned routing keys
- Memory Interleaving for multi-hop reasoning
- 4B model on 2xA800 GPUs, 169GB for 100M tokens

### Key Results
- 4B model beats RAG + Qwen3-235B by +7.2% average on 9 QA benchmarks
- NIAH: 94.84% accuracy at 1M tokens (vs vanilla Qwen3-4B at 24.69%)
- <9% degradation from 16k training to 100M inference

### Limitations
- Wins 4/9 benchmarks, loses 5 (MuSiQue gap: -16.5%)
- No code/weights released yet ("Coming Soon")
- No latency numbers published
- Static corpus only (no incremental updates)
- 169GB GPU memory = $30K+ hardware

### Relationship to Gradata
**Complementary, not competitive.** MSA solves recall (finding needles in 100M haystacks). Gradata solves learning (graduating corrections into behavioral rules). MSA commoditizes the recall layer, which strengthens Gradata's positioning: "Models are getting better at remembering. They still can't learn from their mistakes."

### What to Steal
1. **Document-wise RoPE** — apply to rule injection (each rule gets own position context)
2. **Three-phase lifecycle framing** (from EverMemOS: Episodic Trace → Semantic Consolidation → Reconstructive Recollection)
3. **MemCell/MemScene abstractions** — typed correction cells for the SDK

### EverMemOS (Product)
- GitHub: 3.3K stars, Apache 2.0
- Architecture: Episodic Trace Formation → Semantic Consolidation → Reconstructive Recollection
- Stack: MongoDB + Elasticsearch + Milvus + Redis
- Benchmark: 92.3% on LoCoMo (SOTA as of early 2026)
- Cloud product coming later 2026

---

## 1. MemGPT / Letta (ICLR 2024 Preprint, arXiv:2310.08560)

### Paper: "MemGPT: Towards LLMs as Operating Systems"
**Authors:** Charles Packer, Vivian Fang, et al. (UC Berkeley Sky Lab)

### Evaluation Tasks
1. **Document QA** -- Questions from NaturalQuestions-Open dataset with Wikipedia documents as context. Tests ability to analyze documents exceeding the LLM context window.
2. **Multi-session Chat (Deep Memory Retrieval)** -- Agent asked questions about topics from prior conversations (sessions 1-5). Tests long-term conversational memory.
3. **Conversation Opener Task** -- Measures quality of conversation initiations using CSIM scores.
4. **Nested KV Retrieval** -- Stress test for recursive context management. MemGPT was the only approach able to consistently complete beyond 2 nesting levels.

### Metrics Used
- **LLM Judge Accuracy** -- Binary correctness as judged by a separate LLM
- **ROUGE-L** -- Longest common subsequence between generated and reference text
- **CSIM** -- Conversation similarity metric for opener quality
- **Task completion rate** for nested KV retrieval

### Baselines
- GPT-3.5 Turbo (fixed context)
- GPT-4 (fixed context)
- Non-oracle fixed-context baselines capped at retriever performance

### Key Results
- MemGPT significantly outperformed both GPT-4 and GPT-3.5 on LLM Judge accuracy and ROUGE-L
- Fixed-context baselines are capped at retriever performance; MemGPT breaks this ceiling via multiple archival storage queries
- Only system to handle nested KV beyond 2 levels

### Limitations Acknowledged
- Evaluation focused on memory retrieval, not behavioral adaptation
- No measurement of whether memory improves user-specific outcomes over time
- No correction-based learning signal
- System cost (token overhead) not thoroughly benchmarked against simpler approaches

### What We Can Steal
- **LLM-as-Judge methodology** for evaluating output quality
- **ROUGE-L as objective metric** for measuring draft quality against accepted versions (maps to our edit distance metric)
- The **operating system metaphor** is powerful framing -- we can position Gradata as the "learning layer" that MemGPT's memory layer lacks

### Letta Skill Learning Results (2026)
Letta also published skill learning results on Terminal Bench 2.0:
- +21.1% improvement with trajectory-only skills
- +36.8% improvement with feedback-enriched skills
- -15.7% cost reduction, -10.4% fewer tool calls

This is the closest competitor approach to our correction-based learning, but critically: Letta learns from agent trajectories (self-reflection), NOT from user corrections/edits.

---

## 2. Mem0 (arXiv:2504.19413)

### Paper: "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory"
**Published:** April 2025

### Evaluation Methodology
- Primary benchmark: **LOCOMO** (Long-term Conversational Memory)
- Six baseline categories tested: memory-augmented systems, RAG variants (varying chunk sizes and k-values), full-context approach, open-source memory solutions, proprietary model systems, dedicated memory management platforms

### Metrics Used
- **LLM-as-a-Judge Score** (primary) -- Overall quality rating by a judge LLM
- **p95 Latency** (seconds)
- **Token consumption** per conversation
- Performance breakdown by question type: single-hop, temporal, multi-hop, open-domain

### Key Numerical Results
- 26% relative uplift over OpenAI memory (66.9% vs 52.9% LLM-as-Judge)
- Mem0^g (graph variant) adds ~2% on temporal questions via explicit relationship edges
- 91% lower p95 latency (1.44s vs 17.12s for full-context)
- 90% token reduction (~1.8K tokens vs 26K for full-context)

### What Mem0 Does NOT Validate
- **No behavioral improvement measurement** -- They measure memory retrieval accuracy, not whether the AI got better at a user's tasks
- **No correction tracking** -- Memories are extracted passively from conversations, not from user edits
- **No longitudinal quality proof** -- No "the system improved from session 1 to session N" evidence
- **No pattern graduation** -- Facts are stored or not; no confidence-based promotion
- **No quality feedback loop** -- No mechanism to know if a retrieved memory actually helped

### Critical Finding from MemoryBench
MemoryBench (arXiv:2510.17281) tested Mem0, A-Mem, and MemoryOS against simple RAG baselines. Result: **none of the advanced memory systems consistently outperformed RAG baselines** across heterogeneous task formats. Mem0 showed inconsistent memory construction times and poor generalization beyond the LOCOMO-style tasks it was designed for.

### What We Can Steal
- LOCOMO as a benchmark framework structure (5 question types)
- LLM-as-Judge methodology (widely accepted in the field)
- Token efficiency metrics (important for practical deployment)
- **Their gap is our paper's thesis**: "Mem0 remembers. Gradata learns."

---

## 3. Key Related Academic Work

### 3.1 PAHF: Personalized Agents from Human Feedback (arXiv:2602.16173, Feb 2026)

**CLOSEST PRIOR ART TO GRADATA.** This paper is critical.

**Approach:** Three-step iterative loop:
1. Pre-action clarification (agent asks questions before acting)
2. Action grounded in retrieved preferences from memory
3. Post-action feedback integration when preferences drift

**Memory Update:** Detect-summarize-integrate pipeline. New feedback assessed for salience, summarized via LLM, then merged with similar existing entries (above threshold tau) or added as new entries.

**Preference Drift Handling:** Post-action feedback is the correction mechanism. Theoretical proof: without post-action updates, agents incur Omega(T) errors under preference switches. With immediate post-action updates after errors, mistakes reduce to O(K) where K = number of preference switches.

**Metrics:**
- Success Rate (SR)
- Feedback Frequency (FF) -- proportion of tasks requiring human feedback
- Average Cumulative Personalization Error (ACPE): ACPE_t = (1/t) * sum(PE_s) for s=1..t

**Baselines:** No Memory, Pre-action Only, Post-action Only, PAHF (both channels)

**Key Results:**
- Embodied manipulation: PAHF 70.5% success vs 32.3% no-memory
- Post-drift: PAHF 68.8% vs 44.8% no-memory
- Online shopping: PAHF 70.3% post-drift vs 27.0% baseline

**Critical Differences from Gradata:**
- PAHF learns preference facts; Gradata learns behavioral rules
- PAHF has no graduation mechanism (no INSTINCT -> PATTERN -> RULE)
- PAHF operates on simulated users; Gradata operates on a real user over months
- PAHF does not track diff-based learning signal
- PAHF has no quality proof/manifest system

**What We Must Cite and Differentiate:** PAHF's ACPE metric is directly comparable to our CRO. Their theoretical O(K) bound for correction learning is useful framing. We should position Gradata as "PAHF for behavioral rules, not just preference facts, validated longitudinally on a real user."

### 3.2 ARIA: Adaptive Reflective Interactive Agent (arXiv:2507.17131, Jul 2025)

**Approach:** LLM agent that learns updated domain knowledge at test time via structured self-dialogue. Identifies knowledge gaps, requests targeted corrections from human experts. Maintains timestamped knowledge repository with conflict detection.

**Deployed at:** TikTok Pay, serving 150M+ monthly active users.

**Key Relevance:** Their "timestamped knowledge repository with conflict detection" is analogous to our CARL system. Their "detecting and resolving conflicting or outdated knowledge" maps to our lesson retirement/update mechanism.

**Critical Difference:** ARIA learns domain knowledge (rules, regulations). Gradata learns user-specific behavioral patterns from corrections. Different learning signal, different target.

### 3.3 Personalized-RLHF / P-RLHF (arXiv:2402.05133, Feb 2024)

**Approach:** Lightweight user model captures individual preferences, jointly learned with personalized LLM from human feedback. Handles both explicit (textual) and implicit (encoded in feedback) preferences.

**Key Insight:** Vanilla RLHF assumes uniform preferences across all users. P-RLHF breaks this assumption with per-user models.

**Difference from Gradata:** P-RLHF requires model fine-tuning. Gradata achieves personalization through context injection without weight changes. P-RLHF is a training-time approach; Gradata is a deployment-time approach.

### 3.4 Hypotheses-to-Theories (HtT) Framework (arXiv:2310.07064)

**THE CLOSEST PRIOR ART TO OUR GRADUATION MECHANISM.**

**Approach:** Two-stage rule learning:
1. **Induction stage:** LLM generates and verifies rules over training examples
2. **Deduction stage:** Rules that appear and lead to correct answers sufficiently often are collected into a rule library. LLM then uses the library for reasoning.

**Results:** 10-30% absolute accuracy gain. Rules are transferable across models and problem formulations.

**Critical Comparison to Gradata:**
- HtT's "rules that appear sufficiently often" = our "INSTINCT that appears 3+ times graduates to PATTERN"
- HtT's rule library = our lessons.md at RULE level
- HtT applies to reasoning tasks; Gradata applies to behavioral adaptation from user corrections
- HtT rules are task-agnostic; Gradata rules are user-specific
- HtT has no confidence scoring or decay mechanism
- HtT has no retirement/invalidation of rules

**What We Must Cite:** HtT establishes that LLMs can learn and apply rules from examples. Gradata extends this to: LLMs can learn behavioral rules from user corrections, with confidence-scored graduation and decay.

### 3.5 Self-Improving LLM Agents at Test-Time / TT-SI (arXiv:2510.07841, Oct 2025)

**Approach:** Three-step self-improvement: (1) identify samples model struggles with (self-awareness), (2) generate similar examples from uncertain samples (self-data augmentation), (3) test-time fine-tuning.

**Results:** +5.48% absolute accuracy, 68x fewer training samples needed.

**Difference from Gradata:** TT-SI uses self-generated data for fine-tuning. Gradata uses human corrections for context injection. TT-SI requires model weight updates; Gradata does not.

### 3.6 Survey: Personalized Large Language Models (arXiv:2502.11528, Feb 2025)

**Key Taxonomy (three levels):**
1. **Prompting** for personalized context (input level)
2. **Finetuning** for personalized adapters (model level)
3. **Alignment** for personalized preferences (objective level)

**CRITICAL GAP IDENTIFIED BY THE SURVEY:** The survey does NOT discuss correction-based or edit-based personalization. The three categories cover information injection, parameter modification, and preference alignment -- but NOT iterative refinement from user corrections.

**Future Directions Identified:**
- Lifelong update (dynamic preference evolution)
- Cross-domain adaptation
- Information scarcity handling
- Realistic benchmarks reflecting real-world preference diversity

**Gradata fills the gap between all three categories:** We use prompting (context injection) but derive the context from a correction-based learning loop that resembles alignment. This is a genuinely novel position in the taxonomy.

---

## 4. Evaluation Benchmarks Landscape

### 4.1 Existing Benchmarks

| Benchmark | Focus | Tasks | Metrics | Venue |
|-----------|-------|-------|---------|-------|
| **LOCOMO** | Long-term conversational memory | Single-hop, multi-hop, temporal, adversarial QA + summarization | F1, ROUGE, LLM-as-Judge | ACL 2024 |
| **LongMemEval** | Interactive memory over sustained interactions | Information extraction, multi-session reasoning, temporal reasoning, knowledge updates, abstention | Accuracy, 30% drop baseline | ICLR 2025 |
| **MemoryBench** | Memory + continual learning from feedback | Declarative (semantic + episodic) + procedural memory | Off-policy and on-policy evaluation protocols | arXiv 2025 |
| **Evo-Memory** | Self-evolving memory at test time | 10 multi-turn goal-oriented + reasoning datasets | Answer accuracy, success rate, step efficiency, sequence robustness | arXiv 2025 (DeepMind) |
| **PersonalLLM** | Individual preference adaptation | 10,402 prompts x 8 LLM responses, diverse reward models | Dirichlet-weighted preference simulation | ICLR 2025 |
| **PersonaLens** | Task-oriented assistant personalization | Diverse user profiles with rich preferences | LLM-as-Judge for personalization, response quality, task success | ACL Findings 2025 |
| **LaMP / LongLamp** | Dialogue-based personalization | User history conditioning | Task-specific metrics | Various |

### 4.2 Standard Metrics in the Field

**For classification/retrieval:** Accuracy, F1, MCC, MAE, RMSE
**For generation:** ROUGE-1, ROUGE-L, BLEU, METEOR, SBERT, LLM-as-Evaluator
**For personalization-specific:**
- EGISES (measuring insensitivity to user differences)
- P-Accuracy (combining accuracy with personalization awareness)
- PerSEval (personalization evaluation)
- ACPE from PAHF (average cumulative personalization error)

**For recommendation:** Hit Ratio, Precision, Recall, NDCG

### 4.3 What No Benchmark Measures (Our Opportunity)

No existing benchmark measures:
1. **Correction-to-output ratio over time** (our CRO)
2. **First draft acceptance rate** (our FDAR)
3. **Pattern graduation from observations to rules** (our INSTINCT -> PATTERN -> RULE lifecycle)
4. **Category extinction** (specific error types going to zero)
5. **Edit distance between AI draft and user-accepted version** trending downward
6. **Blind comparison between brain-on and brain-off** for the same user

This is a genuine gap. We could propose a new benchmark category: "Behavioral Adaptation Benchmarks" that measures whether AI systems demonstrably improve at user-specific tasks through correction-based learning.

### 4.4 Statistical Methods in Use

- **LLM-as-Judge** is now the dominant evaluation paradigm (used by Mem0, LOCOMO, PersonaLens, MemoryBench)
- **Interrupted Time Series (ITS)** is an established quasi-experimental design for single-subject longitudinal studies, widely used in health policy and behavioral research
- **Poisson regression** for count-based outcome variables (correction counts) is standard
- **Binomial test** for blind comparisons is uncontroversial
- **Kaplan-Meier survival curves** for "time to last correction" in a category would be novel and compelling

---

## 5. Publication Strategy

### 5.1 arXiv Categories

**Primary:** cs.AI (Artificial Intelligence) -- Broadest reach for agentic systems
**Secondary:** cs.CL (Computation and Language) -- For the NLP/LLM community
**Tertiary:** cs.HC (Human-Computer Interaction) -- For the single-user study methodology

### 5.2 Conference Venue Recommendations

| Venue | Fit | Minimum Rigor | Deadline | Notes |
|-------|-----|--------------|----------|-------|
| **CHI 2027** | HIGH | Qualitative + quantitative, N=1 acceptable as "Research through Design" or "case study" | Sep 2026 | Best fit for single-user longitudinal study. CHI accepts case studies and Research through Design with N=1. Design your paper around the methodology innovation, not just results. |
| **CSCW 2027** | HIGH | Mixed methods acceptable, longitudinal studies valued | Apr/Oct 2026 | CSCW actively debating whether human-AI collaboration counts as CSCW. Perfect timing. A 2024 panel asked: "Is Human-AI Interaction CSCW?" |
| **ACL/EMNLP 2026** | MEDIUM | Strong quantitative results needed, baselines against existing systems | Various | System paper track would fit. Need strong ablation study (brain-on vs brain-off, with vs without graduation). N=1 is a harder sell here. |
| **NeurIPS 2026** | MEDIUM-LOW | Novel algorithm/framework expected, strong baselines | May 2026 | Datasets & Benchmarks track could work if we frame it as proposing a new benchmark for behavioral adaptation. |
| **ICLR 2027** | MEDIUM | Needs technical novelty beyond "we tracked corrections" | Oct 2026 | Position paper or workshop paper more realistic than main conference. |

### 5.3 Recommended Strategy: Multi-tier Publication

**Tier 1 (Immediate, April 2026):** arXiv preprint
- Title suggestion: "Learning from Corrections: Confidence-Scored Rule Graduation for Persistent LLM Personalization"
- Categories: cs.AI, cs.CL, cs.HC
- Include: methodology, preliminary results from existing 71 sessions, study protocol
- Purpose: Timestamp the idea, establish priority, get citations

**Tier 2 (September 2026):** CHI 2027 submission
- Full study results (30-day prospective + 71-session retrospective)
- Frame as: "Research through Design" or "Case Study" with rigorous methodology
- Emphasize: The methodology innovation (correction-based graduation), not just N=1

**Tier 3 (Post-CHI):** ACL/EMNLP system paper
- After gathering multi-user data (even 3-5 users over a shorter period)
- Or: propose the benchmark formally

### 5.4 Is a Single-User Study Publishable?

**YES, with caveats.** Evidence from the literature:

1. **CHI routinely publishes N=1 studies** as "Research through Design" (e.g., CHI 2025 published a system co-designed with one DHH user)
2. **CSCW is actively interested** in human-AI collaboration studies, including single-person-and-AI setups
3. **The methodology must be rigorous** -- our study protocol (ITS, blind comparison, Poisson regression) significantly exceeds what most N=1 studies provide
4. **Required caveats:**
   - Generalizability is limited; results apply to one power-user in one domain
   - User adaptation confound cannot be fully separated from system learning
   - Blind comparison partially addresses this but cannot eliminate it
   - Replication with additional users is needed (frame as future work)
5. **Framing matters:** Position as "demonstrating feasibility and methodology for correction-based learning" rather than "proving correction-based learning works universally"

---

## 6. Novelty Analysis: What Has Nobody Studied?

### 6.1 Confirmed Novel Contributions

| Contribution | Closest Prior Art | Why We're Different |
|-------------|------------------|-------------------|
| **Correction-to-rule graduation with confidence scoring** | HtT framework (arXiv:2310.07064) | HtT learns task rules from examples. We learn behavioral rules from user corrections with confidence decay and session-type-aware weighting. |
| **Diff-based learning signal** | PAHF (arXiv:2602.16173) | PAHF uses post-action feedback. We use the actual textual diff between AI draft and user-accepted version. Richer signal. |
| **INSTINCT -> PATTERN -> RULE lifecycle** | No direct prior art | No system in the literature has a confidence-scored multi-stage graduation mechanism for behavioral lessons derived from user corrections. |
| **Category extinction tracking** | No direct prior art | No benchmark or system tracks whether specific error categories go to zero over time. |
| **Session-type-aware decay** | No direct prior art | Decay that distinguishes between sales sessions and system sessions (so sales lessons don't decay during system sessions) is novel. |
| **Brain manifest / quality proof** | No direct prior art | A machine-readable proof of what an AI has learned, with correction counts, confidence scores, and graduation history. Neither Mem0 nor Letta has this. |
| **Longitudinal single-user correction tracking** | PAHF (simulated users over 4 phases) | Real user, real tasks, real corrections over 100+ sessions spanning months. No simulation. |

### 6.2 What Is NOT Novel (Must Acknowledge)

- Memory systems for LLMs (Mem0, Letta, LangMem, A-Mem, MemoryOS all exist)
- Context injection for personalization (well-established, covered in the survey)
- LLM-as-Judge evaluation (standard methodology)
- Rule learning from examples (HtT)
- Human-in-the-loop learning (ARIA, PAHF, HULA)
- Self-improving agents (TT-SI, EvoTest, SCoRe)

### 6.3 The Gap Statement (for the paper)

Suggested framing:

> Existing LLM memory systems (Mem0, Letta/MemGPT) optimize for *what the AI remembers*. Personalization approaches (P-RLHF, PersonalLLM) optimize for *what the AI prefers*. Self-improving agents (SCoRe, TT-SI) optimize for *what the AI can do*. None of these systems address a fundamental question: **can an AI demonstrably reduce the corrections a specific user needs to make over time?**
>
> We introduce correction-based behavioral learning with confidence-scored rule graduation: a mechanism where user corrections are logged, classified, and progressively promoted from observations (INSTINCT) to verified patterns (PATTERN) to enforced rules (RULE) based on frequency, recency, and cross-session validation. Unlike memory retrieval systems, this approach produces measurable behavioral change. Unlike fine-tuning approaches, it requires no model weight updates. Unlike simulated user studies, we validate on a real user performing real tasks over [N] sessions spanning [M] months.

---

## 7. Methodology We Should Adopt

### 7.1 From Mem0/Letta
- **LLM-as-Judge** for blind comparison evaluation (widely accepted)
- **Token efficiency reporting** (show that our approach is not expensive)
- **LOCOMO-style question taxonomy** (adapt for behavioral memory: single-hop preference recall, multi-session rule application, temporal preference evolution, adversarial rule conflict)

### 7.2 From PAHF
- **ACPE metric** (maps directly to our CRO; use both)
- **Phase-based evaluation** (initial learning, steady state, post-drift)
- **No-memory baseline** as mandatory comparison
- **Theoretical framing** of O(K) error bound under preference switches

### 7.3 From MemoryBench
- **Separate declarative vs procedural memory evaluation** (our system handles both: factual corrections are declarative, workflow corrections are procedural)
- **User feedback simulation framework** (for scaling beyond N=1)
- **Off-policy and on-policy evaluation protocols**

### 7.4 From Evo-Memory (DeepMind)
- **Four-dimensional evaluation**: accuracy, success rate, step efficiency, sequence robustness
- **Sequence robustness** is important -- do our rules maintain performance across varying task orders?

### 7.5 From HtT
- **Rule transferability testing** -- do rules learned from one user help another user in the same domain?
- **Ablation: with vs without rule library** (maps to our brain-on vs brain-off)

### 7.6 Novel Metrics We Should Propose
- **Correction Rate per Output (CRO)** -- our primary metric
- **First Draft Acceptance Rate (FDAR)** -- "right first time" rate
- **Category Extinction Rate** -- Kaplan-Meier survival for error types
- **Graduation Velocity** -- how quickly lessons reach RULE status
- **Edit Distance Trend** -- Levenshtein distance between draft and final, normalized

---

## 8. Recommended Metrics for the Paper

### Primary
| Metric | Source/Precedent | Our Implementation |
|--------|-----------------|-------------------|
| Correction Rate per Output (CRO) | Novel (analogous to PAHF's ACPE) | Poisson regression with session number predictor |
| First Draft Acceptance Rate (FDAR) | Novel (analogous to MemoryBench's success rate) | Logistic regression |
| Blind Comparison Win Rate | Standard (used by PersonalLLM, LLM-as-Judge) | Binomial test with Clopper-Pearson CI |

### Secondary
| Metric | Source/Precedent | Our Implementation |
|--------|-----------------|-------------------|
| Edit Distance (Levenshtein) | Established in NLP evaluation | Normalized by output length, trend over sessions |
| LLM-as-Judge Quality Score | Mem0, LOCOMO, PersonaLens | Applied to blind comparison outputs |
| Category Extinction | Novel | Kaplan-Meier survival curves |
| Lesson Lifecycle Distribution | Novel | Stacked area chart over sessions |
| Token Efficiency | Mem0 precedent | Compare brain-context tokens vs full-history tokens |

---

## 9. Key Papers Reference List

### Must-Cite (Core Related Work)
1. Packer et al. "MemGPT: Towards LLMs as Operating Systems" (arXiv:2310.08560, 2023/2024)
2. Chheda et al. "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory" (arXiv:2504.19413, 2025)
3. "Learning Personalized Agents from Human Feedback" / PAHF (arXiv:2602.16173, 2026)
4. Wan et al. "Large Language Models can Learn Rules" / HtT (arXiv:2310.07064, 2023)
5. "Enabling Self-Improving Agents to Learn at Test Time With Human-In-The-Loop Guidance" / ARIA (arXiv:2507.17131, 2025)
6. "A Survey of Personalized Large Language Models" (arXiv:2502.11528, 2025)

### Must-Cite (Benchmarks)
7. Maharana et al. "Evaluating Very Long-Term Conversational Memory of LLM Agents" / LOCOMO (ACL 2024)
8. Wu et al. "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory" (ICLR 2025)
9. "MemoryBench: A Benchmark for Memory and Continual Learning in LLM Systems" (arXiv:2510.17281, 2025)
10. "Evo-Memory: Benchmarking LLM Agent Test-time Learning with Self-Evolving Memory" (arXiv:2511.20857, 2025)
11. Zollo et al. "PersonalLLM: Tailoring LLMs to Individual Preferences" (ICLR 2025)

### Should-Cite (Supporting)
12. "Personalized Language Modeling from Personalized Human Feedback" / P-RLHF (arXiv:2402.05133, 2024)
13. "Self-Improving LLM Agents at Test-Time" / TT-SI (arXiv:2510.07841, 2025)
14. "PersonaLens: A Benchmark for Personalization Evaluation in Conversational AI Assistants" (ACL Findings 2025)
15. "Training Language Models to Self-Correct via Reinforcement Learning" / SCoRe (arXiv:2409.12917, 2024)
16. "Personalization of Large Language Models: A Survey" (arXiv:2411.00027, 2024/2025)
17. "From Reasoning to Learning: A Survey on Hypothesis Discovery and Rule Learning with LLMs" (TMLR 2025)
18. "Enabling Personalized Long-term Interactions in LLM-based Agents through Persistent Memory and User Profiles" (arXiv:2510.07925, 2025)

### Methodology References
19. Bernal et al. (2017) -- ITS design guidelines
20. Linden (2015) -- "Conducting Interrupted Time-series Analysis for Single- and Multiple-group Comparisons" (Stata Journal)

---

## 10. Summary: Positioning Gradata

### The Landscape
```
                    REMEMBERS FACTS          LEARNS BEHAVIOR
                    |                        |
Weight Updates:     P-RLHF, SCoRe           (empty -- fine-tuning for
                                              behavioral adaptation from
                                              corrections doesn't exist)

Context Injection:  Mem0, Letta,             GRADATA (unique position)
                    LangMem, A-Mem

Self-Generated:     TT-SI, EvoTest           HtT (task rules, not
                                              user-specific behavior)
```

### Our Unique Position
Gradata occupies a genuinely unoccupied cell in the landscape: **context-injection-based behavioral learning from user corrections**. Every competitor either:
- Remembers facts but doesn't learn behavior (Mem0, LangMem)
- Learns behavior but requires weight updates (P-RLHF, SCoRe)
- Self-improves but not from user corrections (TT-SI, EvoTest)
- Learns rules but not user-specific behavior (HtT)
- Learns from trajectories but not from user edits (Letta skill learning)

The PAHF paper (Feb 2026) is the closest competitor, but it operates on simulated users, learns preference facts (not behavioral rules), and has no graduation mechanism.

### The One-Line Pitch for Reviewers
"While Mem0 remembers what users said and Letta remembers what agents did, Gradata learns from what users corrected -- graduating observations into confidence-scored behavioral rules that demonstrably reduce correction rates over time."
