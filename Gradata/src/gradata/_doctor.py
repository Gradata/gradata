"""
Gradata Doctor — Environment and brain health diagnostics.

Usage:
    from gradata._doctor import diagnose, print_diagnosis
    report = diagnose()
    print_diagnosis(report)

    # Or via CLI:
    gradata doctor
    gradata doctor --cloud     # cloud-only checks
    gradata doctor --no-cloud  # skip cloud probes (offline)
"""

from __future__ import annotations
import logging

import contextlib
import json
import os
import shutil
import socket
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
logger = logging.getLogger(__name__)


_CLOUD_PROBE_TIMEOUT = 5.0  # seconds — keep doctor fast even when offline


def _check_python_version():
    """Check Python >= 3.11."""
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 11):
        return {"name": "python_version", "status": "ok", "detail": version_str}
    return {
        "name": "python_version",
        "status": "fail",
        "detail": f"{version_str} — Python >= 3.11 required",
    }


def _check_vector_store():
    """Report vector store status. FTS5 is primary search, sqlite-vec planned."""
    return {
        "name": "vector_store",
        "status": "ok",
        "detail": "FTS5 is the primary search engine. sqlite-vec planned for vector similarity.",
    }


def _check_sentence_transformers():
    """Check if sentence-transformers is importable."""
    try:
        import sentence_transformers

        version = getattr(sentence_transformers, "__version__", "unknown")
        return {"name": "sentence_transformers", "status": "ok", "detail": version}
    except ImportError:
        return {
            "name": "sentence_transformers",
            "status": "missing",
            "detail": "pip install sentence-transformers",
        }
    except Exception as e:
        return {
            "name": "sentence_transformers",
            "status": "error",
            "detail": str(e),
        }


def _check_sqlite3():
    """Check sqlite3 availability."""
    try:
        version = sqlite3.sqlite_version
        return {"name": "sqlite3", "status": "ok", "detail": version}
    except Exception as e:
        return {"name": "sqlite3", "status": "fail", "detail": str(e)}


def _check_brain_dir():
    """Check BRAIN_DIR environment variable if set."""
    brain_dir = os.environ.get("BRAIN_DIR")
    if brain_dir is None:
        return {
            "name": "brain_dir",
            "status": "fail",
            "detail": "BRAIN_DIR not set; feedback persistence raises BrainNotConfiguredError",
        }
    p = Path(brain_dir)
    if p.is_dir():
        return {"name": "brain_dir", "status": "ok", "detail": str(p)}
    if p.exists():
        return {
            "name": "brain_dir",
            "status": "fail",
            "detail": f"{p} exists but is not a directory",
        }
    return {
        "name": "brain_dir",
        "status": "fail",
        "detail": f"{p} does not exist",
    }


def _resolve_brain_path():
    """Find brain directory from env or _paths module."""
    brain_dir = os.environ.get("BRAIN_DIR")
    if brain_dir:
        return Path(brain_dir)
    try:
        from gradata._paths import DB_PATH, resolve_brain_dir

        # If DB_PATH points to a real system.db, use its parent
        if DB_PATH.exists():
            return DB_PATH.parent
        # Otherwise fall back to resolve_brain_dir (which uses cwd)
        d = resolve_brain_dir()
        if d and (d / "system.db").exists():
            return d
    except Exception:
        logger.warning('Suppressed exception in _resolve_brain_path', exc_info=True)
    return None


def _skip(name: str) -> dict:
    return {"name": name, "status": "skip", "detail": "no brain dir resolved"}


def _check_system_db(brain_path):
    """Check system.db exists and is readable."""
    if brain_path is None:
        return _skip("system_db")
    db = brain_path / "system.db"
    if not db.exists():
        return {
            "name": "system_db",
            "status": "skip",
            "detail": "system.db not found (brain may not be initialized)",
        }
    try:
        conn = sqlite3.connect(str(db))
        conn.execute("SELECT 1")
        conn.close()
        size_kb = round(db.stat().st_size / 1024, 1)
        return {"name": "system_db", "status": "ok", "detail": f"readable, {size_kb} KB"}
    except Exception as e:
        return {"name": "system_db", "status": "fail", "detail": f"corrupt or locked: {e}"}


def _check_events_jsonl(brain_path):
    """Check events.jsonl exists."""
    if brain_path is None:
        return _skip("events_jsonl")
    ej = brain_path / "events.jsonl"
    if not ej.exists():
        return {
            "name": "events_jsonl",
            "status": "skip",
            "detail": "events.jsonl not found (brain may not be initialized)",
        }
    try:
        size_kb = round(ej.stat().st_size / 1024, 1)
        return {"name": "events_jsonl", "status": "ok", "detail": f"exists, {size_kb} KB"}
    except Exception as e:
        return {"name": "events_jsonl", "status": "fail", "detail": str(e)}


