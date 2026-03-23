"""
Onboarding wizard for bootstrapping a new AIOS Brain.

Supports two modes:
  - Interactive: prompts user for brain config via input()
  - Non-interactive: all values passed as kwargs

Usage:
    # Interactive (CLI)
    from aios_brain.onboard import onboard
    brain = onboard("./my-brain")

    # Non-interactive (programmatic)
    brain = onboard("./my-brain", name="SalesBrain", domain="Sales",
                     company="Acme Corp", embedding="local")
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


# ── Schema: SQLite tables created for every new brain ──────────────────

_TABLES_SQL = [
    # Core event log
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        session INTEGER,
        type TEXT NOT NULL,
        source TEXT,
        data_json TEXT,
        tags_json TEXT,
        valid_from TEXT,
        valid_until TEXT
    )
    """,
    # Structured facts extracted from knowledge files
    """
    CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect TEXT NOT NULL,
        company TEXT,
        fact_type TEXT NOT NULL,
        fact_value TEXT NOT NULL,
        confidence REAL DEFAULT 0.5,
        source TEXT,
        extracted_at TEXT,
        last_verified TEXT,
        session INTEGER,
        stale BOOLEAN DEFAULT 0
    )
    """,
    # Lesson application tracking
    """
    CREATE TABLE IF NOT EXISTS lesson_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_id TEXT NOT NULL,
        session INTEGER,
        applied_at TEXT,
        context TEXT,
        outcome TEXT,
        success BOOLEAN DEFAULT 1
    )
    """,
    # Named entities (people, companies, products)
    """
    CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        metadata_json TEXT,
        first_seen TEXT,
        last_seen TEXT,
        mention_count INTEGER DEFAULT 1
    )
    """,
]

_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)",
    "CREATE INDEX IF NOT EXISTS idx_events_session ON events(session)",
    "CREATE INDEX IF NOT EXISTS idx_facts_prospect ON facts(prospect)",
    "CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_lesson_apps_lesson ON lesson_applications(lesson_id)",
]

# ── Subdirectories every brain gets ────────────────────────────────────

_SUBDIRS = [
    "prospects",
    "sessions",
    "emails",
    "vault",
    "scripts",
]


