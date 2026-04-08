"""Correction provenance authentication via HMAC-SHA256.

Each correction gets a signed provenance record that proves:
- Who made the correction (user_id)
- Which session it occurred in
- What was corrected (correction_hash)

Anomaly detection intentionally excluded. Relying on provenance +
audit trail + 3-signal graduation for integrity guarantees.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime


def create_provenance_record(
    *, user_id: str, correction_hash: str, session: int, salt: str,
) -> dict:
    """Create an HMAC-SHA256 signed provenance record for a correction.

    Args:
        user_id: Identifier for the user who made the correction.
        correction_hash: SHA-256 hash of the correction content.
        session: Session number where the correction occurred.
        salt: Per-brain salt used as HMAC key.

    Returns:
        Dict with user_id, correction_hash, session, timestamp, and hmac.
    """
    if not user_id or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")
    if not correction_hash or not correction_hash.strip():
        raise ValueError("correction_hash must be a non-empty string")
    if not isinstance(session, int) or session < 0:
        raise ValueError(f"session must be a non-negative integer, got {session!r}")
    if not salt or not salt.strip():
        raise ValueError("salt must be a non-empty string")
    timestamp = datetime.now(UTC).isoformat()
    message = f"{user_id}|{correction_hash}|{session}|{timestamp}"
    signature = hmac.new(
        salt.encode(), message.encode(), hashlib.sha256,
    ).hexdigest()
    return {
        "user_id": user_id,
        "correction_hash": correction_hash,
        "session": session,
        "timestamp": timestamp,
        "hmac": signature,
    }


def verify_provenance(record: dict, salt: str) -> bool:
    """Verify an HMAC-SHA256 signed provenance record.

    Args:
        record: Provenance record from create_provenance_record().
        salt: Per-brain salt (must match the one used to create).

    Returns:
        True if the record is authentic and untampered.
    """
    try:
        message = (
            f"{record['user_id']}|{record['correction_hash']}"
            f"|{record['session']}|{record['timestamp']}"
        )
        expected = hmac.new(
            salt.encode(), message.encode(), hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, record["hmac"])
    except (KeyError, TypeError):
        return False