"""
Tests for gradata._file_lock.platform_lock — cross-platform advisory locking.

Run: pytest tests/test_file_lock.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from gradata._file_lock import platform_lock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_via_lock(path: Path, payload: bytes, results: list, idx: int) -> None:
    """Thread target: acquire platform_lock and append payload."""
    try:
        with open(path, "ab") as fh:
            with platform_lock(fh):
                fh.seek(0, 2)
                fh.write(payload)
                fh.flush()
        results[idx] = "ok"
    except Exception as exc:  # pragma: no cover
        results[idx] = repr(exc)


# ---------------------------------------------------------------------------
# 1. timeout=None — blocks indefinitely (matches pre-refactor behaviour)
# ---------------------------------------------------------------------------

class TestTimeoutNone:
    """platform_lock(fh, timeout=None) must not raise and must write correctly."""

    def test_writes_data_under_lock(self, tmp_path):
        """Basic smoke-test: data written inside the context manager is persisted."""
        target = tmp_path / "events.jsonl"
        payload = b'{"type":"test"}\n'
        with open(target, "ab") as fh:
            with platform_lock(fh):
                fh.seek(0, 2)
                fh.write(payload)
                fh.flush()
        assert target.read_bytes() == payload

    def test_lock_released_after_block(self, tmp_path):
        """Verify the lock is released so a second acquisition on the same file succeeds."""
        target = tmp_path / "events.jsonl"
        target.touch()
        with open(target, "ab") as fh:
            with platform_lock(fh):
                pass  # hold and release
        # A second open + lock must succeed (no hang / error).
        with open(target, "ab") as fh2:
            with platform_lock(fh2):
                fh2.write(b"second\n")
                fh2.flush()
        assert b"second" in target.read_bytes()

    def test_lock_released_on_exception(self, tmp_path):
        """Lock must be released even when the body raises."""
        target = tmp_path / "events.jsonl"
        target.touch()
        with open(target, "ab") as fh:
            try:
                with platform_lock(fh):
                    raise ValueError("boom")
            except ValueError:
                pass
        # Must be able to re-acquire immediately.
        with open(target, "ab") as fh2:
            with platform_lock(fh2):
                fh2.write(b"after_error\n")
                fh2.flush()
        assert b"after_error" in target.read_bytes()


# ---------------------------------------------------------------------------
# 2. Timeout success — lock acquired before deadline
# ---------------------------------------------------------------------------

class TestTimeoutSuccess:
    """When the lock is free, timeout path must acquire and release cleanly."""

    def test_acquires_immediately_when_free(self, tmp_path):
        target = tmp_path / "events.jsonl"
        target.touch()
        with open(target, "ab") as fh:
            with platform_lock(fh, timeout=5.0):
                fh.seek(0, 2)
                fh.write(b"with_timeout\n")
                fh.flush()
        assert b"with_timeout" in target.read_bytes()


# ---------------------------------------------------------------------------
# 3. Timeout failure — deadline exceeded → TimeoutError
# ---------------------------------------------------------------------------

class TestTimeoutFailure:
    """When the lock cannot be acquired within timeout, TimeoutError is raised."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows: mocked separately below")
    def test_posix_timeout_raises(self, tmp_path):
        """Simulate POSIX lock held by another process — every flock call raises OSError."""
        import fcntl

        target = tmp_path / "events.jsonl"
        target.touch()

        with open(target, "ab") as fh:
            with patch("fcntl.flock", side_effect=OSError("locked")):
                with pytest.raises(TimeoutError, match="Could not acquire lock"):
                    with platform_lock(fh, timeout=0.05):
                        pass  # should not reach here

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only msvcrt path")
    def test_win32_timeout_raises(self, tmp_path):
        """Simulate Windows lock held — every LK_NBLCK call raises OSError."""
        import msvcrt

        target = tmp_path / "events.jsonl"
        target.touch()

        with open(target, "ab") as fh:
            with patch("msvcrt.locking", side_effect=OSError("locked")):
                with pytest.raises(TimeoutError, match="Could not acquire lock"):
                    with platform_lock(fh, timeout=0.05):
                        pass


# ---------------------------------------------------------------------------
# 4. Concurrent access simulation — no data interleaving
# ---------------------------------------------------------------------------

class TestConcurrentAccess:
    """Multiple threads writing through platform_lock must not interleave lines."""

    def test_concurrent_writes_produce_intact_lines(self, tmp_path):
        """Each thread writes a single complete JSON line; all lines must be intact."""
        target = tmp_path / "events.jsonl"
        target.touch()

        n_threads = 8
        results = [None] * n_threads
        threads = [
            threading.Thread(
                target=_write_via_lock,
                args=(target, f'{{"i":{i}}}\n'.encode(), results, i),
            )
            for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Every result must be "ok".
        assert all(r == "ok" for r in results), results

        # Every line written must be a complete, parseable JSON object.
        import json
        lines = [ln for ln in target.read_text().splitlines() if ln.strip()]
        assert len(lines) == n_threads
        parsed = {json.loads(ln)["i"] for ln in lines}
        assert parsed == set(range(n_threads))


# ---------------------------------------------------------------------------
# 5. OSError fallthrough — no timeout, lock fails → proceeds unlocked
# ---------------------------------------------------------------------------

class TestOSErrorFallthrough:
    """Without a timeout, an OSError on lock acquisition must NOT propagate."""

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX path tested here")
    def test_posix_oserror_proceeds_unlocked(self, tmp_path):
        import fcntl

        target = tmp_path / "events.jsonl"
        target.touch()

        with open(target, "ab") as fh:
            with patch("fcntl.flock", side_effect=OSError("simulated")):
                # Should NOT raise — falls through and yields without a lock.
                with platform_lock(fh):
                    fh.seek(0, 2)
                    fh.write(b"unlocked_fallthrough\n")
                    fh.flush()

        assert b"unlocked_fallthrough" in target.read_bytes()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows path tested here")
    def test_win32_oserror_proceeds_unlocked(self, tmp_path):
        import msvcrt

        target = tmp_path / "events.jsonl"
        target.touch()

        with open(target, "ab") as fh:
            with patch("msvcrt.locking", side_effect=OSError("simulated")):
                with platform_lock(fh):
                    fh.seek(0, 2)
                    fh.write(b"unlocked_fallthrough\n")
                    fh.flush()

        assert b"unlocked_fallthrough" in target.read_bytes()
