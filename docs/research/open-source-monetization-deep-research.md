# Open Source AI Tool Monetization for Solo Founders (2026)
## Deep Research Report — Honest Analysis with Real Examples

Date: 2026-03-26

---

## 1. Open-Core Success Stories for Small Teams (2023-2026)

### Projects That Successfully Monetized

| Project | Team Size | Funding | Revenue | What's Open | What's Proprietary |
|---------|-----------|---------|---------|-------------|-------------------|
| **Grafana Labs** | ~800 (started small) | $540M+ total | **$400M+ ARR** (Sep 2025) | Grafana, Loki, Tempo (AGPLv3) | Grafana Cloud, Enterprise Stack, OnCall |
| **Pydantic** | ~15 | $17.2M (Sequoia) | Not disclosed | Pydantic library (300M downloads/month) | Logfire (observability), Pydantic AI enterprise |
| **Mem0** | Unknown (small) | $24M (YC S24 + Basis Set) | Not disclosed (186M API calls/qtr) | Vector memory (Python SDK) | Graph memory, analytics, HIPAA ($249/mo) |
| **Letta (MemGPT)** | 13 | $10M (Felicis, $70M val) | $1.4M (June 2025) | Full agent runtime | Cloud hosting, enterprise features |
| **CrewAI** | ~10+ | $18M (Insight Partners) | Not disclosed | CrewAI framework (10M agents/month) | CrewAI Enterprise (150 beta customers in 6 months) |
| **LangChain** | 233 | $260M total ($1.25B val) | Not disclosed | LangChain framework | LangSmith (observability, usage-based) |
| **Postiz** | 1 (solo) | $0 (bootstrapped) | **$14.2K/month** | Social media scheduler | Cloud-hosted version |
| **Instructor** | 1 (Jason Liu) | $0 | $0 (monetizes via consulting + angel investing) | Full library | Nothing — pure open source |

### Key Patterns

**What gets open sourced:** The core framework/library that developers integrate. This is the distribution channel. The goal is ubiquity, not revenue.

**What stays proprietary:**
- Hosted/managed versions (Grafana Cloud, Mem0 Platform, Letta Cloud)
- Observability/analytics dashboards (LangSmith, Logfire)
- Enterprise features (SSO, RBAC, HIPAA, SOC 2, audit logs)
- Advanced capabilities that require infrastructure (Mem0 graph memory requires Neo4j)

**The honest numbers:** Only Grafana Labs ($400M+ ARR) has proven this model at real scale as an independent company. LangChain raised $260M but hasn't disclosed revenue. Most open-core AI companies are pre-revenue or early revenue, subsidized by VC.

**The Instructor exception:** Jason Liu built one of the most influential AI libraries (cited by OpenAI as inspiration for their structured output feature, 320K+ downloads/month) and monetized it through *personal brand* — consulting, angel investing (Andreessen Horowitz scout), and speaking. He never built a paid tier. This is a legitimate solo founder strategy: open source as reputation engine.

---

## 2. "Fork and Steal" Incidents — The Complete Scorecard

### The Big Four Cases

#### Redis vs. AWS Valkey (2024-2026)
- **What happened:** Redis switched to SSPL in March 2024 to block cloud providers. Within weeks, AWS, Google, Oracle, and Ericsson backed a fork called Valkey under the Linux Foundation (BSD 3-clause).
- **Outcome:** Catastrophic for Redis. 83% of large companies adopted or tested Valkey by late 2024. AWS launched ElastiCache for Valkey at significant discounts. Core contributors permanently migrated. Redis reversed course to AGPLv3 in 2025, but the damage was done. Redis's own CEO acknowledged: "This achieved our goal — AWS and Google now maintain their own fork — but the change hurt our relationship with the Redis community."
- **Who won:** AWS. The fork succeeded. Redis lost community trust AND market share.

#### Elasticsearch vs. Amazon OpenSearch (2021-2026)
- **What happened:** Elastic changed to SSPL/Elastic License in 2021. AWS forked Elasticsearch 7.10.2 as OpenSearch under Apache 2.0. OpenSearch moved to Linux Foundation in late 2024.
- **Outcome:** OpenSearch became a real competitor with aggressive AI/vector search development (FAISS integration, hybrid search). Elastic eventually added AGPLv3 as a license option in late 2024.
- **Who won:** Draw. Elastic survived ($1.2B+ revenue) because they had a strong enterprise customer base and brand before the fork. But OpenSearch took significant market share, especially in the AWS ecosystem.