def _check_manifest(brain_path):
    """Check brain.manifest.json is valid JSON."""
    if brain_path is None:
        return _skip("brain_manifest")
    mf = brain_path / "brain.manifest.json"
    if not mf.exists():
        return {
            "name": "brain_manifest",
            "status": "skip",
            "detail": "brain.manifest.json not found (optional)",
        }
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
        version = data.get("schema_version", "?")
        return {"name": "brain_manifest", "status": "ok", "detail": f"valid JSON, schema {version}"}
    except json.JSONDecodeError as e:
        return {"name": "brain_manifest", "status": "fail", "detail": f"invalid JSON: {e}"}
    except Exception as e:
        return {"name": "brain_manifest", "status": "fail", "detail": str(e)}


def _check_vectorstore(brain_path):
    """Check .vectorstore/ directory."""
    if brain_path is None:
        return _skip("vectorstore")
    vs = brain_path / ".vectorstore"
    if not vs.exists():
        return {
            "name": "vectorstore",
            "status": "skip",
            "detail": ".vectorstore/ not found (embeddings not enabled)",
        }
    if vs.is_dir():
        file_count = sum(1 for _ in vs.rglob("*") if _.is_file())
        return {"name": "vectorstore", "status": "ok", "detail": f"exists, {file_count} files"}
    return {
        "name": "vectorstore",
        "status": "fail",
        "detail": ".vectorstore exists but is not a directory",
    }


def _check_disk_space(brain_path):
    """Check available disk space > 100MB."""
    check_path = brain_path if brain_path and brain_path.exists() else Path.cwd()
    try:
        usage = shutil.disk_usage(str(check_path))
        free_mb = round(usage.free / (1024 * 1024), 1)
        if free_mb > 100:
            return {"name": "disk_space", "status": "ok", "detail": f"{free_mb} MB free"}
        return {
            "name": "disk_space",
            "status": "warn",
            "detail": f"{free_mb} MB free — recommend > 100 MB",
        }
    except Exception as e:
        return {"name": "disk_space", "status": "error", "detail": str(e)}


def _gradata_config_path() -> Path:
    env = os.environ.get("GRADATA_CONFIG")
    if env:
        return Path(env)
    return Path.home() / ".gradata" / "config.toml"


def _read_cloud_config() -> dict:
    """Parse ~/.gradata/config.toml (tomllib in py311+). Returns {} on any failure."""
    path = _gradata_config_path()
    if not path.exists():
        return {}
    try:
        import tomllib
    except ImportError:
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f).get("cloud", {})
    except Exception:
        return {}


def _check_cloud_config():
    """Is the user logged in? Config file present with credentials + brain_id?"""
    path = _gradata_config_path()
    if not path.exists():
        return {
            "name": "cloud_config",
            "status": "missing",
            "detail": f"{path} not found — run `gradata login`",
        }
    cfg = _read_cloud_config()
    if not cfg.get("api_key"):
        return {
            "name": "cloud_config",
            "status": "fail",
            "detail": f"{path} missing [cloud] credentials — re-run `gradata login`",
        }
    brain_id = cfg.get("brain_id", "") or "(unset)"
    return {
        "name": "cloud_config",
        "status": "ok",
        "detail": f"logged in — brain_id={brain_id}",
    }


def _check_cloud_env_vars():
    """Report which cloud-sync env vars are set (without leaking values)."""
    enabled = os.environ.get("GRADATA_CLOUD_SYNC", "").strip() in ("1", "true", "yes")
    url_set = bool(os.environ.get("GRADATA_CLOUD_URL") or os.environ.get("GRADATA_SUPABASE_URL"))
    key_set = bool(
        os.environ.get("GRADATA_CLOUD_KEY") or os.environ.get("GRADATA_SUPABASE_SERVICE_KEY")
    )
    if not (enabled or url_set or key_set):
        return {
            "name": "cloud_env",
            "status": "skip",
            "detail": "GRADATA_CLOUD_SYNC not enabled (optional Supabase push path)",
        }
    missing = []
    if not url_set:
        missing.append("GRADATA_CLOUD_URL / GRADATA_SUPABASE_URL")
    if not key_set:
        missing.append("GRADATA_CLOUD_KEY / GRADATA_SUPABASE_SERVICE_KEY")
    if missing:
        return {
            "name": "cloud_env",
            "status": "fail",
            "detail": f"GRADATA_CLOUD_SYNC=1 but missing: {', '.join(missing)}",
        }
    status = "ok" if enabled else "warn"
    detail = "enabled, URL+key set" if enabled else "URL+key set but GRADATA_CLOUD_SYNC!=1"
    return {"name": "cloud_env", "status": status, "detail": detail}


