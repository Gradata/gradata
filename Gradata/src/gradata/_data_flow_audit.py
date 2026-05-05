"""
Data Flow Audit.
==================
Verifies data pipes connect: events, indexes, facts, hooks, embeddings.
"""

import json
import sqlite3
from datetime import datetime

import gradata._paths as _p
from gradata._paths import BrainContext

CHECKS = []


def _check(name: str, passed: bool, detail: str = ""):
    CHECKS.append({"name": name, "passed": passed, "detail": detail})


def check_event_pipes(ctx: "BrainContext | None" = None):
    known_types = [
        "CORRECTION",
        "GATE_RESULT",
        "GATE_OVERRIDE",
        "OUTPUT",
        "AUDIT_SCORE",
        "LESSON_CHANGE",
        "CALIBRATION",
        "HEALTH_CHECK",
        "COST_EVENT",
        "TOOL_FAILURE",
        "HALLUCINATION",
        "STALE_DATA",
        "VERIFICATION",
        "STEP_COMPLETE",
        "DEFER",
    ]
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        rows = conn.execute("SELECT DISTINCT type FROM events").fetchall()
        conn.close()
        emitted_types = {r[0] for r in rows}
    except Exception:
        emitted_types = set()
    for t in known_types:
        _check(
            f"event_pipe:{t}",
            t in emitted_types,
            "has emissions" if t in emitted_types else "no emissions found",
        )


def check_index_completeness(ctx: BrainContext | None = None):
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    manifest_path = brain_dir / ".embed-manifest.json"
    if not manifest_path.exists():
        _check("index:manifest_exists", False, ".embed-manifest.json missing")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    indexed_files = set(manifest.keys())
    skip_dirs = {".git", ".vectorstore", "scripts", "cache", "backups", "archive"}
    brain_files = set()
    for f in brain_dir.rglob("*.md"):
        if any(part in skip_dirs for part in f.parts):
            continue
        if f.name.startswith("_") or f.name in {"README.md", ".gitkeep"}:
            continue
        rel = str(f.relative_to(brain_dir)).replace("\\", "/")
        brain_files.add(rel)
    missing = brain_files - indexed_files
    if missing:
        _check(
            "index:completeness", False, f"{len(missing)} files not indexed: {list(missing)[:5]}"
        )
    else:
        _check("index:completeness", True, f"{len(brain_files)} files all indexed")


def check_facts_freshness(ctx: "BrainContext | None" = None):
    prospects_dir = ctx.prospects_dir if ctx else _p.PROSPECTS_DIR
    if not prospects_dir.exists():
        _check("facts:prospects_dir", False, "prospects/ not found")
        return
    prospect_files = [f for f in prospects_dir.glob("*.md") if not f.name.startswith("_")]
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        if "facts" not in tables:
            _check("facts:table_exists", False, "facts table missing")
            conn.close()
            return
        rows = conn.execute("SELECT DISTINCT prospect FROM facts WHERE stale = 0").fetchall()
        conn.close()
        prospects_with_facts = {r[0] for r in rows}
    except Exception as e:
        _check("facts:query", False, f"DB error: {e}")
        return
    missing = []
    for f in prospect_files:
        name = f.stem.split("\u2014")[0].split("\u2013")[0].split("-")[0].strip()
        if name not in prospects_with_facts:
            found = any(name.lower() in p.lower() for p in prospects_with_facts)
            if not found:
                missing.append(name)
    if missing:
        _check("facts:coverage", False, f"{len(missing)} prospects missing facts: {missing[:5]}")
    else:
        _check("facts:coverage", True, f"{len(prospect_files)} prospects all have facts")


def check_embeddings(ctx: BrainContext | None = None):
    """Check SQLite brain_embeddings table for indexed chunks."""
    import sqlite3

    db = ctx.db_path if ctx else _p.DB_PATH
    try:
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT COUNT(*) FROM brain_embeddings").fetchone()
        count = row[0] if row else 0
        conn.close()
        _check("embeddings:sqlite", count > 0, f"{count} chunks in brain_embeddings")
    except Exception:
        _check("embeddings:sqlite", True, "brain_embeddings table not yet created (ok)")


def check_fts5(ctx: BrainContext | None = None):
    db = ctx.db_path if ctx else _p.DB_PATH
    try:
        conn = sqlite3.connect(str(db))
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        if "brain_fts" not in tables:
            _check("fts5:table", False, "brain_fts virtual table missing")
            conn.close()
            return
        count = conn.execute("SELECT COUNT(*) FROM brain_fts_content").fetchone()[0]
        conn.close()
        _check("fts5:data", count > 0, f"{count} chunks indexed")
    except Exception as e:
        _check("fts5:query", False, f"error: {e}")


def check_manifest(ctx: BrainContext | None = None):
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    manifest_path = brain_dir / "brain.manifest.json"
    if not manifest_path.exists():
        _check("manifest:exists", False, "brain.manifest.json not found")
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = ["schema_version", "metadata", "quality", "database", "rag"]
        missing = [k for k in required if k not in manifest]
        if missing:
            _check("manifest:schema", False, f"missing keys: {missing}")
        else:
            _check("manifest:schema", True, f"v{manifest['schema_version']}")
    except Exception as e:
        _check("manifest:parse", False, f"JSON error: {e}")


def run_audit(ctx: "BrainContext | None" = None) -> dict:
    CHECKS.clear()
    check_event_pipes(ctx=ctx)
    check_index_completeness(ctx=ctx)
    check_facts_freshness(ctx=ctx)
    check_embeddings(ctx=ctx)
    check_fts5(ctx=ctx)
    check_manifest(ctx=ctx)
    passed = sum(1 for c in CHECKS if c["passed"])
    total = len(CHECKS)
    score = round(passed / total * 100, 1) if total > 0 else 0
    return {
        "timestamp": datetime.now().isoformat(),
        "passed": passed,
        "total": total,
        "score": score,
        "checks": CHECKS,
    }
