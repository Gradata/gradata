"""Brain mixin — Export, Manifest, Context, Stats, Briefing, and Git Backfill methods."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BrainExportMixin:
    """Manifest generation, export, context compilation, stats, briefing, and git backfill for Brain."""

    # ── Manifest ───────────────────────────────────────────────────────

    def manifest(self) -> dict:
        """Generate brain.manifest.json and return it."""
        try:
            from gradata._brain_manifest import generate_manifest, write_manifest
            m = generate_manifest(ctx=self.ctx)
            write_manifest(m, ctx=self.ctx)
            return m
        except ImportError:
            # Minimal manifest without brain_manifest module
            return {
                "schema_version": "1.0.0",
                "metadata": {
                    "brain_version": "unknown",
                    "domain": "unknown",
                },
            }

    # ── Export ──────────────────────────────────────────────────────────

    def export(self, output_path: str = None, mode: str = "full") -> "Path":
        """Export brain as a shareable archive."""
        try:
            from gradata._export_brain import export_brain
            return export_brain(
                include_prospects=(mode != "no-prospects"),
                domain_only=(mode == "domain-only"),
                ctx=self.ctx,
            )
        except ImportError as e:
            raise RuntimeError(f"Export requires brain modules: {e}")

    # ── Context ────────────────────────────────────────────────────────

    def context_for(self, message: str) -> str:
        """Compile relevant context for a user message."""
        try:
            from gradata._context_compile import compile_context
            return compile_context(message, ctx=self.ctx)
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
        import sqlite3

        md_count = sum(1 for _ in self.dir.rglob("*.md")
                       if ".git" not in str(_) and "scripts" not in str(_))
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        # Check for embeddings in SQLite
        has_embeddings = False
        embedding_count = 0
        if self.db_path.exists():
            try:
                conn = sqlite3.connect(str(self.db_path))
                row = conn.execute(
                    "SELECT COUNT(*) FROM brain_embeddings"
                ).fetchone()
                embedding_count = row[0] if row else 0
                has_embeddings = embedding_count > 0
                conn.close()
            except Exception:
                pass

        return {
            "brain_dir": str(self.dir),
            "markdown_files": md_count,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "embedding_chunks": embedding_count,
            "has_manifest": self.manifest_path.exists(),
            "has_embeddings": has_embeddings,
        }

    # ── Briefing (portable context for any agent) ──────────────────────

    def briefing(self, output_dir: str | Path = ".") -> str:
        """Generate a brain briefing and return as markdown.

        The briefing is a single file any AI agent can consume:
        Claude Code, Cursor, Copilot, or any system prompt.

        Args:
            output_dir: Where to write export files (optional).

        Returns:
            Markdown string with rules, anti-patterns, corrections, health.
        """
        try:
            from gradata.enhancements.brain_briefing import generate_briefing
            b = generate_briefing(self)
            return b.to_markdown()
        except ImportError:
            return "# Brain Briefing\n\nBriefing module not available."

    def export_briefing(
        self,
        output_dir: str | Path = ".",
        formats: list[str] | None = None,
    ) -> dict:
        """Export briefing to agent-specific files.

        Writes to BRAIN-RULES.md, .cursorrules, copilot-instructions.md.

        Args:
            output_dir: Directory to write files to.
            formats: List of targets ("claude", "cursor", "copilot", "generic").
        """
        try:
            from gradata.enhancements.brain_briefing import export_briefing
            written = export_briefing(self, output_dir, formats)
            return {k: str(v) for k, v in written.items()}
        except ImportError:
            return {"error": "Briefing module not available."}

    # ── Git Backfill ─────────────────────────────────────────────────────

    def backfill_from_git(
        self,
        repo_path: str | Path = ".",
        lookback_days: int = 90,
        file_patterns: list[str] | None = None,
        max_commits: int = 500,
    ) -> dict:
        """Bootstrap this brain from git history.

        Walks git log, extracts before/after diffs, and feeds them as
        corrections. A new brain can start with months of learning.

        Args:
            repo_path: Path to the git repository.
            lookback_days: How far back to scan (default 90 days).
            file_patterns: Glob patterns to filter (default: py, md, ts, js, txt).
            max_commits: Max commits to process.

        Returns:
            Dict with backfill statistics.
        """
        import logging
        logger = logging.getLogger("gradata")

        try:
            from gradata.enhancements.git_backfill import backfill_from_git
            stats = backfill_from_git(
                brain=self,
                repo_path=repo_path,
                lookback_days=lookback_days,
                file_patterns=file_patterns,
                max_commits=max_commits,
            )
            return stats.to_dict()
        except ImportError:
            return {"error": "git_backfill module not available"}
        except Exception as e:
            logger.warning("Git backfill failed: %s", e)
            return {"error": str(e)}
