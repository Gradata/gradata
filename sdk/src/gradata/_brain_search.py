"""Brain mixin — Search and Embedding methods."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BrainSearchMixin:
    """Search and embedding capabilities for Brain."""

    # ── Search ─────────────────────────────────────────────────────────

    def search(self, query: str, mode: str = None, top_k: int = 5,
               file_type: str = None) -> list[dict]:
        """Search the brain using FTS5 keyword search.

        All modes use FTS5 keyword search. sqlite-vec planned for vector similarity.
        """
        try:
            from gradata._query import brain_search
            results = brain_search(
                query, file_type=file_type, top_k=top_k, mode=mode, ctx=self.ctx
            )
        except ImportError:
            # Fallback: basic file grep
            results = self._grep_search(query, top_k)
        if not results:
            import logging
            logging.getLogger("gradata").debug(
                "search() returned no results. Brain may be empty — "
                "add content via correct(), embed(), or create markdown files."
            )
        return results

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
        """Embed brain files into SQLite. Returns chunks embedded.

        Embeddings stored in SQLite brain_embeddings table.
        """
        try:
            from gradata._embed import main as embed_main
            return embed_main(brain_dir=self.dir, full=full)
        except ImportError as e:
            raise ImportError(
                f"Embedding requires additional dependencies: {e}\n"
                "Run: pip install sentence-transformers"
            ) from e
        except Exception as e:
            print(f"Embed error: {e}")
            return -1
