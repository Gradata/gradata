"""Tenant UUID read/create for a given brain directory.

The tenant UUID is stored at ``<brain_dir>/.tenant_id`` as a plain UTF-8
file. This file is the single local source of truth for which tenant a
brain belongs to. It is intentionally separate from system.db so it
survives DB rebuilds.

Usage (as module):
    from brain.scripts.migrations.tenant_uuid import get_or_create_tenant_id
    tid = get_or_create_tenant_id(Path("C:/.../SpritesWork/brain"))

CLI:
    python src/gradata/_migrations/tenant_uuid.py --brain C:/.../brain
"""
from __future__ import annotations

import argparse
import os
import uuid
from pathlib import Path

TENANT_FILE = ".tenant_id"


def get_or_create_tenant_id(brain_dir: str | Path) -> str:
    """Atomic read-or-create of the brain's tenant UUID.

    Uses ``O_CREAT | O_EXCL`` on a temp file + ``os.replace`` so two
    concurrent callers cannot mint different UUIDs for the same brain.
    The loser of the race falls through to read the winner's value.
    """
    brain = Path(brain_dir).expanduser().resolve()
    brain.mkdir(parents=True, exist_ok=True)
    fpath = brain / TENANT_FILE

    if fpath.exists():
        tid = fpath.read_text(encoding="utf-8").strip()
        if _is_valid_uuid(tid):
            return tid

    # Exclusive create of a per-process temp file, then atomic rename.
    new_tid = str(uuid.uuid4())
    tmp = brain / f".tenant_id.tmp.{os.getpid()}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(tmp, flags, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(new_tid)
        # os.replace is atomic on POSIX AND on Windows (overwrites target).
        # If the target already exists (another process won), we still replace
        # with our tmp -- but we'll read the existing file below instead.
        if not fpath.exists():
            os.replace(tmp, fpath)
        else:
            # Lost the race: drop our temp, read what the winner wrote.
            os.unlink(tmp)
    except FileExistsError:
        # Extremely unlikely (PID collision); fall back to reading disk.
        pass

    tid = fpath.read_text(encoding="utf-8").strip()
    if _is_valid_uuid(tid):
        return tid
    # Shouldn't happen; return our generated UUID as last resort.
    return new_tid


def read_tenant_id(brain_dir: str | Path) -> str | None:
    fpath = Path(brain_dir).expanduser().resolve() / TENANT_FILE
    if not fpath.exists():
        return None
    tid = fpath.read_text(encoding="utf-8").strip()
    return tid if _is_valid_uuid(tid) else None


def _is_valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _main() -> int:
    ap = argparse.ArgumentParser(description="Read or create brain tenant UUID")
    ap.add_argument("--brain", required=True, help="Path to brain directory")
    ap.add_argument("--peek", action="store_true", help="Read only; never create")
    args = ap.parse_args()

    if args.peek:
        tid = read_tenant_id(args.brain)
        if tid is None:
            print("(no tenant id)")
            return 1
        print(tid)
        return 0

    print(get_or_create_tenant_id(args.brain))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
