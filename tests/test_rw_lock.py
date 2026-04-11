"""Tests for reader-writer lock."""

import threading
import time

from gradata.rules.rw_lock import RWLock


class TestRWLock:
    def test_read_lock_context_manager(self):
        lock = RWLock()
        with lock.read_lock():
            assert lock._readers == 1
        assert lock._readers == 0

    def test_multiple_readers(self):
        lock = RWLock()
        lock.acquire_read()
        lock.acquire_read()
        assert lock._readers == 2
        lock.release_read()
        lock.release_read()

    def test_write_lock_context_manager(self):
        lock = RWLock()
        with lock.write_lock():
            assert not lock._writer_event.is_set()
        assert lock._writer_event.is_set()

    def test_write_excludes_new_reads(self):
        lock = RWLock()
        results = []
        lock.acquire_write()

        def try_read():
            lock.acquire_read()
            results.append("read")
            lock.release_read()

        t = threading.Thread(target=try_read)
        t.start()
        time.sleep(0.1)
        assert results == []  # read blocked
        lock.release_write()
        t.join(timeout=1)
        assert results == ["read"]
