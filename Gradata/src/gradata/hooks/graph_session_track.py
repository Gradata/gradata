"""PostToolUse hook: set session flag when code-review-graph schemas are activated.

Fires after every ToolSearch call. If the query includes "code-review-graph",
writes a flag file that graph_first_check.py reads to allow subsequent Glob/Grep calls.
"""

from __future__ import annotations

import logging
import os
import tempfile

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "ToolSearch",
    "profile": Profile.STANDARD,
    "timeout": 2000,
}


def flag_path(session_id: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"gradata_graph_active_{session_id}")


def main(data: dict) -> dict | None:
    try:
        session_id = data.get("session_id", "")
        if not session_id:
            return None

        tool_input = data.get("tool_input", {})
        query = tool_input.get("query", "")

        if "code-review-graph" not in query:
            return None

        fp = flag_path(session_id)
        if not os.path.exists(fp):
            with open(fp, "w") as fh:
                fh.write("1")
            _log.debug("graph_session_track: graph activated for session %s", session_id)
    except Exception as exc:
        _log.debug("graph_session_track error: %s", exc)
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
