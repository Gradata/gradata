"""Tenant identity for the Gradata SDK.

Reads (and lazily creates) the per-brain tenant UUID. All new
``INSERT`` paths should include ``tenant_id`` from :func:`get_tenant_id`.

Resolution order:
1. ``GRADATA_TENANT_ID`` env var (for tests, CI, overrides).
2. ``<brain_dir>/.tenant_id`` on disk.
3. Generate a new UUID and write it to ``<brain_dir>/.tenant_id``.

The tenant UUID lives in a dotfile (not in system.db) so it survives
DB rebuilds and can be read by tooling outside the SDK (cloud sync,
migrations, diagnostics).
"""
from __future__ import annotations

import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Final

TENANT_FILE: Final[str] = ".tenant_id"
ENV_TENANT_ID: Final[str] = "GRADATA_TENANT_ID"


def _is_valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def get_tenant_id(brain_dir: str | Path) -> str:
    """Return this brain's tenant UUID. Creates the file if missing.

    Args:
        brain_dir: Path to the brain directory (the one containing system.db).

    Returns:
        A valid UUID string.
    """
    env = os.environ.get(ENV_TENANT_ID, "").strip()
    if env and _is_valid_uuid(env):
        return env

    brain = Path(brain_dir).expanduser().resolve()
    fpath = brain / TENANT_FILE
    if fpath.exists():
        tid = fpath.read_text(encoding="utf-8").strip()
        if _is_valid_uuid(tid):
            return tid

    brain.mkdir(parents=True, exist_ok=True)
    tid = str(uuid.uuid4())
    fpath.write_text(tid, encoding="utf-8")
    return tid


def peek_tenant_id(brain_dir: str | Path) -> str | None:
    """Read the tenant UUID without creating it. Returns None if absent/invalid."""
    env = os.environ.get(ENV_TENANT_ID, "").strip()
    if env and _is_valid_uuid(env):
        return env
    fpath = Path(brain_dir).expanduser().resolve() / TENANT_FILE
    if not fpath.exists():
        return None
    tid = fpath.read_text(encoding="utf-8").strip()
    return tid if _is_valid_uuid(tid) else None


@lru_cache(maxsize=32)
def _cached(brain_key: str) -> str:
    return get_tenant_id(brain_key)


def tenant_for(brain_dir: str | Path) -> str:
    """Cached form of :func:`get_tenant_id` for hot paths.

    When ``GRADATA_TENANT_ID`` is set, the cache is bypassed so that
    tests and CI overrides take effect immediately without needing to
    clear the lru_cache manually.
    """
    env = os.environ.get(ENV_TENANT_ID, "").strip()
    if env and _is_valid_uuid(env):
        return env
    return _cached(str(Path(brain_dir).expanduser().resolve()))
