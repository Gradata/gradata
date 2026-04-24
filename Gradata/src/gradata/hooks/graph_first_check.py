"""PreToolUse hook: block Glob/Grep for code exploration until code-review-graph is activated.

Exploratory searches (Glob patterns, Grep in src/tests dirs) are blocked with a redirect
to ToolSearch → semantic_search_nodes/query_graph. Once the session flag is set by
graph_session_track.py, all subsequent calls pass through.

Bypass: set GRADATA_GRAPH_CHECK=0 to disable.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Glob|Grep",
    "profile": Profile.STANDARD,
    "timeout": 2000,
    "blocking": True,
}

_CODE_GLOB = re.compile(
    r"\*\*?/.*\.(py|ts|js|tsx|jsx|go|rs|rb|java|cpp|c|h)$"
    r"|/src/|/tests?/|gradata|hooks|middleware|integrations",
    re.I,
)
_CODE_PATH = re.compile(r"\b(src|tests?|gradata|hooks|middleware|integrations|lib|app)\b", re.I)

_BLOCK_MSG = (
    "graph_first_check: Activate code-review-graph before exploring code. Call:\n\n"
    '  ToolSearch({query: "select:mcp__code-review-graph__semantic_search_nodes,'
    "mcp__code-review-graph__query_graph,mcp__code-review-graph__get_impact_radius,"
    'mcp__code-review-graph__get_review_context"})\n\n'
    "Then use semantic_search_nodes or query_graph instead of Glob/Grep."
)


def flag_path(session_id: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"gradata_graph_active_{session_id}")


def graph_activated(session_id: str) -> bool:
    return bool(session_id) and os.path.exists(flag_path(session_id))


def _looks_exploratory(tool_name: str, tool_input: dict) -> bool:
    if tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", "") or ""
        return bool(
            _CODE_GLOB.search(pattern) or _CODE_PATH.search(pattern) or _CODE_PATH.search(path)
        )
    if tool_name == "Grep":
        path = str(tool_input.get("path", "") or "")
        glob = str(tool_input.get("glob", "") or "")
        return bool(_CODE_PATH.search(path) or _CODE_GLOB.search(glob))
    return False


def main(data: dict) -> dict | None:
    try:
        if os.environ.get("GRADATA_GRAPH_CHECK", "1") == "0":
            return None

        session_id = data.get("session_id", "")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})

        if not _looks_exploratory(tool_name, tool_input):
            return None

        if graph_activated(session_id):
            return None

        return {"decision": "block", "reason": _BLOCK_MSG}
    except Exception as exc:
        _log.debug("graph_first_check error: %s", exc)
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
