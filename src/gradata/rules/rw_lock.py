"""Reader-writer lock for concurrent brain access."""

from __future__ import annotations

import threading
from contextlib import contextmanager


class RWLock:
    """Multiple readers OR one writer. No starvation."""

    def __init__(self):
        self._lock = threading.Lock()
        self._readers = 0
        self._writer_event = threading.Event()
        self._writer_event.set()  # no writer initially

    def acquire_read(self):
        self._writer_event.wait()
        with self._lock:
            self._readers += 1

    def release_read(self):
        with self._lock:
            self._readers -= 1
            if self._readers == 0:
                self._writer_event.set()

    def acquire_write(self):
        self._writer_event.clear()
        # Wait for readers to finish
        while True:
            with self._lock:
                if self._readers == 0:
                    return

    def release_write(self):
        self._writer_event.set()

    @contextmanager
    def read_lock(self):
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()

    @contextmanager
    def write_lock(self):
        self.acquire_write()
        try:
            yield
        finally:
            self.release_write()
