"""SessionStart hook: inject the most recent unconsumed handoff doc.

Siblings :mod:`gradata.hooks.inject_brain_rules`. Runs before brain-rules
injection in the SessionStart sequence so the fresh agent sees the
handoff first (primacy), followed by standing rules.

After injection the handoff is moved to ``{handoff_dir}/consumed/`` so
it does not re-inject on the next session. Skipped on compact/resume
events (same policy as brain-rules) — the compacted summary already
carries forward recent work.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from gradata.contrib.patterns.handoff import (
    consume_handoff,
    default_handoff_dir,
    parse_rules_snapshot_ts,
    pick_latest_unconsumed,
)
from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

HANDOFF_ACTIVE_FILE = ".handoff_active.json"

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "SessionStart",
    "profile": Profile.MINIMAL,
    "timeout": 5000,
}

_MAX_HANDOFF_CHARS = int(os.environ.get("GRADATA_HANDOFF_MAX_CHARS", "4000"))


def _sanitize(text: str) -> str:
    """Strip any literal ``</handoff>`` that would close our wrapper early."""
    return text.replace("</handoff>", "&lt;/handoff&gt;")


def main(data: dict) -> dict | None:
    if os.environ.get("GRADATA_INJECT_HANDOFF_ON_COMPACT", "0") != "1":
        source = str(data.get("source", "") or "").lower()
        if source in ("compact", "resume"):
            return None

    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    handoff_dir = default_handoff_dir(brain_dir)
    candidate = pick_latest_unconsumed(handoff_dir)
    if candidate is None:
        return None

    try:
        body = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        _log.debug("handoff read failed (%s) — skipping injection", exc)
        return None

    if len(body) > _MAX_HANDOFF_CHARS:
        body = body[:_MAX_HANDOFF_CHARS] + "\n<!-- truncated -->"

    safe = _sanitize(body.strip())
    block = f'<handoff source="{candidate.name}">\n{safe}\n</handoff>'

    rules_ts = parse_rules_snapshot_ts(body)
    if rules_ts:
        try:
            import json as _json

            sentinel = Path(brain_dir) / HANDOFF_ACTIVE_FILE
            sentinel.write_text(
                _json.dumps({"rules_snapshot_ts": rules_ts, "source": candidate.name}),
                encoding="utf-8",
            )
        except OSError as exc:
            _log.debug("handoff sentinel write failed: %s", exc)

    consume_handoff(candidate)

    try:
        from gradata import _events as events

        events.emit(
            event_type="handoff.injected",
            source="inject_handoff_hook",
            data={"file": candidate.name, "chars": len(safe), "rules_ts": rules_ts or ""},
            tags=["handoff", "injection"],
        )
    except Exception as exc:
        _log.debug("handoff.injected emit failed: %s", exc)

    return {"result": block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
