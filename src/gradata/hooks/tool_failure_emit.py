"""PostToolUse hook: detect tool failures and emit TOOL_FAILURE event."""
from __future__ import annotations

import re

from ._base import resolve_brain_dir, run_hook
from ._base import Profile

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "Bash",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

# Error indicators
ERROR_PATTERNS = [
    re.compile(r"\berror\b", re.I),
    re.compile(r"\bfailed\b", re.I),
    re.compile(r"\btraceback\b", re.I),
    re.compile(r"\bException\b"),
    re.compile(r"\bHTTP\s+[45]\d{2}\b"),
    re.compile(r"\b[45]\d{2}\s+(Bad Request|Unauthorized|Forbidden|Not Found|Internal Server Error|Bad Gateway|Service Unavailable)\b", re.I),
    re.compile(r"\bECONNREFUSED\b"),
    re.compile(r"\brate limit\b", re.I),
]

# False positive filters
FALSE_POSITIVES = [
    re.compile(r"\berror handling\b", re.I),
    re.compile(r"\berror message\b", re.I),
    re.compile(r"\bno errors? found\b", re.I),
    re.compile(r"\berror['\"]\s*[=:]", re.I),  # variable named error
    re.compile(r"#.*\berror\b", re.I),  # comments
    re.compile(r"\berror_count\s*=\s*0\b", re.I),
]


def _is_false_positive(text: str) -> bool:
    return any(fp.search(text) for fp in FALSE_POSITIVES)


def main(data: dict) -> dict | None:
    try:
        output = data.get("tool_output", "") or ""
        if isinstance(output, dict):
            output = str(output)
        if not output:
            return None

        signals: list[str] = []
        for _df_pat in ERROR_PATTERNS:
            _df_m = _df_pat.search(output)
            if _df_m and not _is_false_positive(
                output[max(0, _df_m.start() - 50):min(len(output), _df_m.end() + 50)]
            ):
                signals.append(_df_m.group())
        if not signals:
            return None

        brain_dir = resolve_brain_dir()

        if brain_dir:
            from .._events import emit
            from .._paths import BrainContext
            ctx = BrainContext.from_brain_dir(brain_dir)
            command = data.get("tool_input", {}).get("command", "")[:200]
            emit(
                "TOOL_FAILURE",
                source="hook:tool_failure_emit",
                data={
                    "tool": "Bash",
                    "signals": signals[:5],
                    "command_preview": command,
                    "output_preview": output[:300],
                },
                ctx=ctx,
            )
    except Exception:
        pass
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
