"""Per-brain salt for non-deterministic graduation thresholds.

Each brain gets a unique 32-byte salt stored as `.brain_salt` in the vault.
The salt jitters PATTERN_THRESHOLD and RULE_THRESHOLD by +/-5% so that
an attacker who knows the graduation algorithm cannot predict the exact
confidence boundary for any specific brain.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import struct
from pathlib import Path


def generate_brain_salt() -> str:
    """Generate a 32-byte random salt as a 64-char hex string."""
    return secrets.token_hex(32)


def load_or_create_salt(brain_dir: str | Path) -> str:
    """Load .brain_salt from *brain_dir*, creating it if absent.

    Returns the 64-char hex salt string.  The file is created atomically
    on first call and reused on subsequent calls (idempotent).
    """
    import os as _os

    brain_dir = Path(brain_dir)
    brain_dir.mkdir(parents=True, exist_ok=True)
    salt_path = brain_dir / ".brain_salt"

    # Fast path: file already exists and is valid
    if salt_path.is_file():
        content = salt_path.read_text(encoding="utf-8").strip()
        if len(content) == 64:
            return content

    # Create atomically via temp file + rename
    salt = generate_brain_salt()
    tmp_path = salt_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(salt)
            f.flush()
            _os.fsync(f.fileno())
        _os.replace(str(tmp_path), str(salt_path))
    except OSError:
        # Fallback: direct write
        salt_path.write_text(salt, encoding="utf-8")
    return salt


def salt_threshold(base: float, salt: str, tier_name: str) -> float:
    """Compute a salted threshold by jittering *base* within +/-5%.

    Uses HMAC-SHA256(salt, tier_name) to derive a deterministic but
    unpredictable jitter for each (brain, tier) pair.

    Args:
        base: The nominal threshold (e.g. 0.60 or 0.90).
        salt: The brain's 64-char hex salt.
        tier_name: Graduation tier identifier (e.g. "PATTERN" or "RULE").

    Returns:
        A float in [base * 0.95, base * 1.05].
    """
    digest = hmac.new(
        salt.encode("utf-8"),
        tier_name.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    # Map first 4 bytes to a float in [0, 1)
    (value,) = struct.unpack(">I", digest[:4])
    fraction = value / 0xFFFFFFFF  # [0, 1]

    # Map to [-0.05, +0.05] of base
    jitter = (fraction * 0.10 - 0.05) * base
    return base + jitter
