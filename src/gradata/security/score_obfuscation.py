"""Score obfuscation — strip raw confidence floats from prompt-injected rules.

Raw confidence scores (e.g. ``[RULE:0.95]``) leak internal state into LLM
prompts, enabling prompt injection attacks that reference or manipulate
specific thresholds.  This module replaces raw floats with tier labels
(``[RULE]``, ``[PATTERN]``, ``[INSTINCT]``) for prompt injection while
keeping raw floats available in local dev tools (brain.prove(),
brain.rules(), brain.efficiency()).
"""

from __future__ import annotations

import re
import secrets
import time

# Regex matching bracketed tier labels with trailing float, e.g. [RULE:0.95]
_SCORE_PATTERN = re.compile(r"\[(RULE|PATTERN|INSTINCT):([\d.]+)\]")


def truncate_score(confidence: float) -> str:
    """Map a raw confidence float to its tier label.

    Thresholds match the graduation pipeline:
      - 0.90+ -> "RULE"
      - 0.60-0.89 -> "PATTERN"
      - below 0.60 -> "INSTINCT"

    Args:
        confidence: Raw confidence float in [0.0, 1.0].

    Returns:
        Tier label string.
    """
    if confidence >= 0.90:
        return "RULE"
    if confidence >= 0.60:
        return "PATTERN"
    return "INSTINCT"


def obfuscate_instruction(instruction: str) -> str:
    """Strip raw confidence floats from a formatted instruction string.

    Replaces patterns like ``[RULE:0.95]`` with ``[RULE]``, removing the
    numeric score while preserving the tier label.

    Args:
        instruction: Instruction string that may contain bracketed scores.

    Returns:
        Instruction with all ``[TIER:float]`` replaced by ``[TIER]``.
    """
    return _SCORE_PATTERN.sub(r"[\1]", instruction)


def constant_time_pad(fn, min_ms: float = 20.0, jitter_ms: float = 5.0):
    """Execute *fn* and pad to minimum duration with random jitter.

    Prevents timing side-channels by ensuring that every call takes at
    least ``min_ms + random(0, jitter_ms)`` milliseconds, regardless of
    how fast *fn* completes.

    Args:
        fn: Zero-argument callable to execute.
        min_ms: Minimum execution time in milliseconds.
        jitter_ms: Maximum random jitter added on top of *min_ms*.

    Returns:
        Whatever *fn* returns.
    """
    start = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - start) * 1000
    jitter = (secrets.randbelow(int(jitter_ms * 1000)) / 1000) if jitter_ms > 0 else 0.0
    target_ms = min_ms + jitter
    remaining_ms = target_ms - elapsed_ms
    if remaining_ms > 0:
        time.sleep(remaining_ms / 1000)
    return result
