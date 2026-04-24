"""Tests for graph_first_check and graph_session_track hooks."""

from __future__ import annotations

import os

from gradata.hooks.graph_first_check import flag_path, main as _check_main
from gradata.hooks.graph_session_track import main as _track_main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_check(
    tool_name: str, tool_input: dict, session_id: str = "sess-abc", env: dict | None = None
) -> dict | None:
    data = {"tool_name": tool_name, "tool_input": tool_input, "session_id": session_id}
    original = {k: os.environ.get(k) for k in (env or {})}
    try:
        if env:
            for k, v in env.items():
                os.environ[k] = v
        return _check_main(data)
    finally:
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _run_track(query: str, session_id: str = "sess-abc") -> None:
    _track_main(
        {"tool_name": "ToolSearch", "tool_input": {"query": query}, "session_id": session_id}
    )


def _flag_exists(session_id: str) -> bool:
    return os.path.exists(flag_path(session_id))


def _clear_flag(session_id: str) -> None:
    fp = flag_path(session_id)
    if os.path.exists(fp):
        os.remove(fp)


# ---------------------------------------------------------------------------
# graph_first_check — blocking
# ---------------------------------------------------------------------------


class TestGraphFirstCheck:
    def setup_method(self):
        _clear_flag("sess-test")

    def teardown_method(self):
        _clear_flag("sess-test")

    def test_blocks_code_glob(self):
        result = _run_check("Glob", {"pattern": "**/*.py"}, session_id="sess-test")
        assert result is not None
        assert result["decision"] == "block"

    def test_blocks_src_glob(self):
        result = _run_check("Glob", {"pattern": "src/**/*"}, session_id="sess-test")
        assert result is not None
        assert result["decision"] == "block"

    def test_blocks_grep_in_src(self):
        result = _run_check(
            "Grep", {"pattern": "def main", "path": "src/gradata/"}, session_id="sess-test"
        )
        assert result is not None
        assert result["decision"] == "block"

    def test_blocks_grep_in_tests(self):
        result = _run_check(
            "Grep", {"pattern": "import gradata", "path": "tests/"}, session_id="sess-test"
        )
        assert result is not None
        assert result["decision"] == "block"

    def test_allows_non_code_glob(self):
        assert _run_check("Glob", {"pattern": "*.json"}, session_id="sess-test") is None

    def test_allows_docs_glob(self):
        assert _run_check("Glob", {"pattern": "domain/**/*.md"}, session_id="sess-test") is None

    def test_allows_grep_in_domain(self):
        result = _run_check(
            "Grep", {"pattern": "workshop", "path": "domain/playbooks/"}, session_id="sess-test"
        )
        assert result is None

    def test_allows_after_activation(self):
        _run_track("select:mcp__code-review-graph__semantic_search_nodes", session_id="sess-test")
        assert _run_check("Glob", {"pattern": "**/*.py"}, session_id="sess-test") is None

    def test_bypass_env_var(self):
        result = _run_check(
            "Glob", {"pattern": "**/*.py"}, session_id="sess-test", env={"GRADATA_GRAPH_CHECK": "0"}
        )
        assert result is None

    def test_empty_session_id_blocks(self):
        result = _run_check("Glob", {"pattern": "**/*.py"}, session_id="")
        assert result is not None
        assert result["decision"] == "block"

    def test_glob_hooks_dir_blocked(self):
        result = _run_check(
            "Glob", {"pattern": "hooks/*.py", "path": "src/gradata/"}, session_id="sess-test"
        )
        assert result is not None
        assert result["decision"] == "block"

    def test_block_reason_contains_toolsearch(self):
        result = _run_check("Glob", {"pattern": "**/*.py"}, session_id="sess-test")
        assert result is not None
        assert "ToolSearch" in result["reason"]
        assert "code-review-graph" in result["reason"]


# ---------------------------------------------------------------------------
# graph_session_track — flag writing
# ---------------------------------------------------------------------------


class TestGraphSessionTrack:
    def setup_method(self):
        _clear_flag("sess-track")

    def teardown_method(self):
        _clear_flag("sess-track")

    def test_sets_flag_on_graph_query(self):
        assert not _flag_exists("sess-track")
        _run_track(
            "select:mcp__code-review-graph__semantic_search_nodes,mcp__code-review-graph__query_graph",
            session_id="sess-track",
        )
        assert _flag_exists("sess-track")

    def test_no_flag_for_unrelated_query(self):
        _run_track("select:Read,Edit,Grep", session_id="sess-track")
        assert not _flag_exists("sess-track")

    def test_idempotent(self):
        _run_track("select:mcp__code-review-graph__query_graph", session_id="sess-track")
        _run_track("select:mcp__code-review-graph__query_graph", session_id="sess-track")
        assert _flag_exists("sess-track")

    def test_empty_session_id_no_crash(self):
        _track_main(
            {
                "tool_name": "ToolSearch",
                "tool_input": {"query": "select:mcp__code-review-graph__query_graph"},
                "session_id": "",
            }
        )

    def test_returns_none(self):
        result = _track_main(
            {
                "tool_name": "ToolSearch",
                "tool_input": {"query": "select:mcp__code-review-graph__query_graph"},
                "session_id": "sess-track",
            }
        )
        assert result is None


# ---------------------------------------------------------------------------
# Integration: full cycle
# ---------------------------------------------------------------------------


class TestGraphEnforcementCycle:
    def setup_method(self):
        _clear_flag("sess-cycle")

    def teardown_method(self):
        _clear_flag("sess-cycle")

    def test_full_cycle(self):
        # Before activation: blocked
        result = _run_check("Glob", {"pattern": "**/*.py"}, session_id="sess-cycle")
        assert result is not None and result["decision"] == "block"

        # Activate graph
        _run_track(
            "select:mcp__code-review-graph__semantic_search_nodes,mcp__code-review-graph__query_graph",
            session_id="sess-cycle",
        )
        assert _flag_exists("sess-cycle")

        # After activation: allowed
        assert _run_check("Glob", {"pattern": "**/*.py"}, session_id="sess-cycle") is None

        # Grep also allowed now
        assert (
            _run_check("Grep", {"pattern": "def main", "path": "src/"}, session_id="sess-cycle")
            is None
        )
