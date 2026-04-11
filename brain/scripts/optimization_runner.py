"""
Optimization Runner — Autoresearch loop for worktree sims.
============================================================
Runs in an isolated git worktree. Benchmarks pipeline code, tracks best score,
commits improvements, reverts failures. Writes results.jsonl + SUMMARY.json.

Usage:
    python optimization_runner.py --type conciseness --brain-dir /path/to/brain --events /path/to/events.jsonl --output .tmp/opt-results/ --max-duration 120
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path

_log = logging.getLogger(__name__)


def run_benchmark(brain_dir: Path, events_path: Path, max_events: int = 2000) -> dict:
    """Run brain_benchmark.py and return results."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from brain_benchmark import score_brain

    with tempfile.TemporaryDirectory() as tmp:
        tmp_brain = Path(tmp) / "bench_brain"
        tmp_brain.mkdir()
        (tmp_brain / "system.db").touch()
        return score_brain(tmp_brain, events_path, max_events=max_events, use_llm_judge=False)


def optimization_loop(
    opt_type: str,
    brain_dir: Path,
    events_path: Path,
    output_dir: Path,
    max_iterations: int = 100,
    max_duration_minutes: int = 120,
):
    """Run the optimization loop.

    For each iteration:
    1. Benchmark current code state
    2. Compare to best score
    3. If improved: commit and keep
    4. If not: revert via git checkout
    5. Write results to JSONL
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file = output_dir / "results.jsonl"
    start_time = time.time()

    _log.info("Running baseline benchmark...")
    baseline = run_benchmark(brain_dir, events_path)
    best_score = baseline["composite_score"]
    _log.info("Baseline score: %.2f", best_score)

    with open(results_file, "w") as f:
        f.write(
            json.dumps(
                {"iteration": 0, "type": "baseline", "score": best_score, "details": baseline}
            )
            + "\n"
        )

    iteration = 0
    while iteration < max_iterations:
        elapsed = (time.time() - start_time) / 60
        if elapsed >= max_duration_minutes:
            _log.info("Time limit reached (%.1f min). Stopping.", elapsed)
            break

        iteration += 1
        _log.info("=== Iteration %d (%.1f min elapsed) ===", iteration, elapsed)

        current = run_benchmark(brain_dir, events_path)
        current_score = current["composite_score"]

        kept = current_score > best_score
        result = {
            "iteration": iteration,
            "score": current_score,
            "delta": round(current_score - best_score, 4),
            "elapsed_min": round(elapsed, 1),
            "kept": kept,
            "details": current,
        }

        if kept:
            _log.info(
                "IMPROVEMENT: %.2f -> %.2f (+%.2f)",
                best_score,
                current_score,
                current_score - best_score,
            )
            best_score = current_score
            subprocess.run(["git", "add", "-A"], capture_output=True, cwd=str(Path.cwd()))
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"opt({opt_type}): iteration {iteration}, score {current_score:.2f}",
                ],
                capture_output=True,
                cwd=str(Path.cwd()),
            )
        else:
            _log.info("No improvement: %.2f (best: %.2f). Reverting.", current_score, best_score)
            subprocess.run(["git", "checkout", "."], capture_output=True, cwd=str(Path.cwd()))

        with open(results_file, "a") as f:
            f.write(json.dumps(result) + "\n")

    duration = round((time.time() - start_time) / 60, 1)
    _log.info(
        "Done. Best: %.2f (baseline: %.2f, +%.2f) in %d iterations over %.1f min",
        best_score,
        baseline["composite_score"],
        best_score - baseline["composite_score"],
        iteration,
        duration,
    )

    summary = {
        "opt_type": opt_type,
        "baseline_score": baseline["composite_score"],
        "best_score": best_score,
        "improvement": round(best_score - baseline["composite_score"], 4),
        "iterations": iteration,
        "duration_min": duration,
    }
    (output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Run optimization loop in worktree")
    parser.add_argument("--type", required=True, choices=["conciseness", "coldstart", "reversal"])
    parser.add_argument("--brain-dir", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--max-duration", type=int, default=120, help="Max minutes")
    args = parser.parse_args()
    optimization_loop(
        args.type,
        Path(args.brain_dir),
        Path(args.events),
        Path(args.output),
        args.max_iterations,
        args.max_duration,
    )
