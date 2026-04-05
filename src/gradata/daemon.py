"""
Gradata Daemon — HTTP server that holds a Brain in memory.

Provides a long-lived process that IDE plugins (VS Code, JetBrains) and
CLI tools talk to over HTTP.  One daemon per brain directory.

Endpoints:
    GET  /health       — liveness + brain stats
    POST /apply-rules  — inject rules for a task
    POST /correct      — record a correction
    POST /detect       — detect implicit feedback / mode
    POST /end-session  — close the current session

Usage:
    python -m gradata.daemon --brain-dir ./my-brain
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sqlite3
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from socketserver import ThreadingMixIn

import gradata

logger = logging.getLogger("gradata.daemon")

# ── Category detection from file extension ─────────────────────────────

_EXT_CATEGORY: dict[str, str] = {
    ".py": "CODE", ".js": "CODE", ".ts": "CODE", ".tsx": "CODE", ".jsx": "CODE",
    ".rs": "CODE", ".go": "CODE", ".java": "CODE", ".rb": "CODE", ".c": "CODE",
    ".cpp": "CODE", ".h": "CODE", ".cs": "CODE", ".swift": "CODE", ".kt": "CODE",
    ".md": "CONTENT", ".txt": "CONTENT", ".rst": "CONTENT",
    ".json": "CONFIG", ".yaml": "CONFIG", ".yml": "CONFIG", ".toml": "CONFIG",
    ".ini": "CONFIG", ".env": "CONFIG",
    ".html": "FRONTEND", ".css": "FRONTEND", ".scss": "FRONTEND", ".vue": "FRONTEND",
    ".svelte": "FRONTEND",
}


def _category_from_path(file_path: str) -> str:
    """Detect edit category from file extension."""
    ext = Path(file_path).suffix.lower()
    return _EXT_CATEGORY.get(ext, "GENERAL")


# ── Idle timeout ────────────────────────────────────────────────────────
IDLE_TIMEOUT_SECONDS = 600  # 10 minutes


# ── Threaded HTTP server ────────────────────────────────────────────────

class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTPServer that handles each request in a new thread."""
    daemon_threads = True
    allow_reuse_address = True


