"""Smoke test for autoresearch consolidation loop.

Exercises the SDK's critical public flows end-to-end in a throwaway tmpdir.
Runs in ~5-30 seconds. Catches regressions tests miss (broken imports,
bad module-level side effects, public API breakage).

Exit 0 = all flows green. Non-zero = gate trip, commit discarded.
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path


def main() -> int:
    try:
        from gradata import Brain  # noqa: F401 — import is itself a gate
    except Exception:
        print("SMOKE_FAIL: import gradata.Brain", file=sys.stderr)
        traceback.print_exc()
        return 10

    with tempfile.TemporaryDirectory() as td:
        brain_path = Path(td) / "brain"
        try:
            brain = Brain.init(str(brain_path))
        except Exception:
            print("SMOKE_FAIL: Brain.init", file=sys.stderr)
            traceback.print_exc()
            return 11

        try:
            brain.log_output(
                "draft email about Q2 pricing",
                output_type="email",
                self_score=7,
            )
        except Exception:
            print("SMOKE_FAIL: log_output", file=sys.stderr)
            traceback.print_exc()
            return 12

        try:
            brain.correct(
                draft="Hi team, the price is $100.",
                final="Hi team — the investment is $100.",
            )
        except Exception:
            print("SMOKE_FAIL: correct", file=sys.stderr)
            traceback.print_exc()
            return 13

        try:
            brain.apply_brain_rules("draft message to stakeholder about pricing")
        except Exception:
            print("SMOKE_FAIL: apply_brain_rules", file=sys.stderr)
            traceback.print_exc()
            return 14

        try:
            brain.search("pricing objections")
        except Exception:
            print("SMOKE_FAIL: search", file=sys.stderr)
            traceback.print_exc()
            return 15

        try:
            brain.manifest()
        except Exception:
            print("SMOKE_FAIL: manifest", file=sys.stderr)
            traceback.print_exc()
            return 16

    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
