"""Pilot ablation harness: GRADATA_BETA_LB_GATE on vs off.

Measures the effect of the Beta lower-bound promotion gate (PR #86,
``self_improvement._passes_beta_lb_gate``) on two axes:

1. **Graduation-rate delta** — how many PATTERN -> RULE transitions
   the gate blocks on a seeded synthetic brain where some lessons have
   inflated ``lesson.confidence`` but weak Beta posteriors (high α/β
   skew).
2. **Preference lift** — Sonnet outputs on a small task set, scored by
   Haiku as judge, with the pre-gate rule set vs the post-gate rule set
   injected.

This is a **pilot** (~5 tasks, 2 iterations, ~20 synthetic lessons) — NOT
the full v4 replication. Oliver runs it manually when he wants a signal,
then decides whether to default the gate on or to scale up.

Design mirrors:
- ``brain/scripts/ab_test_constitutional.py`` — A/B scaffolding + judge loop
- ``brain/scripts/brain_benchmark.py`` — per-task replay + scoring

Safety gate
-----------
The script makes paid Anthropic API calls. To avoid accidental spend,
runs without ``GRADATA_ABLATION_CONFIRM=1`` do a **dry-run only**:
print trial count, token estimate, dollar estimate, then exit 0. Set
``GRADATA_ABLATION_CONFIRM=1`` in env to actually execute the pilot.

Usage
-----
    # Dry run (safe, no API calls):
    python brain/scripts/ablation_beta_lb_gate.py --tasks 5 --iterations 2

    # Actually run (paid API calls):
    GRADATA_ABLATION_CONFIRM=1 python brain/scripts/ablation_beta_lb_gate.py \
        --tasks 10 --iterations 2

    # Against a real brain fixture instead of the synthetic seed:
    GRADATA_ABLATION_CONFIRM=1 python brain/scripts/ablation_beta_lb_gate.py \
        --brain-fixture C:/Users/olive/SpritesWork/brain --tasks 5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import ensure_sdk_on_path

ensure_sdk_on_path()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ablation_beta_lb_gate")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_JUDGE_MODEL = "claude-haiku-4-5"

# Rough token accounting for dry-run cost estimate (per trial).
# Each trial = 1 generation call (Sonnet) + 1 shared judge call (Haiku, amortised across A/B).
EST_INPUT_TOKENS_PER_GEN = 800     # rules + task prompt
EST_OUTPUT_TOKENS_PER_GEN = 400    # draft
EST_INPUT_TOKENS_PER_JUDGE = 1500  # task + both outputs + rubric
EST_OUTPUT_TOKENS_PER_JUDGE = 150  # short JSON verdict

# April 2026 published list pricing ($/M tokens).
SONNET_INPUT_PER_M = 3.00
SONNET_OUTPUT_PER_M = 15.00
HAIKU_INPUT_PER_M = 1.00
HAIKU_OUTPUT_PER_M = 5.00

# Decision criteria (from .tmp/autoresearch-synthesis.md §5 / §6).
DEFAULT_PREF_LIFT_THRESHOLD = 0.01       # gate ON if pref-lift >= +1.0%
DEFAULT_GRAD_DROP_THRESHOLD = 0.50       # ... AND graduation-rate drop <= 50%

TASKS: list[dict[str, str]] = [
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
        "task": "Review a Python function that validates email addresses and flag issues.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Draft a support reply to a customer reporting intermittent 500 errors on checkout.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Write an apology to a customer whose data export was delayed by 48 hours.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Critique a REST endpoint that returns HTTP 200 with an error payload on failure.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Write a break-up email to a prospect who has gone dark for 6 weeks.",
        "domain": "sales",
        "task_type": "email_draft",
    },
    {
        "task": "Draft a reply explaining that the feature they requested is on the roadmap for Q3.",
        "domain": "support",
        "task_type": "support_reply",
    },
    {
        "task": "Review test coverage for a new auth middleware and identify missing cases.",
        "domain": "engineering",
        "task_type": "code_review",
    },
    {
        "task": "Respond to a customer who reports a billing charge they don't recognize.",
        "domain": "support",
        "task_type": "support_reply",
    },
]


# ---------------------------------------------------------------------------
# Synthetic test brain — deterministic, reproducible seed
# ---------------------------------------------------------------------------


def build_synthetic_brain(seed: int = 42):
    """Build ~20 PATTERN-tier lessons with varied (α, β) so the gate discriminates.

    Design: confidence is set above RULE_THRESHOLD (0.90) for every lesson so
    the mean-threshold path WOULD promote them all. The Beta posterior is
    what varies:

    - "strong" lessons: α>>β, high fire_count — Beta.ppf(0.05, α, β) >= 0.70
    - "weak" lessons:   low α+β OR skewed toward β — ppf below threshold
    - "borderline": α/β near 0.70 threshold

    Gate-off graduates all 20. Gate-on should graduate roughly the strong
    subset (~10). The exact split depends on scipy availability; both
    branches of ``_beta_ppf_05`` are exercised.
    """
    from gradata._types import Lesson, LessonState
    from gradata.enhancements.self_improvement import MIN_APPLICATIONS_FOR_RULE

    rng = random.Random(seed)

    specs: list[tuple[str, float, float, int, str, str, str]] = [
        # (label, alpha, beta_param, fire_count, category, domain, task_type)
        # STRONG (should pass gate): α>>β, many fires
        ("strong_1", 18.0, 2.0, 20, "DRAFTING", "sales", "email_draft"),
        ("strong_2", 25.0, 3.0, 28, "ACCURACY", "engineering", "code_review"),
        ("strong_3", 15.0, 1.0, 16, "PROCESS", "support", "support_reply"),
        ("strong_4", 22.0, 2.0, 24, "STYLE", "sales", "email_draft"),
        ("strong_5", 12.0, 1.0, 13, "DRAFTING", "support", "support_reply"),
        ("strong_6", 30.0, 4.0, 34, "ACCURACY", "engineering", "code_review"),
        ("strong_7", 18.0, 2.0, 20, "PROCESS", "sales", "email_draft"),
        ("strong_8", 20.0, 3.0, 23, "STYLE", "engineering", "code_review"),
        ("strong_9", 14.0, 1.0, 15, "DRAFTING", "support", "support_reply"),
        ("strong_10", 16.0, 2.0, 18, "ACCURACY", "sales", "email_draft"),
        # WEAK (should be blocked by gate): few observations, some skew
        ("weak_1", 3.0, 1.0, 4, "DRAFTING", "sales", "email_draft"),       # fire_count < 5
        ("weak_2", 4.0, 2.0, 6, "PROCESS", "engineering", "code_review"),  # low total, ppf low
        ("weak_3", 5.0, 3.0, 8, "STYLE", "support", "support_reply"),      # ppf ~0.3
        ("weak_4", 6.0, 4.0, 10, "DRAFTING", "sales", "email_draft"),      # borderline low
        ("weak_5", 7.0, 5.0, 12, "ACCURACY", "engineering", "code_review"),# borderline low
        # BORDERLINE (some pass, some don't — exercises gate decisions)
        ("borderline_1", 10.0, 2.0, 12, "PROCESS", "support", "support_reply"),
        ("borderline_2", 8.0, 2.0, 10, "STYLE", "sales", "email_draft"),
        ("borderline_3", 11.0, 3.0, 14, "DRAFTING", "engineering", "code_review"),
        ("borderline_4", 9.0, 3.0, 12, "ACCURACY", "support", "support_reply"),
        ("borderline_5", 13.0, 4.0, 17, "PROCESS", "sales", "email_draft"),
    ]

    descriptions = [
        "Use active voice in the opening line",
        "Flag any function that mutates its input argument",
        "Acknowledge the customer's frustration before proposing a fix",
        "Lead with the prospect's stated goal, not our product",
        "Confirm receipt within 2 sentences before asking clarifying questions",
        "Check for SQL injection on every user-supplied filter value",
        "Restate the agreed next step in every email",
        "Prefer early returns over nested conditionals",
        "Offer two concrete next steps, never more than three",
        "Require explicit type hints on public functions",
        "Cite the exact error code the customer reported",
        "Suggest one alternative if the direct request isn't possible",
        "Use colons, not em dashes, in email prose",
        "Link the Calendly URL as HTML, never raw",
        "Verify the Stripe webhook signature before trusting the payload",
        "Acknowledge the wait time explicitly if over 24 hours",
        "Reference the prospect's LinkedIn activity when intro-ing",
        "Flag any PR that adds a dependency for under 20 lines of use",
        "Offer a same-week slot if the customer is churn-risk",
        "Restate the agenda in three bullets in confirmation emails",
    ]
    rng.shuffle(descriptions)

    lessons: list[Lesson] = []
    for i, (label, alpha, beta_p, fires, cat, domain, ttype) in enumerate(specs):
        scope_json = json.dumps({"domain": domain, "task_type": ttype})
        lesson = Lesson(
            date="2026-04-01",
            state=LessonState.PATTERN,
            # Confidence above RULE_THRESHOLD so mean-path promotes; gate is the discriminator.
            confidence=0.92,
            category=cat,
            description=descriptions[i % len(descriptions)],
            fire_count=max(fires, MIN_APPLICATIONS_FOR_RULE),
            sessions_since_fire=0,
            alpha=alpha,
            beta_param=beta_p,
            scope_json=scope_json,
        )
        # Tag so tests can inspect which specs promoted.
        lesson._ablation_label = label  # type: ignore[attr-defined]
        lessons.append(lesson)

    return lessons


def load_brain_fixture(path: Path):
    """Parse lessons.md from a real brain directory."""
    from gradata.enhancements.self_improvement import parse_lessons

    lessons_path = path / "lessons.md"
    if not lessons_path.is_file():
        raise FileNotFoundError(f"lessons.md not found at {lessons_path}")
    return parse_lessons(lessons_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Graduation simulation — deep-copies lessons so A/B don't contaminate each other
# ---------------------------------------------------------------------------


def simulate_graduation(lessons: list, gate_on: bool) -> dict[str, Any]:
    """Run ``graduate()`` on a deep copy of lessons under the given gate flag.

    Returns a dict with per-lesson promoted/blocked decisions and aggregate counts.
    """
    import copy

    from gradata._types import LessonState
    from gradata.enhancements.self_improvement import graduate

    pool = copy.deepcopy(lessons)

    prev_env = os.environ.get("GRADATA_BETA_LB_GATE")
    os.environ["GRADATA_BETA_LB_GATE"] = "1" if gate_on else "0"
    try:
        _active, _graduated = graduate(pool, maturity="INFANT")
    finally:
        if prev_env is None:
            os.environ.pop("GRADATA_BETA_LB_GATE", None)
        else:
            os.environ["GRADATA_BETA_LB_GATE"] = prev_env

    per_lesson: list[dict[str, Any]] = []
    promoted_count = 0
    for lesson in pool:
        label = getattr(lesson, "_ablation_label", lesson.description[:40])
        promoted = lesson.state == LessonState.RULE
        if promoted:
            promoted_count += 1
        per_lesson.append(
            {
                "label": label,
                "alpha": lesson.alpha,
                "beta_param": lesson.beta_param,
                "fire_count": lesson.fire_count,
                "final_state": lesson.state.name,
                "promoted_to_rule": promoted,
            }
        )

    # Derive the post-graduation rule set for downstream injection.
    rule_lessons = [l for l in pool if l.state == LessonState.RULE]

    return {
        "gate_on": gate_on,
        "pattern_to_rule_count": promoted_count,
        "total_patterns_considered": len(lessons),
        "per_lesson": per_lesson,
        "rule_lessons": rule_lessons,
    }


# ---------------------------------------------------------------------------
# Anthropic client wrapper (seam for mocking in tests)
# ---------------------------------------------------------------------------


def _make_anthropic_client():
    """Return an Anthropic client. Kept as a tiny function so tests can monkey-patch it."""
    import anthropic  # noqa: F401 — imported for side-effect of failing early if missing

    return anthropic.Anthropic()


def _call_claude(client, *, model: str, system: str, prompt: str, max_tokens: int) -> str:
    """Call messages.create and return the concatenated text. Isolated for mocking."""
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    parts: list[str] = []
    for block in getattr(msg, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


# ---------------------------------------------------------------------------
# Generation + judging
# ---------------------------------------------------------------------------


_GEN_SYSTEM = (
    "You are an assistant generating a single on-task draft. "
    "Follow the injected rules. Produce ONLY the requested draft — no preamble."
)

_JUDGE_SYSTEM = (
    "You are a strict, impartial evaluator. Return ONLY a JSON object with "
    "integer keys output_a and output_b, each scored 1 to 10 on overall quality. "
    "No prose, no markdown."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _format_rules(rule_lessons: list, max_rules: int = 6) -> str:
    """Format rule lessons as a terse injection block."""
    selected = rule_lessons[:max_rules]
    if not selected:
        return ""
    lines = ["<rules>"]
    for lesson in selected:
        lines.append(f"- {lesson.description}")
    lines.append("</rules>")
    return "\n".join(lines)


def _generate(client, model: str, task: str, rules_text: str) -> str:
    prompt = f"{rules_text}\n\nTASK: {task}\n\nDraft:" if rules_text else f"TASK: {task}\n\nDraft:"
    return _call_claude(client, model=model, system=_GEN_SYSTEM, prompt=prompt, max_tokens=500)


def _judge(
    client,
    judge_model: str,
    task: str,
    output_a: str,
    output_b: str,
    a_label: str,
) -> dict[str, int] | None:
    prompt = (
        f"TASK: {task}\n\n"
        f"----- OUTPUT A -----\n{output_a}\n----- END -----\n\n"
        f"----- OUTPUT B -----\n{output_b}\n----- END -----\n\n"
        "Rate each output 1-10 on overall quality (on-task, useful, correct).\n"
        'Respond with exactly: {"output_a": int, "output_b": int}\n'
        f"(a_label={a_label}, for bookkeeping)"
    )
    raw = _call_claude(
        client, model=judge_model, system=_JUDGE_SYSTEM, prompt=prompt, max_tokens=200
    )
    m = _JSON_RE.search(raw or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    out: dict[str, int] = {}
    for k in ("output_a", "output_b"):
        v = obj.get(k)
        if not isinstance(v, (int, float)):
            return None
        out[k] = max(1, min(10, int(round(v))))
    return out


# ---------------------------------------------------------------------------
# Cost estimation (dry run)
# ---------------------------------------------------------------------------


def estimate_cost(n_tasks: int, n_iterations: int) -> dict[str, Any]:
    """Compute rough trial count + dollar cost for the pilot.

    Per task×iteration:
      - 2 generations (one per condition) on Sonnet
      - 1 judge call on Haiku (judges A vs B together)
    """
    trials = n_tasks * n_iterations
    n_gens = trials * 2
    n_judges = trials

    gen_in = n_gens * EST_INPUT_TOKENS_PER_GEN
    gen_out = n_gens * EST_OUTPUT_TOKENS_PER_GEN
    judge_in = n_judges * EST_INPUT_TOKENS_PER_JUDGE
    judge_out = n_judges * EST_OUTPUT_TOKENS_PER_JUDGE

    gen_cost = (gen_in / 1_000_000) * SONNET_INPUT_PER_M + (gen_out / 1_000_000) * SONNET_OUTPUT_PER_M
    judge_cost = (judge_in / 1_000_000) * HAIKU_INPUT_PER_M + (judge_out / 1_000_000) * HAIKU_OUTPUT_PER_M

    return {
        "trials": trials,
        "generations": n_gens,
        "judges": n_judges,
        "total_input_tokens": gen_in + judge_in,
        "total_output_tokens": gen_out + judge_out,
        "estimated_cost_usd": round(gen_cost + judge_cost, 3),
    }


# ---------------------------------------------------------------------------
# Main pilot loop
# ---------------------------------------------------------------------------


@dataclass
class TaskResult:
    task_index: int
    task: str
    iteration: int
    output_a: str  # gate off (baseline)
    output_b: str  # gate on
    score_a: int | None = None
    score_b: int | None = None
    judge_ok: bool = False
    error: str = ""


def run_pilot(
    *,
    lessons: list,
    n_tasks: int,
    n_iterations: int,
    model: str,
    judge_model: str,
    client_factory=_make_anthropic_client,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute the pilot and return aggregate metrics."""
    # 1. Graduation simulation — one pass per condition on the same lesson pool.
    grad_off = simulate_graduation(lessons, gate_on=False)
    grad_on = simulate_graduation(lessons, gate_on=True)

    rules_off = grad_off["rule_lessons"]
    rules_on = grad_on["rule_lessons"]

    # 2. Generation + judging across task×iteration matrix.
    client = client_factory()
    rng = random.Random(seed)
    task_results: list[TaskResult] = []

    tasks = TASKS[:n_tasks]
    rules_off_text = _format_rules(rules_off)
    rules_on_text = _format_rules(rules_on)

    score_a_list: list[int] = []
    score_b_list: list[int] = []

    for it in range(n_iterations):
        for ti, task_spec in enumerate(tasks):
            task = task_spec["task"]
            log.info(
                "Iter %d/%d, task %d/%d: %s",
                it + 1,
                n_iterations,
                ti + 1,
                len(tasks),
                task[:60],
            )

            tr = TaskResult(task_index=ti, task=task, iteration=it, output_a="", output_b="")
            try:
                tr.output_a = _generate(client, model, task, rules_off_text)
                tr.output_b = _generate(client, model, task, rules_on_text)
            except Exception as e:  # noqa: BLE001
                tr.error = f"generation: {e}"
                task_results.append(tr)
                continue

            # Randomize A/B label order so the judge doesn't always see baseline first.
            if rng.random() < 0.5:
                judged = _judge(client, judge_model, task, tr.output_a, tr.output_b, a_label="off")
                if judged:
                    tr.score_a = judged["output_a"]
                    tr.score_b = judged["output_b"]
            else:
                judged = _judge(client, judge_model, task, tr.output_b, tr.output_a, a_label="on")
                if judged:
                    tr.score_b = judged["output_a"]
                    tr.score_a = judged["output_b"]

            if judged:
                tr.judge_ok = True
                if tr.score_a is not None:
                    score_a_list.append(tr.score_a)
                if tr.score_b is not None:
                    score_b_list.append(tr.score_b)
            else:
                tr.error = "judge_parse_failed"

            task_results.append(tr)

    mean_a = sum(score_a_list) / len(score_a_list) if score_a_list else 0.0
    mean_b = sum(score_b_list) / len(score_b_list) if score_b_list else 0.0
    pref_lift = (mean_b - mean_a) / mean_a if mean_a else 0.0

    grad_drop = (
        (grad_off["pattern_to_rule_count"] - grad_on["pattern_to_rule_count"])
        / grad_off["pattern_to_rule_count"]
        if grad_off["pattern_to_rule_count"] > 0
        else 0.0
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "judge_model": judge_model,
        "n_tasks": n_tasks,
        "n_iterations": n_iterations,
        "conditions": {
            "gate_off": {
                "graduations": grad_off["pattern_to_rule_count"],
                "mean_judge_score": round(mean_a, 3),
            },
            "gate_on": {
                "graduations": grad_on["pattern_to_rule_count"],
                "mean_judge_score": round(mean_b, 3),
            },
        },
        "metrics": {
            "graduation_drop_pct": round(grad_drop, 4),
            "preference_lift_pct": round(pref_lift, 4),
            "usable_judge_scores": len(score_a_list),
        },
        "per_task": [asdict(r) for r in task_results],
        "per_lesson_off": grad_off["per_lesson"],
        "per_lesson_on": grad_on["per_lesson"],
    }


