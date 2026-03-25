# Legal & IP Structure Analysis: AIOS Brain SDK

**Gap:** I19 from AUDIT.md
**Researched:** 2026-03-25
**Companion docs:** IP-PROTECTION-MODELS.md (business models), IP-PROTECTION-ARCHITECTURE.md (technical protection)

---

## 1. Ownership: Who Owns the Trained Brain Data?

### The Core Question

The SDK is open source. A user installs it, trains a brain over 200+ sessions by correcting AI outputs. The brain contains: events.jsonl (correction history), system.db (graduated rules, embeddings), markdown lessons, and brain.manifest.json (quality proof). Who owns this data?

### Legal Analysis

**The user owns their trained brain data.** This is settled law under multiple frameworks:

- **Copyright (US, 17 USC 102):** The correction history, lesson text, and behavioral rules are original works of authorship created by the user. The SDK is a tool -- like Photoshop does not own your photos, the SDK does not own your brain data.
- **Database rights (EU, Directive 96/9/EC):** The user made a "substantial investment in obtaining, verifying, or presenting the contents" of the database. The sui generis database right belongs to the maker (the user), not the tool provider.
- **Contract law:** Without a EULA/ToS claiming otherwise, there is no contractual basis for Sprites to claim ownership. Open-source SDK + no cloud account = no contract.

**Where it gets complicated: the cloud sync and marketplace.**

Once the user syncs their brain to Sprites cloud or lists it on the marketplace, contract terms apply. This is where Sprites can define:

- License to host and serve the brain (required for marketplace)
- License to generate anonymized aggregate analytics across brains (required for meta-learning)
- No transfer of ownership (user keeps ownership, grants Sprites a license)

### Recommendation

**Structure:** User owns brain data. Always. Sprites gets a non-exclusive, revocable license when user opts into cloud/marketplace. Specific terms:

| Scenario | Ownership | Sprites License |
|----------|-----------|-----------------|
| Local-only SDK use | User owns 100% | None needed |
| Cloud sync (backup/portability) | User owns 100% | License to host, transmit back to user, generate anonymized aggregates |
| Marketplace listing | User owns 100% | License to host, serve inference to renters, generate anonymized aggregates, display quality metrics publicly |
| User deletes account | User owns 100% | All licenses terminate. Sprites deletes within 30 days. |

**Action item:** Draft a Brain Ownership Policy (plain English, 1 page) and a ToS addendum for cloud/marketplace. Budget: $2-5K legal review.

---

## 2. IP Protection: What Qualifies as Trade Secret?

### What IS protectable in a trained brain

