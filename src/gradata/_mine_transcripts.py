"""Backfill brain events from Claude Code transcript archives.

Walks ~/.claude/projects/*/*.jsonl and emits IMPLICIT_FEEDBACK events matching
the format the live user-prompt hook produces. Packaged as an SDK module so
every Gradata user can bootstrap their brain from their own transcript history.

Public entry point: run_mine(brain_root, projects_root, project, commit, dry_run).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
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

# ── Correction category taxonomy ──
# Ported from .claude/hooks/reflect/scripts/capture_learning.py so mined
# IMPLICIT_FEEDBACK signals can dual-emit as CORRECTION events with the same
# categorization the live hook produces. Order matters: specific categories
# before broad ones (ACCURACY contains "wrong" which would swallow others).
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "DATA_INTEGRITY": ["filter", "owner", "oliver only", "anna", "shared",
                       "duplicate", "overlap", "wrong person", "wrong deal"],
    "ARCHITECTURE": ["import", "module", "class", "function", "refactor",
                     "dependency", "structure", "script", "python", "def "],
    "TOOL": ["tool", "api", "mcp", "install", "config", "command", "endpoint",
             "token", "integration"],
    "LEADS": ["lead", "prospect", "enrich", "csv", "campaign", "instantly",
              "apollo", "linkedin", "icp"],
    "PRICING": ["price", "cost", "pricing", "monthly", "annual", "$",
                "starter", "standard", "plan"],
    "DEMO_PREP": ["demo", "cheat sheet", "battlecard", "prep"],
    "DRAFTING": ["email", "draft", "subject line", "follow-up", "copy",
                 "prose", "paragraph", "rewrite", "subject"],
    "CONTEXT": ["session type", "startup context", "context window",
                "already know", "load context", "you loaded"],
    "PROCESS": ["skip", "forgot", "missing step", "workflow", "told you",
                "step", "order"],
    "THOROUGHNESS": ["incomplete", "all of them", "don't stop", "finish",
                     "remaining", "rest of", "the rest"],
    "POSITIONING": ["agency", "competitor", "frame", "position", "pitch",
                    "messaging", "value prop"],
    "COMMUNICATION": ["unclear", "ambiguous", "severity", "blocker",
                      "too verbose", "verbose", "too long", "confusing"],
    "TONE": ["tone", "aggressive", "pushy", "salesy", "formal", "casual",
             "softer", "harsh"],
    "ACCURACY": ["incorrect", "inaccurate", "verify", "hallucin", "fabricat",
                 "made up", "not real", "doesn't exist", "never said",
                 "misquot", "stale", "wrong number", "wrong data",
                 "wrong name", "wrong company"],
}


def _classify_correction(text: str) -> str:
    """Classify a correction into the 14-category taxonomy. Falls back to GENERAL."""
    normalised = " ".join(text.split()).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw.lower() in normalised for kw in keywords):
            return category
    return "GENERAL"


def _pattern_hash(category: str, text: str) -> str:
    """Stable 16-char hash keyed on category + normalized text.

    Matches the graduation-sweep.py hashing scheme so mined patterns dedup
    correctly against any future live-hook emissions of the same phrase.
    """
    n = unicodedata.normalize("NFC", text.lower().strip())
    n = " ".join(n.split())
    return hashlib.sha256(f"{category.upper()}:{n}".encode()).hexdigest()[:16]


def _session_uuid_to_int(session_uuid: str) -> int:
    """Stable 31-bit int from session UUID for correction_patterns.session_id.

    The patterns table requires INTEGER session_id (used for distinct-session
    counting during graduation). Hashing keeps collisions improbable while
    letting the graduation query (COUNT(DISTINCT session_id) >= min_sessions)
    work correctly across separately-mined transcript files.
    """
    if not session_uuid:
        return 0
    h = hashlib.sha256(session_uuid.encode()).hexdigest()[:8]
    return int(h, 16) & 0x7FFFFFFF


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


_NOISE_PREFIXES = (
    "<system-reminder",
    "<command-message",
    "<command-name",
    "<local-command-stdout",
    "<observed_from_primary_session",
    "<progress_summary",
    "<bash-stdout",
    "<bash-stderr",
)

_NOISE_SUBSTRINGS = (
    "<scheduled-task",
    "<observed_from_primary_session",
    "progress summary checkpoint",
    "caveat: the messages below were generated",
    "base directory for this skill",
    "this session is being continued from a previous",
    "summary below covers the earlier portion",
)


def _mine_session(path: Path) -> list[dict]:
    events: list[dict] = []
    # Skip entire claude-mem observer project — every event is a wrapped
    # echo of another session's traffic, not a real user correction.
    if "claude-mem-observer" in path.parent.name:
        return events
    for msg in _iter_jsonl(path):
        text = _extract_user_text(msg)
        if not text:
            continue
        stripped = text.lstrip()
        if stripped.startswith(_NOISE_PREFIXES):
            continue
        lowered = text[:400].lower()
        if any(marker in lowered for marker in _NOISE_SUBSTRINGS):
            continue
        signals = _detect_signals(text)
        if not signals:
            continue
        unique = list(dict.fromkeys(signals))
        snippet = re.sub(r'[\"\\\n]', " ", text[:100])
        category = _classify_correction(text)
        session_uuid = msg.get("sessionId") or path.stem
        events.append({
            "ts": msg.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "event": "IMPLICIT_FEEDBACK",
            "source": "gradata.mine",
            "category": category,
            "session_uuid": session_uuid,
            "text": text[:200],
            "data": json.dumps({
                "signals": ",".join(unique),
                "snippet": snippet,
                "session_id": session_uuid,
                "uuid": msg.get("uuid", ""),
                "project": path.parent.name,
                "category": category,
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

    # Dual-write via _events.emit() so events land in both events.jsonl AND
    # system.db — session_close._has_new_triggers reads the DB, so without
    # the DB write, graduation won't see these backfilled events.
    # emit() dedup key (tenant_id, ts, type, source) + ts override makes
    # re-runs idempotent while preserving historical timestamps.
    from gradata._events import emit as _emit
    from gradata.brain import Brain
    brain = Brain(brain_root)  # ensures table + ctx setup
    written = 0
    skipped = 0
    for ev in total_events:
        try:
            payload = json.loads(ev["data"])
        except (json.JSONDecodeError, TypeError):
            skipped += 1
            continue
        try:
            _emit(
                event_type=ev["event"],
                source=ev["source"],
                data=payload,
                session=0,
                ts=ev["ts"],
                ctx=brain.ctx,
            )
        except Exception:
            skipped += 1
            continue
        written += 1

    # Graduation-bridge: upsert mined signals directly into correction_patterns
    # so the rule_pipeline can lift them into RULE-state lessons. Bypasses
    # graduation-sweep's session-window filter (which only reads the last few
    # sessions, never a historical session=0 backfill). Each mined transcript
    # session becomes a distinct session_id via UUID hash, so min_sessions
    # graduation thresholds still work across independently-mined transcripts.
    patterns_written = 0
    patterns_skipped = 0
    try:
        from gradata.enhancements.meta_rules_storage import (
            upsert_correction_patterns_batch,
        )
        db_path = brain.ctx.db_path
        batch: list[tuple[str, str, str, int, str]] = []
        seen: set[tuple[str, int]] = set()
        for ev in total_events:
            category = ev.get("category") or "GENERAL"
            text = ev.get("text") or ""
            if len(text) < 10:
                patterns_skipped += 1
                continue
            session_uuid = ev.get("session_uuid") or ""
            session_id = _session_uuid_to_int(session_uuid)
            phash = _pattern_hash(category, text)
            dedup_key = (phash, session_id)
            if dedup_key in seen:
                patterns_skipped += 1
                continue
            seen.add(dedup_key)
            batch.append((phash, category, text, session_id, "minor"))
        if batch:
            patterns_written = upsert_correction_patterns_batch(db_path, batch)
    except Exception as exc:
        print(f"[commit] pattern upsert skipped: {exc}", file=sys.stderr)

    print(f"\n[commit] wrote {written} events to events.jsonl + system.db ({skipped} skipped)")
    print(f"[commit] upserted {patterns_written} correction_patterns ({patterns_skipped} skipped)")
    return 0
