"""Tests for gradata.daemon — HTTP server skeleton."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from gradata.daemon import GradataDaemon


@pytest.fixture()
def daemon(tmp_path):
    """Start a daemon on an OS-assigned port against a fresh brain."""
    from gradata import Brain

    brain_dir = tmp_path / "test-brain"
    Brain.init(brain_dir)

    pid_file = tmp_path / "daemon.pid"
    d = GradataDaemon(brain_dir=brain_dir, port=0, pid_file=pid_file)

    # Bind immediately so we can read the port before serve_forever blocks
    d._try_bind(0)
    d._server._daemon = d  # type: ignore[attr-defined]
    d._port = d._server.server_address[1]

    # Write PID file and start idle timer
    from gradata.daemon import _write_pid_file
    if d._pid_file:
        _write_pid_file(d._pid_file, d._port, d._brain_dir, d._started_at)
    d._reset_idle_timer()

    server_thread = threading.Thread(target=d._server.serve_forever, daemon=True)
    server_thread.start()

    yield d

    d._server.shutdown()
    d._cleanup()


def _get(port: int, path: str) -> dict:
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _post(port: int, path: str, body: dict | None = None) -> dict:
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


class TestHealth:
    def test_health_returns_expected_shape(self, daemon):
        result = _get(daemon.port, "/health")

        assert result["status"] == "ok"
        assert result["sdk_version"] == "0.2.0"
        assert "brain_dir" in result
        assert isinstance(result["uptime_seconds"], (int, float))
        assert result["uptime_seconds"] >= 0
        assert isinstance(result["active_sessions"], int)
        assert isinstance(result["rules_count"], int)
        assert isinstance(result["lessons_count"], int)

    def test_health_brain_dir_matches(self, daemon):
        result = _get(daemon.port, "/health")
        assert result["brain_dir"] == str(daemon._brain_dir)


class TestStubEndpoints:
    def test_apply_rules_stub(self, daemon):
        result = _post(daemon.port, "/apply-rules", {"task": "write email"})
        assert result == {
            "rules": [],
            "injection_text": "",
            "mode_detected": "chat",
            "fired_rule_ids": [],
        }

    def test_detect_stub(self, daemon):
        result = _post(daemon.port, "/detect", {"user_message": "something"})
        assert result["mode"] == "chat"
        assert result["mode_confidence"] == 0.0
        assert "implicit_feedback" in result
        assert isinstance(result["implicit_feedback"]["detected"], bool)

    def test_end_session_stub(self, daemon):
        result = _post(daemon.port, "/end-session")
        assert "corrections_captured" in result
        assert "instructions_extracted" in result
        assert "lessons_graduated" in result
        assert "meta_rules_synthesized" in result
        assert "convergence" in result
        assert result["cross_project_candidates"] == []


class TestNotFound:
    def test_get_unknown_path(self, daemon):
        url = f"http://127.0.0.1:{daemon.port}/nonexistent"
        req = urllib.request.Request(url)
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 404


class TestPidFile:
    def test_pid_file_written(self, daemon):
        assert daemon._pid_file.exists()
        data = json.loads(daemon._pid_file.read_text(encoding="utf-8"))
        assert data["port"] == daemon.port
        assert "pid" in data
        assert data["sdk_version"] == "0.2.0"
        assert "started_at" in data
        assert data["brain_dir"] == str(daemon._brain_dir)


class TestApplyRules:
    def test_apply_rules_returns_structure(self, daemon):
        """On empty brain, returns empty rules with correct shape."""
        result = _post(daemon.port, "/apply-rules", {
            "prompt": "write an email",
            "session_id": "test-001",
            "context": {"agent_type": "general"},
        })
        assert result["rules"] == []
        assert result["injection_text"] == ""
        assert result["mode_detected"] == "chat"
        assert result["fired_rule_ids"] == []

    def test_apply_rules_with_seeded_lessons(self, daemon):
        """Seed a RULE-level lesson and verify it appears in the response."""
        lessons_path = daemon._brain_dir / "lessons.md"
        lessons_path.write_text(
            "[2026-04-08] [RULE:0.92] CODE: Always add type annotations to function parameters\n",
            encoding="utf-8",
        )

        result = _post(daemon.port, "/apply-rules", {
            "prompt": "write a Python function",
            "session_id": "test-002",
            "context": {"agent_type": "general"},
        })

        assert len(result["rules"]) >= 1
        rule = result["rules"][0]
        assert "rule_id" in rule
        assert rule["tier"] == "RULE"
        assert rule["category"] == "CODE"
        assert "type annotations" in rule["instruction"]
        assert isinstance(rule["relevance"], (int, float))
        assert rule["relevance"] > 0

        # injection_text should be non-empty
        assert len(result["injection_text"]) > 0

        # fired_rule_ids should match
        assert result["fired_rule_ids"] == [r["rule_id"] for r in result["rules"]]

        # Verify daemon stores fired rules keyed by session_id
        assert "test-002" in daemon._fired_rules
        assert daemon._fired_rules["test-002"] == result["fired_rule_ids"]


class TestCategoryFromPath:
    def test_python_is_code(self):
        from gradata.daemon import _category_from_path
        assert _category_from_path("src/main.py") == "CODE"

    def test_js_is_code(self):
        from gradata.daemon import _category_from_path
        assert _category_from_path("app/index.js") == "CODE"

    def test_markdown_is_content(self):
        from gradata.daemon import _category_from_path
        assert _category_from_path("docs/README.md") == "CONTENT"

    def test_json_is_config(self):
        from gradata.daemon import _category_from_path
        assert _category_from_path("package.json") == "CONFIG"

    def test_html_is_frontend(self):
        from gradata.daemon import _category_from_path
        assert _category_from_path("index.html") == "FRONTEND"

    def test_unknown_ext_is_general(self):
        from gradata.daemon import _category_from_path
        assert _category_from_path("data.xyz") == "GENERAL"


class TestCorrectEndpoint:
    def test_correct_captures_correction(self, daemon):
        """Send a real correction and verify response shape."""
        result = _post(daemon.port, "/correct", {
            "old_string": "This is — a test",
            "new_string": "This is, a test",
            "file_path": "docs/guide.md",
            "session_id": "correct-001",
        })
        assert result["captured"] is True
        assert isinstance(result["severity"], str)
        assert len(result["severity"]) > 0
        assert isinstance(result["misfired_rules"], list)
        assert isinstance(result["accepted_rules"], list)

    def test_correct_no_change_returns_false(self, daemon):
        """Same old/new string returns captured=False."""
        result = _post(daemon.port, "/correct", {
            "old_string": "hello world",
            "new_string": "hello world",
            "file_path": "test.py",
            "session_id": "correct-002",
        })
        assert result["captured"] is False
        assert result["error"] == "no change"

    def test_correct_empty_strings_returns_false(self, daemon):
        """Both empty strings returns captured=False."""
        result = _post(daemon.port, "/correct", {
            "old_string": "",
            "new_string": "",
            "file_path": "",
            "session_id": "",
        })
        assert result["captured"] is False
        assert result["error"] == "no change"


class TestDetectEndpoint:
    def test_detect_no_feedback(self, daemon):
        """Normal text should return detected=false."""
        result = _post(daemon.port, "/detect", {
            "user_message": "Please write a function that adds two numbers.",
            "session_id": "detect-001",
        })
        assert result["implicit_feedback"]["detected"] is False
        assert result["implicit_feedback"]["signals"] == []
        assert result["implicit_feedback"]["related_rules"] == []
        assert result["implicit_feedback"]["action_taken"] is None
        assert result["mode"] == "chat"
        assert result["mode_confidence"] == 0.0

    def test_detect_with_pushback(self, daemon):
        """Pushback text should return detected=true with signals."""
        result = _post(daemon.port, "/detect", {
            "user_message": "That's wrong, stop doing that. I told you not to use em dashes.",
            "session_id": "detect-002",
            "recent_fired_rules": ["TONE:1234"],
        })
        fb = result["implicit_feedback"]
        assert fb["detected"] is True
        assert len(fb["signals"]) > 0
        assert fb["related_rules"] == ["TONE:1234"]
        assert fb["action_taken"] == "logged"
        assert result["mode"] == "chat"
        assert result["mode_confidence"] == 0.0


class TestEndSessionEndpoint:
    def test_end_session_returns_summary(self, daemon):
        """End session should return all required summary keys."""
        result = _post(daemon.port, "/end-session", {
            "session_id": "end-001",
            "session_type": "full",
        })
        assert "corrections_captured" in result
        assert "instructions_extracted" in result
        assert "lessons_graduated" in result
        assert "meta_rules_synthesized" in result
        assert "convergence" in result
        assert isinstance(result["convergence"], dict)
        assert result["cross_project_candidates"] == []

    def test_end_session_cleans_up_session(self, daemon):
        """Calling /end-session should remove the session_id from daemon state."""
        # Pre-populate session state
        daemon._sessions["cleanup-001"] = 42
        daemon._fired_rules["cleanup-001"] = ["RULE:abc"]

        result = _post(daemon.port, "/end-session", {
            "session_id": "cleanup-001",
            "session_type": "full",
        })

        assert "cleanup-001" not in daemon._sessions
        assert "cleanup-001" not in daemon._fired_rules
        assert result["cross_project_candidates"] == []


class TestSessionCounter:
    def test_session_counter_starts_at_1_for_fresh_brain(self, daemon):
        assert daemon._session_counter >= 1
