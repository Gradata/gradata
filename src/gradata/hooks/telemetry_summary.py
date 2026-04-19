"""Rollup of recent gradata hook injections (injected/suppressed/bytes per hook) from
``{GRADATA_BRAIN_DIR}/telemetry.jsonl``. Run ``python -m gradata.hooks.telemetry_summary``."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from ._base import resolve_brain_dir


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    return f"{n / (1024 * 1024):.2f}MB"


def summarize(rows: list[dict]) -> str:
    if not rows:
        return "(no telemetry recorded — set GRADATA_TELEMETRY=on and run a hook)"

    by_hook: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "bytes": 0, "skips": 0})
    total_calls = 0
    total_bytes = 0
    for r in rows:
        hook = r.get("hook", "?")
        b = int(r.get("bytes", 0))
        by_hook[hook]["calls"] += 1
        by_hook[hook]["bytes"] += b
        if b == 0:
            by_hook[hook]["skips"] += 1
        total_calls += 1
        total_bytes += b

    lines = [
        f"gradata telemetry — {total_calls} hook calls, {_format_bytes(total_bytes)} total injected",
        "",
        f"  {'hook':<28} {'calls':>6} {'skipped':>8} {'bytes':>10}  avg",
        "  " + "-" * 64,
    ]
    for hook in sorted(by_hook, key=lambda h: -by_hook[h]["bytes"]):
        s = by_hook[hook]
        avg = s["bytes"] // s["calls"] if s["calls"] else 0
        lines.append(
            f"  {hook:<28} {s['calls']:>6} {s['skips']:>8} {_format_bytes(s['bytes']):>10}  {avg}B"
        )
    skipped_total = sum(s["skips"] for s in by_hook.values())
    if total_calls:
        skip_pct = 100 * skipped_total / total_calls
        lines.append("")
        lines.append(f"  Suppressed {skipped_total}/{total_calls} calls ({skip_pct:.1f}%)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gradata-telemetry")
    parser.add_argument("--tail", type=int, default=500, help="last N entries (default 500)")
    parser.add_argument("--reset", action="store_true", help="truncate telemetry log and exit")
    args = parser.parse_args(argv)

    brain_dir = resolve_brain_dir()
    if not brain_dir:
        print("(no brain dir resolved — set GRADATA_BRAIN_DIR)", file=sys.stderr)
        return 1
    log_path = Path(brain_dir) / "telemetry.jsonl"

    if args.reset:
        if log_path.is_file():
            log_path.unlink()
            print(f"truncated {log_path}")
        else:
            print("(no telemetry file to truncate)")
        return 0

    rows: list[dict] = []
    if log_path.is_file():
        with log_path.open("r", encoding="utf-8") as _ld_fh:
            for _ld_line in _ld_fh.readlines()[-args.tail :]:
                try:
                    rows.append(json.loads(_ld_line))
                except (json.JSONDecodeError, ValueError):
                    continue
    print(summarize(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