def _ask(prompt: str, default: str = "") -> str:
    """Prompt user with a default value. Returns stripped answer or default."""
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _build_manifest(name: str, domain: str, embedding: str) -> dict:
    """Build the initial brain.manifest.json content."""
    return {
        "schema_version": "1.0.0",
        "metadata": {
            "brain_name": name,
            "brain_version": "v0.1.0",
            "domain": domain,
            "maturity_phase": "INFANT",
            "sessions_trained": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "quality": {
            "correction_rate": None,
            "lessons_graduated": 0,
            "lessons_active": 0,
            "first_draft_acceptance": None,
        },
        "memory_composition": {
            "episodic": 0,
            "semantic": 0,
            "procedural": 0,
            "strategic": 0,
        },
        "database": {
            "engine": "sqlite3",
            "path": "system.db",
            "tables": ["events", "facts", "lesson_applications", "entities"],
            "event_types": 0,
            "total_events": 0,
        },
        "rag": {
            "active": False,
            "provider": embedding,
            "model": "local" if embedding == "local" else "gemini-embedding-2-preview",
            "dimensions": 384 if embedding == "local" else 768,
            "chunks_indexed": 0,
            "hybrid_search": False,
            "fts5_enabled": False,
        },
        "behavioral_contract": {
            "safety_rules": 0,
            "global_rules": 0,
            "domain_rules": 0,
            "total": 0,
        },
        "tag_taxonomy": {},
        "paths": {
            "brain_dir": "$BRAIN_DIR",
            "domain_dir": "$DOMAIN_DIR",
            "working_dir": "$WORKING_DIR",
        },
        "api_requirements": {
            "gemini": {
                "env_var": "GEMINI_API_KEY",
                "required": embedding == "gemini",
                "tier": "free",
            },
        },
        "bootstrap": [
            {
                "step": "set_env_vars",
                "desc": "Set BRAIN_DIR, WORKING_DIR, DOMAIN_DIR",
                "required": True,
            },
            {
                "step": "init_db",
                "command": "aios-brain init .",
                "required": True,
            },
            {
                "step": "embed_brain",
                "command": "aios-brain embed --full",
                "required": True,
            },
        ],
        "compatibility": {
            "python": ">=3.11",
            "chromadb": ">=0.5.0",
            "platform": "any",
        },
    }


def _create_db(db_path: Path) -> None:
    """Create system.db with all required tables and indexes."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    for sql in _TABLES_SQL:
        conn.execute(sql)
    for sql in _INDEXES_SQL:
        conn.execute(sql)
    conn.commit()
    conn.close()


def _create_company_md(brain_dir: Path, company: str) -> None:
    """Create a starter company.md file."""
    content = (
        f"# {company}\n\n"
        f"## Overview\n"
        f"Company: {company}\n\n"
        f"## ICP\n"
        f"(Define your ideal customer profile here)\n\n"
        f"## Product\n"
        f"(Describe your product/service here)\n\n"
        f"## Competitors\n"
        f"(List known competitors)\n"
    )
    (brain_dir / "company.md").write_text(content, encoding="utf-8")


def onboard(
    path: str | Path,
    *,
    name: str | None = None,
    domain: str | None = None,
    company: str | None = None,
    embedding: str | None = None,
    interactive: bool = True,
) -> "Brain":
    """
    Bootstrap a new brain with the onboarding wizard.

    Args:
        path: Directory to create the brain in.
        name: Brain name (used in manifest). Prompted if None and interactive.
        domain: Domain (e.g. "Sales", "Engineering"). Prompted if None and interactive.
        company: Company name. If provided, creates company.md. Prompted if None and interactive.
        embedding: "local" (default) or "gemini". Prompted if None and interactive.
        interactive: If False, uses defaults for any missing values.

    Returns:
        Brain instance pointing at the new directory.
    """
    from aios_brain.brain import Brain

    brain_dir = Path(path).resolve()

    if brain_dir.exists() and (brain_dir / "brain.manifest.json").exists():
        raise FileExistsError(
            f"Brain already exists at {brain_dir}. "
            f"Use Brain('{brain_dir}') to open it."
        )

    # ── Collect answers ────────────────────────────────────────────────

    if interactive:
        print("\n=== AIOS Brain — Onboarding Wizard ===\n")

    if name is None:
        if interactive:
            name = _ask("Brain name", default=brain_dir.name)
        else:
            name = brain_dir.name

    if domain is None:
        if interactive:
            domain = _ask("Domain (e.g. Sales, Engineering, Support)", default="General")
        else:
            domain = "General"

    if company is None and interactive:
        company = _ask("Company name (optional, press Enter to skip)", default="")
        if not company:
            company = None

    if embedding is None:
        if interactive:
            print("\nEmbedding provider:")
            print("  local  — No API key needed, runs on-device (default)")
            print("  gemini — Uses Gemini free tier, requires GEMINI_API_KEY")
            embedding = _ask("Choice", default="local")
        else:
            embedding = "local"

    # Validate embedding choice
    embedding = embedding.lower().strip()
    if embedding not in ("local", "gemini"):
        print(f"Unknown embedding provider '{embedding}', falling back to 'local'.")
        embedding = "local"

    # Warn if gemini selected but no key
    if embedding == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        print("\nWARNING: GEMINI_API_KEY not set in environment.")
        print("Embeddings will fail until you set it. You can switch to 'local' later.\n")

    # ── Build the brain ────────────────────────────────────────────────

    brain_dir.mkdir(parents=True, exist_ok=True)

    # Subdirectories
    for sub in _SUBDIRS:
        (brain_dir / sub).mkdir(exist_ok=True)

    # SQLite database
    _create_db(brain_dir / "system.db")

    # brain.manifest.json
    manifest = _build_manifest(name, domain, embedding)
    (brain_dir / "brain.manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )

    # company.md (optional)
    if company:
        _create_company_md(brain_dir, company)

    # Empty embed manifest for delta tracking
    embed_manifest = brain_dir / ".embed-manifest.json"
    if not embed_manifest.exists():
        embed_manifest.write_text("{}", encoding="utf-8")

    # loop-state.md — starting state
    loop_state = brain_dir / "loop-state.md"
    if not loop_state.exists():
        loop_state.write_text(
            "<!-- memory_type: episodic -->\n"
            f"# Loop State — {name}\n\n"
            "## Status\nBrain initialized. No sessions yet.\n\n"
            "## Next Steps\n- Start your first work session\n- Add knowledge files to the brain\n"
            "- Run `aios-brain embed` to index your content\n",
            encoding="utf-8",
        )

    # VERSION.md
    version_file = brain_dir / "VERSION.md"
    if not version_file.exists():
        version_file.write_text(
            f"# {name}\n\nVersion: v0.1.0\n"
            f"Domain: {domain}\nSession 0 — INFANT phase\n",
            encoding="utf-8",
        )

    # ── Success output ─────────────────────────────────────────────────

    brain = Brain(brain_dir)

    if interactive:
        stats = brain.stats()
        print(f"\n{'='*50}")
        print(f"Brain '{name}' created at {brain_dir}")
        print(f"  Domain:    {domain}")
        print(f"  Embedding: {embedding}")
        if company:
            print(f"  Company:   {company}")
        print(f"  DB:        {stats['db_size_mb']} MB")
        print(f"  Files:     {stats['markdown_files']} markdown files")
        print(f"{'='*50}")
        print(f"\nNext steps:")
        print(f"  1. cd {brain_dir}")
        print(f"  2. Add prospect files to prospects/")
        print(f"  3. Run: aios-brain embed --full")
        print(f"  4. Run: aios-brain search \"your query\"")
        if embedding == "gemini":
            print(f"  5. Set GEMINI_API_KEY in your environment")
        print()

    return brain
