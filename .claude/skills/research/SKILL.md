---
name: research
description: General-purpose MECE research diamond for any deep research task. Triggers on "research", "deep dive", "investigate", "evaluate", "compare vendors", "market analysis", "how does X work", "what are the options for", "competitive landscape", "who are the players in", "sizing", "due diligence", "regulatory", "compliance check", "technical evaluation", "benchmark", "assess". Covers prospect research, technical research, market analysis, vendor evaluation, hiring research, regulatory questions, content research, and anything requiring structured depth.
---

# Research Diamond (MECE)

General-purpose research engine. Works for any research task. Produces sourced, structured output with no unsourced assertions. Auto-calibrates depth based on what we already know.

## How It Works

```
L2 MEMORY (action waterfall) -- always runs first, feeds into Phase 0
    |
Phase 0: CONTEXT + DEPTH  Inherit L2 findings. Measure the gap. Auto-select depth.
    |
    +--> GAP IS SMALL (3+ of 7 output sections filled by L2)
    |       Phase 1: 1-2 targeted lookups on missing sections only
    |       Phase 4: Synthesize
    |
    +--> GAP IS MEDIUM (1-2 sections filled, rest unknown)
    |       Phase 1: 2-3 MECE tracks
    |       Phase 2: Quick gap check
    |       Phase 3: 1-2 targeted fills
    |       Phase 4: Synthesize
    |
    +--> GAP IS LARGE (nothing in vault, new domain, zero prior context)
            Phase 1: 3-5 MECE tracks, parallel agents (full diamond)
            Phase 2: Gap analysis, rank top 3
            Phase 3: Wave 2 targeted fills
            Phase 4: Synthesize

    +--> USER SAYS "QUICK" or "just the basics"
            Single-pass lookup regardless of gap size. Speed over completeness.
```

## Phase 0: Context + Auto-Depth

Phase 0 does NOT re-run L2 MEMORY. It inherits L2 findings and measures the gap.

**Step 1: Inherit L2 MEMORY findings.**
The action waterfall L2 already checked: vault, persona MOC, PATTERNS.md, NotebookLM, Gmail history, lessons archive. Those findings are available. Do not re-query these sources.

**Step 2: Determine output format.**
Match the research question to an output template (see templates below). Count the required sections.

**Step 3: Measure the gap.**
For each required section in the output template, check: does L2 already have enough data to fill this section? Score:
- FILLED: L2 has sourced, current data for this section
- PARTIAL: L2 has some data but it is incomplete, stale (>30 days), or single-sourced
- EMPTY: L2 has nothing

**Step 4: Auto-select depth.**

| Gap Score | Depth | What Runs |
|-----------|-------|-----------|
| 70%+ sections FILLED | LIGHT | Skip to Phase 4. Fill remaining gaps with 1-2 targeted lookups inline. |
| 30-70% FILLED | STANDARD | Phase 1 with 2-3 tracks on EMPTY/PARTIAL sections only. Quick gap check. Synthesize. |
| <30% FILLED | DEEP | Full diamond. 3-5 parallel MECE tracks. Gap analysis. Wave 2 fills. |
| User says "quick" | OVERRIDE-LIGHT | Single pass regardless of gap. Flag what was skipped. |

**Step 5: Clarify if ambiguous.**
If the research question could go multiple directions and the gap is STANDARD or DEEP, ask one clarifying question before proceeding. For LIGHT depth, just proceed.

**Additional sources beyond L2 (check if not already covered):**
- brain/scripts/fact_extractor.py -- query structured facts from SQLite
- Pipedrive deal history (if prospect-related)
- Fireflies transcripts (if prior call exists)

## Phase 1: Decompose into MECE Tracks

Decompose the research question into 3-5 tracks. Each track covers a distinct slice with no overlap. Together they cover the full picture with no gaps.

Tracks are determined dynamically by the question type. Examples (not hardcoded):

**Prospect/Demo Prep:**
- Company Intel (size, revenue, tech stack, recent news, hiring signals)
- Contact Intel (role, background, LinkedIn, decision authority, communication style)
- Vertical Context (industry trends, competitor landscape, common pain points)

