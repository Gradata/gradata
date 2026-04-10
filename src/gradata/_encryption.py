"""Encryption at rest for brain databases.

Optional feature — requires: pip install gradata[encrypted]

Encrypt-on-close, decrypt-on-open pattern:
  - Brain opens: decrypt system.db.enc → system.db, use SQLite normally
  - Brain closes: encrypt system.db → system.db.enc, delete plaintext

Key management (priority order):
  1. Brain(encryption_key="...") constructor parameter
  2. GRADATA_ENCRYPTION_KEY environment variable
  3. ~/.gradata/encryption.key auto-generated file
"""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

_SALT_FILE = "system.db.salt"
_ENC_FILE = "system.db.enc"
_DB_FILE = "system.db"


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from passphrase + salt using PBKDF2 (stdlib only)."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 600_000)


def load_or_generate_salt(brain_dir: Path) -> bytes:
    """Load existing salt or generate a new 16-byte salt."""
    salt_path = brain_dir / _SALT_FILE
    if salt_path.is_file():
        return salt_path.read_bytes()
    salt = secrets.token_bytes(16)
    salt_path.write_bytes(salt)
    return salt


def _get_fernet(key_bytes: bytes):
    """Create a Fernet instance from raw 32-byte key. Requires cryptography."""
    try:
        import base64

        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError(
            "Encryption requires the 'cryptography' package.\n"
            "Install it with: pip install gradata[encrypted]"
        ) from None
    fernet_key = base64.urlsafe_b64encode(key_bytes[:32])
    return Fernet(fernet_key)


def encrypt_file(src: Path, dst: Path, key_bytes: bytes) -> Path:
    """Encrypt a file using Fernet (AES-128-CBC + HMAC)."""
    fernet = _get_fernet(key_bytes)
    plaintext = src.read_bytes()
    dst.write_bytes(fernet.encrypt(plaintext))
    return dst


def decrypt_file(src: Path, dst: Path, key_bytes: bytes) -> Path:
    """Decrypt a Fernet-encrypted file."""
    fernet = _get_fernet(key_bytes)
    ciphertext = src.read_bytes()
    dst.write_bytes(fernet.decrypt(ciphertext))
    return dst


def resolve_encryption_key(explicit_key: str | None = None) -> str | None:
    """Resolve encryption key from explicit param, env var, or key file."""
    if explicit_key:
        return explicit_key
    env_key = os.environ.get("GRADATA_ENCRYPTION_KEY")
    if env_key:
        return env_key
    key_file = Path.home() / ".gradata" / "encryption.key"
    if key_file.is_file():
        return key_file.read_text(encoding="utf-8").strip()
    return None


def open_encrypted_db(brain_dir: Path, encryption_key: str) -> None:
    """Decrypt system.db.enc → system.db for use. Call before get_connection."""
    enc_path = brain_dir / _ENC_FILE
    db_path = brain_dir / _DB_FILE
    salt = load_or_generate_salt(brain_dir)
    key_bytes = derive_key(encryption_key, salt)

    if enc_path.is_file() and not db_path.is_file():
        decrypt_file(enc_path, db_path, key_bytes)
    elif enc_path.is_file() and db_path.is_file():
        # Both exist — crash recovery. Re-encrypt from plaintext (more recent).
        pass  # Just use the existing plaintext db


def close_encrypted_db(brain_dir: Path, encryption_key: str) -> None:
    """Encrypt system.db → system.db.enc and remove plaintext.

    Safety: writes to .enc.tmp first, renames atomically, then deletes plaintext.
    If encryption fails, plaintext survives intact.
    """
    db_path = brain_dir / _DB_FILE
    enc_path = brain_dir / _ENC_FILE
    tmp_path = brain_dir / (_ENC_FILE + ".tmp")
    if not db_path.is_file():
        return
    salt = load_or_generate_salt(brain_dir)
    key_bytes = derive_key(encryption_key, salt)
    encrypt_file(db_path, tmp_path, key_bytes)
    if tmp_path.is_file() and tmp_path.stat().st_size > 0:
        tmp_path.replace(enc_path)  # atomic rename
        db_path.unlink()
    else:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError("Encryption produced empty or missing file — plaintext preserved")
