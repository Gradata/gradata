"""Atomic file write helpers."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text to *path* via a sibling temp file and atomic replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")

    try:
        with tmp.open("w", encoding=encoding) as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        _fsync_dir(target.parent)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


def atomic_write_json(path: str | Path, data: object, *, indent: int = 2) -> None:
    """Write JSON to *path* via a sibling temp file and atomic replace."""
    atomic_write_text(path, json.dumps(data, indent=indent) + "\n")


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
