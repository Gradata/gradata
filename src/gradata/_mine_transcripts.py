"""Backfill brain events from Claude Code transcript archives.

Walks ~/.claude/projects/*/*.jsonl and emits IMPLICIT_FEEDBACK events matching
the format the live user-prompt hook produces. Packaged as an SDK module so
every Gradata user can bootstrap their brain from their own transcript history.

Public entry point: run_mine(brain_root, projects_root, project, commit, dry_run).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ── Pushback / reminder / gap / challenge regexes ──
# Ported verbatim from .claude/hooks/user-prompt/implicit-feedback.js so the
# offline backfill produces events identical to the live hook.
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


def _detect_signals(text: str) -> list[str]:
    if not text or len(text) < 10:
        return []
    hits: list[str] = []
    for name, patterns in SIGNAL_GROUPS.items():
        for pattern in patterns:
            if pattern.search(text):
                hits.append(name)
                break
    return hits


def _extract_user_text(msg: dict) -> str:
    if msg.get("type") != "user":
        return ""
    message = msg.get("message") or {}
    if message.get("role") != "user":
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return ""


def _iter_jsonl(path: Path):
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


def _mine_session(path: Path) -> list[dict]:
    events: list[dict] = []
    for msg in _iter_jsonl(path):
        text = _extract_user_text(msg)
        if not text:
            continue
        lowered = text[:200].lower()
        if "<scheduled-task" in lowered or text.startswith("<system-reminder"):
            continue
        signals = _detect_signals(text)
        if not signals:
            continue
        unique = list(dict.fromkeys(signals))
        snippet = re.sub(r'[\"\\\n]', " ", text[:100])
        events.append({
            "ts": msg.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "event": "IMPLICIT_FEEDBACK",
            "source": "gradata.mine",
            "data": json.dumps({
                "signals": ",".join(unique),
                "snippet": snippet,
                "session_id": msg.get("sessionId") or path.stem,
                "uuid": msg.get("uuid", ""),
                "project": path.parent.name,
            }, ensure_ascii=False),
        })
    return events


def run_mine(
    *,
    brain_root: Path,
    projects_root: Path | None = None,
    project: str | None = None,
    commit: bool = False,
    dry_run: bool = True,
) -> int:
    """Scan Claude Code transcripts and emit IMPLICIT_FEEDBACK events.

    Default is dry-run = writes to ``events.backfill.jsonl`` shadow file.
    With ``commit=True``, appends to the live ``events.jsonl``.
    """
    root = projects_root or (Path.home() / ".claude" / "projects")
    if not root.exists():
        print(f"[err] transcript root not found: {root}", file=sys.stderr)
        return 1

    project_dirs: list[Path]
    if project:
        project_dirs = [root / project]
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
        for jf in sorted(pd.glob("*.jsonl")):
            total_sessions += 1
            for ev in _mine_session(jf):
                total_events.append(ev)
                per_project[pd.name] += 1
                payload = json.loads(ev["data"])
                for sig in payload["signals"].split(","):
                    per_signal[sig] += 1

    print("\n=== gradata mine summary ===")
    print(f"Sessions scanned: {total_sessions}")
    print(f"Events extracted: {len(total_events)}")
    print("\nBy signal:")
    for sig, n in per_signal.most_common():
        print(f"  {sig:10s} {n}")
    print("\nBy project (top 10):")
    for proj, n in per_project.most_common(10):
        print(f"  {n:5d}  {proj}")

    brain_root.mkdir(parents=True, exist_ok=True)
    live_events = brain_root / "events.jsonl"
    shadow_events = brain_root / "events.backfill.jsonl"

    if dry_run or not commit:
        if not dry_run:
            with shadow_events.open("w", encoding="utf-8") as fh:
                for ev in total_events:
                    fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            print(f"\n[shadow] wrote {len(total_events)} events -> {shadow_events}")
            print("[shadow] review, then re-run with --commit to merge into live brain")
        else:
            print("\n[dry-run] no file written")
        return 0

    with live_events.open("a", encoding="utf-8") as fh:
        for ev in total_events:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    print(f"\n[commit] appended {len(total_events)} events -> {live_events}")
    return 0
