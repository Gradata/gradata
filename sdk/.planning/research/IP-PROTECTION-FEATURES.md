# Feature Landscape: Brain Marketplace IP Protection

**Domain:** Knowledge-as-a-service marketplace
**Researched:** 2026-03-24

## Table Stakes

Features renters and brain owners expect. Missing = marketplace feels unsafe or unusable.

| Feature | Why Expected | Complexity | Phase |
|---------|--------------|------------|-------|
| Server-side inference only | Renters should not have raw brain files | Medium | 3 |
| API key per renter | Know who is querying, revocable access | Low | 3 |
| Rate limiting | Prevent abuse, create extraction cost | Low | 3 |
| Usage dashboard (owner) | Brain owner sees who queries what, how often | Medium | 3 |
| Usage dashboard (renter) | Renter sees their usage, billing | Medium | 3 |
| ToS with extraction prohibition | Legal backstop | Low | 3 |
| Brain quality scores (public) | Renters need to evaluate before renting | Low (already built) | 3 |
| Last-trained date on listing | Signal freshness, prevent stale brains | Low | 3 |
| Subscription billing | Recurring revenue infrastructure | Medium | 3 |

## Differentiators

Features that set the marketplace apart. Not expected, but create defensibility.

| Feature | Value Proposition | Complexity | Phase |
|---------|-------------------|------------|-------|
| Extraction pattern detection | Detect and flag distillation attempts | High | 3.5 |
| Quality decay for dormant brains | Brains that stop training lose ranking | Medium | 4 |
| Training frequency revenue incentives | Higher share for actively-trained brains | Low | 4 |
| Response shaping (answers not structure) | Inference returns conclusions, not knowledge graph | Medium | 3 |
| Brain improvement timeline | Renters see brain getting better over time (quality graph) | Medium | 4 |
| Composable brain rental | Rent multiple brains that work together | High | 5 |
| Cross-brain meta-learning | All brains improve graduation algorithms together | Very High | 5 |
| Brain provenance chain | Verifiable training history that cannot be faked | Medium | 4 |
| Correction density as trust metric | Measurable proof brain compounds | Low (already built) | 3 |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Downloadable brain files | Game over for IP protection. Brain IS the product. | Server-side inference only |
| DRM encryption on brain files | Wrong model. Adds complexity, weak protection, bad UX. | Physical separation (files never leave server) |
| Response watermarking (Phase 3) | Premature. No revenue to protect. Degrades response quality. | Usage logging (build data for later detection) |
| Client-side brain execution | If files are on renter's machine, they are copyable. Period. | Server-side inference |
| Unlimited query plans | Removes extraction cost barrier. Power users are indistinguishable from extractors. | Usage-based or capped plans |
| Knowledge structure in responses | Exposing which rules/patterns generated an answer helps reverse engineering | Return synthesized answers only |
| Revenue share without training requirements | Incentivizes publish-and-forget. Leads to GPT Store stagnation. | Tie revenue share to training activity |

## Feature Dependencies

```
Server-side inference -> Rate limiting -> Usage logging -> Extraction detection
                                                        -> Usage dashboards
API key management -> Subscription billing -> Revenue share
Brain quality scores -> Marketplace listing -> Quality decay rules
Brain improvement timeline -> Quality decay -> Training frequency incentives
Composable brains -> Cross-brain meta-learning
```

## MVP Recommendation (Phase 3)

Build these and nothing else for protection:

1. **Server-side inference** -- brain files on our servers, API/MCP gateway for queries
2. **API key per renter** -- authentication, revocation, usage tracking
3. **Rate limiting** -- 60/min, 500/hr, 5000/day hard caps
4. **Usage logging** -- every query logged with timestamp, topic embedding, response metrics
5. **Response shaping** -- return answers, never knowledge structure
6. **ToS** -- explicit extraction prohibition
7. **Quality scores on listings** -- sessions, graduation rate, correction density, last trained date

Defer:
- Extraction detection (Phase 3.5): needs usage data to build patterns
- Quality decay (Phase 4): needs marketplace running to matter
- Training incentives (Phase 4): needs brain owners earning revenue
- Composability (Phase 5): needs multiple brains and A2A protocol
- Watermarking (maybe never): premature optimization

## Sources

- [Stripe API Design](https://stripe.com/docs/api) -- API key and rate limiting patterns
- [Anthropic Distillation Detection](https://www.anthropic.com/news/detecting-and-preventing-distillation-attacks)
- [Shopify Revenue Share Model](https://shopify.dev/docs/apps/launch/distribution/revenue-share)
- [GPT Store Analysis](https://www.thegptshop.online/blog/openai-gpt-store-revenue-sharing)
