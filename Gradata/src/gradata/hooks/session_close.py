"""Stop hook: gated graduation/pipeline/tree sweep.

Fires on every Stop (end of every turn) because Claude Code has no
"real" session-end signal. Running the full waterfall on every turn is
expensive and pollutes the brain with redundant SESSION_END rows, so
this hook gates the heavy work on "was there a new correction/edit
since last run?". If not, it only flushes the retain queue (cheap) and
returns.

Gating model:
    <brain>/.last_close_ts    ISO timestamp of the last heavy-work run.
                              Created on first trigger; updated only when
                              work actually fires.

Trigger event types (any new row since last_close_ts fires the waterfall):
    CORRECTION, LESSON_CHANGE, RULE_FAILURE, IMPLICIT_FEEDBACK,
    OUTPUT_ACCEPTED, AGENT_OUTCOME, RULE_PATCHED

On first run (no stamp file) we wait until any trigger row exists and
then run the waterfall against the full event history; the stamp file
is written only after a successful pass.

Safety guards added 2026-04-23 (prevents runaway subprocess fleet):
    1. Concurrency lock  — TEMP/gradata-synthesizer.lock (PID-based).
    2. Hard timeout      — GRADATA_GRADUATION_TIMEOUT (default 300 s).
    3. SDK-only synth    — no claude CLI fallback; ANTHROPIC_API_KEY required.
    4. Throttle          — GRADATA_GRADUATION_INTERVAL_MINUTES + THRESHOLD.
    Kill switch          — GRADATA_DISABLE_GRADUATION=1 skips everything.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import errno as _errno
import logging
import os
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile
logger = logging.getLogger(__name__)


_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "Stop",
    "profile": Profile.MINIMAL,
    "timeout": 15000,
}

STAMP_FILE = ".last_close_ts"

TRIGGER_TYPES = (
    "CORRECTION",
    "LESSON_CHANGE",
    "RULE_FAILURE",
    "IMPLICIT_FEEDBACK",
    "OUTPUT_ACCEPTED",
    "AGENT_OUTCOME",
    "RULE_PATCHED",
)

# ── Stamp file (existing trigger-event gate) ─────────────────────────────────


def _read_stamp(brain_dir: Path) -> str | None:
    p = brain_dir / STAMP_FILE
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _write_stamp(brain_dir: Path, ts: str) -> None:
    with contextlib.suppress(OSError):
        (brain_dir / STAMP_FILE).write_text(ts, encoding="utf-8")


def _has_new_triggers(brain_dir: Path, since: str | None, until: str) -> bool:
    """True iff any TRIGGER_TYPES event rows exist in ``(since, until]``.

    Bounding the query on ``until`` prevents the later stamp write from
    falsely marking rows that arrive mid-waterfall as processed.
    """
    db = brain_dir / "system.db"
    if not db.is_file():
        return False
    placeholders = ",".join("?" * len(TRIGGER_TYPES))
    sql = f"SELECT 1 FROM events WHERE type IN ({placeholders}) AND ts <= ?"
    params: tuple = (*TRIGGER_TYPES, until)
    if since:
        sql += " AND ts > ?"
        params = (*params, since)
    sql += " LIMIT 1"
    try:
        with sqlite3.connect(db) as conn:
            row = conn.execute(sql, params).fetchone()
        return row is not None
    except sqlite3.Error as e:
        _log.debug("trigger check failed: %s", e)
        return False


# ── Concurrency lock (guard #1) ──────────────────────────────────────────────


def _lockfile_path() -> Path:
    override = os.environ.get("GRADATA_LOCK_FILE")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "gradata-synthesizer.lock"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes

            # SYNCHRONIZE access right — enough to test liveness, not to signal.
            handle = ctypes.windll.kernel32.OpenProcess(1048576, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except OSError as exc:
        # EPERM → process exists but we can't signal it (still alive).
        return exc.errno == _errno.EPERM


def _acquire_lock() -> bool:
    """Return True if the lock was acquired, False if a live process holds it."""
    lock_path = _lockfile_path()
    if lock_path.is_file():
        try:
            pid_str = lock_path.read_text(encoding="utf-8").strip()
            pid = int(pid_str)
            if _pid_alive(pid):
                return False  # Another live instance is running.
            # Stale lock from a dead process — fall through to reclaim.
        except (ValueError, OSError):
            logger.warning('Suppressed exception in _acquire_lock', exc_info=True)
    try:
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError:
        return False


def _release_lock() -> None:
    with contextlib.suppress(OSError):
        _lockfile_path().unlink(missing_ok=True)


# ── Hard timeout (guard #2) ──────────────────────────────────────────────────


def _run_with_timeout(fn, timeout_s: float) -> bool:
    """Run *fn* in a thread. Return True if it completed, False if timed out."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            future.result(timeout=timeout_s)
            return True
        except concurrent.futures.TimeoutError:
            _log.warning("graduation waterfall timed out after %.0fs", timeout_s)
            return False


