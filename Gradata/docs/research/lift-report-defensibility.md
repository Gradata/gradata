# Lift Report Statistical Defensibility Analysis

**Date**: 2026-05-22  
**Scope**: Evaluates claims in the Beta-binomial rule confidence system (`_stats.py`, `_scoring.py`, `_confidence.py`)  
**Verdict**: Mixed. Core methodology is sound but relies on observational data with uncontrolled confounds. Claims are defensible with proper caveats.

---

## Executive Summary

The Gradata SDK evaluates whether rules "made the agent better" using a Bayesian Beta-binomial framework: fires and misfires are treated as binomial outcomes with a Beta(1,1) prior to compute a posterior mean and 95% CI. This approach is statistically rigorous for what it measures (posterior credible interval on success rate *given observed fires*), but it answers an observational question, not a causal one. A hostile statistician would reject claims of causality but accept claims about empirical rule performance conditional on existing selection.

---

## Claim 1: "A rule's success rate can be estimated via Beta-binomial posterior"

**Statement**: The system computes `Beta(fires - misfires + 1, misfires + 1)` posterior and publishes the posterior mean as a "confidence" score (lines 106–151 in `_stats.py`).

**Defense**:
- **Sound under the model**: Given that events are sampled iid from an underlying Bernoulli process (rule fires and either succeeds or misfires), the Beta-binomial posterior is the textbook Bayesian solution. The posterior mean is the Bayes-optimal point estimate under squared-error loss.
- **Proper uncertainty quantization**: The 95% credible interval (lines 116–121) correctly captures posterior uncertainty. Lower bound at the 5th percentile (via `_beta_ppf_05`) is conservative and defensible.
- **Flat prior is transparent**: The Beta(1,1) uniform prior (line 107) is explicitly chosen and mathematically equivalent to adding one pseudocount. This is standard in absence of prior knowledge.

**Caveat**: The posterior answers "what is P(success | observed fires)" under the assumption that fires are iid samples from a fixed success-rate distribution. This assumes no drift, no selection bias in *when* rules fire, and no systematic differences between the conditions under which rules fire.

**Defensible reframing**: "The empirical success rate, regularized via Bayesian shrinkage with a flat prior, is X (95% CI: Y–Z)." This is factually correct and makes no causal claim.

---

## Claim 2: "Rules at confidence ≥0.90 are 'proven' to improve agent output"

**Statement**: The system labels rules with `confidence >= 0.90` as RULE state and claims they are "proven" (line 136 in `_stats.py`, confidence_label "PROVEN").

**Challenge**:
- **No causal evidence**: The posterior success rate is observational. A rule with a 95% empirical success rate *among fires where the system chose to apply it* does not prove the rule improved output. Uncontrolled confounds:
  - **Selection bias**: The rule fires only when the system thinks it's relevant. Output quality may improve anyway due to other factors (better prompt, different user context, agent capability drift).
  - **Survivor bias**: Only fires are observed. Rules that fire rarely may be both selective *and* consistently helpful, but appear less confident due to small sample size.
  - **Post-hoc evaluation**: Misfires are determined after the rule executes. If evaluation criteria shift, the same rule can change apparent success rate without any change to its actual quality.

**Defense (weaker)**:
- High empirical success rate is *consistent with* the rule being helpful, but doesn't prove causality.
- In practice, rules with 95% empirical success + >5 fires represent strong evidence *relative to zero information*, even if not causal proof.
- The system uses a "proven" label (not "proven to improve") which could be reinterpreted as "empirically proven to fire successfully in observed conditions."

**Undefendable claim**: "This rule made the agent better" without an experiment. A paired test (same prompt, same agent, with rule vs. without rule) would be stronger.

**Honest reframing**: "Among fires where this rule was applied, it succeeded 95% of the time (95% CI: 87–99%). This suggests it is reliably applicable to its intended scope, but does not prove causality without a control group."

---

## Claim 3: "The 95% confidence interval correctly bounds rule quality"

**Statement**: Beta distribution 5th and 95th percentiles (lines 116–121 in `_stats.py`) form a 95% credible interval for the success probability.

