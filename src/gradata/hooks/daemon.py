"""Persistent HTTP daemon for hook dispatch — avoids ~300ms Windows spawn per hook.

POST /hook/<name> (stdin JSON) runs gradata.hooks.<name>.main(data); GET /health
and /shutdown. Start: python -m gradata.hooks.daemon [--start|--stop]. Clients
should use gradata.hooks.client which falls back to direct invocation.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import logging
import os
import sys
import tempfile
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_log = logging.getLogger(__name__)

PORT = int(os.environ.get("GRADATA_HOOK_DAEMON_PORT", "7819"))
HOST = "127.0.0.1"
PID_FILE = Path(tempfile.gettempdir()) / "gradata-hook-daemon.pid"

_START_TIME = time.time()
_MODULE_CACHE: dict[str, object] = {}


def _run_hook(name: str, body: str) -> dict:
    mod = _MODULE_CACHE.get(name)
    if mod is None:
        try:
            mod = importlib.import_module(f"gradata.hooks.{name}")
            _MODULE_CACHE[name] = mod
        except ImportError:
            mod = None
    if mod is None or not hasattr(mod, "main"):
        return {"error": f"unknown hook: {name}", "exit_code": 127}

    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        return {"error": f"invalid JSON: {exc}", "exit_code": 2}

    old_stdout, old_stderr = sys.stdout, sys.stderr
    out, err = io.StringIO(), io.StringIO()
    try:
        sys.stdout, sys.stderr = out, err
        result = mod.main(data)  # type: ignore[attr-defined]
    except SystemExit as e:
        return {
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
            "exit_code": int(e.code) if isinstance(e.code, int) else 0,
        }
    except Exception:
        return {
            "stdout": out.getvalue(),
            "stderr": err.getvalue() + traceback.format_exc(),
            "exit_code": 1,
        }
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    # main() returning a dict: emit as JSON stdout so the client relays it
    stdout = out.getvalue()
    if isinstance(result, dict) and not stdout:
        stdout = json.dumps(result)
    return {"stdout": stdout, "stderr": err.getvalue(), "exit_code": 0}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silence default HTTP access log
        pass

    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._reply(
                200,
                {
                    "status": "ok",
                    "uptime_s": round(time.time() - _START_TIME, 1),
                    "pid": os.getpid(),
                    "cached_modules": sorted(_MODULE_CACHE.keys()),
                },
            )
        elif self.path == "/shutdown":
            self._reply(200, {"status": "shutting_down"})
            import threading

            threading.Thread(
                target=lambda: (time.sleep(0.1), self.server.shutdown()), daemon=True
            ).start()
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/hook/"):
            self._reply(404, {"error": "not found"})
            return
        name = self.path[len("/hook/") :]
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        result = _run_hook(name, body)
        self._reply(200, result)


def _write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _clear_pid() -> None:
    with contextlib.suppress(FileNotFoundError):
        PID_FILE.unlink()


def run_foreground() -> None:
    server = HTTPServer((HOST, PORT), _Handler)
    _write_pid()
    try:
        _log.info("hook daemon listening on %s:%d (pid=%d)", HOST, PORT, os.getpid())
        server.serve_forever()
    finally:
        _clear_pid()


def stop_daemon() -> bool:
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(f"http://{HOST}:{PORT}/shutdown", timeout=2).read()
        return True
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true", help="Start in background (detached)")
    parser.add_argument("--stop", action="store_true", help="Stop the running daemon")
    parser.add_argument("--status", action="store_true", help="Report status")
    args = parser.parse_args()

    if args.status:
        pid: int | None = None
        if PID_FILE.is_file():
            try:
                pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                pid = None
            if pid is not None:
                import urllib.error
                import urllib.request

                try:
                    with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=0.5):
                        pass
                except (urllib.error.URLError, OSError):
                    pid = None
        print(json.dumps({"running": pid is not None, "pid": pid, "port": PORT}))
        return 0
    if args.stop:
        return 0 if stop_daemon() else 1
    if args.start:
        # Re-spawn ourselves detached. Relies on `python -m gradata.hooks.daemon`
        # (no --start) to run the foreground loop.
        import subprocess

        subprocess.Popen(
            [sys.executable, "-m", "gradata.hooks.daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        return 0

    run_foreground()
    return 0


if __name__ == "__main__":
    sys.exit(main())