# ── Throttle state (guard #4) ────────────────────────────────────────────────


def _throttle_state_path(brain_dir: Path) -> Path:
    state_dir = brain_dir / "state"
    with contextlib.suppress(OSError):
        state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "last_graduation.txt"


def _should_run_graduation(brain_dir: Path, lessons_path: Path) -> bool:
    """Return True if enough time has elapsed OR enough INSTINCT lessons are pending."""
    interval_minutes = float(os.environ.get("GRADATA_GRADUATION_INTERVAL_MINUTES", "60"))
    threshold = int(os.environ.get("GRADATA_GRADUATION_THRESHOLD", "20"))

    # Fast path: enough pending INSTINCT lessons → run regardless of interval.
    if lessons_path.is_file():
        try:
            from gradata.enhancements.self_improvement._confidence import parse_lessons

            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            instinct_count = sum(1 for l in lessons if l.state.name == "INSTINCT")
            if instinct_count >= threshold:
                return True
        except Exception:
            logger.warning('Suppressed exception in _should_run_graduation', exc_info=True)

    # Time-based gate.
    state_path = _throttle_state_path(brain_dir)
    if not state_path.is_file():
        return True  # First run ever.
    try:
        last_ts = datetime.fromisoformat(state_path.read_text(encoding="utf-8").strip())
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=UTC)
        elapsed_minutes = (datetime.now(UTC) - last_ts).total_seconds() / 60
        return elapsed_minutes >= interval_minutes
    except Exception:
        return True


def _update_graduation_state(brain_dir: Path) -> None:
    with contextlib.suppress(OSError):
        _throttle_state_path(brain_dir).write_text(datetime.now(UTC).isoformat(), encoding="utf-8")


# ── Waterfall steps ───────────────────────────────────────────────────────────


def _run_graduation(brain_dir: str) -> None:
    try:
        from gradata.enhancements.self_improvement import format_lessons, graduate, parse_lessons

        lessons_path = Path(brain_dir) / "lessons.md"
        if not lessons_path.is_file():
            return
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        if not lessons:
            return
        active, _ = graduate(lessons)
        lessons_path.write_text(format_lessons(active), encoding="utf-8")
    except Exception as e:
        _log.debug("graduation skipped: %s", e)


def _run_tree_consolidation(brain_dir: str) -> None:
    try:
        from gradata.enhancements.self_improvement import format_lessons, parse_lessons
        from gradata.rules.rule_tree import RuleTree

        lessons_path = Path(brain_dir) / "lessons.md"
        if not lessons_path.is_file():
            return
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        if not lessons:
            return

        if not any(l.path for l in lessons):
            return

        tree = RuleTree(lessons)
        session_fires: dict[str, list] = {}
        for lesson in lessons:
            if lesson.path and lesson.fire_count > 0:
                session_fires.setdefault(lesson.path, []).append(lesson)

        if not session_fires:
            return

        current_session = max(l.fire_count + l.sessions_since_fire for l in lessons)
        results = tree.consolidate(session_fires, current_session=current_session)

        if results["climbed"] > 0 or results["contracted"] > 0:
            lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    except Exception as e:
        _log.debug("tree consolidation skipped: %s", e)


