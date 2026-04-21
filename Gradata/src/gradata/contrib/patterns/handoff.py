"""Context-pressure handoff watchdog.

Monitors token-budget consumption and triggers a preemptive handoff
synthesis before automatic compaction occurs. The goal is UX continuity:
the next agent reads a compact resume doc and picks up in the same
place, instead of losing nuance to auto-compaction.

Threshold defaults to 0.65 (65%) and is overridable via the
``GRADATA_HANDOFF_THRESHOLD`` environment variable.

See GitHub issue #127.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


_DEFAULT_THRESHOLD = 0.65
_MIN_THRESHOLD = 0.10
_MAX_THRESHOLD = 0.95


def _read_threshold() -> float:
    raw = os.environ.get("GRADATA_HANDOFF_THRESHOLD", "")
    if not raw:
        return _DEFAULT_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_THRESHOLD
    if value < _MIN_THRESHOLD or value > _MAX_THRESHOLD:
        return _DEFAULT_THRESHOLD
    return value


def measure_pressure(tokens_used: int, tokens_max: int) -> float:
    """Return fraction of the context budget consumed, clamped to [0.0, 1.0]."""
    if tokens_max <= 0:
        return 0.0
    ratio = tokens_used / tokens_max
    if ratio < 0.0:
        return 0.0
    if ratio > 1.0:
        return 1.0
    return ratio


@dataclass
class HandoffDoc:
    """Compact resume document written when the watchdog fires.

    Intentionally small: the next agent's system prompt has a budget too.
    """

    task_id: str
    agent_name: str
    summary: str
    open_questions: list[str] = field(default_factory=list)
    next_action: str = ""
    artifacts: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def render(self) -> str:
        """Return the doc as a stable Markdown string.

        Shape is fixed so the next agent can pattern-match reliably.
        """
        lines = [
            f"# Handoff — {self.task_id}",
            f"_from_: {self.agent_name}  _at_: {self.created_at}",
            "",
            "## Where we left off",
            self.summary.strip() or "(no summary provided)",
        ]
        if self.next_action:
            lines += ["", "## Next action", self.next_action.strip()]
        if self.open_questions:
            lines += ["", "## Open questions"]
            lines += [f"- {q}" for q in self.open_questions]
        if self.artifacts:
            lines += ["", "## Artifacts"]
            lines += [f"- {a}" for a in self.artifacts]
        return "\n".join(lines) + "\n"


@dataclass
class HandoffWatchdog:
    """Threshold-triggered handoff emitter.

    Call :meth:`check` with the current token counts. When pressure
    crosses the configured threshold, the synthesizer is invoked, the
    resulting :class:`HandoffDoc` is written to ``handoff_dir``, and
    an event is emitted. Subsequent calls are no-ops until :meth:`reset`
    is called (e.g., after the next agent spins up).
    """

    task_id: str
    agent_name: str
    handoff_dir: Path
    synthesizer: Callable[[], HandoffDoc]
    threshold: float = field(default_factory=_read_threshold)
    _fired: bool = field(default=False, init=False, repr=False, compare=False)

    def check(self, tokens_used: int, tokens_max: int) -> HandoffDoc | None:
        """Trigger handoff synthesis if pressure >= threshold and not yet fired.

        Returns the written :class:`HandoffDoc` on first trigger, else None.
        """
        if self._fired:
            return None
        pressure = measure_pressure(tokens_used, tokens_max)
        if pressure < self.threshold:
            return None

        doc = self.synthesizer()
        self._write(doc)
        self._emit(pressure, doc)
        self._fired = True
        return doc

    def reset(self) -> None:
        """Allow the watchdog to fire again. Call after a fresh agent starts."""
        self._fired = False

    def _write(self, doc: HandoffDoc) -> None:
        self.handoff_dir.mkdir(parents=True, exist_ok=True)
        path = self.handoff_dir / f"{doc.task_id}_{doc.agent_name}.handoff.md"
        path.write_text(doc.render(), encoding="utf-8")

    def _emit(self, pressure: float, doc: HandoffDoc) -> None:
        try:
            from gradata import _events as events
        except ImportError:
            return
        events.emit(
            event_type="handoff.triggered",
            source="handoff_watchdog",
            data={
                "task_id": doc.task_id,
                "agent_name": doc.agent_name,
                "pressure": round(pressure, 3),
                "threshold": round(self.threshold, 3),
            },
            tags=["handoff", "context_pressure"],
        )


def load_handoff(task_id: str, agent_name: str, handoff_dir: Path) -> str | None:
    """Read a previously written handoff for the given task/agent, if any."""
    path = Path(handoff_dir) / f"{task_id}_{agent_name}.handoff.md"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


__all__ = [
    "HandoffDoc",
    "HandoffWatchdog",
    "load_handoff",
    "measure_pressure",
]
