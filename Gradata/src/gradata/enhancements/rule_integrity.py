"""
HMAC Rule Signing — tamper detection for graduated rules.
==========================================================
SDK LAYER: Layer 1 (enhancements). Imports from _types only.

Prevents tampered or forged rules from being injected into prompts.
Each rule is signed with HMAC-SHA256 using a secret key. On injection,
the signature is verified; unsigned or tampered rules are skipped with
a WARNING log.

Backward compatible: when no secret key is configured (solo use),
rules pass through unsigned and unverified.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata._paths import BrainContext

logger = logging.getLogger("gradata.rule_integrity")

# Shared regex for parsing lesson lines: [STATE:CONF] CATEGORY: description
_LESSON_PATTERN = re.compile(r"\[(?:INSTINCT|PATTERN|RULE):(\d+\.\d+)\]\s+(\w+):\s+(.+)")

# ---------------------------------------------------------------------------
# Key Management
# ---------------------------------------------------------------------------

_SECRET_KEY: bytes | None = None


def _get_secret_key() -> bytes | None:
    """Load the signing key from environment or return None (unsigned mode).

    The key is cached in the module-level ``_SECRET_KEY`` after the first
    successful load.  This is intentional: the secret does not change within
    a process lifetime, and re-reading the env var on every call would add
    unnecessary overhead during batch signing/verification operations.
    """
    global _SECRET_KEY
    if _SECRET_KEY is not None:
        return _SECRET_KEY
    env_key = os.environ.get("GRADATA_RULE_SECRET", "")
    if env_key:
        _SECRET_KEY = env_key.encode("utf-8")
        return _SECRET_KEY
    return None


def generate_key() -> str:
    """Generate a new random 32-byte hex secret key.

    Returns:
        64-character hex string suitable for GRADATA_RULE_SECRET env var.
    """
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# Rule Signing & Verification
# ---------------------------------------------------------------------------


def _canonical_payload(rule_text: str, category: str, confidence: float) -> bytes:
    """Build a canonical byte payload for signing.

    Deterministic: same inputs always produce the same bytes.
    """
    obj = {
        "rule_text": rule_text.strip(),
        "category": category.strip().upper(),
        "confidence": round(confidence, 2),
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_rule(rule_text: str, category: str, confidence: float) -> str:
    """Generate HMAC-SHA256 signature for a rule.

    Args:
        rule_text: The rule description text.
        category: Lesson category (e.g. "DRAFTING").
        confidence: Confidence float (0.0-1.0), clamped to valid range.

    Returns:
        Hex-encoded HMAC-SHA256 signature, or empty string if no key configured.
    """
    key = _get_secret_key()
    if key is None:
        return ""
    confidence = max(0.0, min(1.0, confidence))
    payload = _canonical_payload(rule_text, category, confidence)
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def verify_rule(rule_text: str, category: str, confidence: float, signature: str) -> bool:
    """Verify rule signature. Returns False if tampered.

    Returns True (pass-through) when:
    - No secret key is configured (unsigned mode)
    - Signature is empty and no key is configured

    Returns False when:
    - Key is configured but signature is empty
    - Key is configured and signature doesn't match
    """
    key = _get_secret_key()
    if key is None:
        return True  # No key = unsigned mode, pass through
    if not signature:
        return False  # Key configured but rule unsigned
    confidence = max(0.0, min(1.0, confidence))
    payload = _canonical_payload(rule_text, category, confidence)
    expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Lesson File Operations
# ---------------------------------------------------------------------------


def sign_lesson_file(lessons_path: Path) -> dict[str, str]:
    """Sign all lessons in a markdown lessons file.

    Parses lesson lines matching [STATE:CONF] CATEGORY: description
    and returns a {category: signature} map.

    Note: Only the *last* rule per category is retained. This is intentional —
    graduation produces one canonical rule per category, so duplicates indicate
    stale entries. The returned dict is keyed by category for O(1) lookup.

    Args:
        lessons_path: Path to lessons.md file.

    Returns:
        Dict mapping category -> HMAC signature. Empty if no key.
    """
    key = _get_secret_key()
    if key is None:
        return {}

    if not lessons_path.exists():
        logger.warning("Lessons file not found: %s", lessons_path)
        return {}

    text = lessons_path.read_text(encoding="utf-8")
    signatures: dict[str, str] = {}

    for line in text.splitlines():
        m = _LESSON_PATTERN.search(line)
        if m:
            confidence = float(m.group(1))
            category = m.group(2).upper()
            description = m.group(3).strip()
            sig = sign_rule(description, category, confidence)
            if sig:
                signatures[category] = sig

    return signatures


def verify_lesson_file(lessons_path: Path, signatures: dict[str, str]) -> list[str]:
    """Verify all lessons against stored signatures.

    Args:
        lessons_path: Path to lessons.md file.
        signatures: Dict of {category: signature} from sign_lesson_file.

    Returns:
        List of tampered category names. Empty = all clean.
    """
    if not _get_secret_key():
        return []  # Unsigned mode

    if not lessons_path.exists():
        return []

    text = lessons_path.read_text(encoding="utf-8")
    tampered: list[str] = []

    for line in text.splitlines():
        m = _LESSON_PATTERN.search(line)
        if m:
            confidence = float(m.group(1))
            category = m.group(2).upper()
            description = m.group(3).strip()
            stored_sig = signatures.get(category, "")
            if not verify_rule(description, category, confidence, stored_sig):
                tampered.append(category)

    return tampered


# ---------------------------------------------------------------------------
# Database Storage
# ---------------------------------------------------------------------------


def _ensure_table(ctx: BrainContext) -> None:
    """Create rule_signatures table if it doesn't exist."""
    with sqlite3.connect(str(ctx.db_path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rule_signatures (
                category TEXT PRIMARY KEY,
                signature TEXT NOT NULL,
                signed_at TEXT NOT NULL
            )
        """)
        conn.commit()


def store_signature(ctx: BrainContext, category: str, signature: str) -> None:
    """Store or update a rule signature in system.db.

    Args:
        ctx: BrainContext (provides db_path and other brain-scoped paths).
        category: Lesson category.
        signature: HMAC hex signature.
    """
    if not signature:
        return
    _ensure_table(ctx)
    with sqlite3.connect(str(ctx.db_path)) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO rule_signatures (category, signature, signed_at)
               VALUES (?, ?, ?)""",
            (category.upper(), signature, datetime.now(UTC).isoformat()),
        )
        conn.commit()


def load_signatures(ctx: BrainContext) -> dict[str, str]:
    """Load all stored signatures from system.db.

    Returns:
        Dict mapping category -> signature. Empty if table doesn't exist.
    """
    _ensure_table(ctx)
    with sqlite3.connect(str(ctx.db_path)) as conn:
        rows = conn.execute("SELECT category, signature FROM rule_signatures").fetchall()
        return {row[0]: row[1] for row in rows}


def sign_and_store(ctx: BrainContext, rule_text: str, category: str, confidence: float) -> str:
    """Sign a rule and store the signature in the database.

    Convenience function for use at graduation time.

    Returns:
        The signature (or empty string if no key configured).
    """
    sig = sign_rule(rule_text, category, confidence)
    if sig:
        store_signature(ctx, category, sig)
    return sig


def _load_signature(ctx: BrainContext, category: str) -> str:
    """Load a single signature for one category from system.db.

    More efficient than load_signatures() when only one category is needed.

    Returns:
        Hex signature string, or empty string if not found.
    """
    _ensure_table(ctx)
    with sqlite3.connect(str(ctx.db_path)) as conn:
        row = conn.execute(
            "SELECT signature FROM rule_signatures WHERE category = ?",
            (category.upper(),),
        ).fetchone()
        return row[0] if row else ""


def verify_from_db(ctx: BrainContext, rule_text: str, category: str, confidence: float) -> bool:
    """Verify a rule against the signature stored in system.db.

    Returns True if:
    - No key configured (unsigned mode)
    - Signature matches

    Returns False if:
    - Key configured but no stored signature
    - Key configured and signature mismatch
    """
    if not _get_secret_key():
        return True
    stored_sig = _load_signature(ctx, category)
    return verify_rule(rule_text, category, confidence, stored_sig)
