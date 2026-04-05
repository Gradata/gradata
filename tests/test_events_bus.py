"""Tests for EventBus — nervous system integration."""

import threading
import time

import pytest

from gradata.events_bus import EventBus


class TestEventBus:
    def setup_method(self):
        self.bus = EventBus()

    def test_on_and_emit(self):
        received = []
        self.bus.on("test", lambda payload: received.append(payload))
        self.bus.emit("test", {"key": "value"})
        assert received == [{"key": "value"}]

    def test_multiple_handlers(self):
        results = []
        self.bus.on("evt", lambda p: results.append("a"))
        self.bus.on("evt", lambda p: results.append("b"))
        self.bus.emit("evt", {})
        assert sorted(results) == ["a", "b"]

    def test_off_removes_handler(self):
        calls = []
        handler = lambda p: calls.append(1)
        self.bus.on("evt", handler)
        self.bus.off("evt", handler)
        self.bus.emit("evt", {})
        assert calls == []

    def test_emit_unknown_event_is_noop(self):
        # Should not raise
        self.bus.emit("nonexistent", {"data": 1})

    def test_handler_error_does_not_propagate(self):
        results = []

        def bad_handler(p):
            raise RuntimeError("boom")

        def good_handler(p):
            results.append("ok")

        self.bus.on("evt", bad_handler)
        self.bus.on("evt", good_handler)
        self.bus.emit("evt", {})
        assert results == ["ok"]

    def test_handler_timeout(self):
        # Sync handlers run directly (no timeout). Async handlers are fire-and-forget.
        # This test verifies a slow async handler doesn't block emit().
        bus = EventBus()

        def slow_handler(p):
            time.sleep(5)

        bus.on("evt", slow_handler, async_handler=True)
        start = time.time()
        bus.emit("evt", {})
        elapsed = time.time() - start
        assert elapsed < 1.0, f"async emit blocked for {elapsed:.1f}s, expected < 1s"

    def test_async_handler(self):
        result = threading.Event()

        def bg_handler(p):
            time.sleep(0.1)
            result.set()

        self.bus.on("evt", bg_handler, async_handler=True)
        self.bus.emit("evt", {})
        # emit should return quickly since handler is async
        assert result.wait(timeout=3.0), "async handler did not complete"

    def test_event_names(self):
        self.bus.on("alpha", lambda p: None)
        self.bus.on("beta", lambda p: None)
        assert "alpha" in self.bus.listeners
        assert "beta" in self.bus.listeners