#### MongoDB vs. Amazon DocumentDB (2019-2026)
- **What happened:** MongoDB switched to SSPL in 2018. Amazon launched DocumentDB as "MongoDB-compatible" in 2019.
- **Outcome:** MongoDB Atlas gained market share (12.1% mindshare, up from 2.4%). DocumentDB found to be 26.7% more expensive and supports only a limited subset of features. DocumentDB never caught up.
- **Who won:** MongoDB. They survived because: (1) They had a massive head start on features. (2) Atlas cloud product was already mature. (3) DocumentDB compatibility was limited and more expensive. (4) MongoDB had strong developer brand loyalty.

#### HashiCorp Terraform vs. OpenTofu (2023-2026)
- **What happened:** HashiCorp switched to BSL in August 2023. Community forked as OpenTofu under Linux Foundation. IBM acquired HashiCorp for $6.4B (closed February 2025).
- **Outcome:** OpenTofu reached 9.8M downloads, 300% annual growth, CNCF Sandbox status. Fidelity migrated 50,000+ state files. Feature parity at 95%+. IBM has not reversed the BSL decision.
- **Who won:** Too early to call. HashiCorp got acquired (exit for shareholders). OpenTofu is growing but hasn't displaced Terraform yet.

#### Grafana vs. Amazon Managed Grafana
- **What happened:** Grafana switched to AGPLv3 in 2021 (preemptive move). AWS launched Amazon Managed Grafana anyway.
- **Outcome:** Grafana Labs reached $400M+ ARR, 7,000+ customers. Amazon Managed Grafana exists but hasn't disrupted Grafana's growth.
- **Who won:** Grafana. The AGPL license means AWS can host it, but must contribute changes back. Grafana's cloud product is better and more feature-rich. Brand wins.

### Defense Strategies — What Actually Works

| Defense | Worked? | Example |
|---------|---------|---------|
| SSPL license change | **No.** Triggers fork. | Redis, Elastic |
| AGPL license (preemptive) | **Yes.** Discourages strip-mining without killing community. | Grafana |
| BSL license change | **Partial.** Gets you acquired but creates a fork. | HashiCorp |
| Superior product + cloud service | **Yes.** If you're already ahead, the fork can't catch up. | MongoDB Atlas |
| Developer brand loyalty | **Yes.** If devs love you, they won't switch to a soulless fork. | MongoDB, Grafana |
| Speed of innovation | **Yes.** If you ship faster than the fork. | Elastic (eventually) |
| Raising enough money to out-execute | **Yes, but not for solo founders.** | All of the above had $100M+ war chests |

### The Brutal Truth for a Solo Founder

Every company that survived a big-tech fork had: (a) $100M+ in funding, (b) a large engineering team, (c) an established enterprise customer base, and (d) a mature cloud product BEFORE the fork happened. A solo founder has none of these. If AWS decides to build your thing, you cannot out-engineer them. Your defense must be structural, not operational.

---

## 3. Network Effect Moats in AI Tools

### Data Moats > Code Moats

The consensus from 2025 research is clear: **infrastructure is commoditizing, data is the moat.** The real competitive advantage is not the model or the code but the data feeding it.

**The data flywheel:** More usage -> more data -> better models -> better product -> more usage. This is self-reinforcing and competitors cannot buy their way into it.

### AI Tools with Genuine Network Effects

| Tool | Network Effect Type | Forkable? |
|------|-------------------|-----------|
| **GitHub Copilot** | Code corpus from millions of repos. Each user's code improves suggestions for everyone. | No. The data is the product. |
| **Grammarly** | Writing correction data across 30M+ daily users. Corrections improve models for everyone. | No. 15+ years of correction data. |
| **Mem0** | More users = better memory extraction heuristics (in theory). Cross-user patterns for common preferences. | Partially. The code is open but the aggregate learning data from cloud users is not. |
| **Grafana** | Not really network effects. Brand + ecosystem lock-in. | Yes, but brand loyalty prevents it. |

### The Three Moat Types

