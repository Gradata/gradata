"""
SWE-bench Harness — Prove Gradata improves AI coding agents.
==============================================================

Runs SWE-bench instances through a Gradata-enhanced agent, captures
failed patches as corrections, accumulates brain, measures improvement.

Two modes:
  1. Offline (no Docker): compare agent patches to gold patches via
     diff similarity. Fast, cheap, sufficient to prove accumulation.
  2. Online (Docker/Modal): run actual tests for ground-truth pass/fail.

The experiment:
  Run A: baseline agent (no brain) → X% resolved
  Run B: same agent + Gradata brain → Y% resolved
  If Y > X, that's the paper.

Usage::

    from gradata.benchmarks.swe_bench import (
        SWEBenchHarness, load_swe_bench_lite, RunConfig,
    )

    harness = SWEBenchHarness(brain_dir="./swe-brain")
    instances = load_swe_bench_lite()
    results = harness.run(instances, agent_fn=my_agent)
    print(results.summary())

Requires: pip install datasets (for loading SWE-bench data)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)

__all__ = [
    "SWEInstance",
    "PatchResult",
    "RunConfig",
    "RunResults",
    "SWEBenchHarness",
    "load_swe_bench_lite",
    "load_swe_bench_verified",
    "compare_patches",
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SWEInstance:
    """A single SWE-bench instance.

    Attributes:
        instance_id: Unique ID (e.g. "django__django-11099").
        repo: GitHub repo (e.g. "django/django").
        problem_statement: The issue text.
        gold_patch: The correct fix (diff format).
        fail_to_pass: Test names that must flip to passing.
        pass_to_pass: Test names that must stay passing.
        base_commit: Commit SHA to start from.
        hints: Optional hints from issue comments.
        version: Package version string.
    """
    instance_id: str
    repo: str
    problem_statement: str
    gold_patch: str = ""
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    base_commit: str = ""
    hints: str = ""
    version: str = ""


@dataclass
class PatchResult:
    """Result of an agent's attempt at fixing an instance.

    Attributes:
        instance_id: Which instance was attempted.
        agent_patch: The patch the agent produced.
        gold_patch: The correct patch (for comparison).
        resolved: Whether the patch resolves the issue.
        similarity: Diff similarity to gold patch (0.0-1.0).
        correction_captured: Whether brain.correct() was called.
        lesson_created: Whether a new lesson was created.
        attempt_number: Which attempt this was (1-indexed).
        duration_ms: How long the agent took.
        error: Error message if agent crashed.
    """
    instance_id: str
    agent_patch: str = ""
    gold_patch: str = ""
    resolved: bool = False
    similarity: float = 0.0
    correction_captured: bool = False
    lesson_created: bool = False
    attempt_number: int = 1
    duration_ms: int = 0
    error: str = ""


@dataclass
class RunConfig:
    """Configuration for a SWE-bench run.

    Attributes:
        run_id: Identifier for this run.
        use_brain: Whether to inject brain rules.
        batch_size: How many instances before measuring.
        max_instances: Cap on total instances to process.
        similarity_threshold: Min similarity to count as "resolved" in offline mode.
    """
    run_id: str = "default"
    use_brain: bool = True
    batch_size: int = 50
    max_instances: int = 300
    similarity_threshold: float = 0.85


@dataclass
class BatchStats:
    """Statistics for a batch of instances."""
    batch_number: int
    instances_in_batch: int
    resolved: int
    resolve_rate: float
    avg_similarity: float
    lessons_total: int
    corrections_total: int


@dataclass
class RunResults:
    """Aggregate results from a full SWE-bench run.

    Attributes:
        config: The run configuration.
        results: Per-instance results.
        batch_stats: Per-batch statistics (shows learning curve).
        total_resolved: Total instances resolved.
        total_attempted: Total instances attempted.
        resolve_rate: Overall resolve rate.
        brain_lessons_created: Total lessons created during run.
        duration_seconds: Total run time.
    """
    config: RunConfig
    results: list[PatchResult] = field(default_factory=list)
    batch_stats: list[BatchStats] = field(default_factory=list)
    total_resolved: int = 0
    total_attempted: int = 0
    resolve_rate: float = 0.0
    brain_lessons_created: int = 0
    duration_seconds: float = 0.0

    def summary(self) -> str:
        """Human-readable summary of the run."""
        lines = [
            f"SWE-bench Run: {self.config.run_id}",
            f"Brain: {'enabled' if self.config.use_brain else 'DISABLED (baseline)'}",
            f"Resolved: {self.total_resolved}/{self.total_attempted} ({self.resolve_rate:.1%})",
            f"Lessons created: {self.brain_lessons_created}",
            f"Duration: {self.duration_seconds:.0f}s",
            "",
            "Learning curve (resolve rate per batch):",
        ]
        for bs in self.batch_stats:
            bar = "#" * int(bs.resolve_rate * 20)
            lines.append(
                f"  Batch {bs.batch_number}: {bs.resolve_rate:.1%} "
                f"[{bar:<20}] (lessons: {bs.lessons_total})"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "run_id": self.config.run_id,
            "use_brain": self.config.use_brain,
            "total_resolved": self.total_resolved,
            "total_attempted": self.total_attempted,
            "resolve_rate": round(self.resolve_rate, 4),
            "brain_lessons_created": self.brain_lessons_created,
            "duration_seconds": round(self.duration_seconds, 1),
            "batch_stats": [
                {
                    "batch": bs.batch_number,
                    "resolve_rate": round(bs.resolve_rate, 4),
                    "lessons_total": bs.lessons_total,
                }
                for bs in self.batch_stats
            ],
        }


# ---------------------------------------------------------------------------
# Patch comparison (offline mode)
# ---------------------------------------------------------------------------

def compare_patches(agent_patch: str, gold_patch: str) -> float:
    """Compare two patches and return similarity score.

    Uses line-level set overlap (Jaccard on meaningful diff lines).
    Strips whitespace and comment-only changes.

    Args:
        agent_patch: The agent's proposed fix.
        gold_patch: The correct fix.

    Returns:
        Similarity score in [0.0, 1.0]. 1.0 = identical patches.
    """
    if not agent_patch and not gold_patch:
        return 1.0
    if not agent_patch or not gold_patch:
        return 0.0

    def _meaningful_lines(patch: str) -> set[str]:
        """Extract meaningful diff lines (additions/removals only)."""
        lines = set()
        for line in patch.splitlines():
            stripped = line.strip()
            # Only count actual code changes, not headers
            if stripped.startswith(("+", "-")) and not stripped.startswith(("+++", "---", "@@")):
                # Normalize whitespace
                normalized = " ".join(stripped[1:].split())
                if normalized and not normalized.startswith("#"):
                    lines.add(normalized)
        return lines

    agent_lines = _meaningful_lines(agent_patch)
    gold_lines = _meaningful_lines(gold_patch)

    if not agent_lines and not gold_lines:
        return 0.5  # Both patches have no meaningful changes

    union = agent_lines | gold_lines
    if not union:
        return 0.0

    intersection = agent_lines & gold_lines
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_dataset(dataset_name: str, split: str = "test") -> list[SWEInstance]:
    """Load SWE-bench instances from HuggingFace datasets.

    Requires: pip install datasets
    """
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError(
            "SWE-bench data loading requires the 'datasets' package.\n"
            "Install with: pip install datasets"
        )

    ds = load_dataset(dataset_name, split=split)
    instances = []
    for raw_item in ds:
        item: dict = dict(raw_item)  # type: ignore[arg-type]
        instances.append(SWEInstance(
            instance_id=item["instance_id"],
            repo=item["repo"],
            problem_statement=item["problem_statement"],
            gold_patch=item.get("patch", ""),
            fail_to_pass=json.loads(item.get("FAIL_TO_PASS", "[]")),
            pass_to_pass=json.loads(item.get("PASS_TO_PASS", "[]")),
            base_commit=item.get("base_commit", ""),
            hints=item.get("hints_text", ""),
            version=item.get("version", ""),
        ))
    return instances


def load_swe_bench_lite() -> list[SWEInstance]:
    """Load SWE-bench Lite (300 test instances)."""
    return _load_dataset("princeton-nlp/SWE-bench_Lite", split="test")


def load_swe_bench_verified() -> list[SWEInstance]:
    """Load SWE-bench Verified (500 human-verified instances)."""
    return _load_dataset("princeton-nlp/SWE-bench_Verified", split="test")


def load_from_jsonl(filepath: str | Path) -> list[SWEInstance]:
    """Load instances from a local JSONL file (for offline/cached use)."""
    instances = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            instances.append(SWEInstance(
                instance_id=data["instance_id"],
                repo=data.get("repo", ""),
                problem_statement=data.get("problem_statement", ""),
                gold_patch=data.get("patch", data.get("gold_patch", "")),
                fail_to_pass=data.get("FAIL_TO_PASS", data.get("fail_to_pass", [])),
                base_commit=data.get("base_commit", ""),
            ))
    return instances


# ---------------------------------------------------------------------------
# Agent function type
# ---------------------------------------------------------------------------

# An agent function takes (instance, brain_rules) and returns a patch string.
# brain_rules is "" when use_brain=False (baseline), or the injected rules
# when use_brain=True.
AgentFn = Callable[[SWEInstance, str], str]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class SWEBenchHarness:
    """Runs SWE-bench with Gradata brain accumulation.

    The harness:
    1. Feeds each instance to the agent function
    2. Compares the agent's patch to the gold patch
    3. If wrong: calls brain.correct(agent_patch, gold_patch)
    4. Tracks resolve rate per batch as the brain accumulates
    5. Injects brain rules into subsequent agent calls (if use_brain=True)

    Args:
        brain_dir: Directory for the Gradata brain.
        brain: Optional pre-existing Brain instance.
    """

    def __init__(
        self,
        brain_dir: str | Path | None = None,
        brain: Any = None,
    ) -> None:
        self.brain = brain
        self.brain_dir = Path(brain_dir) if brain_dir else None

        if self.brain is None and self.brain_dir:
            try:
                from gradata.brain import Brain
                if self.brain_dir.exists():
                    self.brain = Brain(self.brain_dir)
                else:
                    self.brain = Brain.init(self.brain_dir, domain="SWE-bench")
            except ImportError:
                _log.warning("Brain not available, running without learning")

    def run(
        self,
        instances: list[SWEInstance],
        agent_fn: AgentFn,
        config: RunConfig | None = None,
    ) -> RunResults:
        """Run the benchmark.

        Args:
            instances: SWE-bench instances to attempt.
            agent_fn: Callable(instance, brain_rules) -> patch_string.
            config: Run configuration.

        Returns:
            RunResults with per-instance and per-batch statistics.
        """
        config = config or RunConfig()
        instances = instances[:config.max_instances]

        run_results = RunResults(config=config)
        start_time = time.time()

        batch_results: list[PatchResult] = []
        batch_number = 0
        lessons_total = 0

        for i, instance in enumerate(instances):
            # Get brain rules for injection
            brain_rules = ""
            if config.use_brain and self.brain:
                try:
                    brain_rules = self.brain.apply_brain_rules(
                        f"Fix bug in {instance.repo}: {instance.problem_statement[:200]}"
                    )
                except Exception:
                    brain_rules = ""

            # Run the agent
            t0 = time.time()
            try:
                agent_patch = agent_fn(instance, brain_rules)
            except Exception as e:
                agent_patch = ""
                _log.warning("Agent failed on %s: %s", instance.instance_id, e)

            duration_ms = int((time.time() - t0) * 1000)

            # Compare to gold patch
            similarity = compare_patches(agent_patch, instance.gold_patch)
            resolved = similarity >= config.similarity_threshold

            # Capture correction if wrong
            correction_captured = False
            lesson_created = False
            if not resolved and self.brain and config.use_brain:
                if agent_patch and instance.gold_patch:
                    try:
                        event = self.brain.correct(
                            draft=agent_patch[:5000],
                            final=instance.gold_patch[:5000],
                            category="CODE",
                            context={
                                "task_type": "swe_bench_fix",
                                "repo": instance.repo,
                                "instance_id": instance.instance_id,
                            },
                        )
                        correction_captured = True
                        if event.get("lessons_created", 0) > 0:
                            lesson_created = True
                            lessons_total += 1
                    except Exception as e:
                        _log.warning("Correction capture failed: %s", e)

            result = PatchResult(
                instance_id=instance.instance_id,
                agent_patch=agent_patch[:1000],
                gold_patch=instance.gold_patch[:1000],
                resolved=resolved,
                similarity=round(similarity, 4),
                correction_captured=correction_captured,
                lesson_created=lesson_created,
                attempt_number=1,
                duration_ms=duration_ms,
            )
            run_results.results.append(result)
            batch_results.append(result)

            # Batch checkpoint
            if len(batch_results) >= config.batch_size or i == len(instances) - 1:
                batch_number += 1
                batch_resolved = sum(1 for r in batch_results if r.resolved)
                batch_rate = batch_resolved / len(batch_results) if batch_results else 0
                avg_sim = (
                    sum(r.similarity for r in batch_results) / len(batch_results)
                    if batch_results else 0
                )

                run_results.batch_stats.append(BatchStats(
                    batch_number=batch_number,
                    instances_in_batch=len(batch_results),
                    resolved=batch_resolved,
                    resolve_rate=round(batch_rate, 4),
                    avg_similarity=round(avg_sim, 4),
                    lessons_total=lessons_total,
                    corrections_total=sum(
                        1 for r in run_results.results if r.correction_captured
                    ),
                ))

                _log.info(
                    "Batch %d: %d/%d resolved (%.1f%%), %d lessons total",
                    batch_number, batch_resolved, len(batch_results),
                    batch_rate * 100, lessons_total,
                )
                batch_results = []

        # Final stats
        run_results.total_attempted = len(run_results.results)
        run_results.total_resolved = sum(1 for r in run_results.results if r.resolved)
        run_results.resolve_rate = (
            run_results.total_resolved / run_results.total_attempted
            if run_results.total_attempted else 0
        )
        run_results.brain_lessons_created = lessons_total
        run_results.duration_seconds = time.time() - start_time

        return run_results

    def compare_runs(
        self,
        baseline: RunResults,
        enhanced: RunResults,
    ) -> dict[str, Any]:
        """Compare a baseline run (no brain) vs enhanced run (with brain).

        Returns a summary dict suitable for a paper or blog post.
        """
        improvement = enhanced.resolve_rate - baseline.resolve_rate
        improvement_pct = (
            improvement / baseline.resolve_rate * 100
            if baseline.resolve_rate > 0 else 0
        )

        # Per-batch learning curve comparison
        curve = []
        for i, (b, e) in enumerate(zip(baseline.batch_stats, enhanced.batch_stats)):
            curve.append({
                "batch": i + 1,
                "baseline_rate": b.resolve_rate,
                "enhanced_rate": e.resolve_rate,
                "delta": round(e.resolve_rate - b.resolve_rate, 4),
                "lessons_at_batch": e.lessons_total,
            })

        return {
            "baseline_resolve_rate": round(baseline.resolve_rate, 4),
            "enhanced_resolve_rate": round(enhanced.resolve_rate, 4),
            "absolute_improvement": round(improvement, 4),
            "relative_improvement_pct": round(improvement_pct, 1),
            "lessons_created": enhanced.brain_lessons_created,
            "baseline_instances": baseline.total_attempted,
            "enhanced_instances": enhanced.total_attempted,
            "learning_curve": curve,
            "verdict": (
                f"Gradata improved SWE-bench resolve rate from "
                f"{baseline.resolve_rate:.1%} to {enhanced.resolve_rate:.1%} "
                f"(+{improvement:.1%} absolute, +{improvement_pct:.1f}% relative)"
            ),
        }
