"""EventBus -- lightweight in-memory pub/sub for Gradata's nervous system.

This is the IN-MEMORY subscriber notification system. It does NOT persist events.
For event persistence (JSONL + SQLite), see _events.py / brain.emit().

Both systems fire in brain_correct() and brain_end_session() intentionally:
  - EventBus.emit() -> notifies in-memory subscribers (embeddings, session_history)
  - brain.emit() / _events.emit() -> writes to events.jsonl + system.db

Do NOT merge these two systems. They serve different purposes.
"""

from __future__ import annotations

import atexit
import logging
import threading
import weakref
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

MAX_LISTENERS_PER_EVENT = 50
MAX_ASYNC_WORKERS = 4

# Track all live EventBus instances so atexit can drain them. WeakSet so
# normal close() / GC doesn't keep them alive forever.
_LIVE_BUSES: weakref.WeakSet[EventBus] = weakref.WeakSet()
_ATEXIT_REGISTERED = False
_ATEXIT_LOCK = threading.Lock()


def _drain_all_buses_atexit() -> None:
    """Close any EventBus that survived to interpreter shutdown."""
    for bus in list(_LIVE_BUSES):
        try:
            bus.close(timeout=2.0)
        except Exception:
            logger.exception("EventBus atexit drain failed for %r", bus)


def _ensure_atexit_registered() -> None:
    global _ATEXIT_REGISTERED
    if _ATEXIT_REGISTERED:
        return
    with _ATEXIT_LOCK:
        if _ATEXIT_REGISTERED:
            return
        atexit.register(_drain_all_buses_atexit)
        _ATEXIT_REGISTERED = True


class EventBus:
    """In-process event bus with bounded listeners, thread safety, and thread pool.

    Lifecycle:
      bus = EventBus()
      bus.on("evt", handler)
      bus.emit("evt", payload)
      bus.close()                    # explicit shutdown — drains async work, rejects new

    Workers are atexit-registered so background threads cannot outlive the
    process even if a caller forgets to close().
    """

    def __init__(self) -> None:
        self.listeners: dict[str, list[tuple[Callable, bool]]] = defaultdict(list)
        self._pool = ThreadPoolExecutor(max_workers=MAX_ASYNC_WORKERS, thread_name_prefix="gradata-bus")
        self._lock = threading.Lock()
        self._closed = False
        _LIVE_BUSES.add(self)
        _ensure_atexit_registered()

    def on(self, event: str, handler: Callable, async_handler: bool = False) -> None:
        """Subscribe *handler* to *event*. Deduplicates and bounds per event."""
        with self._lock:
            if self._closed:
                logger.warning("EventBus.on() on closed bus; ignoring %r", event)
                return
            entries = self.listeners[event]
            if any(h is handler for h, _ in entries):
                return
            if len(entries) >= MAX_LISTENERS_PER_EVENT:
                logger.warning("EventBus: max listeners (%d) reached for %r", MAX_LISTENERS_PER_EVENT, event)
                return
            entries.append((handler, async_handler))

    def off(self, event: str, handler: Callable) -> None:
        """Remove *handler* from *event*."""
        with self._lock:
            entries = self.listeners.get(event, [])
            self.listeners[event] = [(h, a) for h, a in entries if h is not handler]

    def emit(self, event: str, payload: Any = None) -> None:
        """Emit *event* with *payload*. Errors are logged, never raised.

        After close(), emit() is a no-op (logged at DEBUG). This prevents
        late-shutdown handlers from raising RuntimeError on the dead pool.
        """
        with self._lock:
            if self._closed:
                logger.debug("EventBus.emit(%r) after close — dropped", event)
                return
            handlers = list(self.listeners.get(event, []))
        for handler, is_async in handlers:
            if is_async:
                try:
                    self._pool.submit(self._safe_call, handler, payload)
                except RuntimeError:
                    # Pool was shut down between the lock check and submit.
                    logger.debug("EventBus async submit after shutdown — dropped")
            else:
                self._safe_call(handler, payload)

    def close(self, timeout: float | None = None) -> None:
        """Drain async handlers and reject further work. Idempotent.

        Subsequent emit() / on() calls become no-ops.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self.listeners.clear()
            pool = self._pool
        pool.shutdown(wait=True, cancel_futures=False)
        if timeout is not None:
            # Best-effort: ThreadPoolExecutor has no per-call timeout, but
            # workers should already be drained by shutdown(wait=True). If
            # any thread is still alive after the wait, log it.
            for t in threading.enumerate():
                if t.name.startswith("gradata-bus") and t.is_alive():
                    t.join(timeout=timeout)

    # Backwards compat alias.
    shutdown = close

    @staticmethod
    def _safe_call(handler: Callable, payload: Any) -> None:
        try:
            handler(payload)
        except Exception:
            logger.exception("Handler %s raised an exception", handler)