def _run_pipeline(brain_dir: str, data: dict) -> None:
    try:
        from gradata.enhancements.rule_pipeline import run_rule_pipeline

        lessons_path = Path(brain_dir) / "lessons.md"
        db_path = Path(brain_dir) / "system.db"
        if not lessons_path.is_file():
            return
        current_session = int(data.get("session_number") or 0)
        result = run_rule_pipeline(
            lessons_path=lessons_path,
            db_path=db_path,
            current_session=current_session,
        )
        if result.graduated or result.meta_rules_created or result.hooks_promoted:
            _log.info(
                "Pipeline: %d graduated, %d meta-rules, %d hooks",
                len(result.graduated),
                len(result.meta_rules_created),
                len(result.hooks_promoted),
            )
    except Exception as e:
        _log.debug("pipeline skipped: %s", e)


_SOUL_CANDIDATES = (
    "domain/soul.md",
    "../Sprites/domain/soul.md",
    "Sprites/domain/soul.md",
)


def _load_soul_mandatories(brain_dir: Path) -> list[str]:
    """Pull hard voice rules out of soul.md as [MANDATORY] VOICE: lines.

    soul.md is the source of truth for HOW the agent communicates (em-dash
    ban, opener format, humanizer check, banned phrases). These rules never
    graduate through lessons.md — they're author-intent, not learned — so
    they need a stable injection path into brain_prompt.md.

    We prefer an explicit SOUL_MD env override, then probe a few known
    locations relative to the brain dir and its parents. On miss we return
    an empty list so the synthesizer falls back to lessons-only output.
    """
    import re

    paths: list[Path] = []
    override = os.environ.get("SOUL_MD")
    if override:
        paths.append(Path(override))

    anchors: list[Path] = [brain_dir, brain_dir.parent, brain_dir.parent.parent]
    for env_key in ("WORKING_DIR", "CLAUDE_PROJECT_DIR"):
        env_val = os.environ.get(env_key)
        if env_val:
            anchors.append(Path(env_val))
    with contextlib.suppress(OSError):
        anchors.append(Path.cwd())

    for anchor in anchors:
        for rel in _SOUL_CANDIDATES:
            paths.append(anchor / rel)

    soul_text: str | None = None
    for candidate in paths:
        try:
            if candidate.is_file():
                soul_text = candidate.read_text(encoding="utf-8")
                break
        except OSError:
            continue

    if not soul_text:
        return []

    lines: list[str] = []
    seen: set[str] = set()
    for raw in soul_text.splitlines():
        stripped = raw.strip()
        if not stripped.startswith(("*", "-")):
            continue
        body = re.sub(r"^[*\-]\s+", "", stripped)
        body = re.sub(r"^\*\*([^*]+)\*\*:?\s*", r"\1: ", body)
        body = body.strip().rstrip(".")
        if len(body) < 12 or len(body) > 400:
            continue
        key = body.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"[MANDATORY] VOICE: {body}")
    return lines


def _bracket_confidence(c: float) -> str:
    """Bucket raw FSRS confidence into 3 stable bands for cache-key stability.

    Raw floats tick constantly (FSRS updates on every event), causing a cache
    miss on every session_close even when no meaningful rule change occurred.
    Three bands give the synthesizer enough signal without thrashing the cache.
    """
    if c < 0.5:
        return "low"
    if c < 0.75:
        return "mid"
    return "high"