def _check_cloud_reachable():
    """Can we reach the cloud API host? Low-cost TCP probe."""
    cfg = _read_cloud_config()
    api_url = (
        cfg.get("api_url") or os.environ.get("GRADATA_API_URL") or "https://api.gradata.ai/api/v1"
    )
    host = api_url.split("://", 1)[-1].split("/", 1)[0]
    try:
        socket.create_connection((host, 443), timeout=_CLOUD_PROBE_TIMEOUT).close()
        return {"name": "cloud_reachable", "status": "ok", "detail": f"{host}:443 reachable"}
    except OSError as e:
        return {
            "name": "cloud_reachable",
            "status": "fail",
            "detail": f"{host}:443 unreachable ({e.__class__.__name__})",
        }


def _probe_api(url: str, bearer: str) -> tuple[int, str]:
    """GET url with Bearer token. Returns (status_code, body_snippet). (0, err) on network fail."""
    auth = "Bearer " + bearer
    req = urllib.request.Request(
        url,
        headers={"Authorization": auth, "User-Agent": "gradata-sdk-doctor/0.6"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=_CLOUD_PROBE_TIMEOUT) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = ""
        with contextlib.suppress(Exception):
            body = e.read(512).decode("utf-8", errors="replace")
        return e.code, body
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e)


def _check_cloud_auth():
    """Does the stored credential work against the API?"""
    cfg = _read_cloud_config()
    bearer = cfg.get("api_key") or ""
    if not bearer:
        return {"name": "cloud_auth", "status": "skip", "detail": "no credential — skip"}
    api_url = cfg.get("api_url", "https://api.gradata.ai/api/v1").rstrip("/")
    brain_id = cfg.get("brain_id", "")
    probe_url = f"{api_url}/brains/{brain_id}" if brain_id else f"{api_url}/auth/whoami"
    code, body = _probe_api(probe_url, bearer)
    if code == 0:
        return {"name": "cloud_auth", "status": "error", "detail": f"network: {body[:80]}"}
    if 200 <= code < 300:
        return {"name": "cloud_auth", "status": "ok", "detail": f"HTTP {code} — token accepted"}
    if code in (401, 403):
        return {
            "name": "cloud_auth",
            "status": "fail",
            "detail": f"HTTP {code} — token rejected; re-run `gradata login`",
        }
    if code == 404:
        return {
            "name": "cloud_auth",
            "status": "warn",
            "detail": f"HTTP 404 on {probe_url} — endpoint may have moved",
        }
    return {"name": "cloud_auth", "status": "warn", "detail": f"HTTP {code}"}


def _check_cloud_has_data():
    """Does the cloud actually have rows for this brain? Addresses the
    'HTTP 200 != visible data' silent-failure mode."""
    cfg = _read_cloud_config()
    bearer = cfg.get("api_key") or ""
    brain_id = cfg.get("brain_id")
    if not (bearer and brain_id):
        return {"name": "cloud_has_data", "status": "skip", "detail": "not logged in — skip"}
    api_url = cfg.get("api_url", "https://api.gradata.ai/api/v1").rstrip("/")
    code, body = _probe_api(f"{api_url}/brains/{brain_id}/analytics", bearer)
    if code == 0:
        return {"name": "cloud_has_data", "status": "error", "detail": f"network: {body[:80]}"}
    if code == 404:
        return {
            "name": "cloud_has_data",
            "status": "warn",
            "detail": f"brain_id={brain_id} not found in cloud — no sessions synced yet",
        }
    if not (200 <= code < 300):
        return {"name": "cloud_has_data", "status": "warn", "detail": f"HTTP {code}"}
    try:
        data = json.loads(body) if body else {}
        sessions = data.get("session_count") or data.get("sessions") or 0
        if sessions:
            return {
                "name": "cloud_has_data",
                "status": "ok",
                "detail": f"{sessions} sessions synced to dashboard",
            }
        return {
            "name": "cloud_has_data",
            "status": "warn",
            "detail": "connected, but 0 sessions visible — telemetry may not have fired yet",
        }
    except json.JSONDecodeError:
        return {"name": "cloud_has_data", "status": "warn", "detail": "non-JSON response"}