**Technical Evaluation:**
- Architecture Options (approaches, trade-offs, scalability patterns)
- Performance Benchmarks (speed, cost, resource usage, real-world data)
- Ecosystem Health (community size, maintenance cadence, documentation quality, lock-in risk)

**Market Analysis:**
- Market Structure (TAM/SAM/SOM, growth rate, key players, segmentation)
- Demand Signals (buying patterns, adoption curves, channel dynamics)
- Competitive Dynamics (positioning, pricing models, differentiation, switching costs)

**Vendor Evaluation:**
- Capability Fit (feature matrix against requirements)
- Cost/Risk Profile (pricing, contracts, lock-in, compliance)
- Social Proof (case studies, reviews, reference customers, community sentiment)

**Regulatory/Compliance:**
- Regulatory Landscape (applicable laws, jurisdictions, enforcement trends)
- Compliance Requirements (specific obligations, timelines, penalties)
- Implementation Path (what changes are needed, cost, timeline, risk)

**Run tracks in parallel.** Each track gets its own search agent. Agents report back with:
- Findings (bulleted, sourced)
- Confidence (HIGH/MEDIUM/LOW per finding)
- Source quality (primary source, secondary, inferred, unconfirmed)

Adapted from ECC iterative-retrieval: each agent runs a DISPATCH, EVALUATE, REFINE loop (max 2 cycles per track). First search casts a wide net. Second search uses terminology discovered in the first pass to go deeper. Relevance scoring: 0.8-1.0 = direct answer, 0.5-0.7 = related context, below 0.5 = drop.

## Phase 2: Gap Analysis

After Wave 1 completes, review all findings across tracks and ask:

| Check | Action |
|-------|--------|
| What is missing? | Findings that should exist but do not (e.g., no pricing data for a vendor) |
| What is unverified? | Claims from a single source or LOW confidence findings |
| Where do sources conflict? | Two tracks produced contradictory information |
| What assumptions were made? | Inferences the agents made without direct evidence |
| What would change the recommendation? | The finding that, if wrong, flips the conclusion |

Rank all gaps by impact on the final output. Select top 3 gaps only.

Output: "GAP ANALYSIS: [N] findings solid, [M] gaps identified. Top 3: [list with impact rating]"

## Phase 3: Wave 2 Targeted Fills

Run targeted research on the top 3 gaps only. Do not re-research what is already solid.

For each gap:
1. Identify the specific question that needs answering
2. Choose the best source (web search, specific API, direct file read, user question)
3. Execute and evaluate
4. If the gap cannot be filled, flag it explicitly in the final output as UNCONFIRMED

Wave 2 agents are focused, not broad. One query per gap, not a full research sweep.

## Phase 4: Synthesize

Combine all findings into the requested output format. Rules:

1. **Every claim has a source or is flagged [UNCONFIRMED].** No unsourced assertions. Period.
2. **Distinguish facts from inferences from recommendations.** Adapted from ECC market-research quality checklist.
3. **Flag outdated information.** If a data point is older than 6 months, note the date.
4. **Include counterarguments.** If the research supports a recommendation, include the strongest argument against it.
5. **Simplify the decision.** The output should make the next action obvious, not require further interpretation.

Select the output template based on research type (see below), or use a custom format if the user specified one.

## Output Templates

### 1. Prospect/Demo Prep Doc
```
## [Company] -- Demo Prep

### Company Snapshot
- Industry: | Size: | Revenue: | Tech Stack:
- Recent news/signals:

### Contact: [Name]
- Role: | Background: | Decision authority:
- Communication style: | LinkedIn:

### Qualifying Questions (TRAP structure)
1. [Question targeting known pain point]
2. [Question probing current workflow]
3. [Question surfacing budget/timeline]

### Pain Points (ranked by likelihood)
1. [Pain] -- evidence: [source]
2. [Pain] -- evidence: [source]

### Demo Walkthrough (mapped to pains)
1. Show [feature] to address [pain 1]
2. Show [feature] to address [pain 2]

### Objection Handling
| Likely Objection | Response | Proof Point |

### Close Plan
- Recommended next step:
- Backup if pushback:
```

