"""Cross-platform advisory exclusive file-lock context manager.

Windows: msvcrt.locking on byte 0 (caller must seek to 0 first).
POSIX: fcntl.flock(LOCK_EX) — process-level, sufficient for events.jsonl.
timeout=None blocks indefinitely; timeout=<s> retries with exponential
backoff (0.01→0.1s cap) and raises TimeoutError. On OSError with no
timeout, falls through unlocked rather than dropping data (advisory only).
"""

from __future__ import annotations

import contextlib
import sys
import time
from collections.abc import Generator
from typing import IO

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKOFF_START = 0.01  # seconds
_BACKOFF_CAP = 0.10  # seconds
_BACKOFF_MULT = 2.0


def _backoff_intervals(
    start: float = _BACKOFF_START, cap: float = _BACKOFF_CAP, mult: float = _BACKOFF_MULT
):
    """Yield truncated exponential backoff intervals forever."""
    interval = start
    while True:
        yield interval
        interval = min(interval * mult, cap)


# ---------------------------------------------------------------------------
# Windows implementation
# ---------------------------------------------------------------------------


def _lock_win32(fh: IO, timeout: float | None) -> bool:
    """Acquire msvcrt advisory lock on byte 0.

    Returns True if locked, False if OSError without timeout (fall-through).
    Raises TimeoutError if timeout is exceeded.
    """
    import msvcrt  # type: ignore[import]

    # msvcrt.locking locks *nbytes* bytes at the CURRENT file position, so we
    # must be at 0 to make every writer contend on the same range.
    fh.seek(0)

    if timeout is None:
        # Blocking mode — matches original behaviour.
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        except OSError:
            return False  # fallthrough: proceed unlocked
        return True

    # Non-blocking retry loop.
    deadline = time.monotonic() + timeout
    for interval in _backoff_intervals():
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True  # acquired
        except OSError:
            pass
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Could not acquire lock on {fh.name} within {timeout}s")
        time.sleep(min(interval, remaining))

    # Unreachable, but satisfies type checker.
    raise TimeoutError(f"Could not acquire lock on {fh.name} within {timeout}s")  # pragma: no cover


# ---------------------------------------------------------------------------
# POSIX implementation
# ---------------------------------------------------------------------------


def _lock_posix(fh: IO, timeout: float | None) -> bool:
    """Acquire fcntl exclusive lock.

    Returns True if locked, False if OSError without timeout (fall-through).
    Raises TimeoutError if timeout is exceeded.
    """
    import fcntl  # type: ignore[import]

    if timeout is None:
        # Blocking mode — matches original behaviour.
        try:
            fcntl.flock(fh, fcntl.LOCK_EX)
        except OSError:
            return False
        return True

    # Non-blocking retry loop.
    deadline = time.monotonic() + timeout
    for interval in _backoff_intervals():
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            pass
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Could not acquire lock on {fh.name} within {timeout}s")
        time.sleep(min(interval, remaining))

    raise TimeoutError(f"Could not acquire lock on {fh.name} within {timeout}s")  # pragma: no cover


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def platform_lock(fh: IO, *, timeout: float | None = None) -> Generator[None, None, None]:
    """Advisory exclusive lock on an open file handle.

    Windows: ``msvcrt.locking`` on byte 0.  If *timeout* is given, retries
    ``LK_NBLCK`` with truncated exponential backoff until timeout, then raises
    ``TimeoutError``.

    POSIX: ``fcntl.flock(LOCK_EX)``.  If *timeout* is given, retries
    ``LOCK_EX | LOCK_NB`` with backoff until timeout, then raises
    ``TimeoutError``.

    If *timeout* is ``None`` (default), blocks indefinitely — this exactly
    matches the pre-refactor behaviour of ``_locked_append_many``.

    On lock acquisition failure without a timeout, falls through and yields
    without holding a lock (matches pre-refactor silent-fallthrough).

    Parameters
    ----------
    fh:
        An open file handle (binary or text mode).
    timeout:
        Maximum seconds to wait for the lock.  ``None`` = wait forever.
    """
    if sys.platform == "win32":
        import msvcrt  # type: ignore[import]

        locked = _lock_win32(fh, timeout)
        try:
            yield
        finally:
            if locked:
                fh.seek(0)
                with contextlib.suppress(OSError):
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl  # type: ignore[import]

        locked = _lock_posix(fh, timeout)
        try:
            yield
        finally:
            if locked:
                with contextlib.suppress(OSError):
                    fcntl.flock(fh, fcntl.LOCK_UN)
