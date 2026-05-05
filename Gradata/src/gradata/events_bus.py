"""EventBus -- lightweight in-memory pub/sub for Gradata's nervous system.

This is the IN-MEMORY subscriber notification system. It does NOT persist events.
For event persistence (JSONL + SQLite), see _events.py / brain.emit().

Both systems fire in brain_correct() and brain_end_session() intentionally:
  - EventBus.emit() -> notifies in-memory subscribers (embeddings, session_history)
  - brain.emit() / _events.emit() -> writes to events.jsonl + system.db

Do NOT merge these two systems. They serve different purposes.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

MAX_LISTENERS_PER_EVENT = 50
MAX_ASYNC_WORKERS = 4


class EventBus:
    """In-process event bus with bounded listeners, thread safety, and thread pool."""

    def __init__(self) -> None:
        self.listeners: dict[str, list[tuple[Callable, bool]]] = defaultdict(list)
        self._pool = ThreadPoolExecutor(
            max_workers=MAX_ASYNC_WORKERS, thread_name_prefix="gradata-bus"
        )
        self._lock = threading.Lock()

    def on(self, event: str, handler: Callable, async_handler: bool = False) -> None:
        """Subscribe *handler* to *event*. Deduplicates and bounds per event."""
        with self._lock:
            entries = self.listeners[event]
            if any(h is handler for h, _ in entries):
                return
            if len(entries) >= MAX_LISTENERS_PER_EVENT:
                logger.warning(
                    "EventBus: max listeners (%d) reached for %r", MAX_LISTENERS_PER_EVENT, event
                )
                return
            entries.append((handler, async_handler))

    def off(self, event: str, handler: Callable) -> None:
        """Remove *handler* from *event*."""
        with self._lock:
            entries = self.listeners.get(event, [])
            self.listeners[event] = [(h, a) for h, a in entries if h is not handler]

    def emit(self, event: str, payload: Any = None) -> None:
        """Emit *event* with *payload*. Errors are logged, never raised."""
        with self._lock:
            handlers = list(self.listeners.get(event, []))
        for handler, is_async in handlers:
            if is_async:
                self._pool.submit(self._safe_call, handler, payload)
            else:
                self._safe_call(handler, payload)

    @staticmethod
    def _safe_call(handler: Callable, payload: Any) -> None:
        try:
            handler(payload)
        except Exception:
            logger.exception("Handler %s raised an exception", handler)
