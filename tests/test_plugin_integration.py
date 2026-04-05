"""Integration test: daemon receives correction, extracts instruction, rules inject on next call."""
import json
import threading
import time
import urllib.request

import pytest
from pathlib import Path

from tests.conftest import init_brain


@pytest.fixture
def running_daemon(tmp_path):
    """Start a daemon with a fresh brain, return (url, brain_dir)."""
    brain = init_brain(tmp_path)
    brain_dir = brain.dir

    from gradata.daemon import GradataDaemon
    d = GradataDaemon(str(brain_dir), port=0)

    # Event to signal the server is ready
    ready = threading.Event()
    original_start = d.start

    def _start_and_signal():
        # Monkey-patch: we know start() sets self._port before serve_forever()
        original_start()

    t = threading.Thread(target=_start_and_signal, daemon=True)
    t.start()

    # Wait for the server to bind — port changes from 0 once _try_bind runs
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if d._server is not None:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Daemon did not start within 10 seconds")

    # Small grace period for serve_forever to begin accepting
    time.sleep(0.3)
    actual_port = d.port

    yield f"http://127.0.0.1:{actual_port}", brain_dir

    # Shutdown: call in a thread to avoid blocking if something is stuck
    stop_thread = threading.Thread(target=d.stop, daemon=True)
    stop_thread.start()
    stop_thread.join(timeout=5)


def _post(url, endpoint, body):
    req = urllib.request.Request(
        f"{url}{endpoint}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


def _get(url, endpoint):
    req = urllib.request.Request(f"{url}{endpoint}")
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


# ── Tests ──────────────────────────────────────────────────────────────


def test_health_endpoint(running_daemon):
    url, brain_dir = running_daemon
    r = _get(url, "/health")
    assert r["status"] == "ok"
    assert "sdk_version" in r
    assert r["lessons_count"] >= 0
    assert r["rules_count"] >= 0


def test_full_learning_loop(running_daemon):
    url, brain_dir = running_daemon

    # 1. Apply rules on empty brain — should return nothing
    r1 = _post(url, "/apply-rules", {"prompt": "write code", "session_id": "s1"})
    assert len(r1["rules"]) == 0

    # 2. Send a correction
    r2 = _post(url, "/correct", {
        "old_string": "def foo(x):\n    return x",
        "new_string": "def foo(x: int) -> int:\n    return x",
        "file_path": "/project/main.py",
        "session_id": "s1",
    })
    assert r2["captured"] is True

    # 3. End session (graduation sweep)
    r3 = _post(url, "/end-session", {"session_id": "s1", "session_type": "full"})
    assert isinstance(r3["corrections_captured"], int)

    # 4. Check that lessons.md now has content
    lessons = (brain_dir / "lessons.md").read_text(encoding="utf-8")
    assert len(lessons) > 0


def test_implicit_feedback_detection(running_daemon):
    url, brain_dir = running_daemon

    result = _post(url, "/detect", {
        "user_message": "that's wrong, stop doing that",
        "session_id": "s2",
        "recent_fired_rules": [],
    })
    assert result["implicit_feedback"]["detected"] is True
    assert len(result["implicit_feedback"]["signals"]) > 0


def test_no_op_correction_rejected(running_daemon):
    """Identical old/new strings should not be captured."""
    url, _ = running_daemon
    r = _post(url, "/correct", {
        "old_string": "same text",
        "new_string": "same text",
        "file_path": "/project/main.py",
        "session_id": "s3",
    })
    assert r["captured"] is False


def test_not_found_returns_404(running_daemon):
    """Unknown endpoints return 404."""
    url, _ = running_daemon
    req = urllib.request.Request(
        f"{url}/nonexistent",
        data=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 404
