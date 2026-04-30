"""PostToolUse hook: detect tool failures and emit TOOL_FAILURE event."""

from __future__ import annotations
import logging

import re

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile
logger = logging.getLogger(__name__)


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
    re.compile(
        r"\b[45]\d{2}\s+(Bad Request|Unauthorized|Forbidden|Not Found|Internal Server Error|Bad Gateway|Service Unavailable)\b",
        re.I,
    ),
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


def _detect_failure(output: str) -> list[str]:
    if not output:
        return []
    signals = []
    for pattern in ERROR_PATTERNS:
        match = pattern.search(output)
        if match:
            # Check context around match for false positives
            start = max(0, match.start() - 50)
            end = min(len(output), match.end() + 50)
            context = output[start:end]
            if not _is_false_positive(context):
                signals.append(match.group())
    return signals


def main(data: dict) -> dict | None:
    try:
        output = data.get("tool_output", "") or ""
        if isinstance(output, dict):
            output = str(output)
        if not output:
            return None

        signals = _detect_failure(output)
        if not signals:
            return None

        brain_dir = resolve_brain_dir()

        if brain_dir:
            from gradata._events import emit
            from gradata._paths import BrainContext

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
        logger.warning('Suppressed exception in main', exc_info=True)
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
