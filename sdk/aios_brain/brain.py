"""
Brain — Core SDK class for operating a personal AI brain.

A Brain is a directory containing:
  - Markdown knowledge files (prospects, sessions, patterns, personas, etc.)
  - system.db (SQLite event log, facts, metrics)
  - .vectorstore/ (ChromaDB embeddings for semantic search)
  - .embed-manifest.json (file hash tracking for delta embedding)
  - brain.manifest.json (machine-readable brain spec)

Usage:
    brain = Brain.init("./my-brain")           # Bootstrap a new brain
    brain = Brain("./my-brain")                # Open existing brain

    # Search
    results = brain.search("budget objections")
    results = brain.search("Hassan Ali", mode="keyword")

    # Embed
    brain.embed()                              # Delta (only changed files)
    brain.embed(full=True)                     # Full re-embed

    # Events
    brain.emit("CORRECTION", "user", {"category": "DRAFTING", "detail": "..."})
    events = brain.query_events(event_type="CORRECTION", last_n_sessions=3)

    # Facts
    facts = brain.get_facts(prospect="Hassan Ali")

    # Manifest
    manifest = brain.manifest()                # Generate brain.manifest.json

    # Export
    brain.export("./exports/my-brain.zip")     # Package for marketplace
"""

import json
import os
import sqlite3
import sys
from pathlib import Path


