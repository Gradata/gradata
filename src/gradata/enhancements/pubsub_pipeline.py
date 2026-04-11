"""Pub/sub event pipeline for decoupled correction processing.

Unlike learning_pipeline.py (sequential chain), this is a pub/sub system
where stages subscribe to event types independently. Stage failures don't
block other stages. Used for async/background processing patterns.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

_log = logging.getLogger(__name__)


class PubSubPipeline:
    """Lightweight pub/sub pipeline for correction processing.

    Each stage subscribes to an event type. When an event fires,
    all subscribers for that type run in registration order.
    Stage failures are logged but don't block other stages.
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._event_log: list[dict] = []

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> list[dict]:
        """Emit an event. Returns list of stage results."""
        results = []
        self._event_log.append({"type": event_type, "data": data})
        for handler in self._subscribers.get(event_type, []):
            try:
                result = handler(data or {})
                results.append({"handler": handler.__name__, "status": "ok", "result": result})
            except Exception as e:
                _log.warning("Pipeline stage %s failed: %s", handler.__name__, e)
                results.append({"handler": handler.__name__, "status": "error", "error": str(e)})
        return results

    @property
    def event_log(self) -> list[dict]:
        return list(self._event_log)
