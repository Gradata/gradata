"""Pipeline rewriter — read-only proposer for graduation-threshold adjustments.

Meta-Harness B (companion to Meta-Harness A per-rule RULE_FAILURE attribution
in ``inject_brain_rules.py``).

Reads three signals from the live brain:
  - current lesson population (state distribution, fire_count, confidence)
  - ``RULE_FAILURE`` events (both self-healing-emitted and hook-emitted variants)
  - ``CORRECTION`` events (raw user corrections by session)

and produces **proposals** — it does not mutate thresholds. Proposals are
written as a markdown ADR so a human can review, edit, and apply the deltas
by hand to the constants in ``self_improvement/_confidence.py``.

The four thresholds this module reasons about:
  - ``PATTERN_THRESHOLD`` (0.60)   — confidence to promote INSTINCT → PATTERN
  - ``RULE_THRESHOLD`` (0.90)      — confidence to promote PATTERN → RULE
  - ``MIN_APPLICATIONS_FOR_PATTERN`` (3) — fire_count to promote to PATTERN
  - ``MIN_APPLICATIONS_FOR_RULE`` (5)    — fire_count to promote to RULE
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class ThresholdProposal:
    """One suggested delta against a named threshold constant."""

    constant: str
    current: float
    proposed: float
    evidence_count: int
    rationale: str

    @property
    def delta(self) -> float:
        return round(self.proposed - self.current, 3)


@dataclass
class PipelineDiagnostic:
    """Full diagnostic snapshot. Humans read the ADR; tests read this."""

    population: dict[str, int] = field(default_factory=dict)
    stuck_at_instinct: int = 0
    stuck_at_pattern: int = 0
    over_promoted_rules: list[dict] = field(default_factory=list)
    recent_graduations: int = 0
    recent_demotions: int = 0
    rule_failure_count: int = 0
    correction_count: int = 0
    proposals: list[ThresholdProposal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _count_by_state(lessons: Iterable) -> dict[str, int]:
    counts: dict[str, int] = {}
    for lesson in lessons:
        name = getattr(getattr(lesson, "state", None), "name", None) or "UNKNOWN"
        counts[name] = counts.get(name, 0) + 1
    return counts


def _failures_by_description(rule_failure_events: list[dict]) -> dict[str, int]:
    """Group RULE_FAILURE events by the rule description they attribute to.

    Two payload shapes exist in the wild:
      - self_healing emits ``failed_rule_description``
      - capture_learning (hook, Meta-Harness A) emits ``description``
    """
    by_desc: dict[str, int] = {}
    for event in rule_failure_events:
        data = event.get("data", {}) or {}
        raw = data.get("failed_rule_description") or data.get("description") or ""
        # Guard against non-string descriptions (e.g. legacy dict payloads).
        desc = raw.strip() if isinstance(raw, str) else str(raw).strip()
        if not desc:
            continue
        by_desc[desc] = by_desc.get(desc, 0) + 1
    return by_desc


def analyze_pipeline(
    lessons: list,
    rule_failure_events: list[dict],
    correction_events: list[dict],
    *,
    pattern_threshold: float = 0.60,
    rule_threshold: float = 0.90,
    min_apps_pattern: int = 3,
    min_apps_rule: int = 5,
    over_promoted_failure_rate: float = 0.30,
) -> PipelineDiagnostic:
    """Compute diagnostics + proposals from the current brain state.

    Pure function — no I/O. All side-effecting orchestration lives in
    :func:`run_pipeline_rewriter` which calls this.
    """
    diag = PipelineDiagnostic()
    diag.population = _count_by_state(lessons)
    diag.rule_failure_count = len(rule_failure_events)
    diag.correction_count = len(correction_events)

    failures_by_desc = _failures_by_description(rule_failure_events)

    for lesson in lessons:
        state_name = getattr(getattr(lesson, "state", None), "name", None) or ""
        conf = float(getattr(lesson, "confidence", 0.0) or 0.0)
        fires = int(getattr(lesson, "fire_count", 0) or 0)
        desc = (getattr(lesson, "description", "") or "").strip()

        if state_name == "INSTINCT" and fires >= min_apps_pattern and conf < pattern_threshold:
            diag.stuck_at_instinct += 1
        if state_name == "PATTERN" and fires >= min_apps_rule and conf < rule_threshold:
            diag.stuck_at_pattern += 1

        if state_name == "RULE":
            failures = failures_by_desc.get(desc, 0)
            if fires > 0:
                rate = failures / max(fires, 1)
                if rate >= over_promoted_failure_rate:
                    diag.over_promoted_rules.append(
                        {
                            "category": getattr(lesson, "category", ""),
                            "description": desc[:80],
                            "fire_count": fires,
                            "failure_count": failures,
                            "failure_rate": round(rate, 3),
                        }
                    )

    # ── Proposal generation ────────────────────────────────────────────────
    # Each proposal is conservative: at most one step in one direction, with
    # explicit evidence count. Never stacks multiple deltas on one constant.

    rule_pop = diag.population.get("RULE", 0)
    pattern_pop = diag.population.get("PATTERN", 0)
    instinct_pop = diag.population.get("INSTINCT", 0)
    total = rule_pop + pattern_pop + instinct_pop

    if diag.stuck_at_instinct >= 5 and diag.stuck_at_instinct >= (instinct_pop * 0.2):
        # Many INSTINCTs have enough fires but confidence isn't reaching 0.60.
        # Either confidence scoring is broken OR the bar is too high. Propose
        # a modest drop to 0.55 so the population can flow; human re-examines.
        diag.proposals.append(
            ThresholdProposal(
                constant="PATTERN_THRESHOLD",
                current=pattern_threshold,
                proposed=round(max(0.50, pattern_threshold - 0.05), 2),
                evidence_count=diag.stuck_at_instinct,
                rationale=(
                    f"{diag.stuck_at_instinct} INSTINCT lessons have "
                    f"fire_count>={min_apps_pattern} but confidence<{pattern_threshold}. "
                    "Promotions are bottlenecked on the confidence bar, not fire_count."
                ),
            )
        )

    if diag.over_promoted_rules:
        # Rules are graduating then failing frequently. Raise the hardest
        # gate: fire_count floor for RULE promotion.
        diag.proposals.append(
            ThresholdProposal(
                constant="MIN_APPLICATIONS_FOR_RULE",
                current=float(min_apps_rule),
                proposed=float(min_apps_rule + 1),
                evidence_count=len(diag.over_promoted_rules),
                rationale=(
                    f"{len(diag.over_promoted_rules)} graduated RULEs have "
                    f"failure_rate>={over_promoted_failure_rate:.0%}. "
                    "Raise fire_count floor to demand more evidence before promotion."
                ),
            )
        )

    if total >= 20 and rule_pop == 0:
        # No RULEs at all across a non-trivial population — either
        # MIN_APPLICATIONS_FOR_RULE or RULE_THRESHOLD is starving promotion.
        diag.proposals.append(
            ThresholdProposal(
                constant="MIN_APPLICATIONS_FOR_RULE",
                current=float(min_apps_rule),
                proposed=float(max(3, min_apps_rule - 1)),
                evidence_count=total,
                rationale=(
                    f"Zero RULEs in a population of {total}. Fire-count floor may "
                    "be starving promotion; try one step lower."
                ),
            )
        )

    if not diag.proposals:
        diag.notes.append("No threshold adjustments recommended — pipeline looks healthy.")

    return diag


def write_adr(diag: PipelineDiagnostic, output_dir: Path) -> Path:
    """Write a markdown ADR capturing the diagnostic + proposals.

    Filename: ``adr-pipeline-rewriter-<YYYYMMDD-HHMMSS>.md``.
    Returns the absolute path written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"adr-pipeline-rewriter-{ts}.md"

    lines: list[str] = []
    lines.append(f"# ADR — Pipeline threshold proposals ({ts})")
    lines.append("")
    lines.append(
        "_Auto-generated read-only proposals from `pipeline_rewriter.py`. "
        "Review, edit, and apply by hand to `self_improvement/_confidence.py`._"
    )
    lines.append("")
    lines.append("## Diagnostic snapshot")
    lines.append("")
    lines.append(f"- Population: `{json.dumps(diag.population, sort_keys=True)}`")
    lines.append(f"- RULE_FAILURE events examined: **{diag.rule_failure_count}**")
    lines.append(f"- CORRECTION events examined: **{diag.correction_count}**")
    lines.append(f"- Stuck at INSTINCT (fires ok, confidence low): **{diag.stuck_at_instinct}**")
    lines.append(f"- Stuck at PATTERN (fires ok, confidence low): **{diag.stuck_at_pattern}**")
    lines.append(f"- Over-promoted RULEs (failure_rate ≥ 30%): **{len(diag.over_promoted_rules)}**")
    if diag.over_promoted_rules:
        lines.append("")
        lines.append("### Over-promoted RULEs")
        lines.append("")
        for row in diag.over_promoted_rules[:10]:
            lines.append(
                f"- `{row['category']}`: {row['description']} — "
                f"fires={row['fire_count']}, failures={row['failure_count']}, "
                f"rate={row['failure_rate']}"
            )

    lines.append("")
    lines.append("## Proposals")
    lines.append("")
    if not diag.proposals:
        lines.append("_None — pipeline appears healthy at current thresholds._")
    else:
        for p in diag.proposals:
            lines.append(f"### `{p.constant}`: {p.current} → {p.proposed} (Δ {p.delta:+})")
            lines.append("")
            lines.append(f"- Evidence count: **{p.evidence_count}**")
            lines.append(f"- Rationale: {p.rationale}")
            lines.append("")

    if diag.notes:
        lines.append("## Notes")
        lines.append("")
        for note in diag.notes:
            lines.append(f"- {note}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_pipeline_rewriter(brain, output_dir: Path, *, limit: int = 500) -> Path:
    """Orchestrator: pull signals from a Brain, analyze, write ADR.

    Args:
        brain: A ``gradata.brain.Brain`` with ``query_events`` and a loaded
            lesson list available via ``brain.all_lessons`` or equivalent.
        output_dir: Where to write the ADR (e.g. ``docs/architecture/``).
        limit: Max events of each type to pull. Default 500 keeps analysis
            bounded on large brains.

    Returns:
        Path to the written ADR.
    """
    # Lesson population
    lessons: list = []
    for attr in ("all_lessons", "lessons"):
        maybe = getattr(brain, attr, None)
        if maybe is None:
            continue
        try:
            value = maybe() if callable(maybe) else maybe
            lessons = list(value)  # type: ignore[arg-type]
            break
        except Exception:
            continue

    # Events
    try:
        rule_failures = brain.query_events(event_type="RULE_FAILURE", limit=limit)
    except Exception:
        rule_failures = []
    try:
        corrections = brain.query_events(event_type="CORRECTION", limit=limit)
    except Exception:
        corrections = []

    diag = analyze_pipeline(lessons, rule_failures, corrections)
    return write_adr(diag, output_dir)
