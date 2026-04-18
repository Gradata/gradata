"""
Parallel Execution Pattern — Dependency-Aware Task Dispatch
============================================================
SDK LAYER: Pure logic, stdlib only. No domain-specific content.

Provides two execution strategies:

``ParallelBatch``
    Dispatch a flat list of independent tasks. Each task is called
    sequentially (no asyncio); errors are caught per-task and never
    propagate to siblings. The host process (e.g. Claude Code agents)
    supplies real concurrency by spawning multiple instances.

``DependencyGraph``
    Accept tasks with ``depends_on`` edges, sort them into topological
    *waves*, execute each wave in order, and forward the output of
    completed tasks to their dependents via ``input_data``.

``merge_results``
    Combine a list of ``TaskResult`` objects into a single value using
    one of three strategies: ``"combine"`` (list), ``"best_of"``
    (highest-ranked successful result), or ``"synthesize"``
    (structured summary dict).

Note on "concurrent" semantics
-------------------------------
This SDK version is synchronous. Tasks in the same wave are called one
after another. The graph guarantees *logical* parallelism — tasks that
have no dependency relationship between them will never block each other
from being scheduled together if the caller adds true concurrency on top.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ParallelTask:
    """A single unit of work within a parallel batch or dependency graph.

    Args:
        id: Unique identifier for this task within the batch.
        objective: Human-readable description of what this task does.
        handler: Callable invoked with ``input_data`` as its sole
            positional argument.  Must return a value (or raise).
        input_data: Data passed to ``handler`` at invocation time.
            Dependents receive the *output* of their upstream tasks
            merged into this field by ``DependencyGraph``.
        depends_on: Task IDs that must complete successfully before
            this task is eligible to run.
    """

    id: str
    objective: str
    handler: Callable[..., Any]
    input_data: Any = None
    depends_on: list[str] = field(default_factory=list)


@dataclass
class TaskResult:
    """Outcome of executing a single ``ParallelTask``.

    Args:
        task_id: Mirrors ``ParallelTask.id``.
        success: ``True`` if ``handler`` returned without raising.
        output: Return value of ``handler``, or ``None`` on failure.
        error: Stringified exception message when ``success`` is
            ``False``; ``None`` otherwise.
        duration_ms: Wall-clock time spent executing the handler.
    """

    task_id: str
    success: bool
    output: Any
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class ParallelResult:
    """Aggregated outcome of a full batch or graph execution.

    Args:
        results: Mapping of ``task_id`` to its ``TaskResult``.
        execution_order: Wave-based execution schedule.  Each inner list
            contains the IDs of tasks that were eligible to run
            simultaneously (no outstanding dependencies between them).
        all_succeeded: ``True`` only when every task's
            ``TaskResult.success`` is ``True``.
        total_duration_ms: Cumulative wall-clock time across all waves.
    """

    results: dict[str, TaskResult]
    execution_order: list[list[str]]
    all_succeeded: bool
    total_duration_ms: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_task(task: ParallelTask) -> TaskResult:
    """Invoke *task.handler* with *task.input_data* and capture the result.

    Exceptions are caught and stored in ``TaskResult.error``; they do
    **not** propagate to the caller.

    Args:
        task: The task to execute.

    Returns:
        A ``TaskResult`` reflecting success or failure.
    """
    start = time.monotonic()
    try:
        output = task.handler(task.input_data)
        duration_ms = (time.monotonic() - start) * 1000.0
        return TaskResult(
            task_id=task.id,
            success=True,
            output=output,
            duration_ms=round(duration_ms, 2),
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000.0
        return TaskResult(
            task_id=task.id,
            success=False,
            output=None,
            error=str(exc),
            duration_ms=round(duration_ms, 2),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ParallelBatch:
    """Execute a flat list of independent tasks with per-task error isolation.

    Tasks are assumed to have *no* dependency relationships.  If any task
    declares ``depends_on``, those dependencies are ignored — use
    ``DependencyGraph`` instead.

    Args:
        *tasks: One or more ``ParallelTask`` instances.

    Example::

        result = ParallelBatch(task_a, task_b, task_c).run()
        if not result.all_succeeded:
            failures = [r for r in result.results.values() if not r.success]
    """

    def __init__(self, *tasks: ParallelTask) -> None:
        self._tasks: list[ParallelTask] = list(tasks)

    def run(self) -> ParallelResult:
        """Execute all tasks and return an aggregated ``ParallelResult``.

        Returns:
            ``ParallelResult`` with a single wave containing all task IDs,
            each task's ``TaskResult``, and aggregate success/timing data.
        """
        batch_start = time.monotonic()
        results: dict[str, TaskResult] = {}

        for task in self._tasks:
            results[task.id] = _run_task(task)

        total_duration_ms = round((time.monotonic() - batch_start) * 1000.0, 2)
        execution_order = [[t.id for t in self._tasks]] if self._tasks else []
        all_succeeded = all(r.success for r in results.values())

        return ParallelResult(
            results=results,
            execution_order=execution_order,
            all_succeeded=all_succeeded,
            total_duration_ms=total_duration_ms,
        )


class DependencyGraph:
    """Execute tasks in dependency-respecting topological waves.

    Tasks with no ``depends_on`` entries run in the first wave.
    Subsequent waves run after all their declared dependencies have
    completed.  Outputs from completed tasks are passed to their
    dependents by overwriting ``input_data`` before invocation.

    If a dependency task **failed**, the dependent task is skipped and
    recorded as failed with an explanatory error string rather than
    halting the entire graph.

    Args:
        tasks: List of ``ParallelTask`` objects, potentially with
            dependency edges declared via ``depends_on``.

    Raises:
        ValueError: Raised at construction time if the dependency graph
            contains cycles or references to unknown task IDs.

    Example::

        fetch = ParallelTask("fetch", "Fetch data", fetch_fn)
        parse = ParallelTask("parse", "Parse result", parse_fn, depends_on=["fetch"])
        graph = DependencyGraph([fetch, parse])
        result = graph.run()
    """

    def __init__(self, tasks: list[ParallelTask]) -> None:
        self._tasks: list[ParallelTask] = tasks
        _tmap: dict[str, ParallelTask] = {t.id: t for t in tasks}
        _indeg: dict[str, int] = {t.id: 0 for t in tasks}
        _deps: dict[str, list[str]] = defaultdict(list)
        for _t in tasks:
            for _dep in _t.depends_on:
                if _dep not in _tmap:
                    raise ValueError(
                        f"Task '{_t.id}' declares dependency on unknown task '{_dep}'."
                    )
                _indeg[_t.id] += 1
                _deps[_dep].append(_t.id)
        _waves: list[list[str]] = []
        _ready: list[str] = [_tid for _tid, _d in _indeg.items() if _d == 0]
        while _ready:
            _wave = sorted(_ready)
            _waves.append(_wave)
            _next: list[str] = []
            for _tid in _wave:
                for _child in _deps[_tid]:
                    _indeg[_child] -= 1
                    if _indeg[_child] == 0:
                        _next.append(_child)
            _ready = _next
        if sum(len(_w) for _w in _waves) != len(tasks):
            raise ValueError(
                f"Dependency cycle detected. Tasks involved: {[_tid for _tid in _indeg if _indeg[_tid] > 0]}"
            )
        self._waves: list[list[str]] = _waves
        self._task_map: dict[str, ParallelTask] = {t.id: t for t in tasks}

    def run(self) -> ParallelResult:
        """Execute the graph wave-by-wave and return a ``ParallelResult``.

        Dependent tasks receive the upstream task's ``output`` as their
        ``input_data``.  When multiple dependencies exist, their outputs
        are collected into a ``dict[task_id, output]`` and passed as
        ``input_data``.

        Returns:
            ``ParallelResult`` with per-task results, the execution wave
            order, aggregate success flag, and total wall-clock time.
        """
        graph_start = time.monotonic()
        results: dict[str, TaskResult] = {}

        for wave in self._waves:
            for tid in wave:
                task = self._task_map[tid]

                # Check whether any dependency failed; skip if so.
                failed_deps = [
                    dep for dep in task.depends_on if dep in results and not results[dep].success
                ]
                if failed_deps:
                    results[tid] = TaskResult(
                        task_id=tid,
                        success=False,
                        output=None,
                        error=(f"Skipped: upstream dependencies failed: {failed_deps}"),
                    )
                    continue

                # Forward upstream outputs into input_data.
                if task.depends_on:
                    upstream_outputs = {dep: results[dep].output for dep in task.depends_on}
                    if len(upstream_outputs) == 1:
                        # Single parent: pass the value directly for ergonomics.
                        task.input_data = next(iter(upstream_outputs.values()))
                    else:
                        task.input_data = upstream_outputs

                results[tid] = _run_task(task)

        total_duration_ms = round((time.monotonic() - graph_start) * 1000.0, 2)
        all_succeeded = all(r.success for r in results.values())

        return ParallelResult(
            results=results,
            execution_order=self._waves,
            all_succeeded=all_succeeded,
            total_duration_ms=total_duration_ms,
        )


# ---------------------------------------------------------------------------
# Result merging
# ---------------------------------------------------------------------------


def merge_results(
    results: list[TaskResult],
    strategy: str = "combine",
) -> Any:
    """Merge a list of task results into a single value.

    Args:
        results: ``TaskResult`` objects to merge.  Failed results are
            excluded from all strategies.
        strategy: One of:

            ``"combine"``
                Return a list of all successful outputs in the order
                the results were provided.

            ``"best_of"``
                Return the single output whose stringified length is
                longest (a heuristic for "most complete" text output).
                Falls back to the first successful output if outputs are
                non-string.

            ``"synthesize"``
                Return a ``dict`` with keys ``"outputs"`` (list of
                successful outputs), ``"count"`` (number of successful
                tasks), ``"failed"`` (list of failed task IDs), and
                ``"total"`` (total tasks provided).

    Returns:
        Merged value.  Returns an empty list / ``None`` / empty dict
        when there are no successful results.

    Raises:
        ValueError: If *strategy* is not one of the three recognised
            values.
    """
    valid_strategies = {"combine", "best_of", "synthesize"}
    if strategy not in valid_strategies:
        raise ValueError(
            f"Unknown merge strategy '{strategy}'. Choose from: {sorted(valid_strategies)}"
        )

    successful = [r for r in results if r.success]
    failed_ids = [r.task_id for r in results if not r.success]

    if strategy == "combine":
        return [r.output for r in successful]

    if strategy == "best_of":
        if not successful:
            return None
        try:
            return max(successful, key=lambda r: len(str(r.output))).output
        except (TypeError, ValueError):
            return successful[0].output

    # strategy == "synthesize"
    return {
        "outputs": [r.output for r in successful],
        "count": len(successful),
        "failed": failed_ids,
        "total": len(results),
    }
