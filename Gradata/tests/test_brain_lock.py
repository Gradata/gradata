"""Brain service lock tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gradata._brain_lock import acquire_brain_lock
from gradata.exceptions import BrainLockedError


class MockDaemon:
    def __init__(self, brain_dir: Path):
        self._lock_cm = acquire_brain_lock(brain_dir)

    def start(self) -> None:
        self._lock_cm.__enter__()

    def stop(self) -> None:
        self._lock_cm.__exit__(None, None, None)


def test_second_mock_daemon_raises_brain_locked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        brain_dir = Path(tmp) / "brain"
        brain_dir.mkdir()

        first = MockDaemon(brain_dir)
        second = MockDaemon(brain_dir)
        first.start()
        try:
            try:
                second.start()
            except BrainLockedError:
                return
        finally:
            first.stop()
    raise AssertionError("expected BrainLockedError")