# ── Request handler ─────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    """Routes requests to the parent GradataDaemon instance."""

    # Suppress default stderr logging — we use our own logger
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        logger.debug(format, *args)

    # ── Routing ─────────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._handle_health()
        else:
            self._not_found()

    def do_POST(self) -> None:  # noqa: N802
        routes: dict[str, object] = {
            "/apply-rules": self._handle_apply_rules,
            "/correct": self._handle_correct,
            "/detect": self._handle_detect,
            "/end-session": self._handle_end_session,
        }
        handler = routes.get(self.path)
        if handler:
            handler()  # type: ignore[operator]
        else:
            self._not_found()

    # ── Helpers ─────────────────────────────────────────────────────────

    @property
    def daemon(self) -> "GradataDaemon":
        return self.server._daemon  # type: ignore[attr-defined]

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self) -> None:
        self._send_json({"error": "not found"}, 404)

    # ── Endpoint handlers ───────────────────────────────────────────────

    def _handle_health(self) -> None:
        self.daemon._reset_idle_timer()
        d = self.daemon
        with d._brain_lock:
            lessons = d._brain._load_lessons()
            rules_count = sum(
                1 for lesson in lessons if lesson.state.name == "RULE"
            )
            lessons_count = len(lessons)

        uptime = time.monotonic() - d._started_mono
        self._send_json({
            "status": "ok",
            "sdk_version": gradata.__version__,
            "brain_dir": str(d._brain.dir),
            "uptime_seconds": round(uptime, 2),
            "active_sessions": len(d._sessions),
            "rules_count": rules_count,
            "lessons_count": lessons_count,
        })

    def _handle_apply_rules(self) -> None:
        self.daemon._reset_idle_timer()
        body = self._read_json()

        prompt = body.get("prompt", "")
        session_id = body.get("session_id", "")
        context = body.get("context", {})

        d = self.daemon
        with d._brain_lock:
            # Load and parse lessons
            lessons_path = d._brain_dir / "lessons.md"
            if lessons_path.exists():
                from gradata.enhancements.self_improvement import parse_lessons
                lessons_text = lessons_path.read_text(encoding="utf-8")
                lessons = parse_lessons(lessons_text)
            else:
                lessons = []

            # Build scope and apply rules
            from gradata._scope import RuleScope
            from gradata.rules.rule_engine import apply_rules, format_rules_for_prompt

            scope = RuleScope(
                task_type=context.get("task_type", ""),
                agent_type=context.get("agent_type", "general"),
            )
            applied = apply_rules(lessons, scope, max_rules=10, user_message=prompt)

            # Format injection text
            injection_text = format_rules_for_prompt(applied) if applied else ""

        # Build structured response
        rules_out = []
        fired_ids = []
        for ar in applied:
            rules_out.append({
                "rule_id": ar.rule_id,
                "tier": ar.lesson.state.value,
                "category": ar.lesson.category,
                "instruction": ar.instruction,
                "relevance": ar.relevance,
            })
            fired_ids.append(ar.rule_id)

        # Store fired rule IDs for acceptance tracking
        if session_id:
            d._fired_rules[session_id] = fired_ids

        self._send_json({
            "rules": rules_out,
            "injection_text": injection_text,
            "mode_detected": "chat",
            "fired_rule_ids": fired_ids,
        })

    def _handle_correct(self) -> None:
        self.daemon._reset_idle_timer()
        body = self._read_json()

        old_string = body.get("old_string", "")
        new_string = body.get("new_string", "")
        file_path = body.get("file_path", "")
        session_id = body.get("session_id", "")

        # No-op guard
        if old_string == new_string or (not old_string and not new_string):
            self._send_json({"captured": False, "error": "no change"})
            return

        # Category detection
        category = _category_from_path(file_path) if file_path else "GENERAL"

        # Session mapping
        d = self.daemon
        session_num = d._get_session_num(session_id) if session_id else None

        # Call brain.correct under lock
        try:
            with d._brain_lock:
                result = d._brain.correct(
                    draft=old_string,
                    final=new_string,
                    category=category,
                    session=session_num,
                )
        except Exception as exc:
            self._send_json({"captured": False, "error": str(exc)})
            return

        # Acceptance attribution: category-based
        fired_rules = d._fired_rules.get(session_id, [])
        misfired: list[str] = []
        untested: list[str] = []
        for rule_id in fired_rules:
            # Extract category prefix from rule_id (e.g. "TONE:4821" -> "TONE")
            rule_cat = rule_id.split(":")[0] if ":" in rule_id else ""
            if rule_cat == category:
                misfired.append(rule_id)
            else:
                untested.append(rule_id)
        # Keep only untested rules in the fired set
        if session_id:
            d._fired_rules[session_id] = untested

        # Build response
        self._send_json({
            "captured": True,
            "severity": result.get("severity", "unknown"),
            "instruction_extracted": result.get("instruction", ""),
            "lesson_created": result.get("lesson_created", False),
            "lesson_state": result.get("lesson_state", "INSTINCT"),
            "misfired_rules": misfired,
            "accepted_rules": [],
            "addition_detected": False,
            "correction_conflict": None,
        })

    def _handle_detect(self) -> None:
        self.daemon._reset_idle_timer()
        body = self._read_json()

        user_message = body.get("user_message", "")
        session_id = body.get("session_id", "")

        d = self.daemon
        session_num = d._get_session_num(session_id) if session_id else None

        try:
            with d._brain_lock:
                result = d._brain.detect_implicit_feedback(
                    user_message, session=session_num,
                )
        except Exception as exc:
            logger.warning("detect_implicit_feedback failed: %s", exc)
            result = {"signals": []}

        signals = result.get("signals", [])
        detected = len(signals) > 0

        # Build related_rules from recent_fired_rules if feedback detected
        recent_fired = body.get("recent_fired_rules", [])
        related_rules = recent_fired if detected else []

        self._send_json({
            "implicit_feedback": {
                "detected": detected,
                "signals": signals,
                "related_rules": related_rules,
                "action_taken": "logged" if detected else None,
            },
            "mode": "chat",
            "mode_confidence": 0.0,
        })

    def _handle_end_session(self) -> None:
        self.daemon._reset_idle_timer()
        body = self._read_json()

        session_id = body.get("session_id", "")
        session_type = body.get("session_type", "full")

        d = self.daemon

        # Run graduation sweep
        try:
            with d._brain_lock:
                result = d._brain.end_session(session_type=session_type)
        except Exception as exc:
            logger.warning("end_session failed: %s", exc)
            result = {}

        # Clean up session state
        if session_id:
            d._sessions.pop(session_id, None)
            d._fired_rules.pop(session_id, None)

        # Get convergence data
        try:
            with d._brain_lock:
                convergence = d._brain.convergence()
        except Exception:
            convergence = {}

        self._send_json({
            "corrections_captured": result.get("corrections_captured", 0),
            "instructions_extracted": result.get("instructions_extracted", 0),
            "lessons_graduated": result.get("lessons_graduated", 0),
            "meta_rules_synthesized": result.get("meta_rules_synthesized", 0),
            "convergence": convergence,
            "cross_project_candidates": [],
        })


