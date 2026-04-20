"""
Cross-Validation Synthesis — compare MiroFish consensus to Gradata architecture.
=================================================================================
Reads outputs from all sims and produces a synthesis document categorizing:
  - VALIDATED: blind experts converged on what we already have
  - GAPS: experts converged on what we DON'T have (implement)
  - QUESTIONABLE: experts rejected what we DO have (investigate)
  - NOVEL: we built what nobody proposed (moat or mistake)

Usage:
    python cross_validate.py --sim-a .tmp/mirofish/sim_a/ --sim-b .tmp/mirofish/sim_b/ --opt-results .tmp/opt-results/ --output .tmp/cross-validation/
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)

GRADATA_FEATURES = {
    "correction_detection": "Edit distance + keyword-based severity classification",
    "graduation_pipeline": "INSTINCT (0.40) -> PATTERN (0.60) -> RULE (0.90) with confidence scoring",
    "scope_matching": "7-dimension scope (task_type, category, tone, etc.) with weighted matching",
    "rule_injection": "Top-N rules formatted as XML, injected into prompt via primacy/recency positioning",
    "contradiction_detection": "Polarity pairs + action opposites heuristic matching",
    "meta_rules": "Auto-cluster 3+ related graduated rules into higher-order principles",
    "confidence_math": "Arithmetic addition with severity-weighted increments/decrements",
    "implicit_approval": "OUTPUT_ACCEPTED events from non-corrections (added S102)",
    "bayesian_confidence": "Beta posterior integrated into confidence pipeline (added S102)",
    "semantic_severity": "Meaning-preserving detection to downgrade trivial edits (added S102)",
    "rule_suppression": "Track suppressed rules to fix denominator bias (added S102)",
    "temporal_scope": "Temporal context dimension for time-relevant rules (added S102)",
    "intent_classifier": "Dual-layer heuristic+LLM intent classification (added S102)",
    "rosch_taxonomy": "6-category hierarchical taxonomy with backward compat (added S102)",
}


def load_synthesis(sim_dir: Path) -> str:
    path = sim_dir / "SYNTHESIS.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "[Synthesis not yet available — sim still running or failed]"


def load_opt_results(opt_dir: Path) -> dict:
    summary_path = opt_dir / "SUMMARY.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text())
    return {"status": "not_completed"}


def synthesize(
    sim_a_dir: Path,
    sim_b_dir: Path,
    opt_results_dir: Path,
    output_dir: Path,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)

    sim_a = load_synthesis(sim_a_dir)
    sim_b = load_synthesis(sim_b_dir)

    opt_conciseness = load_opt_results(opt_results_dir / "conciseness")
    opt_coldstart = load_opt_results(opt_results_dir / "coldstart")
    opt_reversal = load_opt_results(opt_results_dir / "reversal")

    features_list = "\n".join(f"- **{k}**: {v}" for k, v in GRADATA_FEATURES.items())

    doc = f"""# Cross-Validation Synthesis
Generated: {datetime.now().isoformat()}

## Gradata's Current Architecture
{features_list}

---

## MiroFish Sim A: Blind Learning Architecture Consensus

{sim_a}

---

## MiroFish Sim B: Blind Distribution Architecture Consensus

{sim_b}

---

## Optimization Results

### Conciseness
```json
{json.dumps(opt_conciseness, indent=2)}
```

### Cold Start
```json
{json.dumps(opt_coldstart, indent=2)}
```

### Preference Reversal
```json
{json.dumps(opt_reversal, indent=2)}
```

---

## Comparison Matrix

### VALIDATED (experts converged on what we already have)
_To be filled after reading sim syntheses -- match against GRADATA_FEATURES above_

### GAPS (experts converged on what we DON'T have)
_To be filled after reading sim syntheses -- features proposed by consensus not in GRADATA_FEATURES_

### QUESTIONABLE (experts rejected what we DO have)
_To be filled after reading sim syntheses -- features in GRADATA_FEATURES that experts criticized_

### NOVEL (we built what nobody proposed)
_To be filled after reading sim syntheses -- features in GRADATA_FEATURES not mentioned by any expert_

---

## Next Steps
1. Implement GAP features in priority order
2. Investigate QUESTIONABLE features -- are we wrong or are they?
3. Protect NOVEL features -- these may be our moat
4. Generate marketing claims from VALIDATED features with confidence intervals
"""

    output_path = output_dir / "SYNTHESIS.md"
    output_path.write_text(doc, encoding="utf-8")
    _log.info("Synthesis written to %s", output_path)
    return doc


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Cross-validate MiroFish results against Gradata architecture"
    )
    parser.add_argument("--sim-a", required=True, help="Sim A output directory")
    parser.add_argument("--sim-b", required=True, help="Sim B output directory")
    parser.add_argument("--opt-results", required=True, help="Optimization results directory")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()
    synthesize(Path(args.sim_a), Path(args.sim_b), Path(args.opt_results), Path(args.output))