class Brain:
    """A personal AI brain backed by a directory of knowledge files."""

    def __init__(self, brain_dir: str | Path):
        self.dir = Path(brain_dir).resolve()
        if not self.dir.exists():
            raise FileNotFoundError(f"Brain directory not found: {self.dir}")

        self.db_path = self.dir / "system.db"
        self.vectorstore_dir = self.dir / ".vectorstore"
        self.manifest_path = self.dir / "brain.manifest.json"
        self.embed_manifest_path = self.dir / ".embed-manifest.json"

        # Add scripts to path for imports
        scripts_dir = self.dir / "scripts"
        if scripts_dir.exists() and str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

    @classmethod
    def init(cls, brain_dir: str | Path, domain: str = "General") -> "Brain":
        """Bootstrap a new brain directory with empty structure."""
        brain_dir = Path(brain_dir).resolve()
        brain_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        for sub in ["prospects", "sessions", "personas", "objections",
                     "competitors", "emails", "learnings", "metrics",
                     "pipeline", "demos", "vault", "scripts"]:
            (brain_dir / sub).mkdir(exist_ok=True)

        # Create empty system.db with schema
        db_path = brain_dir / "system.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("""
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
        """)
        conn.execute("""
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
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_prospect ON facts(prospect)")
        conn.commit()
        conn.close()

        # Create VERSION.md
        version_file = brain_dir / "VERSION.md"
        if not version_file.exists():
            version_file.write_text(
                f"# Brain Version\n\nCurrent Version: v0.1.0\n"
                f"Domain: {domain}\nSession 0 — INFANT phase\n",
                encoding="utf-8",
            )

        # Create empty embed manifest
        manifest_file = brain_dir / ".embed-manifest.json"
        if not manifest_file.exists():
            manifest_file.write_text("{}", encoding="utf-8")

        # Create empty PATTERNS.md
        patterns = brain_dir / "emails" / "PATTERNS.md"
        if not patterns.exists():
            patterns.write_text(
                "# Email Patterns\n\nNo patterns yet. They emerge from real interactions.\n",
                encoding="utf-8",
            )

        # Create loop-state.md
        loop_state = brain_dir / "loop-state.md"
        if not loop_state.exists():
            loop_state.write_text(
                "<!-- memory_type: episodic -->\n"
                "# Loop State -- Last Updated (never)\n\n"
                "## Pipeline Summary\n0 active prospects | $0 pipeline value\n\n"
                "## What Changed\nBrain initialized. No sessions yet.\n\n"
                "## Next Session Tasks\n- Start your first work session\n\n"
                "## Deferred\n(none)\n\n"
                "## Loop Health\nScore: 0/10 -- Fresh brain, no data yet.\n",
                encoding="utf-8",
            )

        return cls(brain_dir)

    # ── Search ─────────────────────────────────────────────────────────

    def search(self, query: str, mode: str = None, top_k: int = 5,
               file_type: str = None) -> list[dict]:
        """Search the brain using keyword, semantic, or hybrid mode."""
        try:
            from query import brain_search
            return brain_search(
                query, file_type=file_type, top_k=top_k, mode=mode
            )
        except ImportError:
            # Fallback: basic file grep
            return self._grep_search(query, top_k)

    def _grep_search(self, query: str, top_k: int) -> list[dict]:
        """Fallback search: grep through markdown files."""
        results = []
        query_lower = query.lower()
        for f in self.dir.rglob("*.md"):
            if ".git" in str(f) or "scripts" in str(f):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if query_lower in text.lower():
                    # Find the matching line for context
                    for line in text.splitlines():
                        if query_lower in line.lower():
                            results.append({
                                "source": str(f.relative_to(self.dir)),
                                "text": line[:200],
                                "score": 1.0,
                                "confidence": "keyword_match",
                            })
                            break
            except Exception:
                continue
            if len(results) >= top_k:
                break
        return results

    # ── Embedding ──────────────────────────────────────────────────────

    def embed(self, full: bool = False) -> int:
        """Embed brain files into ChromaDB. Returns chunks embedded."""
        try:
            from embed import main as embed_main
            # Set args for embed.py
            sys.argv = ["embed.py"]
            if full:
                sys.argv.append("--full")
            # Capture the result
            embed_main()
            return 0  # embed_main doesn't return count cleanly
        except Exception as e:
            print(f"Embed error: {e}")
            return -1

    # ── Events ─────────────────────────────────────────────────────────

    def emit(self, event_type: str, source: str, data: dict = None,
             tags: list = None, session: int = None) -> dict:
        """Emit an event to the brain's event log."""
        try:
            from events import emit
            return emit(event_type, source, data or {}, tags or [], session)
        except ImportError:
            # Fallback: direct SQLite write
            return self._emit_direct(event_type, source, data, tags, session)

    def _emit_direct(self, event_type, source, data, tags, session):
        """Direct SQLite event emission without events.py."""
        from datetime import datetime, timezone
        conn = sqlite3.connect(str(self.db_path))
        ts = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO events (ts, session, type, source, data_json, tags_json) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, session, event_type, source,
             json.dumps(data or {}), json.dumps(tags or []))
        )
        conn.commit()
        conn.close()
        return {"ts": ts, "type": event_type, "source": source}

    def query_events(self, event_type: str = None, session: int = None,
                     last_n_sessions: int = None, limit: int = 100) -> list[dict]:
        """Query events from the brain's event log."""
        try:
            from events import query
            return query(event_type=event_type, session=session,
                         last_n_sessions=last_n_sessions, limit=limit)
        except ImportError:
            return []

    # ── Facts ──────────────────────────────────────────────────────────

    def get_facts(self, prospect: str = None, fact_type: str = None) -> list[dict]:
        """Query structured facts from the brain."""
        try:
            from fact_extractor import query_facts
            return query_facts(prospect=prospect, fact_type=fact_type)
        except ImportError:
            return []

    def extract_facts(self) -> int:
        """Extract structured facts from all prospect files."""
        try:
            from fact_extractor import extract_all, store_facts
            facts = extract_all()
            store_facts(facts)
            return len(facts)
        except ImportError:
            return 0

    # ── Manifest ───────────────────────────────────────────────────────

    def manifest(self) -> dict:
        """Generate brain.manifest.json and return it."""
        try:
            from brain_manifest import generate_manifest, write_manifest
            m = generate_manifest()
            write_manifest(m)
            return m
        except ImportError:
            # Minimal manifest without brain_manifest.py
            return {
                "schema_version": "1.0.0",
                "metadata": {
                    "brain_version": "unknown",
                    "domain": "unknown",
                },
            }

    # ── Export ──────────────────────────────────────────────────────────

    def export(self, output_path: str = None, mode: str = "full") -> Path:
        """Export brain as a shareable archive."""
        try:
            from export_brain import export_brain
            return export_brain(
                include_prospects=(mode != "no-prospects"),
                domain_only=(mode == "domain-only"),
            )
        except ImportError as e:
            raise RuntimeError(f"Export requires brain scripts: {e}")

    # ── Context ────────────────────────────────────────────────────────

    def context_for(self, message: str) -> str:
        """Compile relevant context for a user message."""
        try:
            from context_compile import compile_context
            return compile_context(message)
        except ImportError:
            # Fallback: basic search
            results = self.search(message[:100], top_k=3)
            if not results:
                return ""
            lines = ["## Brain Context"]
            for r in results:
                lines.append(f"- [{r.get('source', '')}] {r.get('text', '')[:150]}")
            return "\n".join(lines)

    # ── Info ───────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return brain statistics."""
        md_count = sum(1 for _ in self.dir.rglob("*.md")
                       if ".git" not in str(_) and "scripts" not in str(_))
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        vs_size = sum(f.stat().st_size for f in self.vectorstore_dir.rglob("*")
                      if f.is_file()) if self.vectorstore_dir.exists() else 0

        return {
            "brain_dir": str(self.dir),
            "markdown_files": md_count,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "vectorstore_size_mb": round(vs_size / 1024 / 1024, 2),
            "has_manifest": self.manifest_path.exists(),
            "has_embeddings": self.vectorstore_dir.exists() and vs_size > 0,
        }

    def __repr__(self):
        return f"Brain('{self.dir}')"