| Component | IP Type | Protectable? | Notes |
|-----------|---------|-------------|-------|
| Graduated rules (INSTINCT/PATTERN/RULE) | Trade secret (user's) | Yes | Derived from user's proprietary corrections. Meets Uniform Trade Secrets Act criteria: (1) economic value from not being known, (2) reasonable efforts to maintain secrecy (server-side inference). |
| Correction history (events.jsonl) | Trade secret (user's) | Yes | Contains proprietary business decisions, communication preferences, domain expertise. |
| Brain manifest (quality scores) | Not secret | No | Public by design (marketplace listing). |
| Graduation algorithm (thresholds, decay rates) | Trade secret (Sprites') | Yes | The SDK code is open source, but the cloud-side inference engine, meta-learning algorithms, and quality verification logic can remain proprietary. |
| Embedding model weights | Not ours | No | Using all-MiniLM-L6-v2 (Apache 2.0). |

### Can graduation thresholds be patented?

**Likely not, and not worth pursuing.** Analysis:

- **Alice/Mayo test (US):** Software patents require the claim to be tied to a specific technical improvement, not an abstract idea. "Graduating a behavioral rule after N confirmations" is likely an abstract idea -- a mathematical threshold applied to a database counter. Post-Alice, the USPTO rejects ~65% of abstract software method claims.
- **Cost:** $15-25K for a US utility patent. $50-80K for international coverage. 3-5 year prosecution timeline.
- **Enforcement:** Against open-source community forks? Practically impossible and reputation-destroying.
- **Better alternative:** Trade secret for the cloud-side implementation (inference engine, meta-learning, quality verification). The SDK publishes the basic algorithm; the production implementation with optimizations, caching, and cross-brain intelligence stays server-side.

### Recommendation

Do not pursue patents. Invest in trade secret protection for cloud-side logic. The open-source SDK deliberately publishes the "what" (graduation pipeline concept) while keeping the "how at scale" proprietary (cloud inference, meta-learning, quality verification). This is the MySQL/Redis model: open core, proprietary cloud.

---

## 3. License Choice: MIT vs Apache 2.0 vs BSL

### Comparison for Marketplace Strategy

| Factor | MIT | Apache 2.0 | BSL (Business Source License) |
|--------|-----|-----------|-------------------------------|
| **Permissiveness** | Maximum. No conditions except attribution. | Permissive with patent grant. | Restrictive until conversion date (typically 3-4 years). |
| **Patent protection** | None. A contributor could patent their contribution and sue users. | Explicit patent grant from contributors. Users are protected. | Varies by implementation. |
| **Fork risk** | Anyone can fork and build competing marketplace. Legal. | Same fork risk as MIT. | Fork allowed for non-competing use only. Cannot offer hosted service. |
| **Community adoption** | Highest. No friction. | High. Enterprise-friendly. | Low-Medium. Developers distrust "open-ish" licenses. |
| **Enterprise acceptance** | Universal | Universal | Mixed. Some enterprises ban BSL as "not truly open source." |
| **Precedent** | React, Vue, Node, Express | Kubernetes, TensorFlow, Android | Sentry, MariaDB, Hashicorp (Terraform), CockroachDB |
| **Cloud provider risk** | AWS can fork and offer "Managed AIOS Brain" tomorrow. | Same as MIT. | Explicitly prevents this. |
| **OSI approved** | Yes | Yes | No. OSI does not consider BSL open source. |

### The Real Decision

The question is not "which license is most open" but "what is the primary threat?"

**Threat 1: Cloud provider commoditization (AWS/Azure forks your SDK and offers managed service).** This killed Elasticsearch (Amazon OpenSearch), Redis (Amazon ElastiCache), and MongoDB (DocumentDB). BSL was created specifically to prevent this. Hashicorp switched Terraform to BSL in 2023 after years of AWS free-riding. Sentry adopted FSL (Fair Source License, BSL variant) in 2024 for the same reason.

**Threat 2: Direct competitor forks your SDK and builds competing marketplace.** Both MIT and Apache 2.0 allow this. BSL prevents it.

**Threat 3: Community rejection tanks adoption.** Hashicorp's BSL switch triggered the OpenTofu fork (18K GitHub stars). The community backlash was severe. But Hashicorp's revenue grew 15% the following year -- enterprise customers did not care.

### Recommendation: Apache 2.0 NOW, consider BSL at revenue

**Phase 1 (pre-revenue, current):** Apache 2.0.
- Rationale: You need community adoption and credibility. Nobody will contribute to or adopt a BSL-licensed SDK with zero users. The patent grant protects early adopters. Enterprise IT departments greenlight Apache 2.0 automatically. Fork risk is theoretical when there is nothing to fork-and-monetize yet.

**Phase 2 (post-revenue, post-marketplace launch):** Evaluate BSL for the cloud components.
- The SDK (patterns/, enhancements/, brain.py) stays Apache 2.0 forever. Breaking this promise destroys trust.
- The cloud sync server, marketplace inference engine, meta-learning service, and quality verification API can be BSL or proprietary from day one. These are never part of the open-source SDK.
- This is the "open core" model: open SDK, proprietary cloud. Used by GitLab, Supabase, Grafana.

**Immediate action:** Change pyproject.toml from MIT to Apache-2.0. Add a LICENSE file (Apache 2.0 full text). Add NOTICE file (required by Apache 2.0).

---

## 4. Marketplace IP: Derivative Works and Improvement Rights

### Scenario: User A trains a sales brain. User B rents it. User B's corrections improve the brain.

This is the hardest legal question and must be resolved BEFORE marketplace launch.

### Option A: No Improvement Feedback (Simple, Recommended for MVP)

User B rents inference access. User B's queries and the answers they receive are logged for billing and anomaly detection. But User B's corrections, if any, stay with User B. User A's brain is not modified by User B's usage.

- Pro: Clean ownership. No derivative work questions. No GDPR complications from mixing user data.
- Con: Misses the compounding network effect. Brains do not improve from rental.
- Legal complexity: Low.

### Option B: Opt-in Improvement Feedback (Better, Recommended for V2)

User B can choose to contribute corrections back. If they do:

- User B retains ownership of their corrections.
- User B grants User A a license to incorporate corrections into the brain.
- User A's brain improves. User A can accept or reject each correction.
- User B gets a discount or credit for contributing (incentive alignment).

This is the Wikipedia/open-source model: contributors grant a license, not ownership.

- Pro: Brains compound faster. Network effect. Pricing incentive alignment.
- Con: Requires clear contributor license agreement. GDPR data processing agreement needed if cross-border.
- Legal complexity: Medium. Need a Contributor License Agreement (CLA) for brain improvements.

### Option C: Automatic Improvement (Risky, Not Recommended)

User B's usage automatically improves User A's brain without opt-in.

- Pro: Maximum compounding.
- Con: GDPR Article 6 requires a legal basis for processing. "Legitimate interest" is weak here. User B may not want their behavioral patterns feeding into a product they do not own. Regulatory risk is high, especially in EU.
- Legal complexity: High. Do not do this.

### Recommendation

Launch marketplace with Option A. Add Option B in V2 with explicit opt-in, CLA, and GDPR-compliant data processing agreement. Never do Option C.

---

## 5. Trademark: "AIOS Brain"

### Feasibility Analysis

**"AIOS":** Problematic as a standalone mark. "AIOS" is a common abbreviation (AI Operating System) used by multiple projects. A trademark search shows:

- AIOS is used by at least 3 other AI projects on GitHub (aios-foundation, AIOS by Rutgers, etc.)
- Descriptive marks (marks that describe what the product does) are hard to register. "AI Operating System" is descriptive.
- USPTO would likely issue a Section 2(e)(1) refusal (merely descriptive) for AIOS alone.

**"AIOS Brain":** Better but still descriptive. "Brain" in the context of AI is generic. The combination might achieve distinctiveness through use (acquired distinctiveness, Section 2(f)), but this requires extensive evidence of consumer recognition.

**"Sprites":** Strong mark. Arbitrary/fanciful in the AI context. No descriptive connection to the product. High registrability. "Sprites.ai" is even stronger (domain name reinforces distinctiveness).

### Recommendation

| Mark | Registrability | Cost (US) | Recommendation |
|------|---------------|-----------|----------------|
| AIOS | Very Low (descriptive) | $250-400 filing + likely $2-5K prosecution | Do not file |
| AIOS Brain | Low-Medium (descriptive combination) | $250-400 filing + $2-5K prosecution | Do not file |
| Sprites | High (arbitrary) | $250-400 filing, likely approved | File when budget allows |
| Sprites Brain | High (arbitrary + descriptive) | $250-400 filing | Consider for marketplace branding |
| Sprites AI | High | $250-400 | File alongside Sprites |

**Immediate action:** Do not file anything yet. Pre-revenue trademark filing is $250-400 per class per mark, plus $2-5K for attorney prosecution if objections arise. File "Sprites" in Class 42 (SaaS, software development tools) and Class 9 (downloadable software) when there is revenue to protect.

**Risk mitigation now (free):** Use TM symbol (not (R)) on "Sprites" in all public materials. This establishes common law trademark rights without registration. Example: "Sprites(TM) Brain SDK."

---

## 6. Data Privacy: GDPR/CCPA Implications for Brain Marketplace

### What a Trained Brain Contains

A brain trained on sales interactions contains:

- Behavioral patterns ("Oliver prefers direct tone, uses colons not dashes, avoids bold mid-paragraph")
- Communication preferences derived from corrections
- Potentially: prospect names, company names, deal values, email content (in events.jsonl)

### GDPR Analysis (EU Users)

| GDPR Concept | Application to Brain Marketplace |
|--------------|----------------------------------|
| **Personal data (Art. 4)** | Behavioral patterns derived from an identifiable person ARE personal data. "Oliver prefers X" is personal data about Oliver. |
| **Data controller (Art. 4)** | Brain owner = data controller for their own data. Sprites = data processor when hosting on cloud. |
| **Legal basis (Art. 6)** | Local use: not applicable (personal/household exemption). Cloud sync: legitimate interest or consent. Marketplace: consent (user opts in to list brain). |
| **Right to erasure (Art. 17)** | If brain contains data about third parties (prospect names, behavioral observations about colleagues), those third parties have erasure rights. |
| **Data transfer (Art. 46)** | If brain is trained in EU and hosted on US servers, need Standard Contractual Clauses or equivalent. |
| **DPIA (Art. 35)** | Brain marketplace likely triggers DPIA requirement (systematic processing of behavioral data at scale). |

### CCPA Analysis (California Users)

| CCPA Concept | Application |
|--------------|-------------|
| **Personal information** | Same as GDPR: behavioral patterns linked to identifiable person = personal info. |
| **Right to know** | Users must be told what brain data is collected and how it is used. |
| **Right to delete** | Users can request deletion. Must comply within 45 days. |
| **Right to opt out of sale** | If brain rental constitutes "sale" of personal information, users must be able to opt out. The 2023 CPRA amendments broadened "sale" to include "sharing for cross-context behavioral advertising." Brain rental is likely not "sale" under CCPA if the renter pays for inference, not raw data. |

### The Critical Problem: Third-Party Data in Brains

A sales brain trained on real prospect interactions contains personal data about those prospects. Those prospects never consented to their behavioral patterns being used in a marketplace.

**Example:** Brain learns "When emailing CFOs at mid-market SaaS companies, use ROI framing, not technical framing." This is a generalized pattern -- no personal data. Fine.

**Example:** Brain learns "John Smith at Acme Corp responded positively to break-up emails." This is personal data about John Smith. Not fine for marketplace.

### Recommendation: Scrubbing Pipeline

Before any brain enters the marketplace, implement a scrubbing step:

1. **Entity removal:** Strip all named entities (people, companies, deal values) from graduated rules. Rules should be abstract: "CFOs at mid-market SaaS respond to ROI framing" not "John Smith at Acme Corp responds to ROI framing."
2. **Pattern generalization:** Graduation from PATTERN to RULE should inherently strip specifics. This is already partially the case -- rules are abstractions by design.
3. **Event history exclusion:** events.jsonl and correction history NEVER enter the marketplace. Only graduated rules and anonymized quality metrics are exposed to renters.
4. **Brain owner attestation:** Before listing, brain owner attests that they have reviewed graduated rules for PII. Sprites provides a scanning tool.

**Action items:**
- Add PII scanning to brain.manifest.json generation (automated NER pass over graduated rules).
- Draft Privacy Policy and Data Processing Agreement for cloud/marketplace.
- Budget $3-5K for GDPR-specific legal review before EU launch.

---

## 7. Competitor Risk: Fork-and-Marketplace Defense

### Scenario: Someone forks the Apache 2.0 SDK and builds their own marketplace.

This is legal under both MIT and Apache 2.0. It cannot be prevented by license choice alone (BSL could prevent it but at adoption cost, see Section 3).

### Defense Layers (ranked by strength)

| # | Defense | Strength | Why |
|---|---------|----------|-----|
| 1 | **Meta-learning moat** | STRONG | Cross-brain pattern discovery requires N=30+ brains. A fork starts at zero. By the time a fork accumulates 30 brains, Sprites has 200+. The gap widens because meta-learning quality improves non-linearly with brain count. |
| 2 | **Brain supply (trained brains already on platform)** | STRONG | Marketplace value = number of quality brains available. First-mover with agency training pipeline (Brains 2-10) creates supply that a fork cannot replicate without doing the training work. |
| 3 | **Quality verification (server-side)** | MEDIUM-STRONG | The SDK publishes basic quality metrics. The cloud service provides verified, tamper-proof quality scores. A fork would need to build their own verification from scratch. |
| 4 | **Trademark (Sprites brand)** | MEDIUM | Brand recognition and trust. "Available on Sprites Marketplace" becomes a quality signal. A fork cannot use the Sprites name. |
| 5 | **Network effects** | MEDIUM | Brain composability (rent 3 brains that work together). Only valuable on a platform with many brains. Fork starts with zero composition opportunities. |
| 6 | **Operational expertise** | MEDIUM | Syncing brains, serving inference, managing billing, handling disputes, preventing extraction. A fork has to build all operational infrastructure. |
| 7 | **Community** | LOW-MEDIUM | Contributors, brain owners, documentation. Forks often struggle with community building. But this is weak alone -- see OpenTofu. |

### The Honest Assessment

A well-funded competitor (AWS, Anthropic, or a VC-backed startup) could fork the SDK and build a competing marketplace within 6-12 months. The technical moat is not in the SDK code. It is in:

1. The trained brain supply (which requires human training time -- not forkable)
2. The meta-learning data (which requires brain count -- not bootstrappable)
3. The cloud-side inference/verification (which is never open-sourced)

This is identical to how WordPress (GPL, fully copyable code) maintains dominance: the code is free, the ecosystem is the moat. WordPress.com (Automattic's hosted service) earns $500M+/year despite WordPress.org being freely forkable.

### Recommendation

Accept fork risk as a feature, not a bug. The SDK being open source is a distribution strategy. A fork that builds a competing marketplace validates the category and expands the total addressable market. Sprites wins by:

1. Being first with trained brain supply (agency pipeline)
2. Having the most brain data for meta-learning
3. Owning the Sprites brand and community trust
4. Keeping cloud-side inference, verification, and meta-learning proprietary

---

## Summary: Action Items by Priority

### Do Now (Free / <$500)

| # | Action | Cost | Notes |
|---|--------|------|-------|
| 1 | Change license from MIT to Apache 2.0 in pyproject.toml, add LICENSE file, add NOTICE file | $0 | Apache 2.0 patent grant protects users. MIT has a patent gap. |
| 2 | Add TM symbol to "Sprites" in public materials | $0 | Establishes common law trademark rights. |
| 3 | Draft Brain Ownership Policy (plain English, 1 page) | $0 | "You own your brain. We host it. You can delete it anytime." |
| 4 | Add PII scanner to brain.manifest.json generation | $0 | NER pass over graduated rules. Flag names, companies, emails. |

### Do Before Marketplace Launch ($5-15K legal budget)

| # | Action | Cost | Notes |
|---|--------|------|-------|
| 5 | Attorney review of Brain Ownership Policy + ToS | $2-5K | Must cover ownership, licensing, deletion, data portability. |
| 6 | GDPR Data Processing Agreement for cloud/marketplace | $2-3K | Required before accepting EU users on cloud service. |
| 7 | Privacy Policy (cloud + marketplace) | $1-2K | Standard but must address brain-specific data types. |
| 8 | File "Sprites" trademark (Class 9 + 42) | $500-800 | Two classes, US filing. Add international when revenue justifies. |

### Do When Revenue Justifies ($15K+)

| # | Action | Cost | Notes |
|---|--------|------|-------|
| 9 | Contributor License Agreement for brain improvements (Option B) | $3-5K | Needed when marketplace adds improvement feedback. |
| 10 | DPIA (Data Protection Impact Assessment) for EU marketplace | $5-10K | Triggered by systematic behavioral data processing at scale. |
| 11 | International trademark filings (EU, UK, Singapore) | $3-5K per jurisdiction | File in jurisdictions where customers concentrate. |
| 12 | Evaluate BSL for cloud components | $5K legal review | Only if cloud provider commoditization becomes a real threat. |

---

## Decision Matrix

| Question | Answer | Confidence |
|----------|--------|------------|
| Who owns the trained brain? | The user. Always. | HIGH |
| Can graduation thresholds be patented? | Likely not, and not worth pursuing. | HIGH |
| MIT or Apache 2.0? | Apache 2.0 (patent grant). | HIGH |
| BSL? | Not now. Reconsider at revenue. | MEDIUM |
| Who owns improvements from rental? | Start with no improvement feedback (Option A). Add opt-in (Option B) later. | HIGH |
| Trademark "AIOS Brain"? | No. Trademark "Sprites" instead. | HIGH |
| GDPR risk? | Real. Scrub PII before marketplace. Event history never enters marketplace. | HIGH |
| Fork defense? | Supply-side moat (trained brains) + meta-learning + proprietary cloud. Not license restrictions. | HIGH |

## Sources

- 17 USC 102 (US Copyright Act, subject matter of copyright)
- EU Directive 96/9/EC (Database Directive, sui generis rights)
- Uniform Trade Secrets Act (UTSA, trade secret definition and protection)
- Alice Corp v. CLS Bank (2014) (US Supreme Court, software patent abstractness test)
- GDPR Articles 4, 6, 17, 35, 46
- CCPA / CPRA (California Consumer Privacy Act, 2023 amendments)
- Hashicorp BSL transition (2023) and community response
- Sentry FSL adoption (2024)
- WordPress/Automattic business model (GPL + hosted service)
- Fenwick: DeepSeek, Model Distillation, and AI IP (2025)
- Apache Software Foundation: Apache 2.0 License FAQ
- USPTO Trademark Manual of Examining Procedure, Section 1209 (descriptiveness)
