"""GET /public/proof — honest ablation-backed quality proof for the dashboard.

Serves the latest Gradata-run ablation results. The file is produced by
scripts/export_ab_proof.py which aggregates the blind-judge scores from a
multi-model, multi-condition ablation run.

Public, unauthenticated: this is the marketing surface. Stale-OK semantics —
if the results file is missing (pre-launch / fresh deploy) we return a
structured empty-state so the dashboard can show an honest "no data yet"
state rather than fabricated numbers.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter

_log = logging.getLogger(__name__)

router = APIRouter()

# Resolve the results file relative to the cloud/ package root so it works
# both locally and when deployed (Railway/Docker image).
_PROOF_PATH = Path(__file__).resolve().parents[2] / "data" / "proof_results.json"


@router.get("/public/proof")
async def get_proof() -> dict:
    """Return the latest ablation-backed proof numbers.

    Response shape mirrors the dashboard ABProofPanel expectations:
    {
      "available": bool,
      "source": str | None,         # e.g. "gradata-ablation-v2-2026-04-14"
      "subjects": list[str],        # model names evaluated
      "judge": str | None,          # judge model id
      "trials": int,                # total subject calls
      "tasks": int,
      "iterations_per_task": int,
      "dimensions": [                # per-dimension lift, ready to render
        {
          "dimension": "correctness",
          "baseline_mean": float,   # 0-1
          "with_rules_mean": float, # 0-1
          "with_full_mean": float,  # 0-1
          "ci_low": float, "ci_high": float,
          "delta_pp": float,         # percentage points, with_full - baseline
          "n_base": int, "n_with": int
        }
      ],
      "per_model": [...]             # optional breakdown
      "updated_at": str
    }
    """
    if not _PROOF_PATH.is_file():
        return {
            "available": False,
            "source": None,
            "reason": "no ablation results published yet",
        }
    try:
        payload = json.loads(_PROOF_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.warning("proof_results.json unreadable: %s", exc)
        return {"available": False, "source": None, "reason": "results file unreadable"}
    if not isinstance(payload, dict):
        _log.warning(
            "proof_results.json has unexpected top-level type %s — treating as unavailable",
            type(payload).__name__,
        )
        return {
            "available": False,
            "source": None,
            "reason": "results file has unexpected JSON shape (expected object)",
        }
    payload.setdefault("available", True)
    return payload
