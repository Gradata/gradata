"""Process-level brain directory lock for long-running services."""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from pathlib import Path
from types import TracebackType

from gradata.exceptions import BrainLockedError

_HELD_LOCKS: set[Path] = set()
_HELD_LOCKS_GUARD = threading.Lock()


class _BrainLock:
    def __init__(self, brain_dir: str | Path):
        self.brain_dir = Path(brain_dir).resolve()
        self.path = self.brain_dir / ".brain.lock"
        self._fh = None
        self._held_in_process = False

    def __enter__(self) -> _BrainLock:
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        with _HELD_LOCKS_GUARD:
            if self.brain_dir in _HELD_LOCKS:
                raise BrainLockedError(f"Brain is already locked: {self.brain_dir}")
            _HELD_LOCKS.add(self.brain_dir)
            self._held_in_process = True

        try:
            self._fh = self.path.open("a+b")
            if sys.platform == "win32":
                self._lock_windows()
            else:
                self._lock_posix()
            self._write_owner()
            return self
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._fh is not None:
            if sys.platform == "win32":
                self._unlock_windows()
            else:
                self._unlock_posix()
            with contextlib.suppress(OSError):
                self._fh.close()
            self._fh = None
        if self._held_in_process:
            with _HELD_LOCKS_GUARD:
                _HELD_LOCKS.discard(self.brain_dir)
            self._held_in_process = False

    def _write_owner(self) -> None:
        assert self._fh is not None
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(str(os.getpid()).encode("ascii"))
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def _lock_posix(self) -> None:
        import fcntl  # type: ignore[import]

        assert self._fh is not None
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise BrainLockedError(f"Brain is already locked: {self.brain_dir}") from exc

    def _unlock_posix(self) -> None:
        import fcntl  # type: ignore[import]

        assert self._fh is not None
        with contextlib.suppress(OSError):
            fcntl.flock(self._fh, fcntl.LOCK_UN)

    def _lock_windows(self) -> None:
        import msvcrt  # type: ignore[import]

        assert self._fh is not None
        self._fh.seek(0)
        try:
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BrainLockedError(f"Brain is already locked: {self.brain_dir}") from exc

    def _unlock_windows(self) -> None:
        import msvcrt  # type: ignore[import]

        assert self._fh is not None
        self._fh.seek(0)
        with contextlib.suppress(OSError):
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)


def acquire_brain_lock(brain_dir: str | Path) -> _BrainLock:
    """Return a context manager holding an exclusive service lock."""
    return _BrainLock(brain_dir)