1. **Code moat:** Open source code. Easily forked. Nearly zero defensibility. Example: Redis.
2. **Data moat:** Proprietary training data, user correction data, behavioral patterns. Cannot be forked. Example: Grammarly's correction corpus, GitHub Copilot's code corpus.
3. **Protocol + Data moat:** Open standard that everyone adopts, with proprietary data layer on top. Nearly unbreakable. Example: email (SMTP is open, Gmail's spam models are proprietary).

**For Gradata specifically:** The correction-to-rule graduation pipeline is a code moat (forkable). The ACCUMULATED correction data across users who train brains is a data moat (not forkable). The brain.manifest.json standard could become a protocol moat if adopted as a format.

---

## 4. Claude/ChatGPT Persistent Memory as Competitive Threat

### Current State (March 2026)

- **Claude:** Launched persistent memory to all users (including free tier) in March 2026. Processes conversations every ~24 hours, distills long-term information, loads into future conversations. Confidence scoring. Includes a memory import tool to port context from ChatGPT.
- **ChatGPT:** Has had memory since February 2024. Remembers preferences, facts, context across conversations.
- **Claude Code:** Has CLAUDE.md files for persistent instructions + auto-memory for corrections/preferences.

### Why This Is an Existential Threat

If Claude and ChatGPT both remember your preferences, your correction patterns, and your behavioral quirks, why would anyone pay for a third-party brain/memory tool?

### Historical Analogies — Platform Sherlock Risk

| Third-Party Feature | Platform Built It | What Happened |
|-------------------|-------------------|---------------|
| Flashlight apps | Apple built-in flashlight (iOS 7) | All flashlight apps died |
| F.lux (night mode) | Apple Night Shift | F.lux survived on desktop, died on mobile |
| Clipboard managers | Apple Universal Clipboard | Third-party managers survived because they do MORE |
| Dropbox file sync | iCloud, OneDrive, Google Drive | Dropbox survived but pivoted to collaboration |
| TweetDeck | Twitter bought it, then degraded it | Cautionary tale of platform dependency |
| Zoom | Google Meet, Microsoft Teams | Zoom survived via superior UX + enterprise |

### Pattern: Who Survives Platform Sherlock

1. **Do 10x more than the platform feature.** Claude's memory stores facts. If your tool learns BEHAVIOR from corrections, graduates patterns to rules, and provides quality proof, that is categorically different.
2. **Be cross-platform.** Claude's memory only works in Claude. ChatGPT's only works in ChatGPT. A brain that works across ALL LLMs has a structural advantage.
3. **Own the data layer.** If user correction data lives in YOUR system (not Claude's, not ChatGPT's), you own the moat. Users can't take their accumulated learning with them.
4. **Serve the use case, not the platform.** Dropbox survived not because it was better at syncing files than iCloud, but because it became a collaboration tool. Don't compete on "memory" — compete on "compound intelligence."

### The Honest Assessment

Claude's native memory handles 80% of what casual users need. The remaining 20% — correction tracking, behavioral adaptation, quality proof, cross-LLM portability, marketplace for trained brains — is where a third-party tool can survive. But "surviving in the 20%" means your TAM is dramatically smaller than "memory for AI." You must be very specific about what you do that Claude's built-in memory cannot.

---

## 5. Solo Founder Constraints — Honest Analysis

### What Actually Works for Solo Founders

Based on real 2025-2026 examples:

| Model | Solo Viability | Revenue Range | Time to Revenue | Examples |
|-------|---------------|---------------|-----------------|----------|
| **SaaS (niche tool)** | High | $5K-$50K/mo | 3-6 months | HeadshotPro ($3.6M ARR), BoredHumans ($8.8M ARR) |
| **Open source + cloud tier** | Medium | $1K-$15K/mo | 6-18 months | Postiz ($14.2K/mo) |
| **Consulting + open source reputation** | High | $10K-$30K/mo | Immediate | Jason Liu/Instructor model |
| **API-as-a-service** | Medium | $2K-$20K/mo | 3-9 months | Many indie API products |
| **Marketplace/platform** | Very Low | $0 for years | 2-5 years | Requires critical mass — NOT for solo |
| **Open source SDK** | Very Low | $0 (unless cloud tier) | 12-24+ months | Needs ecosystem, community, enterprise deals |
| **Course/education** | High | $5K-$50K launch | 1-3 months | leverages open source credibility |

### Should a Solo Founder Attempt Open Source?

**The honest answer: Only if open source is your DISTRIBUTION strategy, not your PRODUCT.**

- **Yes if:** You're building a developer tool where adoption = distribution, and you monetize via cloud hosting, consulting, or a paid tier that adds enterprise features. You must accept that the open source part generates $0 and your income comes from adjacent monetization.
- **No if:** You expect the open source project itself to generate revenue. It won't. Open source is a marketing channel, not a revenue model.
- **Absolutely not if:** You're trying to build a marketplace or platform. These require network effects and scale that a solo founder cannot achieve while also maintaining an open source project.

### The VC-Backed Game vs. Bootstrapped Reality

Every successful open-core AI company in this report raised millions:
- Mem0: $24M
- Letta: $10M
- CrewAI: $18M
- LangChain: $260M
- Pydantic: $17.2M
- Grafana: $540M+

The solo bootstrapped example (Postiz at $14.2K/mo) is real but modest. The Instructor example (Jason Liu) generated income through consulting and angel investing, not the project itself.

**Realistic timeline for a solo founder:**
- Month 1-3: Build and ship MVP, get first users
- Month 3-6: Iterate based on feedback, build community
- Month 6-12: Launch paid tier or consulting, $1K-5K/mo if lucky
- Month 12-24: If product-market fit exists, $5K-15K/mo
- Month 24+: Either raise money to scale, or stay at indie scale

### Minimum Viable Moat for One Person

1. **Proprietary data that compounds over time** (user corrections, behavioral patterns, quality scores)
2. **A format/standard others adopt** (brain.manifest.json as an interoperable format)
3. **Cross-platform portability** (works with Claude, ChatGPT, Gemini, local models)
4. **A published paper or benchmark** that establishes credibility (costs $0, takes 2 weeks)

You CANNOT build:
- An enterprise sales team
- 24/7 support
- SOC 2 / HIPAA compliance
- A marketplace with liquidity
- Competitive cloud infrastructure

---

## 6. Hybrid Models That Protect IP While Maintaining Trust

### The Spectrum of Openness

| Model | Open | Proprietary | AI Tool Example | Solo Viable? |
|-------|------|-------------|-----------------|-------------|
| **Open Spec + Proprietary Implementation** | Standard/format | Code that implements it | brain.manifest.json spec (open) + graduation algorithm (proprietary) | Yes |
| **Open Protocol + Hosted Service** | Wire protocol | Server-side implementation | MCP (open) + Gradata Cloud (proprietary) | Yes |
| **Open Client + Proprietary Backend** | SDK, client libraries | Cloud backend, data processing | Mem0 Python SDK (open) + Mem0 Platform (proprietary) | Yes |
| **Open Core + Enterprise Features** | Core framework | SSO, RBAC, analytics, audit | CrewAI (open) + CrewAI Enterprise (proprietary) | Partially |
| **Fully Open + Consulting** | Everything | Knowledge in your head | Instructor (fully open) + Jason Liu's consulting | Yes |
| **Open Weights + Proprietary Data** | Model architecture | Training data, fine-tuning data | Mistral (open small models, commercial large models) | No (capital intensive) |

### What Works Specifically for AI/ML Tools

**The emerging winner in 2025-2026 is: Open SDK + Proprietary Cloud + Data Moat**

This means:
1. **Open source the SDK/client** — developers can run it locally, inspect the code, build trust. This is your distribution.
2. **Cloud service for the hard parts** — hosted inference, cross-user data aggregation, real-time analytics. This is your revenue.
3. **Data that compounds** — every user who trains a brain adds to a corpus that makes the system better for everyone. This is your moat.

### The Best Analog: Grafana's Model

Grafana's AGPL strategy is the most successful template for a solo founder to study:
- Core product is genuinely open source (AGPL prevents strip-mining without killing contributions)
- Cloud product is clearly better (managed, no ops burden)
- Enterprise features justify premium pricing
- 1% conversion rate on 20M users = $400M ARR
- Never tried to restrict the open source to force upgrades

The key insight: **Grafana never competed with its own open source product.** The cloud product competes on convenience and scale, not on features withheld from open source.

---

## 7. Synthesis: What This Means for Gradata

### The Hard Truths

1. **The marketplace is years away.** Every successful open-core company built a great standalone product first, then added platform/marketplace features. Grafana didn't start with a plugin marketplace. Mem0 didn't start with a brain store. Ship the SDK, get users, prove value, THEN build marketplace.

2. **Claude's native memory handles the easy cases.** Competing on "AI memory" is fighting the platform. Competing on "compound behavioral adaptation with quality proof" is a different category. Make sure your messaging is crystal clear about the difference.

3. **Open source alone generates $0.** Every dollar of revenue in this research came from: hosted cloud services, enterprise features, consulting, or education. The open source part is always the distribution channel, never the product.

4. **A solo founder cannot survive a big-tech fork.** Don't build something that AWS would want to fork. Build something that requires YOUR data to be useful. The graduation algorithm can be forked; the accumulated correction data cannot.

5. **The fastest path to revenue is NOT open source.** It's a niche SaaS tool or consulting. Open source is a long game (12-24 months to any revenue). If you need income now, sell consulting on top of your expertise while building the open source project on the side.

### Recommended Strategy (Honest, Not Cheerleading)

**Phase 1 (Now - Month 6): Prove the concept, generate income**
- Ship the SDK as open source (AGPL license, prevents strip-mining)
- Publish a research paper on correction-to-rule graduation (free credibility)
- Offer consulting/implementation services using Gradata ($150-300/hr)
- Target: $5K-10K/mo from consulting while building community

**Phase 2 (Month 6-12): Build the cloud tier**
- Launch Gradata Cloud (hosted brain sync, cross-device, analytics dashboard)
- Price: Free tier (local only) + $29/mo (cloud sync) + $99/mo (analytics + team)
- Target: 50-100 paying users, $3K-10K/mo from SaaS

**Phase 3 (Month 12-24): Data moat + cross-platform**
- Brain works across Claude, ChatGPT, Gemini, local models
- Cross-user pattern aggregation (anonymized) improves system for everyone
- brain.manifest.json becomes an interoperable standard
- Target: $15K-30K/mo combined (consulting + SaaS)

**Phase 4 (Month 24+): Marketplace IF demand exists**
- Only if Phase 3 proves users want to share/rent trained brains
- Only if the data moat is real and proven
- Consider raising money at this point if the numbers justify it

### The Nuclear Option: Don't Open Source at All

It's worth considering: **you don't HAVE to open source.** Jason Liu and Instructor is the exception, not the rule. Most solo founder successes in 2025-2026 ($3.6M ARR HeadshotPro, $8.8M ARR BoredHumans, $1M+ ARR Photo AI) are CLOSED SOURCE SaaS tools. They got to revenue faster because they didn't spend time managing a community, reviewing PRs, or worrying about forks.

If the goal is revenue, closed-source SaaS with a free tier may be the faster path. If the goal is adoption and eventual platform status, open source is the right call but requires patience and alternative income.

---

## Sources

### Open-Core & Monetization
- [Grafana Labs $400M ARR Announcement](https://grafana.com/press/2025/09/30/grafana-labs-surpasses-400m-arr-and-7000-customers-gains-new-investors-to-accelerate-global-expansion/)
- [LangChain Funding & Valuation](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langchain-setup-tools-agents-memory/langchain-funding-valuation-2025-complete-financial-overview)
- [LangChain Valuation - Sacra](https://sacra.com/c/langchain/)
- [CrewAI $18M Series A](https://siliconangle.com/2024/10/22/agentic-ai-startup-crewai-closes-18m-funding-round/)
- [CrewAI - Insight Partners](https://www.insightpartners.com/ideas/crewai-scaleup-ai-story/)
- [Pydantic Funding - Tracxn](https://tracxn.com/d/companies/pydantic/__epXfjnVmPOg9zCLraoODhQCG6GrGIuPXjlEHvGnpjco)
- [Pydantic Open Source Fund](https://pydantic.dev/articles/pydantic-oss-fund-2025)
- [Instructor - Jason Liu, Latent Space](https://www.latent.space/p/instructor)
- [Postiz Solo Founder $14.2K/mo - Indie Hackers](https://www.indiehackers.com/post/i-did-it-my-open-source-company-now-makes-14-2k-monthly-as-a-single-developer-f2fec088a4)
- [Open Core Ventures Handbook](https://handbook.opencoreventures.com/open-core-model/)
- [Open Source AI Paradox - Trensee](https://www.trensee.com/en/blog/deep-dive-opensource-ai-business-model-2026-03-15)

### Fork & Steal Incidents
- [Redis vs Valkey in 2026 - DEV Community](https://dev.to/synsun/redis-vs-valkey-in-2026-what-the-license-fork-actually-changed-1kni)
- [Redis Returns to AGPL](https://redis.io/blog/agplv3/)
- [Redis Returns to Open Source - InfoQ](https://www.infoq.com/news/2025/05/redis-agpl-license/)
- [Redis Returns to Open Source - Forkable](https://www.forkable.io/p/redis-returns-to-open-source)
- [Elasticsearch vs OpenSearch 2025](https://pureinsights.com/blog/2025/elasticsearch-vs-opensearch-in-2025-what-the-fork/)
- [Elastic's Return to Open Source - InfoWorld](https://www.infoworld.com/article/3499400/elastics-return-to-open-source.html)
- [OpenSearch in 2025 - InfoWorld](https://www.infoworld.com/article/3971473/opensearch-in-2025-much-more-than-an-elasticsearch-fork.html)
- [MongoDB vs DocumentDB Comparison](https://www.mongodb.com/resources/compare/documentdb-vs-mongodb)
- [HashiCorp BSL and IBM Acquisition](https://www.softwareseni.com/hashicorp-terraform-opentofu-and-the-ibm-acquisition-wild-card-for-infrastructure-as-code/)
- [OpenTofu Manifesto](https://opentofu.org/manifesto/)
- [IBM HashiCorp Deal Closing - The Register](https://www.theregister.com/2025/02/28/ibm_hashicorp_deal_closing/)

### Moats & Defensibility
- [Building a Moat in the Age of AI - Insight Partners](https://www.insightpartners.com/ideas/building-a-moat-in-the-age-of-ai/)
- [The AI Moat Spectrum - FourWeekMBA](https://fourweekmba.com/ai-moat-spectrum/)
- [Moats in AI: Mirage or Reality - Oxx VC](https://www.oxx.vc/industry-perspectives/moats-in-ai-mirage-or-reality/)
- [New Software Moats - Bloom VP](https://bloomvp.substack.com/p/the-new-software-moats-stickiness)
- [The New New Moats - Greylock](https://greylock.com/greymatter/the-new-new-moats/)
- [Data Moats - V7 Labs](https://www.v7labs.com/blog/data-moats-a-guide)
- [What Is a Data Moat - The Startup Story](https://thestartupstory.co/data-moat/)

### Claude/ChatGPT Memory & Platform Risk
- [Claude Memory Tool API Docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic Memory Feature - MacRumors](https://www.macrumors.com/2026/03/02/anthropic-memory-import-tool/)
- [Claude Memory Guide 2026](https://www.shareuhack.com/en/posts/claude-memory-feature-guide-2026)
- [Claude Memory Architecture HN Discussion](https://news.ycombinator.com/item?id=45214908)
- [WWDC 2025 Sherlocking - TechCrunch](https://techcrunch.com/2025/06/10/wwdc-2025-everything-that-apple-sherlocked-this-time/)

### Solo Founder Examples
- [Solo Founders Building Million-Dollar Businesses 2026 - Grey Journal](https://greyjournal.net/hustle/grow/solo-founders-million-dollar-ai-businesses-2026/)
- [11 Solo Indie Hackers Making $1M+ ARR - Indie Hackers](https://www.indiehackers.com/post/starting-up/11-solo-indie-hackers-making-1m-in-annual-revenue-NRq6hCm3La6N6UliFRfE)
- [30 Highest-Valued Solo Startups 2026](https://www.wearefounders.uk/the-30-highest-valued-solo-startups-of-2026/)
- [Solopreneur Tech Stack 2026 - PrometAI](https://prometai.app/blog/solopreneur-tech-stack-2026)
- [Solo Dev SaaS Stack - DEV Community](https://dev.to/dev_tips/the-solo-dev-saas-stack-powering-10kmonth-micro-saas-tools-in-2025-pl7)

### Hybrid Models
- [MCP Open Standard - Axios](https://www.axios.com/2025/04/17/model-context-protocol-anthropic-open-source)
- [Grafana AGPL Relicensing](https://grafana.com/blog/2021/04/20/grafana-loki-tempo-relicensing-to-agplv3/)
- [Grafana Labs Revenue - Sacra](https://sacra.com/c/grafana-labs/)