**Defense**:
- **Mathematically correct**: For a Beta posterior, the Bayesian credible interval is exactly the HDI (highest density interval) or quantile interval as computed. This is not a frequentist CI (which would require a different interpretation).
- **Conservative**: Using the 5th percentile as a lower bound is a one-sided conservative bound, not a two-sided symmetric interval. This is defensible for quality assurance (we want a lower bound on what we're confident about).
- **Robust to sample size**: Beta distribution naturally inflates CI width for small samples (few fires). A rule with 2 fires and 0 misfires gets CI ≈ [0.10, 0.98], which correctly reflects high uncertainty.

**Caveat**: The interval bounds the posterior, not ground truth. If the iid Bernoulli assumption is violated (e.g., rule quality drifts over time, or fires cluster in certain user contexts), the interval may be miscalibrated. No test for drift or batch effects is performed.

**Defensible statement**: "The 95% Bayesian credible interval for the success rate is [X, Y], reflecting our posterior belief about the true underlying success probability given observed fires."

---

## Claim 4: "Uniform Beta(1,1) prior is justified"

**Statement**: The system uses `prior_alpha=1.0, prior_beta=1.0` (line 107) throughout, with no domain-specific justification.

**Challenge**:
- **Arbitrary for domain context**: For rules that are "proven" in the codebase (high fires, low misfires), the prior choice barely matters. For new rules (few fires), the prior biases the posterior. Using Beta(1,1) adds one pseudofire and one pseudomisfire, which is conservative for new rules.
- **No sensitivity analysis**: The system doesn't publish how sensitive conclusions are to prior choice (e.g., Beta(0.5, 0.5) vs. Beta(1, 1) vs. informative priors based on rule category).

**Defense**:
- **Non-informative choice**: Beta(1,1) is the standard non-informative prior in the absence of domain knowledge. This is transparent and principled.
- **Consistent across rules**: Using the same prior for all rules is fair and doesn't sneak in hidden assumptions.
- **Regularization effect is mild for mature rules**: Rules with 100+ fires are barely influenced by the prior.

**Honest caveat**: "Results are conditional on a flat prior. Rules with <10 fires depend on prior choice; sensitivity analysis would strengthen claims."

---

## Claim 5: "Misfires are ground truth"

**Statement**: The system treats `misfires` (marked by the user or system as "this rule made output worse") as the true failure count (lines 288–299 in `_scoring.py`).

**Challenge**:
- **Subjective ground truth**: Who decides if output is "worse"? The system detects explicit contradictions (line 598 in `_confidence.py`), but:
  - A rule might help in ways not immediately visible (e.g., sets up future success).
  - A rule might hurt in ways masked by other improvements.
  - Evaluation criteria may change over time or vary by user.
- **Late binding**: Misfires are determined *after* a rule fires and the output is evaluated. This is post-hoc and potentially subject to hindsight bias.
- **Censoring**: Fires that go uncorrected are counted as successes, but might be low-quality improvements that the user simply didn't catch.

**Defense (weak)**:
- **Explicit feedback is better than nothing**: Marked misfires are explicit user corrections, not inferred from silent data. This is less noisy than measuring "success" indirectly.
- **Conservative**: Assuming uncorrected = success is optimistic, but explicit contradictions are very reliable negative feedback.

**Undefendable reframing**: "Misfires = true failures." Misfires are *observed contradictions*, not failures. Absence of observed contradiction ≠ success.

**Honest reframing**: "Misfires represent explicit user contradictions. Fires without contradictions are assumed to be acceptable, but may include undetected low-quality improvements."

---

## Claim 6: "No multiple-comparison problem because rules are independent"

**Implied claim**: The system evaluates many rules in parallel without multiple-comparison correction (no Bonferroni, FDR adjustment). Assumption: rules are independent.

**Challenge**:
- **Rules interact**: Multiple rules fire on the same prompt. If 10 rules fire together and one appears helpful, causality is ambiguous (was it that rule, or the other 9?).
- **Shared data**: All rules are evaluated on the same session transcripts. Dependencies in user behavior (e.g., "this user prefers short output") would induce false correlations.
- **No correction for multiple tests**: If 100 rules are evaluated, and we claim all with 95% CI above 0.50 are "emerging," the family-wise error rate is not controlled.

**Defense**:
- **Not a formal hypothesis test**: The system reports posterior credible intervals, not p-values. No multiple-comparison correction is required if the goal is Bayesian credible intervals (each rule gets its own posterior).
- **Practical significance filter**: Rules must have significant empirical success (high fire count) to be promoted. A rule with 2 fires and lucky success won't graduate past PATTERN tier (lines 54–56 in `_confidence.py`).

**Caveat**: If the system is used to make binary decisions ("promote/demote this rule?") based on credible intervals, then multiple-comparison error does apply.

**Honest caveat**: "Each rule's posterior is computed independently. No multiple-comparison correction is applied. If used to make multiple decisions, family-wise error rate is not controlled."

---

## Claim 7: "Rule quality is stable over time"

**Implied claim**: The Beta-binomial model assumes fires are iid samples from a fixed success distribution. No drift detection is performed.

**Challenge**:
- **Concept drift**: A rule that was excellent for old model versions might hurt with a new model. The system has no time-awareness in the posterior (fires from month 1 and month 12 are weighted equally).
- **Seasonal effects**: Rules for certain user contexts might degrade as the user base changes.
- **No trend test**: The system computes `trend_analysis` (line 18 in `_stats.py`) but doesn't apply it to rule success rates.

**Defense**:
- **Practical safeguard**: Rules are re-evaluated every session (line 651 in `_confidence.py`). If quality drops, fire_count plateaus and misfire_count grows, lowering confidence.
- **Demote on contradiction**: A single explicit contradiction triggers a penalty (lines 837–875 in `_confidence.py`). This is a form of online adaptation.

**Caveat**: The system is reactive (detects decline after it happens), not proactive. A rule in decline from session 100 to 200 might maintain high confidence for 50 sessions before corrections catch up.

**Honest reframing**: "Rule quality is assumed constant within a session. Between-session decline is detected via contradictions but is reactive, not predictive."

---

## Undefendable Claims

### Claim (rejected): "This rule caused the improvement"
**Why**: No counterfactual. Without a control group (same prompt without the rule), causal attribution is impossible. Even with matching on observables, confounding by unobservables is unquantifiable.

**Undefendable reframe**: Cannot be defended. Requires paired experiment.

### Claim (rejected): "Rules are evaluated with correct statistical adjustment"
**Why**: No FDR, Bonferroni, or other multiplicity adjustment for the ~50+ rules in a typical brain.

**Defensible reframe**: "Each rule's posterior is computed independently. Multiple-comparison error is not controlled; use rules as guidance, not binary decisions."

---

## Proposed Experiment to Strengthen Claims

To defend the causal claim "Rule X improves agent output," implement a paired A/B test:

1. **Experimental design**: For each rule in RULE state, run N recent prompts:
   - Variant A: Agent with rule enabled
   - Variant B: Same agent, same rule, *disabled*
   - Keep all other rules constant

2. **Outcome measurement**: Judge success/failure by the same criteria as misfires (explicit contradiction or quality degradation).

3. **Statistical test**: 
   - Use a paired binomial test (McNemar) or paired t-test on success rates
   - Report a causal effect size: P(success | rule) - P(success | no rule)

4. **Repeat**: Run this every month to track whether a rule's causal effect is stable.

**Effort**: Medium. Requires re-running 50–100 prompts per rule, ~5–10 minutes per rule, ~500 rule-hours/quarter.

---

## Recommendations

### For immediate publication (defensible):
1. Rename "confidence" to "**empirical success rate**" to avoid the implication of certainty.
2. Add caveat to all rule reports: "Based on observational data. Does not prove causality."
3. Report the **fire count** and **misfire count** alongside the posterior, so users see the evidence size.
4. Explicitly state the prior: "Beta(1,1) prior assumes no domain knowledge."

### For stronger claims (requires work):
1. Implement paired A/B tests for RULE-state rules quarterly.
2. Add time-awareness: segment fires by month, test for drift using `trend_analysis`.
3. Publish a multiple-comparison correction (FDR) when making categorical decisions.

### For publication context:
- **For internal use**: Current methodology is fine. It's a reasonable heuristic for rule quality.
- **For academic credibility**: Current claims are observational, not causal. Honest framing is essential.
- **For product users**: "Rules are ranked by empirical success rate, not proven to improve your output."

---

## Conclusion

**Verdict**: The Beta-binomial framework is **statistically sound** for estimating posterior success rates from observational data. Claims about rule quality conditional on fires are **defensible**. Claims of causal improvement are **not defensible** without a control group.

The system's real strength is **pragmatic**: rules with 95%+ empirical success on 5+ fires are usually helpful. The real weakness is **theoretical**: no causal proof, confounding by unobservables, and reactive (not predictive) drift detection.

Recommend: publish with honest caveats about observational limitations, and plan paired experiments for the next research cycle.
