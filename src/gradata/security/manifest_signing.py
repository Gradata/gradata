"""HMAC-SHA256 manifest signing and verification.

Signs brain manifests with a per-brain salt so tampering is detectable.
Uses ``hmac.compare_digest`` for timing-safe verification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone


def sign_manifest(manifest: dict, salt: str) -> dict:
    """Return a **new** dict with ``signature`` and ``signed_at`` fields added.

    The original *manifest* is never mutated.
    """
    if not isinstance(manifest, dict):
        raise TypeError("manifest must be a dict")
    if not isinstance(salt, str) or not salt.strip():
        raise ValueError("salt must be a non-empty string")
    payload = _canonical_payload(manifest)
    sig = hmac.new(salt.encode(), payload, hashlib.sha256).hexdigest()
    signed = dict(manifest)
    signed["signature"] = sig
    signed["signed_at"] = datetime.now(timezone.utc).isoformat()
    return signed


def verify_manifest(manifest: dict, salt: str) -> bool:
    """Verify that *manifest* has a valid HMAC-SHA256 signature.

    Returns ``False`` if the signature field is missing or invalid.
    Uses ``hmac.compare_digest`` for timing-safe comparison.
    """
    stored_sig = manifest.get("signature")
    if not isinstance(stored_sig, str) or not stored_sig:
        return False

    payload = _canonical_payload(manifest)
    expected = hmac.new(salt.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(stored_sig, expected)


def _canonical_payload(manifest: dict) -> bytes:
    """Produce canonical JSON bytes, excluding ``signature`` and ``signed_at``."""
    filtered = {k: v for k, v in manifest.items()
                if k not in ("signature", "signed_at")}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode()