def _refresh_brain_prompt(brain_dir: str, data: dict) -> None:
    """Regenerate brain_prompt.md via the model-agnostic call_provider dispatch.

    Uses GRADATA_SYNTHESIZER_MODEL (default claude-opus-4-7). Provider is
    selected by model prefix: claude-* → Anthropic, gpt-* → OpenAI,
    gemini-* → Google, http(s):// → generic OpenAI-compatible endpoint.
    Silently skips if the required API key is absent or the SDK is not
    installed — injection falls back to the fragmented format on miss.
    """
    try:
        from gradata.enhancements.rule_synthesizer import (
            _SYSTEM_PROMPT as _SYNTH_SYSTEM,
        )
        from gradata.enhancements.rule_synthesizer import (
            MAX_OUTPUT_TOKENS,
            _build_user_prompt,
            _compute_cache_key,
            _extract_wisdom_block,
            _read_cache,
            _write_cache,
            call_provider,
        )
        from gradata.enhancements.self_improvement._confidence import parse_lessons

        bd = Path(brain_dir)
        lessons_path = bd / "lessons.md"
        if not lessons_path.is_file():
            return
        lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
        filtered = [
            l
            for l in lessons
            if l.state.name in ("RULE", "PATTERN") and (l.confidence or 0.0) >= 0.60
        ]
        soul_lines = _load_soul_mandatories(bd)
        if not filtered and not soul_lines:
            return

        mandatory_lines = list(soul_lines) + [
            f"[MANDATORY] {l.category}: {l.description}"
            for l in filtered
            if l.state.name == "RULE"
            and (l.confidence or 0.0) >= 0.90
            and int(getattr(l, "fire_count", 0) or 0) >= 10
        ]
        individual_lines = [
            f"[{l.state.name}:{_bracket_confidence(float(l.confidence or 0.0))} fires:{int(getattr(l, 'fire_count', 0) or 0)}] "
            f"{(l.category or 'GENERAL').strip()}: {(l.description or '').strip()}"
            for l in filtered
        ]

        model = os.environ.get("GRADATA_SYNTHESIZER_MODEL", "claude-opus-4-7")

        # Cache by rule signatures so wording tweaks don't bust it.
        cache_key = _compute_cache_key(
            mandatory_lines, [], individual_lines, "", "", "general", model
        )
        cached = _read_cache(bd, cache_key)
        if cached:
            block = cached
        else:
            user_prompt = _build_user_prompt(
                mandatory_lines, [], individual_lines, "", "", "general", "general"
            )
            raw = call_provider(model, _SYNTH_SYSTEM, user_prompt, MAX_OUTPUT_TOKENS, 60.0)
            if raw is None:
                _log.debug("brain_prompt refresh: provider returned nothing")
                return
            block = _extract_wisdom_block(raw)
            if not block or len(block) < 50:
                _log.debug("synthesizer output malformed or too short")
                return
            _write_cache(bd, cache_key, block)

        content = block
        if content.startswith("<brain-wisdom>"):
            content = content[len("<brain-wisdom>") :].lstrip("\n")
        if content.endswith("</brain-wisdom>"):
            content = content[: -len("</brain-wisdom>")].rstrip("\n")
        header = (
            "<!-- AUTO-GENERATED by session_close._refresh_brain_prompt -->\n"
            "<!-- Source of truth: lessons.md. Do not edit directly; next -->\n"
            "<!-- graduation-triggering session will regenerate this file. -->\n\n"
        )
        (bd / "brain_prompt.md").write_text(header + content + "\n", encoding="utf-8")
        _log.info("brain_prompt.md refreshed (%d chars)", len(content))
    except Exception as e:
        _log.debug("brain_prompt refresh skipped: %s", e)


