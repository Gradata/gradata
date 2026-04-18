"""
Observation Hooks — 100% deterministic tool-use observation capture.
=====================================================================
Adapted from: everything-claude-code (affaan-m/everything-claude-code)
continuous-learning-v2/hooks/observe.sh

Captures every tool invocation as a structured observation for the
learning pipeline. Project-scoped via git remote hash for portable
cross-machine identification. Feeds into the graduation engine.

Unlike probabilistic sampling, this fires on 100% of tool calls
to ensure no patterns are missed.

Usage::

    from .observation_hooks import (
        ObservationStore, Observation, ProjectDetector,
        observe_tool_use, get_project_id,
    )

    store = ObservationStore(base_dir=Path("~/.gradata/observations"))
    obs = observe_tool_use(
        tool_name="Bash",
        input_data={"command": "pytest"},
        output_data={"exit_code": 0},
        session_id="s42",
    )
    store.append(obs)
"""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "Observation",
    "ObservationStore",
    "observe_tool_use",
]


@dataclass
class Observation:
    """A single observed tool invocation.

    Attributes:
        timestamp: Unix timestamp of the observation.
        tool_name: Name of the tool invoked (e.g. "Bash", "Edit", "Write").
        input_summary: Summarized input (truncated for storage efficiency).
        output_summary: Summarized output (truncated).
        session_id: Current session identifier.
        project_id: Portable project identifier (git remote hash).
        duration_ms: How long the tool call took (0 if unknown).
        success: Whether the tool call succeeded.
        metadata: Arbitrary metadata.
    """
    timestamp: float
    tool_name: str
    input_summary: str = ""
    output_summary: str = ""
    session_id: str = ""
    project_id: str = ""
    duration_ms: int = 0
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        """Serialize to a single JSONL line."""
        return json.dumps(asdict(self), separators=(",", ":"))


import re as _re

# PII patterns to redact from observations before storage
_PII_PATTERNS = [
    (_re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
    (_re.compile(r'(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b'), '[PHONE]'),
    (_re.compile(r'\b(?:sk-|api[_-]?key[=:]\s*)[A-Za-z0-9_-]{10,}\b', _re.I), '[API_KEY]'),
    (_re.compile(r'\b(?:token[=:]\s*|bearer\s+)[A-Za-z0-9_.-]{10,}\b', _re.I), '[TOKEN]'),
    (_re.compile(r'\b(?:password[=:]\s*|passwd[=:]\s*)\S+', _re.I), '[PASSWORD]'),
    (_re.compile(r'-----BEGIN [A-Z ]+-----'), '[PRIVATE_KEY]'),
]


def observe_tool_use(
    tool_name: str,
    input_data: Any = None,
    output_data: Any = None,
    session_id: str = "",
    project_id: str = "",
    duration_ms: int = 0,
    success: bool = True,
    max_summary_len: int = 500,
) -> Observation:
    """Create an observation from a tool invocation.

    Truncates input/output to max_summary_len characters for storage
    efficiency while preserving enough context for pattern detection.

    Args:
        tool_name: Name of the tool invoked.
        input_data: Raw input (will be str-ified and truncated).
        output_data: Raw output (will be str-ified and truncated).
        session_id: Current session identifier.
        project_id: Portable project identifier.
        duration_ms: Tool call duration in milliseconds.
        success: Whether the call succeeded.
        max_summary_len: Max characters for input/output summaries.

    Returns:
        A structured Observation.
    """
    def _summarize(data: Any) -> str:
        if data is None:
            return ""
        text = str(data) if not isinstance(data, str) else data
        for _rp_pat, _rp_rep in _PII_PATTERNS:
            text = _rp_pat.sub(_rp_rep, text)
        if len(text) > max_summary_len:
            return text[:max_summary_len] + "..."
        return text

    return Observation(
        timestamp=time.time(),
        tool_name=tool_name,
        input_summary=_summarize(input_data),
        output_summary=_summarize(output_data),
        session_id=session_id,
        project_id=project_id,
        duration_ms=duration_ms,
        success=success,
    )



class ObservationStore:
    """Append-only JSONL store for observations, scoped by project.

    Storage layout::

        base_dir/
        ├── global/
        │   └── observations.jsonl
        └── projects/
            └── <project-hash>/
                └── observations.jsonl

    Args:
        base_dir: Root directory for observation storage.
        max_file_size_mb: Max size per JSONL file before rotation.
    """

    def __init__(
        self,
        base_dir: Path | str,
        max_file_size_mb: float = 10.0,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)

    def _get_file(self, project_id: str) -> Path:
        """Get the observations file path for a project."""
        if project_id == "global":
            path = self.base_dir / "global"
        else:
            path = self.base_dir / "projects" / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path / "observations.jsonl"

    def append(self, observation: Observation) -> Path:
        """Append an observation to the project-scoped store.

        Args:
            observation: The observation to store.

        Returns:
            Path to the file the observation was written to.
        """
        project_id = observation.project_id or "global"
        filepath = self._get_file(project_id)

        # Rotate if file too large
        if filepath.exists() and filepath.stat().st_size > self.max_file_size_bytes:
            # Use time_ns to avoid filename collisions within same second
            rotated = filepath.with_suffix(f".{time.time_ns()}.jsonl")
            with contextlib.suppress(OSError):
                filepath.rename(rotated)

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(observation.to_jsonl() + "\n")

        return filepath

    def read_recent(
        self,
        project_id: str = "global",
        limit: int = 100,
    ) -> list[Observation]:
        """Read the most recent observations for a project.

        Args:
            project_id: The project identifier.
            limit: Maximum number of observations to return.

        Returns:
            List of Observation objects, most recent first.
        """
        filepath = self._get_file(project_id)
        if not filepath.exists():
            return []

        lines: list[str] = []
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()

        # Take last N lines
        recent_lines = lines[-limit:] if len(lines) > limit else lines
        recent_lines.reverse()  # Most recent first

        observations: list[Observation] = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                observations.append(Observation(**data))
            except (json.JSONDecodeError, TypeError):
                continue

        return observations

    def count(self, project_id: str = "global") -> int:
        """Count total observations for a project."""
        filepath = self._get_file(project_id)
        if not filepath.exists():
            return 0
        with open(filepath, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def stats(self, project_id: str = "global") -> dict[str, Any]:
        """Get storage statistics for a project."""
        filepath = self._get_file(project_id)
        if not filepath.exists():
            return {"count": 0, "size_bytes": 0, "file": str(filepath)}
        return {
            "count": self.count(project_id),
            "size_bytes": filepath.stat().st_size,
            "file": str(filepath),
        }
