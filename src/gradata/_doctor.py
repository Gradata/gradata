"""
Gradata Doctor — Environment and brain health diagnostics.

Usage:
    from gradata._doctor import diagnose, print_diagnosis
    report = diagnose()
    print_diagnosis(report)

    # Or via CLI:
    gradata doctor
"""

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path


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
        "status": "fts5",
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
            "status": "skip",
            "detail": "BRAIN_DIR not set (optional)",
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
        pass
    return None


def _check_system_db(brain_path):
    """Check system.db exists and is readable."""
    if brain_path is None:
        return {"name": "system_db", "status": "skip", "detail": "no brain dir resolved"}
    db = brain_path / "system.db"
    if not db.exists():
        return {"name": "system_db", "status": "skip", "detail": "system.db not found (brain may not be initialized)"}
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
        return {"name": "events_jsonl", "status": "skip", "detail": "no brain dir resolved"}
    ej = brain_path / "events.jsonl"
    if not ej.exists():
        return {"name": "events_jsonl", "status": "skip", "detail": "events.jsonl not found (brain may not be initialized)"}
    try:
        size_kb = round(ej.stat().st_size / 1024, 1)
        return {"name": "events_jsonl", "status": "ok", "detail": f"exists, {size_kb} KB"}
    except Exception as e:
        return {"name": "events_jsonl", "status": "fail", "detail": str(e)}


def _check_manifest(brain_path):
    """Check brain.manifest.json is valid JSON."""
    if brain_path is None:
        return {"name": "brain_manifest", "status": "skip", "detail": "no brain dir resolved"}
    mf = brain_path / "brain.manifest.json"
    if not mf.exists():
        return {"name": "brain_manifest", "status": "skip", "detail": "brain.manifest.json not found (optional)"}
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
        return {"name": "vectorstore", "status": "skip", "detail": "no brain dir resolved"}
    vs = brain_path / ".vectorstore"
    if not vs.exists():
        return {"name": "vectorstore", "status": "skip", "detail": ".vectorstore/ not found (embeddings not enabled)"}
    if vs.is_dir():
        file_count = sum(1 for _ in vs.rglob("*") if _.is_file())
        return {"name": "vectorstore", "status": "ok", "detail": f"exists, {file_count} files"}
    return {"name": "vectorstore", "status": "fail", "detail": ".vectorstore exists but is not a directory"}


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


def diagnose(brain_dir: str | Path | None = None) -> dict:
    """Run all health checks and return structured report.

    Args:
        brain_dir: Explicit brain directory to check. If None, resolves
                   from BRAIN_DIR env or _paths module.

    Returns:
        {
            "status": "healthy" | "degraded" | "broken",
            "checks": [ {"name": ..., "status": ..., "detail": ...}, ... ]
        }
    """
    # Resolve brain path
    if brain_dir:
        brain_path = Path(brain_dir).resolve()
    else:
        brain_path = _resolve_brain_path()

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