### 2. Competitive Landscape Map
```
## Competitive Landscape: [Market]

### Market Overview
- Size: | Growth: | Key trend:

### Player Map
| Company | Positioning | Strengths | Weaknesses | Pricing | Threat Level |

### Our Differentiation
- vs [Competitor 1]:
- vs [Competitor 2]:

### Gaps in the Market
-

### Recommendation
```

### 3. Technical Evaluation Brief
```
## Technical Evaluation: [Technology/Approach]

### Requirements
| Requirement | Weight | Notes |

### Options Evaluated
| Option | Fits Requirements | Performance | Ecosystem | Cost | Risk |

### Recommendation
- **Pick:** [option] because [reason]
- **Risk:** [biggest risk with this choice]
- **Alternative if:** [condition] then [option B]

### Implementation Notes
```

### 4. Market Sizing (TAM/SAM/SOM)
```
## Market Sizing: [Market]

### TAM (Total Addressable Market)
- Definition: | Size: | Source: | Growth:

### SAM (Serviceable Addressable Market)
- Filters applied: | Size: | Source:

### SOM (Serviceable Obtainable Market)
- Realistic capture: | Assumptions: | Timeline:

### Key Assumptions
| Assumption | Sensitivity | If Wrong |

### Sources
```

### 5. Positioning Brief
```
## Positioning Brief: [Product/Company]

### Target Segment
### Current Perception
### Desired Perception
### Key Differentiators (ranked)
### Messaging Framework
| Audience | Message | Proof Point |
### Competitive Frame
### Risks to Position
```

### 6. Vendor Comparison Matrix
```
## Vendor Comparison: [Category]

### Requirements Checklist
| Requirement | Weight | Vendor A | Vendor B | Vendor C |

### Pricing Comparison
| Model | Vendor A | Vendor B | Vendor C |

### Risk Assessment
| Risk | Vendor A | Vendor B | Vendor C |

### Recommendation
- **Pick:** | **Runner-up:** | **Avoid:**
```

### 7. Regulatory/Compliance Summary
```
## Compliance Summary: [Topic/Regulation]

### Applicable Regulations
| Regulation | Jurisdiction | Effective Date | Penalties |

### Requirements
| Requirement | Status (compliant/gap/unknown) | Action Needed |

### Timeline
### Cost Estimate
### Recommendation
```

### 8. General Research Report (default)
```
## Research Report: [Topic]

### Executive Summary (3-5 sentences)

### Key Findings
1. [Finding] -- [source] -- confidence: [HIGH/MEDIUM/LOW]
2. ...

### Analysis

### Implications

### Risks and Caveats

### Recommendation

### Sources
```

## Integration with Existing Workflows

This skill is the research engine that other gates and workflows call when they need depth:

- **Pre-draft gate** (domain/gates/pre-draft.md): triggers the Prospect/Demo Prep template
- **Demo prep gate** (domain/gates/demo-prep.md): triggers Prospect/Demo Prep with full TRAP structure
- **Prospecting** (domain/playbooks/prospecting-instructions.txt): triggers Company Intel track for qualification
- **System/architecture decisions**: triggers Technical Evaluation Brief
- **Content creation**: triggers General Research Report as input to drafting

The research skill does not replace these gates. It powers the research step within them. When a gate says "research the prospect," this skill runs the diamond. When the gate says "draft the email," it hands off to the drafting workflow with the research output.

## Quality Checklist (adapted from ECC market-research)

Before presenting final output, verify:
- [ ] All figures are sourced or flagged as estimates
- [ ] Outdated information is dated (older than 6 months)
- [ ] Recommendations are supported by findings, not assumed
- [ ] Counterarguments are included
- [ ] Output simplifies the decision (next action is obvious)
- [ ] Facts, inferences, and recommendations are clearly distinguished
- [ ] No unsourced assertions exist anywhere in the output

## Decision Matrix (adapted from ECC search-first)

When research reveals existing solutions or prior work:
- **Exact match exists** (vault, prior session, existing doc) -> use it, cite it, move on
- **Partial match** (related research from different context) -> extend with targeted fills
- **Nothing exists** -> full diamond from scratch
- **Conflicting sources** -> present both, flag the conflict, let Oliver decide
