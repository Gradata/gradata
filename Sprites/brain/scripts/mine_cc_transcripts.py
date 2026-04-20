"""Mine Claude Code transcript archive for implicit-feedback signals.

Walks ~/.claude/projects/*/*.jsonl and extracts user messages matching the
pushback/reminder/gap/challenge regexes from .claude/hooks/user-prompt/
implicit-feedback.js. Emits IMPLICIT_FEEDBACK events in the same format the
live hook produces, so the existing graduation pipeline can consume them.

Default mode is --dry-run: counts only, writes shadow events.backfill.jsonl.
Pass --commit to append to the live brain's events.jsonl.

Usage:
    python brain/scripts/mine_cc_transcripts.py --dry-run
    python brain/scripts/mine_cc_transcripts.py --commit

Scope:
    By default scans every project dir under ~/.claude/projects/. Use
    --project NAME to limit to one (e.g. C--Users-olive-OneDrive-Desktop-Sprites-Work).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──
PROJECTS_ROOT = Path.home() / ".claude" / "projects"
BRAIN_DIR = Path("C:/Users/olive/SpritesWork/brain")
LIVE_EVENTS = BRAIN_DIR / "events.jsonl"
SHADOW_EVENTS = BRAIN_DIR / "events.backfill.jsonl"

# ── Pushback regexes (ported verbatim from implicit-feedback.js) ──
PUSHBACK = [
    re.compile(r"are you sure", re.I),
    re.compile(r"that'?s (?:wrong|not right|incorrect)", re.I),
    re.compile(r"no[,.]?\s+(?:not that|don't|stop)", re.I),
    re.compile(r"why (?:did|didn't|aren't) you", re.I),
    re.compile(r"not accurate", re.I),
]
REMINDER = [
    re.compile(r"make sure", re.I),
    re.compile(r"don'?t forget", re.I),
    re.compile(r"remember to", re.I),
    re.compile(r"i (?:already|just) (?:told|said|asked)", re.I),
    re.compile(r"like i said", re.I),
]
GAP = [
    re.compile(r"what about", re.I),
    re.compile(r"you (?:forgot|missed|skipped|dropped|ignored)", re.I),
    re.compile(r"did you (?:check|verify|test|review)", re.I),
]
CHALLENGE = [
    re.compile(r"are we (?:sure|missing)", re.I),
    re.compile(r"won'?t (?:that|people|this)", re.I),
    re.compile(r"i feel like", re.I),
    re.compile(r"is that (?:right|correct)", re.I),
]
SIGNAL_GROUPS = {
    "PUSHBACK": PUSHBACK,
    "REMINDER": REMINDER,
    "GAP": GAP,
    "CHALLENGE": CHALLENGE,
}


def detect_signals(text: str) -> list[str]:
    """Return list of matched signal names for a given user message."""
    if not text or len(text) < 10:
        return []
    hits: list[str] = []
    for name, patterns in SIGNAL_GROUPS.items():
        for pattern in patterns:
            if pattern.search(text):
                hits.append(name)
                break  # one hit per group is enough
    return hits


def extract_user_text(msg: dict) -> str:
    """Pull user-prompt text out of a transcript message envelope."""
    if msg.get("type") != "user":
        return ""
    message = msg.get("message") or {}
    if message.get("role") != "user":
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Content may be a list of parts (text + tool_result etc.)
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return ""


def iter_jsonl(path: Path):
    """Yield parsed JSON objects from a JSONL file, skipping bad lines."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def mine_session(path: Path) -> list[dict]:
    """Return a list of IMPLICIT_FEEDBACK event dicts for one session file."""
    events: list[dict] = []
    for msg in iter_jsonl(path):
        text = extract_user_text(msg)
        if not text:
            continue
        # Skip the boilerplate scheduled-task prompts and system-injected payloads
        lowered = text[:200].lower()
        if "<scheduled-task" in lowered or text.startswith("<system-reminder"):
            continue
        signals = detect_signals(text)
        if not signals:
            continue
        unique = list(dict.fromkeys(signals))  # preserve order, dedup
        snippet = re.sub(r'[\"\\\n]', " ", text[:100])
        event = {
            "ts": msg.get("timestamp")
            or datetime.now(timezone.utc).isoformat(),
            "event": "IMPLICIT_FEEDBACK",
            "source": "mine_cc_transcripts",
            "data": json.dumps({
                "signals": ",".join(unique),
                "snippet": snippet,
                "session_id": msg.get("sessionId") or path.stem,
                "uuid": msg.get("uuid", ""),
                "project": path.parent.name,
            }, ensure_ascii=False),
        }
        events.append(event)
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Append events to live brain events.jsonl (default: shadow file only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts only; do not write any file (overrides --commit)",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Only scan one project dir (e.g. C--Users-olive-OneDrive-Desktop-Sprites-Work)",
    )
    parser.add_argument(
        "--projects-root",
        default=str(PROJECTS_ROOT),
        help=f"Override transcript root (default: {PROJECTS_ROOT})",
    )
    args = parser.parse_args()

    root = Path(args.projects_root)
    if not root.exists():
        print(f"[err] transcript root not found: {root}", file=sys.stderr)
        return 1

    project_dirs: list[Path]
    if args.project:
        project_dirs = [root / args.project]
    else:
        project_dirs = [p for p in root.iterdir() if p.is_dir()]

    total_sessions = 0
    total_events: list[dict] = []
    per_project: Counter = Counter()
    per_signal: Counter = Counter()

    for pd in project_dirs:
        if not pd.exists():
            print(f"[warn] skip missing {pd}", file=sys.stderr)
            continue
        jsonl_files = sorted(pd.glob("*.jsonl"))
        for jf in jsonl_files:
            total_sessions += 1
            evs = mine_session(jf)
            for ev in evs:
                total_events.append(ev)
                per_project[pd.name] += 1
                payload = json.loads(ev["data"])
                for sig in payload["signals"].split(","):
                    per_signal[sig] += 1

    # ── Report ──
    print(f"\n=== mine_cc_transcripts summary ===")
    print(f"Sessions scanned:      {total_sessions}")
    print(f"Events extracted:      {len(total_events)}")
    print("\nBy signal:")
    for sig, n in per_signal.most_common():
        print(f"  {sig:10s} {n}")
    print("\nBy project (top 10):")
    for proj, n in per_project.most_common(10):
        print(f"  {n:5d}  {proj}")

    if args.dry_run or (not args.commit):
        # Default behavior = write shadow file, don't touch live events
        if not args.dry_run:
            SHADOW_EVENTS.parent.mkdir(parents=True, exist_ok=True)
            with SHADOW_EVENTS.open("w", encoding="utf-8") as fh:
                for ev in total_events:
                    fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            print(f"\n[dry] wrote {len(total_events)} events -> {SHADOW_EVENTS}")
            print("[dry] review, then re-run with --commit to merge into live brain")
        else:
            print("\n[dry-run] no file written")
        return 0

    # --commit: append to live events
    if not LIVE_EVENTS.exists():
        print(f"[err] live events.jsonl not found: {LIVE_EVENTS}", file=sys.stderr)
        return 2
    with LIVE_EVENTS.open("a", encoding="utf-8") as fh:
        for ev in total_events:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    print(f"\n[commit] appended {len(total_events)} events -> {LIVE_EVENTS}")
    print("[commit] run graduation sweep next: python brain/scripts/graduation_sweep.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
