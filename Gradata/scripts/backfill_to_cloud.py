#!/usr/bin/env python3
"""
backfill_to_cloud.py — One-shot historical event replay.

Pushes every event in events.jsonl to gradata-cloud /sync. Idempotent —
server upserts on (brain_id, event_id), so re-running is safe.

Use after fixing Bug 1 (PR #11) + Bug 2 (PRs #12 + #161). Resets the local
sync state so the entire jsonl is replayed.

Usage:
    python scripts/backfill_to_cloud.py [--dry-run]

Requires:
    GRADATA_API_KEY env var
    BRAIN_DIR env var (or pass --brain-dir)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from gradata.cloud.client import CloudClient


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--brain-dir",
        default=os.environ.get("BRAIN_DIR"),
        help="Brain directory (default: $BRAIN_DIR)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Count events to push without actually pushing",
    )
    args = p.parse_args()

    if not args.brain_dir:
        print("ERROR: --brain-dir or $BRAIN_DIR required", file=sys.stderr)
        return 2

    brain_dir = Path(args.brain_dir)
    events_jsonl = brain_dir / "events.jsonl"
    if not events_jsonl.exists():
        print(f"ERROR: {events_jsonl} not found", file=sys.stderr)
        return 2

    # Count events first
    total = 0
    by_type: dict[str, int] = {}
    with open(events_jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            etype = ev.get("type", "unknown")
            by_type[etype] = by_type.get(etype, 0) + 1

    print(f"Found {total} events in {events_jsonl}")
    for etype, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
        print(f"  {etype:30s}  {n}")

    if args.dry_run:
        print("\n--dry-run: not pushing")
        return 0

    # Reset sync state so every event replays
    state_file = brain_dir / ".gradata-sync-state.json"
    if state_file.exists():
        backup = state_file.with_suffix(".json.pre-backfill.bak")
        state_file.rename(backup)
        print(f"Backed up sync state to {backup}")
    state_file.write_text(json.dumps({"last_sync_at": "", "last_event_id": ""}))

    # Connect + sync in a loop until empty
    client = CloudClient(brain_dir=brain_dir)
    if not client.connect():
        print("ERROR: client.connect() failed", file=sys.stderr)
        return 3

    pushed = 0
    iterations = 0
    while True:
        iterations += 1
        result = client.sync()
        if result is None or result is False:
            print(f"sync() returned {result!r} on iteration {iterations}, stopping")
            break
        if isinstance(result, int):
            n = result
        elif isinstance(result, dict):
            n = result.get("ingested_count", 0)
        else:
            n = 0
        pushed += n
        print(f"  iter {iterations}: +{n} events (total {pushed})")
        if n == 0:
            break
        if iterations > 200:
            print("Aborting: 200 iterations without completion")
            break

    print(f"\nDone. Pushed {pushed}/{total} events in {iterations} iterations.")
    return 0 if pushed > 0 or total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
