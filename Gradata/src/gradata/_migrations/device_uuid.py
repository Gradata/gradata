"""Device UUID read/create for a given brain directory.

The device_id is stored at ``<brain_dir>/.device_id`` as a plain UTF-8 file.
It identifies *which machine* wrote an event — scoping authorship so cloud
sync can enforce "one author per event" and deterministic global ordering
on ``(ts, device_id, event_id)``.

Format: ``dev_<32 hex>`` — ``dev_`` prefix + uuid4 hex. Prefixed so logs and
error messages disambiguate from tenant_id (no prefix) and brain_id (``brn_``).

Per-brain, per-machine: two devices sharing a brain get different ids; one
brain on one machine is stable across sessions.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import uuid
from pathlib import Path

DEVICE_FILE = ".device_id"
_DEVICE_RE = re.compile(r"^dev_[0-9a-f]{32}$")


def _new_device_id() -> str:
    return f"dev_{uuid.uuid4().hex}"


def _is_valid(s: str) -> bool:
    return bool(_DEVICE_RE.match(s))


def get_or_create_device_id(brain_dir: str | Path) -> str:
    """Atomic read-or-create of the brain's device id for this machine.

    Same race-safe pattern as ``tenant_uuid.get_or_create_tenant_id``:
    exclusive create of a pid-scoped temp file, atomic ``os.replace``,
    fall through to read on collision.
    """
    brain = Path(brain_dir).expanduser().resolve()
    brain.mkdir(parents=True, exist_ok=True)
    fpath = brain / DEVICE_FILE

    if fpath.exists():
        did = fpath.read_text(encoding="utf-8").strip()
        if _is_valid(did):
            return did

    new_did = _new_device_id()
    tmp = brain / f".device_id.tmp.{os.getpid()}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(tmp, flags, 0o644)
    except FileExistsError:
        # Extremely unlikely PID collision; fall through to disk read.
        pass
    else:
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(new_did)
            if not fpath.exists():
                os.replace(tmp, fpath)
            else:
                os.unlink(tmp)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    if fpath.exists():
        did = fpath.read_text(encoding="utf-8").strip()
        if _is_valid(did):
            return did
    return new_did


def read_device_id(brain_dir: str | Path) -> str | None:
    fpath = Path(brain_dir).expanduser().resolve() / DEVICE_FILE
    if not fpath.exists():
        return None
    did = fpath.read_text(encoding="utf-8").strip()
    return did if _is_valid(did) else None


def _main() -> int:
    ap = argparse.ArgumentParser(description="Read or create brain device id")
    ap.add_argument("--brain", required=True, help="Path to brain directory")
    ap.add_argument("--peek", action="store_true", help="Read only; never create")
    args = ap.parse_args()

    if args.peek:
        did = read_device_id(args.brain)
        if did is None:
            print("(no device id)")
            return 1
        print(did)
        return 0

    print(get_or_create_device_id(args.brain))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
