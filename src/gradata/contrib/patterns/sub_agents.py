"""Sub-Agent Orchestrator — structured delegation with typed contracts:
decompose task → delegations (typed I/O + success criteria) → execute
parallel/sequential → synthesise. Portable layer under ``brain/scripts/spawn.py``
(routing/agent defs stay brain-side). Layer 0 pattern: domain-agnostic.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class Delegation:
    """A structured task delegation to a sub-agent.

    Each delegation has a clear contract: what goes in, what comes out,
    and how to know if it succeeded.
    """

    agent: str  # agent type/name (e.g., "researcher", "writer", "critic")
    objective: str  # one-sentence goal
    input_data: Any = None  # data to pass to the agent
    output_format: str = "text"  # expected output type hint
    success_criteria: str = ""  # how to evaluate success
    depends_on: list[str] = field(default_factory=list)  # delegation IDs this depends on
    timeout_seconds: int = 300
    id: str = ""  # auto-assigned if empty

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"{self.agent}_{id(self) % 10000:04d}"


@dataclass
class DelegationResult:
    """Result of executing a single delegation."""

    delegation_id: str
    agent: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class OrchestratedResult:
    """Result of orchestrating multiple delegations."""

    success: bool
    output: Any  # synthesized final output
    delegations_completed: int
    delegations_total: int
    delegation_results: list[DelegationResult] = field(default_factory=list)
    execution_order: list[list[str]] = field(default_factory=list)  # wave-based
    total_duration_ms: float = 0.0
    qa_passed: bool = True


def orchestrate(
    delegations: list[Delegation],
    handlers: dict[str, Callable] | None = None,
    default_handler: Callable | None = None,
    synthesizer: Callable | None = None,
    qa_check: Callable | None = None,
) -> OrchestratedResult:
    """Execute delegations with dependency ordering and synthesis.

    Args:
        delegations: Tasks to execute.
        handlers: Map of agent name -> callable. Handler receives (delegation, context)
                  where context is a dict of prior delegation outputs.
        default_handler: Fallback handler if agent name not in handlers.
        synthesizer: Optional function to combine all results into final output.
                     Receives list[DelegationResult] -> Any.
        qa_check: Optional function to validate final output. Returns bool.

    Returns:
        OrchestratedResult with all delegation results and synthesized output.
    """
    handlers = handlers or {}
    _completed: set[str] = set()
    _remaining = list(delegations)
    waves: list[list[Delegation]] = []
    while _remaining:
        _wave = [_d for _d in _remaining if all(_dep in _completed for _dep in _d.depends_on)]
        if not _wave:
            _wave = [_remaining[0]]
        waves.append(_wave)
        for _d in _wave:
            _completed.add(_d.id)
        _remaining = [_d for _d in _remaining if _d.id not in _completed]
    execution_order: list[list[str]] = []
    results: list[DelegationResult] = []
    context: dict[str, Any] = {}  # delegation_id -> output

    total_start = time.perf_counter()

    for wave in waves:
        wave_ids: list[str] = []

        for delegation in wave:
            wave_ids.append(delegation.id)
            handler = handlers.get(delegation.agent, default_handler)

            if handler is None:
                results.append(
                    DelegationResult(
                        delegation_id=delegation.id,
                        agent=delegation.agent,
                        success=False,
                        error=f"No handler for agent '{delegation.agent}'",
                    )
                )
                continue

            start = time.perf_counter()
            try:
                output = handler(delegation, context)
                duration = (time.perf_counter() - start) * 1000
                results.append(
                    DelegationResult(
                        delegation_id=delegation.id,
                        agent=delegation.agent,
                        success=True,
                        output=output,
                        duration_ms=round(duration, 2),
                    )
                )
                context[delegation.id] = output
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                results.append(
                    DelegationResult(
                        delegation_id=delegation.id,
                        agent=delegation.agent,
                        success=False,
                        error=str(e),
                        duration_ms=round(duration, 2),
                    )
                )

        execution_order.append(wave_ids)

    total_duration = (time.perf_counter() - total_start) * 1000

    # Synthesize
    if synthesizer:
        try:
            final_output = synthesizer(results)
        except Exception as e:
            final_output = f"Synthesis failed: {e}"
    else:
        # Default: collect successful outputs
        final_output = [r.output for r in results if r.success]

    # QA check
    qa_passed = True
    if qa_check:
        try:
            qa_passed = qa_check(final_output)
        except Exception:
            qa_passed = False

    completed = sum(1 for r in results if r.success)
    return OrchestratedResult(
        success=completed == len(delegations),
        output=final_output,
        delegations_completed=completed,
        delegations_total=len(delegations),
        delegation_results=results,
        execution_order=execution_order,
        total_duration_ms=round(total_duration, 2),
        qa_passed=qa_passed,
    )


# ---------------------------------------------------------------------------
# Agent definition loading (extracted from brain/scripts/spawn.py)
# ---------------------------------------------------------------------------

# Default agent config when definition file is missing
DEFAULT_AGENT_DEFINITION: dict[str, Any] = {
    "name": "unknown",
    "description": "Agent definition not found",
    "model": "sonnet",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "system_prompt": "You are a general-purpose agent. Complete the task given to you.",
    "_warning": "Agent definition file not found — using defaults",
}


def load_agent_definition(
    agent_name: str,
    agents_dir: str | Path,
) -> dict[str, Any]:
    """Read an agent markdown file and parse YAML frontmatter + body.

    Agent definition files are ``.md`` files inside *agents_dir* named
    ``{agent_name}.md``.  They may contain a YAML frontmatter block
    (between ``---`` delimiters) with keys ``name``, ``description``,
    ``model``, and a tool list (``- ToolName``).  The body after the
    frontmatter is used as the system prompt.

    No ``pyyaml`` dependency is required; frontmatter is parsed with a
    simple line-by-line scanner.

    Args:
        agent_name: Stem name of the agent (no ``.md`` extension).
        agents_dir: Directory containing agent definition files.

    Returns:
        Dict with keys ``name``, ``description``, ``model``, ``tools``
        (list[str]), ``system_prompt``, and optionally ``_warning``.
    """
    agents_path = Path(agents_dir)
    agent_file = agents_path / f"{agent_name}.md"

    if not agent_file.exists():
        default = dict(DEFAULT_AGENT_DEFINITION)
        default["name"] = agent_name
        default["_warning"] = f"Agent file not found: {agent_file}"
        return default

    try:
        raw = agent_file.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        default = dict(DEFAULT_AGENT_DEFINITION)
        default["name"] = agent_name
        default["_warning"] = f"Failed to read {agent_file}: {e}"
        return default

    result: dict[str, Any] = {
        "name": agent_name,
        "description": "",
        "model": "sonnet",
        "tools": [],
        "system_prompt": "",
    }

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", raw, re.DOTALL)
    if fm_match:
        frontmatter_text = fm_match.group(1)
        body = fm_match.group(2).strip()

        for line in frontmatter_text.splitlines():
            line = line.strip()
            if line.startswith("name:"):
                result["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                result["description"] = line.split(":", 1)[1].strip()
            elif line.startswith("model:"):
                result["model"] = line.split(":", 1)[1].strip()
            elif line.startswith("- "):
                result["tools"].append(line[2:].strip())

        result["system_prompt"] = body
    else:
        result["system_prompt"] = raw.strip()

    return result


# ---------------------------------------------------------------------------
# Inter-agent handoff management (extracted from brain/scripts/spawn.py)
# ---------------------------------------------------------------------------


def create_handoff(
    task_id: str,
    agent_name: str,
    output: str,
    handoff_dir: str | Path,
) -> str:
    """Write agent output to a handoff file for inter-agent communication.

    Creates ``{handoff_dir}/{task_id}_{agent_name}.md`` containing *output*.

    Args:
        task_id: Unique identifier for the task.
        agent_name: Name of the producing agent.
        output: The agent's output text to hand off.
        handoff_dir: Directory to write the handoff file into (created
            if it does not exist).

    Returns:
        Absolute path to the written handoff file.
    """
    handoff_path = Path(handoff_dir)
    handoff_path.mkdir(parents=True, exist_ok=True)
    filename = f"{task_id}_{agent_name}.md"
    path = handoff_path / filename
    path.write_text(output, encoding="utf-8")
    return str(path)


def read_handoff(
    task_id: str,
    from_agent: str,
    handoff_dir: str | Path,
) -> str:
    """Read a handoff file from a previous agent.

    Looks for ``{handoff_dir}/{task_id}_{from_agent}.md``.

    Args:
        task_id: Unique identifier for the task.
        from_agent: Name of the agent that produced the handoff.
        handoff_dir: Directory containing handoff files.

    Returns:
        The file contents, or an empty string if the file does not exist
        or cannot be read.
    """
    path = Path(handoff_dir) / f"{task_id}_{from_agent}.md"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    return ""