def _refresh_loop_state(brain_dir: str, data: dict) -> None:
    """Regenerate loop-state.md with live stats from DB and lessons.md.

    Read by _context_packet._load_wrapup_context on every sub-agent/wrapup
    packet build. Failures are silenced — a stale file is preferable to a
    broken session close.
    """
    try:
        import subprocess
        from datetime import date

        from gradata.enhancements.self_improvement._confidence import parse_lessons

        bd = Path(brain_dir)

        # Session number: prefer data payload, fall back to persist dir scan.
        session_num = int(data.get("session_number") or 0)
        if not session_num:
            persist_dir = bd / "sessions" / "persist"
            if persist_dir.is_dir():
                nums = []
                for p in persist_dir.glob("session-*.json"):
                    with contextlib.suppress(ValueError, IndexError):
                        nums.append(int(p.stem.split("-", 1)[1]))
                if nums:
                    session_num = max(nums)

        # Corrections this session from SQLite.
        corrections = 0
        db = bd / "system.db"
        if db.is_file() and session_num:
            try:
                with sqlite3.connect(db) as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM events WHERE type = 'CORRECTION' AND session = ?",
                        (session_num,),
                    ).fetchone()
                    corrections = row[0] if row else 0
            except sqlite3.Error:
                logger.warning('Suppressed exception in _refresh_loop_state', exc_info=True)

        # Rule / pattern counts from lessons.md.
        patterns = 0
        rules = 0
        lessons_path = bd / "lessons.md"
        if lessons_path.is_file():
            try:
                lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
                patterns = sum(1 for l in lessons if l.state.name == "PATTERN")
                rules = sum(1 for l in lessons if l.state.name == "RULE")
            except Exception:
                logger.warning('Suppressed exception in _refresh_loop_state', exc_info=True)

        # Recent git commits — try known repo anchors in priority order.
        commits = ""
        anchors: list[Path] = []
        for env_key in ("WORKING_DIR", "CLAUDE_PROJECT_DIR"):
            val = os.environ.get(env_key)
            if val:
                anchors.append(Path(val))
        anchors += [bd.parent, bd.parent.parent]
        with contextlib.suppress(OSError):
            anchors.append(Path.cwd())
        for anchor in anchors:
            try:
                result = subprocess.run(
                    ["git", "-C", str(anchor), "log", "-5", "--oneline"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    commits = result.stdout.strip()
                    break
            except Exception:
                continue

        today = date.today().isoformat()
        lines = [
            "<!-- AUTO-GENERATED by session_close._refresh_loop_state -->",
            "<!-- Source of truth: system.db + lessons.md. Do not edit directly. -->",
            "",
            f"# Loop State — Session {session_num}",
            "",
            f"## Last Session (Session {session_num})",
            f"Date: {today}",
            f"Corrections: {corrections} | Rules: {rules} | Patterns: {patterns}",
            "",
        ]
        if commits:
            lines += ["## Recent Commits", commits, ""]

        (bd / "loop-state.md").write_text("\n".join(lines), encoding="utf-8")
        _log.info("loop-state.md refreshed (session %d)", session_num)
    except Exception as e:
        _log.debug("loop-state refresh skipped: %s", e)


def _resolve_pending_applications(brain_dir: str, data: dict) -> None:
    """Resolve PENDING lesson_applications rows for the current session.

    Heuristic:
      - REJECTED if any CORRECTION/IMPLICIT_FEEDBACK event in the session
        shares the lesson's category (correction against a same-category
        rule implies the rule didn't land).
      - CONFIRMED otherwise (rule survived the session without a
        category-matching correction).

    Best-effort; missing tables / DB errors are swallowed.
    """
    try:
        import json as _json

        db = Path(brain_dir) / "system.db"
        if not db.is_file():
            return
        session_num = int(data.get("session_number") or 0)
        with sqlite3.connect(db) as conn:
            pending = conn.execute(
                "SELECT id, lesson_id, context FROM lesson_applications "
                "WHERE outcome = 'PENDING' AND session = ?",
                (session_num,),
            ).fetchall()
            if not pending:
                return

            event_rows = conn.execute(
                "SELECT data_json FROM events WHERE session = ? "
                "AND type IN ('CORRECTION', 'IMPLICIT_FEEDBACK', 'RULE_FAILURE')",
                (session_num,),
            ).fetchall()
            rejecting_categories: set[str] = set()
            rejecting_descriptions: set[str] = set()
            for (raw,) in event_rows:
                try:
                    payload = _json.loads(raw) if isinstance(raw, str) else raw
                except (TypeError, _json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                cat = payload.get("category")
                desc = payload.get("rule") or payload.get("description")
                if isinstance(cat, str) and cat:
                    rejecting_categories.add(cat.upper())
                if isinstance(desc, str) and desc:
                    rejecting_descriptions.add(desc.strip())

            updates: list[tuple[str, int]] = []
            for row_id, _lesson_id, ctx_raw in pending:
                category = ""
                lesson_desc = ""
                if isinstance(ctx_raw, str) and ctx_raw:
                    try:
                        parsed_ctx = _json.loads(ctx_raw)
                    except (TypeError, _json.JSONDecodeError):
                        parsed_ctx = None
                    if isinstance(parsed_ctx, dict):
                        cat_v = parsed_ctx.get("category")
                        desc_v = parsed_ctx.get("description")
                        if isinstance(cat_v, str):
                            category = cat_v.upper()
                        if isinstance(desc_v, str):
                            lesson_desc = desc_v
                outcome = "CONFIRMED"
                if category and category in rejecting_categories:
                    outcome = "REJECTED"
                elif lesson_desc:
                    for desc in rejecting_descriptions:
                        if desc and desc[:30] and desc[:30] in lesson_desc:
                            outcome = "REJECTED"
                            break
                updates.append((outcome, row_id))

            conn.executemany(
                "UPDATE lesson_applications SET outcome = ?, success = "
                "CASE WHEN ? = 'CONFIRMED' THEN 1 ELSE 0 END WHERE id = ?",
                [(o, o, rid) for o, rid in updates],
            )
            conn.commit()
    except Exception as exc:
        _log.debug("lesson_applications resolve skipped: %s", exc)


def _run_cloud_sync(brain_dir: str, data: dict) -> None:
    """Push session telemetry + corrections to Gradata Cloud.

    Claude Code never calls ``brain.end_session()`` directly, so
    ``_cloud_sync_session`` never fired from IDE sessions before this hook
    path existed. Gated on GRADATA_API_KEY — no key, no sync, no network.
    """
    if not os.environ.get("GRADATA_API_KEY"):
        return
    try:
        from gradata._core import cloud_sync_tick

        session_num = int(data.get("session_number") or 0)
        cloud_sync_tick(brain_dir, session_num)
    except Exception as e:
        _log.warning("cloud sync tick skipped: %s", e)


def _flush_retain_queue(brain_dir: str) -> None:
    """Always runs — cheap + essential so no queued events are lost."""
    try:
        from gradata._events import flush_retain

        result = flush_retain(brain_dir)
        if result.get("written"):
            _log.info("RetainOrchestrator: flushed %d events", result["written"])
    except Exception as e:
        _log.debug("retain flush skipped: %s", e)


def _retroactive_sweep(brain_dir: str, data: dict) -> None:
    """Run implicit_feedback patterns over all session turns retroactively.

    Finds the session transcript via ProviderTranscriptSource (Claude Code
    native JSONL) or GradataTranscriptSource (middleware-written). For each
    user-role turn, runs every SIGNAL_MAP pattern from implicit_feedback.py
    and emits IMPLICIT_FEEDBACK events for matches that aren't already in
    the DB for this session.

    Gated on GRADATA_TRANSCRIPT=1. Skips silently on any error.
    """
    if os.environ.get("GRADATA_TRANSCRIPT") != "1":
        return
    try:
        from gradata._events import emit
        from gradata._paths import BrainContext
        from gradata._transcript_providers import get_transcript_source
        from gradata.hooks.implicit_feedback import SIGNAL_MAP

        session_id = data.get("session_id") or data.get("sessionId")
        source = get_transcript_source(brain_dir, session_id)
        if source is None:
            _log.debug("retroactive_sweep: no transcript source available")
            return

        turns = source.turns()
        user_turns = [t for t in turns if t.get("role") == "user" and t.get("content")]
        if not user_turns:
            return

        session_num = int(data.get("session_number") or 0)
        ctx = BrainContext.from_brain_dir(brain_dir)

        # Load existing IMPLICIT_FEEDBACK events for this session to avoid dupes.
        existing: set[str] = set()
        db = Path(brain_dir) / "system.db"
        if db.is_file():
            try:
                with sqlite3.connect(db) as conn:
                    rows = conn.execute(
                        "SELECT data_json FROM events WHERE type = 'IMPLICIT_FEEDBACK' "
                        "AND session = ?",
                        (session_num,),
                    ).fetchall()
                    for (raw,) in rows:
                        try:
                            import json as _json

                            payload = _json.loads(raw) if isinstance(raw, str) else {}
                            sig = payload.get("signal_type", "")
                            snippet = payload.get("snippet", "")
                            existing.add(f"{sig}:{snippet[:40]}")
                        except Exception:
                            logger.warning('Suppressed exception in _retroactive_sweep', exc_info=True)
            except sqlite3.Error:
                logger.warning('Suppressed exception in _retroactive_sweep', exc_info=True)

        emitted = 0
        for turn in user_turns:
            text = turn.get("content") or ""
            for signal_type, patterns in SIGNAL_MAP.items():
                for pat in patterns:
                    m = pat.search(text)
                    if not m:
                        continue
                    snippet = text[max(0, m.start() - 20) : m.end() + 20].strip()
                    dedup_key = f"{signal_type}:{snippet[:40]}"
                    if dedup_key in existing:
                        continue
                    existing.add(dedup_key)
                    emit(
                        "IMPLICIT_FEEDBACK",
                        source="hook:session_close:retroactive_sweep",
                        data={
                            "signal_type": signal_type,
                            "snippet": snippet,
                            "pattern": pat.pattern,
                            "retroactive": True,
                        },
                        ctx=ctx,
                        session=session_num,
                    )
                    emitted += 1
                    break  # One signal per pattern group per turn is enough.

        if emitted:
            _log.info("retroactive_sweep: emitted %d IMPLICIT_FEEDBACK events", emitted)
        else:
            _log.debug("retroactive_sweep: no new signals found in %d turns", len(user_turns))

        # TTL cleanup for old transcript files.
        try:
            from gradata._transcript import cleanup_ttl

            deleted = cleanup_ttl(brain_dir)
            if deleted:
                _log.debug("retroactive_sweep: cleaned up %d old transcript files", deleted)
        except Exception:
            logger.warning('Suppressed exception in _retroactive_sweep', exc_info=True)

    except Exception as exc:
        _log.debug("retroactive_sweep skipped: %s", exc)


def _run_waterfall(brain_dir_str: str, brain_dir: Path, data: dict, upper_bound: str) -> None:
    _retroactive_sweep(brain_dir_str, data)
    _run_graduation(brain_dir_str)
    _run_pipeline(brain_dir_str, data)
    _run_tree_consolidation(brain_dir_str)
    _resolve_pending_applications(brain_dir_str, data)
    _refresh_brain_prompt(brain_dir_str, data)
    _refresh_loop_state(brain_dir_str, data)
    _run_cloud_sync(brain_dir_str, data)
    _write_stamp(brain_dir, upper_bound)


def main(data: dict) -> dict | None:
    # Kill switch — useful for debugging runaway hooks.
    if os.environ.get("GRADATA_DISABLE_GRADUATION") == "1":
        return None

    brain_dir_str = resolve_brain_dir()
    if not brain_dir_str:
        return None

    brain_dir = Path(brain_dir_str)

    # Always flush: cheap and never idempotent from a data-loss standpoint.
    _flush_retain_queue(brain_dir_str)

    # Gate: new trigger events since last waterfall?
    last_ts = _read_stamp(brain_dir)
    upper_bound = datetime.now(UTC).isoformat()
    if not _has_new_triggers(brain_dir, last_ts, upper_bound):
        return None

    # Gate: throttle (time elapsed or enough pending INSTINCT lessons).
    lessons_path = brain_dir / "lessons.md"
    if not _should_run_graduation(brain_dir, lessons_path):
        _log.debug("graduation throttled: interval not elapsed and threshold not met")
        return None

    # Gate: concurrency lock (prevents stacked invocations).
    if not _acquire_lock():
        _log.debug("graduation skipped: lock held by a live process")
        return None

    try:
        timeout_s = float(os.environ.get("GRADATA_GRADUATION_TIMEOUT", "300"))
        completed = _run_with_timeout(
            lambda: _run_waterfall(brain_dir_str, brain_dir, data, upper_bound),
            timeout_s,
        )
        if completed:
            _update_graduation_state(brain_dir)
    finally:
        _release_lock()

    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
