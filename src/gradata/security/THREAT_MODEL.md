# Gradata Privacy Threat Model

**Version:** 1.0 (2026-04-11)
**Scope:** Gradata SDK local brain + cloud sharing pipeline
**Status:** v1 — covers statistical privacy. Text-level re-identification is out of scope.

---

## Assets at Risk

| Asset | Sensitivity | Location |
|-------|-------------|----------|
| Correction log (draft/final pairs) | CRITICAL — reveals cognitive patterns, knowledge gaps, writing style | system.db events table |
| Rule descriptions | HIGH — may contain domain-specific preferences that identify users | lessons.md, system.db |
| Usage statistics (fire_count, misfires) | MEDIUM — reveals frequency of behavior patterns | lessons.md |
| Brain manifest | LOW — aggregate quality metrics | brain.manifest.json |

## Threat Actors

1. **External attacker** — gains access to brain files (stolen device, exposed cloud endpoint)
2. **Curious platform operator** — Gradata cloud admin with database access
3. **Other marketplace users** — see shared rules, attempt to infer source identity
4. **Malicious contributor** — injects poisoned rules into marketplace

## Attack Vectors

### 1. Profile Inversion (CRITICAL)
**Attack:** The correction log is the most detailed psycho-linguistic profile possible. An attacker reconstructs the user's expertise gaps, biases, and cognitive patterns from correction history.
**Mitigation:** Brain salt (`brain_salt.py`) obfuscates identifiers. Encryption at rest (`_encryption.py`) protects stored data. Cloud sync strips `example_draft` and `example_corrected` fields.
**Residual risk:** Rule description text is shared as-is. A rule like "Oliver always uses methodology instead of approach" is a re-identification vector.

### 2. Correction Poisoning (HIGH)
**Attack:** A malicious actor injects corrections that degrade the knowledge base. All corrections are treated as ground truth.
**Mitigation:** Graduation pipeline requires multiple consistent fires before a rule reaches RULE state. Contradiction detector flags conflicting patterns. Anti-climb prevents oscillation.
**Residual risk:** Slow, consistent poisoning over many sessions could graduate bad rules.

### 3. Side-Channel Inference from Statistics (MEDIUM)
**Attack:** Fire_count and misfire patterns reveal usage frequency. An observer infers which rules a user applies most.
**Mitigation:** Laplace noise (`privacy_model.py`) on fire_count, misfire_count, sessions_since_fire before cloud export. Epsilon-DP with configurable privacy budget.
**Residual risk:** With enough observations, noise can be averaged out.

### 4. Re-Identification from Shared Rules (MEDIUM)
**Attack:** A unique rule in the marketplace (e.g., "always sign emails with 'Cheers, Oliver'") identifies its creator even without explicit attribution.
**Mitigation:** k-anonymity threshold (MIN_K_ANONYMITY=5). A rule must exist in 5+ brains before marketplace listing. transfer_scope gating (UNIVERSAL only by default).
**Residual risk:** Rare but valid universal rules could still identify users. Threshold may need tuning.

### 5. Gradient Inversion (NOT APPLICABLE)
**Note:** Unlike federated learning systems, Gradata shares discrete human-readable rules, not model gradients. Gradient inversion attacks do not apply. This is a structural privacy advantage.

## Mitigations Implemented

| Mitigation | Module | Status |
|------------|--------|--------|
| Encryption at rest | `_encryption.py` | Shipped |
| Brain salt (identifier obfuscation) | `brain_salt.py` | Shipped |
| Correction provenance tracking | `correction_provenance.py` | Shipped |
| Manifest signing | `manifest_signing.py` | Shipped |
| Query budget (rate limiting) | `query_budget.py` | Shipped |
| Score obfuscation | `score_obfuscation.py` | Shipped |
| Laplace DP noise on statistics | `privacy_model.py` | Shipped (S103) |
| PII field stripping on export | `privacy_model.py` | Shipped (S103) |
| k-anonymity threshold | `privacy_model.py` | Shipped (S103) |
| transfer_scope gating | `rule_engine.py` | Shipped |

## Out of Scope for v1

1. **Text-level re-identification** — rule descriptions may contain identifying information. LLM-based text redaction before export is future work.
2. **Secure aggregation** — no multi-party computation for rule synthesis. Rules are shared as plaintext (after sanitization).
3. **Formal DP guarantees on text** — epsilon-DP only applies to numerical statistics, not to text content.
4. **Homomorphic encryption** — not needed since we share rules, not gradients.

## Recommendations for Users

1. Review shared rules before enabling cloud sync (`brain.share()`)
2. Use `transfer_scope=UNIVERSAL` (default) to limit sharing to non-personal rules
3. Set a high epsilon (less noise) for personal brains, low epsilon (more noise) for shared brains
4. Avoid putting PII in correction descriptions (the system doesn't currently redact)
