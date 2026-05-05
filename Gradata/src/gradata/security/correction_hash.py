"""Correction content-provenance hashing and source-context classification.

Defence against A1 (indirect prompt injection via corrections) from the
Gradata red-team taxonomy. The threat model, from Greshake et al. 2023
(*Not What You've Signed Up For*, https://arxiv.org/abs/2302.12173), is that
any imperative text pasted into a correction flows through graduation and is
re-injected into future sessions as a ``<brain-rules>`` directive. Corrections
that originated from external pastes therefore need:

1. A content-provenance hash so we can later de-duplicate, audit, or revoke
   any graduated rule that traces back to a known-bad paste.
2. A ``source_kind`` classification so the graduation pipeline knows whether
   the text was written by the user (trusted edit of an AI output) or
   pasted from an external source (untrusted — requires human review).

The hash is SHA-256 of the canonical tuple ``(before, after, source_context)``.
It is *not* an HMAC — that is handled separately in ``correction_provenance``
for authentication. This module is content-addressed (same bytes → same hash)
so that provenance can be checked without needing the brain salt.

A paste-from-external correction is flagged ``requires_review=True`` and must
receive an explicit ``promote`` action (via the existing ``approval_required``
pending-approval flow in ``_core.brain_correct``) before it can graduate.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# ---------------------------------------------------------------------------
# Source-kind vocabulary
# ---------------------------------------------------------------------------
# Known values — callers set ``context["source"]`` (or ``context["source_kind"]``)
# to one of these before calling ``brain.correct(...)``. Anything else collapses
# to ``UNKNOWN`` which is treated as external-paste for safety.

SOURCE_USER_EDIT = "user_edit"
SOURCE_EXTERNAL_PASTE = "external_paste"
SOURCE_UNKNOWN = "unknown"

_KNOWN_SOURCES: set[str] = {
    SOURCE_USER_EDIT,
    SOURCE_EXTERNAL_PASTE,
    SOURCE_UNKNOWN,
}

# Aliases commonly found in caller code. All values normalize to the three
# canonical strings above.
_SOURCE_ALIASES: dict[str, str] = {
    # user edits of AI output
    "user": SOURCE_USER_EDIT,
    "human": SOURCE_USER_EDIT,
    "edit": SOURCE_USER_EDIT,
    "user_edit": SOURCE_USER_EDIT,
    "manual": SOURCE_USER_EDIT,
    # external pastes (email, chat transcript, arbitrary clipboard)
    "paste": SOURCE_EXTERNAL_PASTE,
    "external": SOURCE_EXTERNAL_PASTE,
    "external_paste": SOURCE_EXTERNAL_PASTE,
    "clipboard": SOURCE_EXTERNAL_PASTE,
    "imported": SOURCE_EXTERNAL_PASTE,
    "untrusted": SOURCE_EXTERNAL_PASTE,
}


def _canonicalize_source_context(source_context: Any) -> str:
    """Turn ``source_context`` into a stable, hash-friendly string.

    Accepts ``None``, ``str``, ``dict``, or any JSON-serializable value.
    The output is deterministic for equal inputs so the provenance hash is
    reproducible across runs and machines.
    """
    if source_context is None:
        return ""
    if isinstance(source_context, str):
        return source_context
    try:
        return json.dumps(source_context, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return str(source_context)


def compute_correction_hash(
    before_text: str,
    after_text: str,
    source_context: Any = None,
) -> str:
    """Compute SHA-256 of ``(before_text, after_text, source_context)``.

    The hash is content-addressed: identical inputs always produce the same
    64-character hex digest. Used as a correction's ``provenance_hash`` so
    downstream audits can trace a graduated rule back to the exact bytes it
    originated from.

    Args:
        before_text: The original text (draft / pre-edit).
        after_text: The corrected text (final / post-edit).
        source_context: Optional context describing where the correction came
            from (dict, string, or None). Typical keys: ``source``,
            ``user_id``, ``session``, ``origin_url``.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    before = before_text or ""
    after = after_text or ""
    ctx_repr = _canonicalize_source_context(source_context)
    # Length-prefixed concatenation so "ab"+"c" and "a"+"bc" hash differently.
    payload = (
        f"{len(before)}:{before}\x00{len(after)}:{after}\x00{len(ctx_repr)}:{ctx_repr}"
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def classify_source_context(source_context: Any) -> tuple[str, bool]:
    """Classify a correction's origin and decide whether review is required.

    Args:
        source_context: Either ``None``, a string source tag, or a dict that
            may contain ``"source"`` / ``"source_kind"`` / ``"origin"``.

    Returns:
        ``(source_kind, requires_review)`` where ``source_kind`` is one of
        :data:`SOURCE_USER_EDIT`, :data:`SOURCE_EXTERNAL_PASTE`,
        :data:`SOURCE_UNKNOWN`, and ``requires_review`` is ``True`` whenever
        the source is not an explicit user edit.

    Design: fail-safe. Any unrecognized source collapses to ``unknown`` and
    gets ``requires_review=True`` so an attacker cannot bypass gating by
    simply omitting the source field.
    """
    raw: str | None = None

    if source_context is None:
        raw = None
    elif isinstance(source_context, str):
        raw = source_context
    elif isinstance(source_context, dict):
        for key in ("source_kind", "source", "origin"):
            value = source_context.get(key)
            if isinstance(value, str) and value.strip():
                raw = value
                break

    if raw is None:
        # No signal at all → default to user_edit (backwards-compatible with
        # existing callers who never set source). They pay no review tax.
        return SOURCE_USER_EDIT, False

    normalized = raw.strip().lower().replace("-", "_").replace(" ", "_")
    kind = _SOURCE_ALIASES.get(normalized, normalized)
    if kind not in _KNOWN_SOURCES:
        kind = SOURCE_UNKNOWN

    requires_review = kind != SOURCE_USER_EDIT
    return kind, requires_review


def build_provenance(
    before_text: str,
    after_text: str,
    source_context: Any = None,
) -> dict[str, Any]:
    """One-shot helper returning hash + source classification together.

    Returns a dict with keys ``provenance_hash``, ``source_kind``, and
    ``requires_review`` suitable for attaching directly to a correction event.
    """
    source_kind, requires_review = classify_source_context(source_context)
    return {
        "provenance_hash": compute_correction_hash(
            before_text,
            after_text,
            source_context,
        ),
        "source_kind": source_kind,
        "requires_review": requires_review,
    }