# ── Main daemon class ──────────────────────────────────────────────────

class GradataDaemon:
    """Long-lived HTTP daemon that holds a Brain in memory.

    Args:
        brain_dir: Path to the brain directory.
        port: Port to listen on.  0 = OS-assigned.
        pid_file: Path to write the PID file.  None = no PID file.
    """

    def __init__(
        self,
        brain_dir: str | Path,
        port: int = 0,
        pid_file: str | Path | None = None,
    ) -> None:
        from gradata import Brain

        self._brain_dir = Path(brain_dir).resolve()
        self._brain = Brain(self._brain_dir)
        self._brain_lock = threading.Lock()

        self._sessions: dict[str, int] = {}
        self._fired_rules: dict[str, list[str]] = {}

        self._port = port
        self._pid_file = Path(pid_file) if pid_file else None
        self._server: _ThreadingHTTPServer | None = None
        self._started_mono = time.monotonic()
        self._started_at = datetime.now(timezone.utc).isoformat()

        # Session counter: pick up from DB
        self._session_counter = self._init_session_counter()

        # Idle auto-shutdown
        self._idle_timer: threading.Timer | None = None

    # ── Session ID → number mapping ────────────────────────────────────

    def _get_session_num(self, session_id: str) -> int:
        """Map a string session_id to an integer, auto-incrementing."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        num = self._session_counter
        self._sessions[session_id] = num
        self._session_counter += 1
        return num

    # ── Session counter init ────────────────────────────────────────────

    def _init_session_counter(self) -> int:
        db_path = self._brain.db_path
        if not db_path.exists():
            return 1
        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
            ).fetchone()
            conn.close()
            max_session = row[0] if row and row[0] is not None else 0
            return max_session + 1
        except Exception:
            logger.debug("Could not read session counter from DB", exc_info=True)
            return 1

    # ── Idle timer ──────────────────────────────────────────────────────

    def _reset_idle_timer(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        self._idle_timer = threading.Timer(IDLE_TIMEOUT_SECONDS, self._idle_shutdown)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _idle_shutdown(self) -> None:
        logger.info("Idle timeout reached (%ds). Shutting down.", IDLE_TIMEOUT_SECONDS)
        self.stop()

    # ── Start / Stop ────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the HTTP server (blocking)."""
        port = self._port if self._port != 0 else _pick_port(str(self._brain_dir))
        self._try_bind(port)

        assert self._server is not None, "Server must be bound after _try_bind"
        self._server._daemon = self  # type: ignore[attr-defined]
        actual_port: int = self._server.server_address[1]
        self._port = actual_port

        logger.info(
            "Gradata daemon listening on port %d (brain=%s)",
            actual_port,
            self._brain_dir,
        )

        # PID file
        if self._pid_file:
            _write_pid_file(self._pid_file, actual_port, self._brain_dir, self._started_at)

        # SIGTERM handler
        _register_signal_handler(self)

        # Start idle timer
        self._reset_idle_timer()

        assert self._server is not None
        try:
            self._server.serve_forever()
        finally:
            self._cleanup()

    def _try_bind(self, port: int) -> int:
        """Try to bind to *port*, falling back up to 10 attempts."""
        last_err: Exception | None = None
        for attempt in range(10):
            try:
                self._server = _ThreadingHTTPServer(("127.0.0.1", port + attempt), _Handler)
                return port + attempt
            except OSError as exc:
                last_err = exc
                logger.debug("Port %d in use, trying next", port + attempt)
        # If all 10 failed, try OS-assigned
        try:
            self._server = _ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            return 0
        except OSError:
            raise RuntimeError(f"Could not bind to any port (last error: {last_err})") from last_err

    def stop(self) -> None:
        """Shutdown the server gracefully."""
        if self._server:
            self._server.shutdown()

    def _cleanup(self) -> None:
        if self._idle_timer:
            self._idle_timer.cancel()
        if self._pid_file and self._pid_file.exists():
            try:
                self._pid_file.unlink()
            except OSError:
                pass

    @property
    def port(self) -> int:
        """Return the actual port the server is listening on."""
        return self._port