def format_summary(result: dict[str, Any]) -> str:
    """Produce a human-readable summary of the pilot result."""
    c = result["conditions"]
    m = result["metrics"]
    lines = [
        "=" * 60,
        "Beta LB Gate Ablation — pilot result",
        "=" * 60,
        f"model:       {result['model']}",
        f"judge:       {result['judge_model']}",
        f"trials:      {result['n_tasks']} tasks x {result['n_iterations']} iters = "
        f"{result['n_tasks'] * result['n_iterations']}",
        "",
        "Graduation (PATTERN -> RULE):",
        f"  gate OFF: {c['gate_off']['graduations']}",
        f"  gate ON:  {c['gate_on']['graduations']}  "
        f"(drop: {m['graduation_drop_pct']:+.1%})",
        "",
        "Judge score (mean, 1-10):",
        f"  gate OFF: {c['gate_off']['mean_judge_score']:.2f}",
        f"  gate ON:  {c['gate_on']['mean_judge_score']:.2f}  "
        f"(pref-lift: {m['preference_lift_pct']:+.1%})",
        "",
        f"usable judge scores: {m['usable_judge_scores']}",
        "-" * 60,
        "Decision criteria (autoresearch synthesis §5/§6):",
        f"  pref-lift >= +{DEFAULT_PREF_LIFT_THRESHOLD:.1%}  "
        f"=> {'YES' if m['preference_lift_pct'] >= DEFAULT_PREF_LIFT_THRESHOLD else 'no'}",
        f"  grad-drop <= {DEFAULT_GRAD_DROP_THRESHOLD:.1%}       "
        f"=> {'YES' if m['graduation_drop_pct'] <= DEFAULT_GRAD_DROP_THRESHOLD else 'no'}",
        "=" * 60,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--tasks", type=int, default=5, help="Number of tasks (default: 5, max 10)")
    p.add_argument("--iterations", type=int, default=2, help="Iterations per task (default: 2)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Generation model")
    p.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL, help="Judge model")
    p.add_argument(
        "--brain-fixture",
        type=str,
        default=None,
        help="Path to a brain directory (lessons.md). If omitted, uses synthetic seed.",
    )
    p.add_argument("--seed", type=int, default=42, help="RNG seed for A/B position randomisation")
    p.add_argument(
        "--output-dir",
        default=".tmp",
        help="Directory to write ablation_beta_lb_<ts>.json (default: .tmp)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    n_tasks = max(1, min(args.tasks, len(TASKS)))
    n_iterations = max(1, args.iterations)

    confirmed = os.environ.get("GRADATA_ABLATION_CONFIRM", "").lower() in ("1", "true", "yes", "on")

    if not confirmed:
        est = estimate_cost(n_tasks, n_iterations)
        print("=" * 60)
        print("DRY RUN — no API calls made.")
        print("=" * 60)
        print(f"tasks            = {n_tasks}")
        print(f"iterations       = {n_iterations}")
        print(f"generation model = {args.model}")
        print(f"judge model      = {args.judge_model}")
        print(f"trials           = {est['trials']}")
        print(f"  generations    = {est['generations']} @ Sonnet")
        print(f"  judge calls    = {est['judges']} @ Haiku")
        print(f"input tokens     ~ {est['total_input_tokens']:,}")
        print(f"output tokens    ~ {est['total_output_tokens']:,}")
        print(f"estimated cost   ~ ${est['estimated_cost_usd']:.2f}")
        print("-" * 60)
        print("To execute the pilot, re-run with:")
        print("  GRADATA_ABLATION_CONFIRM=1 python brain/scripts/ablation_beta_lb_gate.py \\")
        print(f"    --tasks {n_tasks} --iterations {n_iterations}")
        print("=" * 60)
        return 0

    # Load lessons.
    if args.brain_fixture:
        fixture = Path(args.brain_fixture).expanduser()
        log.info("Loading lessons from %s", fixture)
        lessons = load_brain_fixture(fixture)
    else:
        log.info("Building synthetic test brain (seed=%d)", args.seed)
        lessons = build_synthetic_brain(seed=args.seed)

    result = run_pilot(
        lessons=lessons,
        n_tasks=n_tasks,
        n_iterations=n_iterations,
        model=args.model,
        judge_model=args.judge_model,
        seed=args.seed,
    )

    # Persist.
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"ablation_beta_lb_{ts}.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    log.info("Wrote %s", out_path)

    print(format_summary(result))
    print(f"\nFull results: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
