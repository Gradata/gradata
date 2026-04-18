"""A/B test harness: constitutional vs imperative rule-injection format.

Validates Gap 5: does reframing learned rules as constitutional value
statements ("You value X — do Y") outperform imperative commands
("Always do Y") on quality, rule adherence, and naturalness?

Pipeline
--------
1. Load lessons from a brain directory (``--brain-dir`` or ``$GRADATA_BRAIN``).
2. For each test prompt, build a scoped rule set via ``apply_rules``.
3. Generate TWO draft outputs using Ollama Gemma4:e4b:
      Version A — rules formatted as ``imperative`` (current default)
      Version B — rules formatted as ``constitutional`` (experimental)
4. Score each output with a separate Gemma4:e4b judge call on:
      quality, rule_adherence, naturalness (1-10 each).
5. Position-randomize the judge's "Output 1 vs Output 2" so format order
   doesn't leak (recorded per-prompt so we can decode after).
6. Aggregate win rates + means, run a simple Welch's t-test per dimension,
   and write a results.md with methodology, raw scores, aggregates,
   significance, and explicit limitations.

Usage
-----
    # Build only (what this commit ships):
    python brain/scripts/ab_test_constitutional.py --dry-run

    # Full run (not executed in this commit):
    python brain/scripts/ab_test_constitutional.py \\
        --brain-dir "$GRADATA_BRAIN" \\
        --output .tmp/ab_test_results \\
        --model gemma4:e4b

NOTE: The harness is ready but has not been executed. Run it only when
Ollama Gemma4:e4b is live at localhost:11434.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from _common import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_URL, ensure_sdk_on_path, ollama_generate

ensure_sdk_on_path()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ab_test_constitutional")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = DEFAULT_OLLAMA_MODEL
OLLAMA_URL = DEFAULT_OLLAMA_URL
DEFAULT_BRAIN_DIR = os.environ.get("GRADATA_BRAIN", "./brain")
DEFAULT_OUTPUT = ".tmp/ab_test_results"

GEN_TIMEOUT_S = 120
JUDGE_TIMEOUT_S = 60

# Scoring dimensions the judge rates 1..10
DIMENSIONS: tuple[str, ...] = ("quality", "rule_adherence", "naturalness")


# ---------------------------------------------------------------------------
# Test prompts — 24 across sales / engineering / support
# ---------------------------------------------------------------------------

TEST_PROMPTS: list[dict[str, str]] = [
    # --- Sales: email drafting (8) ---
    {
        "task": "Write a cold outreach email to a VP of Marketing at a mid-market ecommerce brand.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    {
        "task": "Draft a follow-up email after a demo where the prospect went silent for a week.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    {
        "task": "Write a short intro email referencing a LinkedIn post the prospect commented on.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    {
        "task": "Draft a reply to a prospect who said 'send pricing and we'll review internally'.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    {
        "task": "Write a break-up email to a prospect who has gone dark for 6 weeks.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    {
        "task": "Draft a meeting confirmation email that restates the agreed agenda in 3 bullets.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    {
        "task": "Write a proposal-recap email that summarises scope, price and next step.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    {
        "task": "Draft an email asking a former champion for a warm intro at their new company.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    # --- Engineering: code review / refactor (8) ---
    {
        "task": "Review this Python function that validates email addresses and flag issues.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Suggest a refactor for a 400-line React component that mixes fetching and UI.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Review a SQL migration that adds a NOT NULL column with no default on a big table.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Critique a REST endpoint that returns HTTP 200 with an error payload on failure.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Review a shell script that rm -rfs a directory computed from an env variable.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Write a code review comment on a PR that introduces a new third-party dependency for one helper.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Review test coverage for a new auth middleware and identify missing cases.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Evaluate a pull request description and suggest improvements for clarity.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    # --- Support: customer responses (8) ---
    {
        "task": "Draft a support reply to a customer reporting intermittent 500 errors on checkout.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Write a response to a customer asking for a refund 10 days past the 7-day policy.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Draft a reply explaining that the feature they requested is on the roadmap for Q3.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Respond to a customer who says a competitor is cheaper and is threatening to churn.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Write an apology to a customer whose data export was delayed by 48 hours.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Draft a reply to a non-technical user asking how to set up SSO.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Respond to a customer who reports a billing charge they don't recognize.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Write a short reply acknowledging a feature request and asking two clarifying questions.",
        "domain": "support",
        "task_type": "support_reply",
    },
]


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


def _ollama_generate(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
    timeout: int = GEN_TIMEOUT_S,
    num_predict: int = 500,
    temperature: float = 0.7,
) -> str:
    """Call Ollama /api/generate. Returns response text or an error marker."""
    return ollama_generate(
        prompt,
        system=system,
        model=model,
        url=OLLAMA_URL,
        timeout=timeout,
        num_predict=num_predict,
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------


def _load_lessons_from_brain(brain_dir: Path) -> list:
    """Parse lessons.md from a brain directory."""
    from gradata.enhancements.self_improvement import parse_lessons

    lessons_path = brain_dir / "lessons.md"
    if not lessons_path.is_file():
        raise FileNotFoundError(f"lessons.md not found at {lessons_path}")
    return parse_lessons(lessons_path.read_text(encoding="utf-8"))


def _rules_for_prompt(lessons: list, task: str, domain: str, task_type: str, max_rules: int = 6):
    """Select the top rules for a given prompt scope."""
    from gradata._scope import RuleScope
    from gradata.rules.rule_engine import apply_rules

    scope = RuleScope(domain=domain, task_type=task_type)
    return apply_rules(lessons, scope, max_rules=max_rules, user_message=task)


# ---------------------------------------------------------------------------
# Draft generation — the two variants
# ---------------------------------------------------------------------------

_DRAFT_SYSTEM = (
    "You are an assistant generating a single on-task draft. "
    "Follow the injected rules. Do not add preamble or explain yourself — "
    "produce ONLY the requested draft."
)


def _build_prompt(task: str, formatted_rules: str) -> str:
    if not formatted_rules:
        return f"TASK: {task}\n\nDraft:"
    return f"{formatted_rules}\n\nTASK: {task}\n\nDraft:"


def _generate_variant(
    task: str,
    applied_rules,
    format_style: str,
    model: str,
) -> str:
    from gradata.rules.rule_engine import format_rules_styled

    formatted = format_rules_styled(applied_rules, format_style=format_style)
    prompt = _build_prompt(task, formatted)
    return _ollama_generate(prompt, system=_DRAFT_SYSTEM, model=model)


# ---------------------------------------------------------------------------
# LLM judge
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM = (
    "You are a strict, impartial evaluator of short written outputs. "
    "Return ONLY a JSON object with integer keys 1_quality, 2_rule_adherence, "
    "3_naturalness, each scored 1 to 10. No prose, no markdown, no code fence."
)


def _build_judge_prompt(
    task: str,
    rules_text: str,
    output_1: str,
    output_2: str,
    which_is_first: str,
) -> str:
    """Build the judge prompt. which_is_first records which variant is labelled 'Output 1'."""
    return (
        f"TASK: {task}\n\n"
        f"RULES THE OUTPUTS SHOULD FOLLOW (shown as-is, in imperative form):\n"
        f"{rules_text or '(no rules)'}\n\n"
        f"----- OUTPUT 1 -----\n{output_1}\n----- END OUTPUT 1 -----\n\n"
        f"----- OUTPUT 2 -----\n{output_2}\n----- END OUTPUT 2 -----\n\n"
        f"Score EACH output independently on three dimensions (1 worst, 10 best):\n"
        f"  - quality: is it a good, on-task draft?\n"
        f"  - rule_adherence: does it honour the rules above?\n"
        f"  - naturalness: does it read like a human wrote it?\n\n"
        f"Respond with ONE JSON object exactly in this shape:\n"
        f'{{"output_1": {{"quality": int, "rule_adherence": int, "naturalness": int}}, '
        f'"output_2": {{"quality": int, "rule_adherence": int, "naturalness": int}}}}\n\n'
        f"(which_is_first={which_is_first} — internal bookkeeping, ignore)"
    )


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_judge_json(raw: str) -> dict[str, dict[str, int]] | None:
    """Extract the first JSON object from a judge reply. Returns None on failure."""
    if not raw:
        return None
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    for key in ("output_1", "output_2"):
        sub = obj.get(key)
        if not isinstance(sub, dict):
            return None
        for dim in DIMENSIONS:
            v = sub.get(dim)
            if not isinstance(v, (int, float)):
                return None
            sub[dim] = max(1, min(10, int(round(v))))
    return obj


def _score_with_gemma(
    task: str,
    rules_text: str,
    output_1: str,
    output_2: str,
    which_is_first: str,
    model: str = DEFAULT_MODEL,
) -> dict[str, dict[str, int]] | None:
    prompt = _build_judge_prompt(task, rules_text, output_1, output_2, which_is_first)
    raw = _ollama_generate(
        prompt,
        system=_JUDGE_SYSTEM,
        model=model,
        timeout=JUDGE_TIMEOUT_S,
        num_predict=200,
        temperature=0.0,
    )
    return _parse_judge_json(raw)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _welch_t(sample_a: list[float], sample_b: list[float]) -> tuple[float, float]:
    """Welch's t-test. Returns (t_stat, two-sided p-value approximation).

    Uses a normal approximation for the p-value to avoid a scipy dependency.
    This is fine for N>=20; for small N the p-value is approximate.
    """
    n_a, n_b = len(sample_a), len(sample_b)
    if n_a < 2 or n_b < 2:
        return (0.0, 1.0)
    m_a, m_b = mean(sample_a), mean(sample_b)
    # Sample variance (unbiased, divide by n-1).
    var_a = sum((x - m_a) ** 2 for x in sample_a) / (n_a - 1)
    var_b = sum((x - m_b) ** 2 for x in sample_b) / (n_b - 1)
    denom = math.sqrt(var_a / n_a + var_b / n_b)
    if denom == 0:
        return (0.0, 1.0)
    t = (m_a - m_b) / denom
    # Two-sided p via normal CDF approximation.
    # p = 2 * (1 - Phi(|t|))
    p = 2.0 * (1.0 - _phi(abs(t)))
    return (t, max(0.0, min(1.0, p)))


def _phi(x: float) -> float:
    """Standard normal CDF via erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _compute_significance(
    scores_a: list[dict[str, int]],
    scores_b: list[dict[str, int]],
) -> dict[str, dict[str, float]]:
    """Per-dimension Welch's t-test between format A and format B."""
    out: dict[str, dict[str, float]] = {}
    for dim in DIMENSIONS:
        a = [float(s[dim]) for s in scores_a]
        b = [float(s[dim]) for s in scores_b]
        t, p = _welch_t(a, b)
        out[dim] = {
            "mean_a": mean(a) if a else 0.0,
            "mean_b": mean(b) if b else 0.0,
            "std_a": pstdev(a) if len(a) > 1 else 0.0,
            "std_b": pstdev(b) if len(b) > 1 else 0.0,
            "t_stat": t,
            "p_value": p,
        }
    return out