def _check_cloud_push_error(brain_path):
    """Surface the last recorded cloud-push error, if any.

    ``_cloud_sync.push`` writes ``cloud_push_error.json`` when a POST fails
    with an HTTP/constraint error. Without this check, watermark stalls from
    23505 unique-violation retries are invisible until someone greps logs.

    The resolved brain path is always included in the detail so a user with
    multiple brains can confirm which one was inspected — the push writer and
    the doctor reader can diverge in multi-brain setups where the daemon was
    started with an explicit ``brain_dir`` that differs from ``BRAIN_DIR``.
    """
    if brain_path is None:
        return _skip("cloud_push_error")
    p = brain_path / "cloud_push_error.json"
    if not p.exists():
        return {
            "name": "cloud_push_error",
            "status": "ok",
            "detail": f"no recent push errors (checked {brain_path})",
        }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {
            "name": "cloud_push_error",
            "status": "warn",
            "detail": f"error file unreadable at {p}: {e}",
        }
    table = data.get("table", "?")
    code = data.get("code", "?")
    recorded = data.get("recorded_at", "?")
    if data.get("constraint_violation"):
        return {
            "name": "cloud_push_error",
            "status": "fail",
            "detail": (
                f"last push to '{table}' blocked by constraint (HTTP {code}) at {recorded} "
                f"in {brain_path} — watermark stalled; run `gradata migrate --brain <dir>` "
                f"or dedupe rows"
            ),
        }
    return {
        "name": "cloud_push_error",
        "status": "warn",
        "detail": f"last push to '{table}' returned HTTP {code} at {recorded} in {brain_path}",
    }


def _cloud_checks(brain_path=None):
    """All cloud checks, ordered so the first failure tells you what to do next."""
    return [
        _check_cloud_config(),
        _check_cloud_env_vars(),
        _check_cloud_reachable(),
        _check_cloud_auth(),
        _check_cloud_has_data(),
        _check_cloud_push_error(brain_path),
    ]


def diagnose(
    brain_dir: str | Path | None = None,
    include_cloud: bool = True,
    cloud_only: bool = False,
) -> dict:
    """Run all health checks and return structured report.

    Args:
        brain_dir: Explicit brain directory to check. If None, resolves
                   from BRAIN_DIR env or _paths module.
        include_cloud: If True, also probe cloud config/reachability/auth.
                       Set False for offline runs.
        cloud_only: Skip local checks, only probe cloud.

    Returns:
        {
            "status": "healthy" | "degraded" | "broken",
            "checks": [ {"name": ..., "status": ..., "detail": ...}, ... ]
        }
    """
    # Resolve brain path
    brain_path = Path(brain_dir).resolve() if brain_dir else _resolve_brain_path()

    if cloud_only:
        checks = _cloud_checks(brain_path)
    else:
        checks = [
            _check_python_version(),
            _check_vector_store(),
            _check_sentence_transformers(),
            _check_sqlite3(),
            _check_brain_dir(),
            _check_system_db(brain_path),
            _check_events_jsonl(brain_path),
            _check_manifest(brain_path),
            _check_vectorstore(brain_path),
            _check_disk_space(brain_path),
        ]
        if include_cloud:
            checks.extend(_cloud_checks(brain_path))

    # Determine overall status — "skip" means not applicable, not a problem
    active_statuses = [c["status"] for c in checks if c["status"] != "skip"]
    if any(s == "fail" for s in active_statuses):
        overall = "broken"
    elif any(s in ("missing", "error", "warn") for s in active_statuses):
        overall = "degraded"
    else:
        overall = "healthy"

    return {"status": overall, "checks": checks}


def print_diagnosis(report: dict) -> None:
    """Print human-readable diagnosis report."""
    status = report["status"]
    icons = {"ok": "+", "skip": "-", "missing": "!", "warn": "!", "fail": "X", "error": "X"}
    labels = {
        "healthy": "HEALTHY",
        "degraded": "DEGRADED",
        "broken": "BROKEN",
    }

    print(f"\n  Gradata Doctor — {labels.get(status, status.upper())}")
    print(f"  {'=' * 46}")

    for check in report["checks"]:
        icon = icons.get(check["status"], "?")
        name = check["name"].replace("_", " ").title()
        detail = check["detail"]
        print(f"  [{icon}] {name:<25} {detail}")

    print()
    if status == "healthy":
        print("  All checks passed. Brain environment is ready.")
    elif status == "degraded":
        print("  Some optional dependencies missing. Core functionality may be limited.")
        print("  Run the suggested pip install commands above to fix.")
    else:
        print("  Critical issues found. Brain cannot operate correctly.")
        print("  Fix the [X] items above before continuing.")
    print()
