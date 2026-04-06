"""EventBus — lightweight in-memory pub/sub for Gradata's nervous system.

This is the IN-MEMORY subscriber notification system. It does NOT persist events.
For event persistence (JSONL + SQLite), see _events.py / brain.emit().

Both systems fire in brain_correct() and brain_end_session() intentionally:
  - EventBus.emit() → notifies in-memory subscribers (embeddings, session_history)
  - brain.emit() / _events.emit() → writes to events.jsonl + system.db

Do NOT merge these two systems. They serve different purposes.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventBus:
    """In-process event bus with timeout and async-handler support.

    Parameters
    ----------
    handler_timeout:
        Max seconds a synchronous handler may run before the bus moves on.
        Default 5.0.
    """

    def __init__(self, handler_timeout: float = 5.0) -> None:
        self.listeners: dict[str, list[tuple[Callable, bool]]] = defaultdict(list)
        self.handler_timeout = handler_timeout
        self._lock = threading.Lock()

    # -- public API -----------------------------------------------------------

    def on(self, event: str, handler: Callable, async_handler: bool = False) -> None:
        """Subscribe *handler* to *event*.

        If *async_handler* is True the handler runs in a daemon thread
        (fire-and-forget) instead of blocking the caller.
        """
        with self._lock:
            if not any(h is handler for h, _ in self.listeners[event]):
                self.listeners[event].append((handler, async_handler))

    def off(self, event: str, handler: Callable) -> None:
        """Remove *handler* from *event*."""
        with self._lock:
            entries = self.listeners.get(event, [])
            self.listeners[event] = [(h, a) for h, a in entries if h is not handler]

    def emit(self, event: str, payload: Any = None) -> None:
        """Emit *event* with *payload*.  Errors are logged, never raised."""
        with self._lock:
            handlers = list(self.listeners.get(event, []))
        for handler, is_async in handlers:
            if is_async:
                threading.Thread(target=self._safe_call, args=(handler, payload, self.handler_timeout), daemon=True).start()
            else:
                self._safe_call(handler, payload, self.handler_timeout)

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _safe_call(handler: Callable, payload: Any, timeout: float = 5.0) -> None:
        """Call *handler* with a timeout guard for synchronous handlers.

        Uses a daemon thread + join(timeout) so a hung handler doesn't
        block the emit loop forever.
        """
        result: list[Exception | None] = [None]

        def _run() -> None:
            try:
                handler(payload)
            except Exception as exc:
                result[0] = exc

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            logger.warning("Handler %s exceeded timeout (%.1fs), moving on", handler, timeout)
        elif result[0] is not None:
            logger.exception("Handler %s raised an exception", handler, exc_info=result[0])