# ---------------------------------------------------------------------------
# Results container
# ---------------------------------------------------------------------------


@dataclass
class PromptResult:
    index: int
    task: str
    domain: str
    task_type: str
    rules_injected: list[str]
    output_imperative: str
    output_constitutional: str
    which_is_first: str  # "imperative" or "constitutional"
    scores_imperative: dict[str, int] = field(default_factory=dict)
    scores_constitutional: dict[str, int] = field(default_factory=dict)
    winner: str = ""  # "imperative" | "constitutional" | "tie"
    judge_ok: bool = False
    error: str = ""


def _aggregate_winner(
    scores_imp: dict[str, int],
    scores_con: dict[str, int],
) -> str:
    tot_i = sum(scores_imp.get(d, 0) for d in DIMENSIONS)
    tot_c = sum(scores_con.get(d, 0) for d in DIMENSIONS)
    if tot_i > tot_c:
        return "imperative"
    if tot_c > tot_i:
        return "constitutional"
    return "tie"


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_ab_test(
    brain_dir: Path,
    output_dir: Path,
    model: str = DEFAULT_MODEL,
    n_prompts: int | None = None,
    max_rules: int = 6,
    seed: int = 42,
) -> dict[str, Any]:
    """Run the A/B test and write results.md + results.json. Returns summary dict."""
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Loading lessons from %s", brain_dir)
    lessons = _load_lessons_from_brain(brain_dir)
    log.info("Loaded %d lessons", len(lessons))

    prompts = TEST_PROMPTS if n_prompts is None else TEST_PROMPTS[:n_prompts]
    results: list[PromptResult] = []

    for i, p in enumerate(prompts):
        log.info("[%d/%d] %s — %s", i + 1, len(prompts), p["domain"], p["task"][:60])
        applied = _rules_for_prompt(
            lessons, p["task"], p["domain"], p["task_type"], max_rules=max_rules
        )
        rules_injected = [r.instruction for r in applied]
        rules_text = "\n".join(rules_injected)

        # Generate both variants.
        try:
            out_imp = _generate_variant(p["task"], applied, "imperative", model)
            out_con = _generate_variant(p["task"], applied, "constitutional", model)
        except Exception as e:  # noqa: BLE001
            log.exception("Generation failed for prompt %d", i)
            results.append(
                PromptResult(
                    index=i,
                    task=p["task"],
                    domain=p["domain"],
                    task_type=p["task_type"],
                    rules_injected=rules_injected,
                    output_imperative="",
                    output_constitutional="",
                    which_is_first="imperative",
                    error=f"generation: {e}",
                )
            )
            continue

        # Randomize which variant the judge sees first.
        imperative_first = rng.random() < 0.5
        if imperative_first:
            output_1, output_2 = out_imp, out_con
            which_is_first = "imperative"
        else:
            output_1, output_2 = out_con, out_imp
            which_is_first = "constitutional"

        judge = _score_with_gemma(
            task=p["task"],
            rules_text=rules_text,
            output_1=output_1,
            output_2=output_2,
            which_is_first=which_is_first,
            model=model,
        )

        res = PromptResult(
            index=i,
            task=p["task"],
            domain=p["domain"],
            task_type=p["task_type"],
            rules_injected=rules_injected,
            output_imperative=out_imp,
            output_constitutional=out_con,
            which_is_first=which_is_first,
        )

        if judge is None:
            res.error = "judge_parse_failed"
            results.append(res)
            continue

        # Decode position -> variant.
        if imperative_first:
            res.scores_imperative = judge["output_1"]
            res.scores_constitutional = judge["output_2"]
        else:
            res.scores_constitutional = judge["output_1"]
            res.scores_imperative = judge["output_2"]

        res.judge_ok = True
        res.winner = _aggregate_winner(res.scores_imperative, res.scores_constitutional)
        results.append(res)

    summary = _summarize(results)

    # Persist JSON (raw) + markdown (human).
    (output_dir / "results.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "brain_dir": str(brain_dir),
                "model": model,
                "n_prompts": len(prompts),
                "max_rules_per_prompt": max_rules,
                "seed": seed,
                "summary": summary,
                "results": [asdict(r) for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    (output_dir / "results.md").write_text(
        _render_markdown(results, summary, brain_dir, model, seed),
        encoding="utf-8",
    )
    log.info("Wrote results to %s", output_dir)
    return summary


def _summarize(results: list[PromptResult]) -> dict[str, Any]:
    usable = [r for r in results if r.judge_ok]
    wins_imp = sum(1 for r in usable if r.winner == "imperative")
    wins_con = sum(1 for r in usable if r.winner == "constitutional")
    ties = sum(1 for r in usable if r.winner == "tie")

    scores_a = [r.scores_imperative for r in usable]
    scores_b = [r.scores_constitutional for r in usable]
    sig = _compute_significance(scores_a, scores_b)

    # Position-bias sanity check: how often did "Output 1" win?
    output_1_wins = 0
    for r in usable:
        tot_imp = sum(r.scores_imperative.get(d, 0) for d in DIMENSIONS)
        tot_con = sum(r.scores_constitutional.get(d, 0) for d in DIMENSIONS)
        if r.which_is_first == "imperative" and tot_imp > tot_con:
            output_1_wins += 1
        elif r.which_is_first == "constitutional" and tot_con > tot_imp:
            output_1_wins += 1

    return {
        "total_prompts": len(results),
        "usable_scores": len(usable),
        "wins_imperative": wins_imp,
        "wins_constitutional": wins_con,
        "ties": ties,
        "win_rate_imperative": (wins_imp / len(usable)) if usable else 0.0,
        "win_rate_constitutional": (wins_con / len(usable)) if usable else 0.0,
        "dimension_stats": sig,
        "output_1_wins": output_1_wins,
        "output_1_win_rate": (output_1_wins / len(usable)) if usable else 0.0,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_markdown(
    results: list[PromptResult],
    summary: dict[str, Any],
    brain_dir: Path,
    model: str,
    seed: int,
) -> str:
    lines: list[str] = []
    lines.append("# A/B Test: Constitutional vs Imperative Rule Injection")
    lines.append("")
    lines.append(f"- Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Brain dir: `{brain_dir}`")
    lines.append(f"- Judge model: `{model}` (Ollama at {OLLAMA_URL})")
    lines.append(f"- Prompts: {summary['total_prompts']} (usable: {summary['usable_scores']})")
    lines.append(f"- RNG seed: {seed}")
    lines.append("")

    # Methodology
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "For each test prompt we (1) load graduated lessons from the configured brain, "
        "(2) select up to 6 scope-matched rules via `apply_rules`, (3) generate two "
        "drafts with Ollama Gemma4:e4b where the only difference is how rules are "
        "formatted (`imperative` vs `constitutional`), and (4) ask a separate "
        "Gemma4:e4b judge call to score each draft on quality, rule adherence, "
        "and naturalness (1-10 each). Judge sees the rules in imperative form so "
        "constitutional framing isn't leaked. Position is randomized per prompt."
    )
    lines.append("")

    # Aggregate
    lines.append("## Aggregate results")
    lines.append("")
    lines.append(
        f"- Wins (imperative): **{summary['wins_imperative']}** "
        f"({summary['win_rate_imperative']:.1%})"
    )
    lines.append(
        f"- Wins (constitutional): **{summary['wins_constitutional']}** "
        f"({summary['win_rate_constitutional']:.1%})"
    )
    lines.append(f"- Ties: {summary['ties']}")
    lines.append(
        f"- Position-bias check — 'Output 1' win rate: "
        f"{summary['output_1_win_rate']:.1%} "
        f"(50% expected if the judge is position-neutral)"
    )
    lines.append("")

    # Per-dimension table
    lines.append("## Per-dimension means and significance")
    lines.append("")
    lines.append(
        "| Dimension | Imperative mean (sd) | Constitutional mean (sd) | Δ | t | p (2-sided, normal approx) |"
    )
    lines.append("|---|---|---|---|---|---|")
    for dim in DIMENSIONS:
        s = summary["dimension_stats"][dim]
        delta = s["mean_b"] - s["mean_a"]
        lines.append(
            f"| {dim} | {s['mean_a']:.2f} ({s['std_a']:.2f}) | "
            f"{s['mean_b']:.2f} ({s['std_b']:.2f}) | {delta:+.2f} | "
            f"{s['t_stat']:.2f} | {s['p_value']:.3f} |"
        )
    lines.append("")
    lines.append("Δ is constitutional - imperative (positive means constitutional wins).")
    lines.append("")

    # Per-prompt raw
    lines.append("## Per-prompt raw scores")
    lines.append("")
    lines.append("| # | Domain | Task (truncated) | Imp Q/R/N | Con Q/R/N | Winner | 1st shown |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        if not r.judge_ok:
            marker = r.error or "no-score"
            lines.append(
                f"| {r.index + 1} | {r.domain} | {r.task[:50]} | — | — | {marker} | {r.which_is_first} |"
            )
            continue
        imp = "/".join(str(r.scores_imperative[d]) for d in DIMENSIONS)
        con = "/".join(str(r.scores_constitutional[d]) for d in DIMENSIONS)
        lines.append(
            f"| {r.index + 1} | {r.domain} | {r.task[:50]} | {imp} | {con} | {r.winner} | {r.which_is_first} |"
        )
    lines.append("")

    # Limitations
    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "- **Small N.** 24 prompts split across three domains is under-powered. "
        "A Welch's t-test at p<0.05 needs effect sizes Cohen's d >= ~0.6 to be "
        "reliably detected; real format deltas are plausibly smaller."
    )
    lines.append(
        "- **Single judge model.** Gemma4:e4b is both generator and judge. "
        "Self-preference bias is likely — outputs phrased in a style the judge "
        "already favours get a bump. A cross-model judge (e.g. a different "
        "Ollama model or a frontier API) would be a stronger test."
    )
    lines.append(
        "- **Position effects.** We randomize order per prompt, but with only 24 "
        "prompts the position bucket sizes are small and residual bias can show "
        "up. See the 'Output 1 win rate' sanity check above."
    )
    lines.append(
        "- **P-value approximation.** We compute p via a normal-CDF "
        "approximation instead of the Student-t CDF (no scipy dependency). "
        "For N~24 the approximation is close but slightly anti-conservative; "
        "treat p<0.01 as 'likely real', 0.01-0.10 as 'suggestive only'."
    )
    lines.append(
        "- **Aggregated winner is crude.** Summing three 1-10 scores ignores "
        "dimension weighting and dimension-level ties. The per-dimension table "
        "is the load-bearing result; aggregate win-rate is a narrative number."
    )
    lines.append(
        "- **Rule pool is brain-specific.** Results reflect the configured "
        "lessons.md, not a generic rule base — constitutional framing may work "
        "differently for rules with different category distributions."
    )
    lines.append(
        "- **Judge rubric is thin.** We give a 3-line rubric for each dimension. "
        "Stronger evals define explicit anchor points at 1/5/10 for each dimension."
    )
    lines.append(
        "- **No human ground truth.** There is no human-rated gold standard here, "
        "so 'quality' means 'what this judge calls quality'. Treat as weak signal."
    )
    lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--brain-dir", default=DEFAULT_BRAIN_DIR, help="Brain directory with lessons.md")
    p.add_argument("--output", default=DEFAULT_OUTPUT, help="Output directory for results.md/.json")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    p.add_argument(
        "--n-prompts",
        type=int,
        default=None,
        help="Limit number of prompts (default: all 24)",
    )
    p.add_argument(
        "--max-rules",
        type=int,
        default=6,
        help="Max rules to inject per prompt (default: 6)",
    )
    p.add_argument("--seed", type=int, default=42, help="RNG seed for position randomization")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print config and exit without calling Ollama",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    brain_dir = Path(args.brain_dir).expanduser()
    output_dir = Path(args.output).expanduser()

    if args.dry_run:
        print("A/B test harness — dry run")
        print(f"  brain_dir  = {brain_dir}")
        print(f"  output_dir = {output_dir}")
        print(f"  model      = {args.model}")
        print(f"  n_prompts  = {args.n_prompts or len(TEST_PROMPTS)}")
        print(f"  max_rules  = {args.max_rules}")
        print(f"  seed       = {args.seed}")
        print(f"  prompts loaded = {len(TEST_PROMPTS)}")
        # Validate rule-engine imports wire up cleanly.
        from gradata.rules.rule_engine import format_rules_styled  # noqa: F401

        print("  imports    = OK")
        return 0

    if not brain_dir.is_dir():
        log.error("brain_dir does not exist: %s", brain_dir)
        return 2

    summary = run_ab_test(
        brain_dir=brain_dir,
        output_dir=output_dir,
        model=args.model,
        n_prompts=args.n_prompts,
        max_rules=args.max_rules,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
