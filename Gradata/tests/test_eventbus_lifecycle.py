"""EventBus lifecycle and thread-safety regressions."""

from __future__ import annotations

import gc
import os
import threading
import time

from gradata import Brain
from gradata.events_bus import EventBus


def _bus_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith("gradata-bus")]


def test_subscribe_unsubscribe_under_concurrent_load() -> None:
    bus = EventBus()
    calls = 0
    calls_lock = threading.Lock()

    def handler(payload: object) -> None:
        nonlocal calls
        with calls_lock:
            calls += 1

    def worker() -> None:
        for _ in range(200):
            bus.on("evt", handler)
            bus.emit("evt", {})
            bus.off("evt", handler)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert calls >= 1
    bus.close()
    assert _bus_threads() == []


def test_eventbus_close_waits_for_executor_and_rejects_late_work() -> None:
    bus = EventBus()
    finished = threading.Event()
    late_calls = 0

    def async_handler(payload: object) -> None:
        time.sleep(0.01)
        finished.set()

    def late_handler(payload: object) -> None:
        nonlocal late_calls
        late_calls += 1

    bus.on("evt", async_handler, async_handler=True)
    bus.emit("evt", {})
    bus.close()
    bus.on("evt", late_handler)
    bus.emit("evt", {})

    assert finished.is_set()
    assert late_calls == 0
    assert _bus_threads() == []


def test_brain_close_cleans_eventbus_executor_across_many_cycles(tmp_path) -> None:
    before = threading.active_count()

    for idx in range(100):
        brain_dir = tmp_path / f"brain-{idx}"
        os.environ["BRAIN_DIR"] = str(brain_dir)
        brain = Brain.init(
            brain_dir,
            name=f"Lifecycle {idx}",
            domain="Testing",
            embedding="local",
            interactive=False,
        )
        done = threading.Event()
        brain.bus.on("evt", lambda payload, done=done: done.set(), async_handler=True)
        brain.bus.emit("evt", {})
        brain.close()
        assert done.is_set()

    gc.collect()
    deadline = time.time() + 5
    while _bus_threads() and time.time() < deadline:
        time.sleep(0.01)

    assert _bus_threads() == []
    assert threading.active_count() <= before + 2