# ── Port allocation ─────────────────────────────────────────────────────

def _pick_port(brain_dir_str: str) -> int:
    """Deterministic port from brain_dir hash: hash % 16383 + 49152."""
    return abs(hash(brain_dir_str)) % 16383 + 49152


# ── PID file ────────────────────────────────────────────────────────────

def _write_pid_file(
    pid_file: Path,
    port: int,
    brain_dir: Path,
    started_at: str,
) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "port": port,
        "pid": os.getpid(),
        "brain_dir": str(brain_dir),
        "sdk_version": gradata.__version__,
        "started_at": started_at,
    }
    pid_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.debug("PID file written: %s", pid_file)


# ── Logging setup ───────────────────────────────────────────────────────

def _setup_logging(brain_dir: Path) -> None:
    log_dir = brain_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "daemon.log",
        maxBytes=1_048_576,  # 1 MB
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    root_logger = logging.getLogger("gradata")
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)


# ── Signal handling ─────────────────────────────────────────────────────

def _register_signal_handler(daemon: GradataDaemon) -> None:
    """Register SIGTERM to cleanly shut down the daemon."""
    def _handler(signum: int, _frame: object) -> None:
        logger.info("Received signal %d, shutting down.", signum)
        daemon.stop()

    # SIGTERM is not available on Windows — guard it.
    # signal.signal() also raises ValueError when called from a non-main thread
    # (e.g. when tests start the daemon in a background thread).
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, _handler)
        except ValueError:
            logger.debug("Cannot register SIGTERM handler (not main thread)")


# ── CLI entrypoint ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Gradata daemon HTTP server")
    parser.add_argument("--brain-dir", required=True, help="Path to the brain directory")
    parser.add_argument("--pid-file", default=None, help="Path to write PID file")
    parser.add_argument("--port", type=int, default=0, help="Port (0 = auto)")
    args = parser.parse_args()

    brain_dir = Path(args.brain_dir).resolve()
    _setup_logging(brain_dir)

    daemon = GradataDaemon(
        brain_dir=brain_dir,
        port=args.port,
        pid_file=args.pid_file,
    )
    daemon.start()


if __name__ == "__main__":
    main()
