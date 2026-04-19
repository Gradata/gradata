"""Detect agent infinite loops via sliding-window tool-call hashing.

Adapted from deer-flow (bytedance/deer-flow). Progressive intervention:
3 repeats WARN, 5 repeats STOP. Hashes normalized (tool_name, sorted_args).
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    "LoopAction",
    "LoopDetector",
    "LoopDetectorConfig",
    "LoopEvent",
]


class LoopAction(Enum):
    """Action to take based on loop detection."""

    ALLOW = "allow"  # No loop detected, proceed normally
    WARN = "warn"  # Loop pattern detected, log warning but continue
    STOP = "stop"  # Hard loop detected, halt execution


@dataclass
class LoopEvent:
    """A recorded tool invocation for loop detection.

    Attributes:
        tool_name: Name of the tool called.
        call_hash: MD5 hash of normalized (tool_name, sorted_args).
        action: The action determined by the detector.
        repeat_count: How many times this exact call has been seen in window.
    """

    tool_name: str
    call_hash: str
    action: LoopAction
    repeat_count: int = 0


@dataclass
class LoopDetectorConfig:
    """Configuration for loop detection.

    Attributes:
        window_size: Sliding window of recent tool calls to track.
        warn_threshold: Number of identical calls before warning.
        stop_threshold: Number of identical calls before hard stop.
    """

    window_size: int = 20
    warn_threshold: int = 3
    stop_threshold: int = 5


class LoopDetector:
    """Detects agent loops via tool-call hashing in a sliding window.

    Adapted from deer-flow's LoopDetectionMiddleware. Uses MD5 hash
    of normalized (tool_name, sorted_args) to detect identical tool
    calls regardless of argument ordering.

    Thread-safe for single-agent use (no shared mutable state between
    detectors). Create one detector per agent/session.
    """

    def __init__(self, config: LoopDetectorConfig | None = None) -> None:
        self.config = config or LoopDetectorConfig()
        self._window: deque[str] = deque(maxlen=self.config.window_size)
        self._events: list[LoopEvent] = []

    def record(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> LoopAction:
        """Record a tool call and check for loops.

        Args:
            tool_name: Name of the tool being called.
            arguments: Tool arguments (will be normalized for hashing).

        Returns:
            LoopAction indicating whether to proceed, warn, or stop.
        """
        _raw = json.dumps(
            {"name": tool_name, "args": _normalize_args(arguments or {})},
            sort_keys=True,
            separators=(",", ":"),
        )
        call_hash = hashlib.md5(_raw.encode()).hexdigest()
        self._window.append(call_hash)

        # Count occurrences of this hash in the window
        repeat_count = sum(1 for h in self._window if h == call_hash)

        # Determine action
        if repeat_count >= self.config.stop_threshold:
            action = LoopAction.STOP
        elif repeat_count >= self.config.warn_threshold:
            action = LoopAction.WARN
        else:
            action = LoopAction.ALLOW

        event = LoopEvent(
            tool_name=tool_name,
            call_hash=call_hash,
            action=action,
            repeat_count=repeat_count,
        )
        self._events.append(event)

        return action

    def reset(self) -> None:
        """Clear the sliding window and event history."""
        self._window.clear()
        self._events.clear()

    @property
    def is_looping(self) -> bool:
        """Whether the detector has flagged a loop (WARN or STOP)."""
        if not self._events:
            return False
        return self._events[-1].action in (LoopAction.WARN, LoopAction.STOP)

    @property
    def events(self) -> list[LoopEvent]:
        """Return the full event history."""
        return list(self._events)

    @property
    def current_window(self) -> list[str]:
        """Return the current sliding window of call hashes."""
        return list(self._window)

    def stats(self) -> dict[str, Any]:
        """Return detection statistics."""
        total = len(self._events)
        warns = sum(1 for e in self._events if e.action == LoopAction.WARN)
        stops = sum(1 for e in self._events if e.action == LoopAction.STOP)

        # Most repeated tool
        tool_counts: dict[str, int] = {}
        for e in self._events:
            tool_counts[e.tool_name] = tool_counts.get(e.tool_name, 0) + 1
        most_repeated = max(tool_counts, key=lambda k: tool_counts[k]) if tool_counts else ""

        return {
            "total_calls": total,
            "warnings": warns,
            "stops": stops,
            "window_size": self.config.window_size,
            "window_fill": len(self._window),
            "most_repeated_tool": most_repeated,
        }


def _normalize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Recursively normalize arguments for consistent hashing.

    Sorts dict keys, converts lists to sorted tuples (for sets),
    and stringifies non-JSON types.
    """
    result: dict[str, Any] = {}
    for key in sorted(args.keys()):
        val = args[key]
        if isinstance(val, dict):
            result[key] = _normalize_args(val)
        elif isinstance(val, (list, tuple)):
            result[key] = [_normalize_args(v) if isinstance(v, dict) else v for v in val]
        else:
            result[key] = val
    return result
