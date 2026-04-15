"""Aggregate blind-judge scores from a Gradata ablation run into proof_results.json.

Reads JSONL judgment files produced by `.tmp/rule-ablation-v2/experiment.py`
and emits the aggregated payload consumed by `GET /api/v1/public/proof`
(see `cloud/app/routes/proof.py` and `cloud/dashboard/.../ABProofPanel.tsx`).

Each judgment line is expected to have at least:
    {
      "model":      str,   # subject model id (e.g. "sonnet")
      "condition":  str,   # one of "base" | "rules" | "full"
      "dimension":  str,   # e.g. "correctness", "preference_adherence", "quality"
      "score":      float, # 0..1 normalized
      "task_id":    str,   # optional, used for trial counting
      "judge":      str,   # optional, judge model id
    }

Empty / missing run directory => `load_judgments` returns `{}` and the export
writes an honest empty-state payload (`available: false`) instead of crashing.
This is the contract `tests/test_proof.py::test_export_script_handles_empty_run_dir`
verifies.

Usage:
    python cloud/scripts/export_ab_proof.py \\
        --run-dir .tmp/rule-ablation-v2/judgments \\
        --out cloud/data/proof_results.json \\
        --source gradata-ablation-v2-2026-04-14
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger("export_ab_proof")

# Conditions we recognize from the ablation. Order matters for the UI: baseline
# first, then incremental layers.
CONDITIONS = ("base", "rules", "full")
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "proof_results.json"


def load_judgments(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Load all `*.jsonl` judgment files under ``run_dir``.

    Returns a mapping of ``filename -> [judgment, ...]``. Returns ``{}`` if the
    directory is missing, not a directory, empty, or contains no readable
    JSONL records. Never raises on malformed input — bad lines are skipped
    with a warning so a partial run still exports something usable.
    """
    if not run_dir or not Path(run_dir).is_dir():
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(Path(run_dir).glob("*.jsonl")):
        records: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as fh:
                for lineno, raw in enumerate(fh, 1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        rec = json.loads(raw)
                    except ValueError as exc:
                        _log.warning("%s:%d skipped (bad JSON): %s", path.name, lineno, exc)
                        continue
                    if isinstance(rec, dict):
                        records.append(rec)
        except OSError as exc:
            _log.warning("could not read %s: %s", path, exc)
            continue
        if records:
            out[path.name] = records
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _ci95(values: list[float]) -> tuple[float, float]:
    """Return (low, high) 95% CI for the mean using a normal approximation."""
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    m = _mean(values)
    if n < 2:
        return (m, m)
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    se = math.sqrt(var / n)
    return (max(0.0, m - 1.96 * se), min(1.0, m + 1.96 * se))


def aggregate(judgments: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Aggregate raw judgments into the proof payload shape.

    See `cloud/app/routes/proof.py` for the full schema.
    """
    flat: list[dict[str, Any]] = [r for recs in judgments.values() for r in recs]
    if not flat:
        return {
            "available": False,
            "source": None,
            "subjects": [],
            "judge": None,
            "trials": 0,
            "dimensions": [],
            "per_model": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "reason": "no judgments found",
        }

    # bucket: scores[(condition, dimension)] = [..]; per_model[(model, condition, dim)] = [..]
    by_cond_dim: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_model_cond_dim: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    subjects: set[str] = set()
    judges: set[str] = set()
    task_ids: set[str] = set()

    for rec in flat:
        model = rec.get("model") or rec.get("subject")
        condition = rec.get("condition") or rec.get("variant")
        dimension = rec.get("dimension")
        score = rec.get("score")
        if not (model and condition and dimension) or not isinstance(score, (int, float)):
            continue
        score = float(score)
        by_cond_dim[(condition, dimension)].append(score)
        by_model_cond_dim[(model, condition, dimension)].append(score)
        subjects.add(model)
        if rec.get("judge"):
            judges.add(rec["judge"])
        if rec.get("task_id"):
            task_ids.add(rec["task_id"])

    dimensions_seen = sorted({d for (_c, d) in by_cond_dim})
    dim_payload: list[dict[str, Any]] = []
    for dim in dimensions_seen:
        base = by_cond_dim.get(("base", dim), [])
        rules = by_cond_dim.get(("rules", dim), [])
        full = by_cond_dim.get(("full", dim), [])
        baseline_mean = round(_mean(base), 3)
        with_rules_mean = round(_mean(rules), 3) if rules else baseline_mean
        with_full_mean = round(_mean(full), 3) if full else with_rules_mean
        best_mean = max(with_rules_mean, with_full_mean)
        ci_pool = rules or full or base
        ci_low, ci_high = _ci95(ci_pool)
        dim_payload.append({
            "dimension": dim,
            "baseline_mean": baseline_mean,
            "with_rules_mean": with_rules_mean,
            "with_full_mean": with_full_mean,
            "best_mean": round(best_mean, 3),
            "ci_low": round(ci_low, 3),
            "ci_high": round(ci_high, 3),
            "delta_pp": round((best_mean - baseline_mean) * 100, 1),
            "n_base": len(base),
            "n_with": len(rules) + len(full),
        })

    per_model: list[dict[str, Any]] = []
    for model in sorted(subjects):
        m_dims: list[dict[str, Any]] = []
        for dim in dimensions_seen:
            base = by_model_cond_dim.get((model, "base", dim), [])
            rules = by_model_cond_dim.get((model, "rules", dim), [])
            full = by_model_cond_dim.get((model, "full", dim), [])
            best_pool = rules or full
            if not base and not best_pool:
                continue
            baseline_mean = round(_mean(base), 3)
            with_best_mean = round(_mean(best_pool), 3) if best_pool else baseline_mean
            m_dims.append({
                "dimension": dim,
                "baseline_mean": baseline_mean,
                "with_best_mean": with_best_mean,
                "delta_pp": round((with_best_mean - baseline_mean) * 100, 1),
            })
        if m_dims:
            per_model.append({"model": model, "dimensions": m_dims})

    return {
        "available": True,
        "source": None,  # set by caller via --source
        "subjects": sorted(subjects),
        "conditions": [c for c in CONDITIONS if any(c == k[0] for k in by_cond_dim)],
        "judge": sorted(judges)[0] if judges else None,
        "trials": len(flat),
        "tasks": len(task_ids),
        "dimensions": dim_payload,
        "per_model": per_model,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_payload(run_dir: Path, source: str | None) -> dict[str, Any]:
    judgments = load_judgments(run_dir)
    payload = aggregate(judgments)
    if source:
        payload["source"] = source
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export ablation results to proof_results.json")
    p.add_argument(
        "--run-dir",
        type=Path,
        default=Path(".tmp/rule-ablation-v2/judgments"),
        help="Directory containing per-run *.jsonl judgment files.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Path to write proof_results.json (default: cloud/data/proof_results.json).",
    )
    p.add_argument(
        "--source",
        type=str,
        default=None,
        help="Source tag to embed (e.g. gradata-ablation-v2-2026-04-14).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payload to stdout instead of writing --out.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = parse_args(argv)
    payload = build_payload(args.run_dir, args.source)
    rendered = json.dumps(payload, indent=2, sort_keys=False)
    if args.dry_run:
        print(rendered)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered + "\n", encoding="utf-8")
    _log.info(
        "wrote %s (available=%s, trials=%s, dims=%s)",
        args.out,
        payload.get("available"),
        payload.get("trials"),
        len(payload.get("dimensions", [])),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
