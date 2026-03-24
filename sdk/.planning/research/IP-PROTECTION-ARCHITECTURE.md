# Architecture: Brain Rental IP Protection

**Domain:** Knowledge-as-a-service, server-side inference
**Researched:** 2026-03-24

## Recommended Architecture: API Proxy with Extraction Detection

```
BRAIN OWNER                    CLOUD                           RENTER
+------------------+    +------------------------+    +------------------+
| Train locally    |    | Brain Storage           |    | MCP Client       |
| (200+ sessions)  |    | (markdown + SQLite)     |    | or API Client    |
| Corrections      |--->| NEVER exposed to renter |    |                  |
| Graduation       |    |                         |    |                  |
+------------------+    | Inference Engine        |    |                  |
                        | - Receives question     |<---|  Send question   |
                        | - Queries brain         |    |                  |
                        | - Returns answer only   |--->|  Get answer      |
                        |                         |    |                  |
                        | Protection Layer        |    |                  |
                        | - Rate limiting         |    |                  |
                        | - Usage logging         |    |                  |
                        | - Anomaly detection     |    |                  |
                        | - API key management    |    |                  |
                        +------------------------+    +------------------+
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Brain Storage | Stores brain files, never exposes directly | Inference Engine only |
| Inference Engine | Processes queries against brain, generates answers | Brain Storage, Protection Layer |
| Protection Layer | Rate limiting, logging, anomaly detection | Inference Engine, Admin Dashboard |
| MCP/API Gateway | Routes requests, authenticates renters | Protection Layer, Renter clients |
| Admin Dashboard | Brain owner views usage, earnings, health | Protection Layer, Brain Storage |
| Sync Service | Brain owner pushes trained updates from local | Brain Storage |

### Data Flow

1. **Brain owner trains locally** (normal Claude Code sessions, corrections, graduation)
2. **Brain owner syncs to cloud** (push updated brain files to server)
3. **Renter sends query** via MCP server or REST API
4. **Gateway authenticates** (API key, subscription check)
5. **Protection layer checks** (rate limit, pattern detection)
6. **Inference engine processes** (query brain, generate answer)
7. **Answer returned** (just the answer, no metadata about brain internals)
8. **Usage logged** (query, timestamp, response size, latency -- for analytics + detection)

## Protection Layers (Depth Defense)

### Layer 1: Physical Separation (Phase 3 MVP)

Brain files live on our servers. Period. The renter's MCP client connects to our endpoint. They never receive:
- Raw markdown knowledge files
- SQLite database
- Graduated rules
- Correction history
- Brain manifest internals (only public-facing scores)

This is the Stripe model: you call the API, you get a result. You never see the fraud model, the routing logic, or the carrier agreements.

### Layer 2: Rate Limiting (Phase 3 MVP)

```
Per API key:
- 60 queries/minute (normal use)
- 500 queries/hour (generous for real usage)
- 5,000 queries/day (hard cap)
- 50,000 queries/month (plan-dependent)

Burst detection:
- 20+ queries in 10 seconds = throttle
- Same query pattern repeated 50+ times = flag
- Queries covering >80% of known topics = alert
```

Rate limits serve double duty: prevent abuse AND create extraction cost. If extracting the brain requires 10,000 queries, and you are limited to 5,000/day at $0.05/query, extraction costs $500+ and takes multiple days -- during which detection kicks in.

### Layer 3: Usage Monitoring (Phase 3.5)

Based on Anthropic's distillation detection patterns:

**Indicators of extraction attempts:**
- Volume concentration: massive query volume focused on specific capability areas
- Repetitive structures: highly similar prompts arriving in rapid succession
- Systematic coverage: queries that methodically cover all topics in the brain
- Chain-of-thought elicitation: prompts designed to extract reasoning, not just answers
- Coordinated accounts: multiple API keys querying similar patterns (shared payment method, similar timing)

**Detection approach:**
- Log all queries with embeddings
- Cluster query patterns per API key
- Alert on coverage >70% of brain topics from single renter in <30 days
- Alert on chain-of-thought extraction patterns
- Human review before action (false positives are worse than missed extraction)

### Layer 4: Response Shaping (Phase 4)

Serve answers, not knowledge structures. The inference engine should:
- Return synthesized answers, not raw retrieval chunks
- Never expose which specific rules or patterns generated the answer
- Never reveal confidence scores of internal graduated rules
- Never return the source markdown file paths or section headings
- Vary response framing to prevent pattern-matching the knowledge structure

This is the difference between "here is what I know about X" (exposes structure) and "based on my expertise, do Y" (serves only the conclusion).

## Anti-Patterns to Avoid

### Anti-Pattern 1: Client-Side Brain Execution
**What:** Running brain inference on the renter's machine
**Why bad:** Game over. If brain files are on their machine, they can copy them regardless of any "protection."
**Instead:** All inference server-side. Always.

### Anti-Pattern 2: DRM on Knowledge Files
**What:** Encrypting markdown/SQLite with device-specific keys
**Why bad:** Encryption is solved for media because playback is controlled. Knowledge files are read by LLMs, and LLM integration points are too diverse to control. Plus, this adds massive complexity for weak protection.
**Instead:** Do not send files at all. Serve inference results only.

### Anti-Pattern 3: Watermarking Responses
**What:** Embedding hidden identifiers in brain responses to trace leaks
**Why bad:** Premature. Adds complexity, can degrade response quality, and does not prevent extraction (it only identifies who extracted after the fact). Wait until there is actual revenue at risk.
**Instead:** Usage logging (simpler, more useful, no quality impact).

### Anti-Pattern 4: Legal-First Protection
**What:** Relying on ToS and NDAs as primary protection
**Why bad:** Enforcement is expensive, slow, cross-jurisdictional, and reactive. By the time you sue, the damage is done.
**Instead:** Technical protection first (server-side inference), legal as backstop.

### Anti-Pattern 5: Overbuilding Protection Pre-Revenue
**What:** Building sophisticated fingerprinting, watermarking, and detection before anyone is paying for brains
**Why bad:** YAGNI. Protection complexity should scale with revenue. Zero revenue = zero extraction attempts.
**Instead:** MVP protection (server-side + rate limiting + logging). Add sophistication when there is something worth stealing.

## Scalability Considerations

| Concern | At 10 renters | At 1K renters | At 100K renters |
|---------|--------------|---------------|-----------------|
| Inference cost | Negligible | Need caching for common queries | Must cache aggressively, tiered pricing |
| Extraction risk | Low (know each renter) | Medium (hard to monitor all) | High (automated detection required) |
| Rate limiting | Simple per-key limits | Need tiered plans | Need adaptive/ML-based limits |
| Storage | Single brain file per owner | Need partitioning | Need distributed storage |
| Latency | Direct query, <500ms | Need edge caching | Need CDN-like inference distribution |

## Sources

- [Anthropic Distillation Detection](https://www.anthropic.com/news/detecting-and-preventing-distillation-attacks) -- behavioral fingerprinting patterns
- [Stripe API Architecture](https://stripe.com/docs/api) -- API proxy pattern reference
- [Netflix DRM Architecture](https://www.vdocipher.com/blog/2022/05/netflix-drm/) -- DRM layer approach (adapted)
- [ArXiv: IP Protection for Deep Learning Models](https://arxiv.org/html/2411.05051v1) -- MLaaS protection patterns
