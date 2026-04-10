"""Supabase wiki store — pgvector-backed wiki for cloud users.

Replaces local qmd (BM25 full-text) with pgvector (semantic similarity)
for rule injection and wiki search. Same API surface so the injection
hook works with either backend.

Requires: supabase-py + pgvector extension enabled on the Supabase project.

Schema (auto-created via ensure_schema()):
  - wiki_pages: page content + pgvector embedding
  - wiki_sources: raw source tracking (what was ingested)

Usage:
    store = WikiStore(supabase_url="...", supabase_key="...")
    store.ensure_schema()
    store.upsert_page({"title": "Rule: CODE", "category": "CODE", ...})
    results = store.search("code implementation", limit=5)
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension (fixed by model choice)

# SQL for schema creation (run via Supabase SQL editor or RPC)
SCHEMA_SQL = f"""
-- Enable pgvector extension
create extension if not exists vector;

-- Wiki pages: content + vector embedding for semantic search
create table if not exists wiki_pages (
    id              text primary key,
    brain_id        text not null,
    title           text not null,
    category        text,
    page_type       text not null default 'concept',
    content         text not null,
    content_hash    text not null,
    embedding       vector({EMBEDDING_DIM}),
    tags            jsonb default '[]'::jsonb,
    source_file     text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- Sources: track what raw documents were ingested
create table if not exists wiki_sources (
    id              text primary key,
    brain_id        text not null,
    title           text not null,
    source_type     text not null default 'document',
    source_url      text,
    file_path       text,
    content_hash    text not null,
    ingested_at     timestamptz not null default now(),
    metadata        jsonb default '{{}}'::jsonb
);

-- Indexes for common queries
create index if not exists idx_wiki_pages_brain on wiki_pages(brain_id);
create index if not exists idx_wiki_pages_category on wiki_pages(category);
create index if not exists idx_wiki_sources_brain on wiki_sources(brain_id);

-- Vector similarity index (IVFFlat for fast approximate search)
-- Only create if embedding column is populated
-- create index if not exists idx_wiki_pages_embedding
--     on wiki_pages using ivfflat (embedding vector_cosine_ops) with (lists = 100);
"""

# RLS policies (users can only access their own brain's data)
RLS_SQL = """
alter table wiki_pages enable row level security;
alter table wiki_sources enable row level security;

create policy if not exists "wiki_pages_brain_isolation"
    on wiki_pages for all
    using (brain_id = current_setting('app.brain_id', true));

create policy if not exists "wiki_sources_brain_isolation"
    on wiki_sources for all
    using (brain_id = current_setting('app.brain_id', true));
"""


@dataclass
class WikiPage:
    """A wiki page retrieved from the store."""

    id: str
    title: str
    category: str | None
    content: str
    page_type: str
    tags: list[str]
    similarity: float = 0.0


class WikiStore:
    """Supabase-backed wiki store with pgvector semantic search.

    Drop-in replacement for local qmd search in the rule injection hook.
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        brain_id: str,
    ) -> None:
        try:
            from supabase import create_client
        except ImportError:
            raise ImportError(
                "supabase-py required for cloud wiki. "
                "Install with: pip install gradata[cloud-wiki]"
            ) from None
        self.client = create_client(supabase_url, supabase_key)
        self.brain_id = brain_id
        self._embedder: Any = None

    def _get_embedder(self) -> Any:
        """Lazy-load sentence-transformers model."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                raise ImportError(
                    "sentence-transformers required for embeddings. "
                    "Install with: pip install gradata[embeddings]"
                ) from None
        return self._embedder

    def _embed(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        model = self._get_embedder()
        return model.encode(text).tolist()

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    def _page_id(brain_id: str, title: str) -> str:
        digest = hashlib.sha256(f"{brain_id}:{title}".encode()).hexdigest()[:12]
        return f"wp_{digest}"

    @staticmethod
    def _source_id(brain_id: str, path_or_url: str) -> str:
        digest = hashlib.sha256(f"{brain_id}:{path_or_url}".encode()).hexdigest()[:12]
        return f"ws_{digest}"

    # ── Schema management ─────────────────────────────────────────────

    def ensure_schema(self) -> None:
        """Create wiki tables if they don't exist.

        Attempts to use the ``exec_sql`` Supabase RPC function. This is NOT
        a standard Supabase function — you must create it manually first, or
        run the SQL in ``SCHEMA_SQL`` directly via the Supabase SQL editor.
        """
        try:
            self.client.rpc("exec_sql", {"sql": SCHEMA_SQL}).execute()
            _log.info("Wiki schema ensured for brain %s", self.brain_id)
        except Exception as e:
            _log.warning(
                "Schema creation via RPC failed. Run SCHEMA_SQL and "
                "SEARCH_RPC_SQL manually in the Supabase SQL editor: %s", e,
            )

    # ── Page CRUD ─────────────────────────────────────────────────────

    def upsert_page(
        self,
        title: str,
        content: str,
        category: str | None = None,
        page_type: str = "concept",
        tags: list[str] | None = None,
        source_file: str | None = None,
        embed: bool = True,
    ) -> str:
        """Insert or update a wiki page. Returns page ID."""
        page_id = self._page_id(self.brain_id, title)
        now = datetime.now(UTC).isoformat()

        row: dict[str, Any] = {
            "id": page_id,
            "brain_id": self.brain_id,
            "title": title,
            "category": category,
            "page_type": page_type,
            "content": content,
            "content_hash": self._content_hash(content),
            "tags": json.dumps(tags or []),
            "source_file": source_file,
            "updated_at": now,
        }

        if embed:
            try:
                row["embedding"] = self._embed(f"{title}\n{content[:500]}")
            except ImportError:
                _log.debug("Embeddings unavailable, storing page without vector")

        self.client.table("wiki_pages").upsert(row).execute()
        return page_id

    def get_page(self, title: str) -> WikiPage | None:
        """Get a page by title."""
        page_id = self._page_id(self.brain_id, title)
        resp = (
            self.client.table("wiki_pages")
            .select("*")
            .eq("id", page_id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None
        return self._row_to_page(resp.data)

    def delete_page(self, title: str) -> bool:
        """Delete a page by title."""
        page_id = self._page_id(self.brain_id, title)
        self.client.table("wiki_pages").delete().eq("id", page_id).execute()
        return True

    # ── Search ────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 5) -> list[WikiPage]:
        """Semantic search via pgvector cosine similarity.

        This is the cloud replacement for ``qmd search``.
        Returns pages ranked by embedding similarity.
        """
        try:
            query_vec = self._embed(query)
        except ImportError:
            return self._text_search(query, limit)

        # Use Supabase RPC for vector similarity search
        resp = self.client.rpc("wiki_search", {
            "query_embedding": query_vec,
            "match_brain_id": self.brain_id,
            "match_count": limit,
        }).execute()

        if not resp.data:
            return []

        pages = []
        for row in resp.data:
            page = self._row_to_page(row)
            page.similarity = row.get("similarity", 0.0)
            pages.append(page)
        return pages

    def search_by_category(self, category: str) -> list[WikiPage]:
        """Get all pages in a category (for rule injection)."""
        resp = (
            self.client.table("wiki_pages")
            .select("*")
            .eq("brain_id", self.brain_id)
            .eq("category", category.upper())
            .execute()
        )
        return [self._row_to_page(row) for row in (resp.data or [])]

    def search_categories(self, query: str, limit: int = 10) -> set[str]:
        """Semantic search returning matched categories (for rule injection hook).

        Drop-in replacement for _wiki_categories() in inject_brain_rules.py.
        """
        pages = self.search(query, limit=limit)
        return {p.category.upper() for p in pages if p.category}

    def _text_search(self, query: str, limit: int) -> list[WikiPage]:
        """Fallback text search when embeddings unavailable."""
        resp = (
            self.client.table("wiki_pages")
            .select("*")
            .eq("brain_id", self.brain_id)
            .ilike("content", "%{}%".format(query.replace("%", r"\%").replace("_", r"\_")))
            .limit(limit)
            .execute()
        )
        return [self._row_to_page(row) for row in (resp.data or [])]

    # ── Source tracking ───────────────────────────────────────────────

    def add_source(
        self,
        title: str,
        source_type: str = "document",
        source_url: str | None = None,
        file_path: str | None = None,
        content_hash: str = "",
        metadata: dict | None = None,
    ) -> str:
        """Track an ingested source document."""
        source_id = self._source_id(self.brain_id, source_url or file_path or title)
        self.client.table("wiki_sources").upsert({
            "id": source_id,
            "brain_id": self.brain_id,
            "title": title,
            "source_type": source_type,
            "source_url": source_url,
            "file_path": file_path,
            "content_hash": content_hash,
            "metadata": json.dumps(metadata or {}),
        }).execute()
        return source_id

    def list_sources(self) -> list[dict]:
        """List all tracked sources for this brain."""
        resp = (
            self.client.table("wiki_sources")
            .select("*")
            .eq("brain_id", self.brain_id)
            .order("ingested_at", desc=True)
            .execute()
        )
        return resp.data or []

    # ── Sync from local wiki ──────────────────────────────────────────

    def sync_from_local(self, wiki_dir: str | Path) -> dict[str, int]:
        """Upload local wiki pages to Supabase.

        Reads all .md files from wiki_dir, compares content hashes,
        and upserts changed pages. Returns counts.
        """
        wiki_path = Path(wiki_dir)
        if not wiki_path.is_dir():
            return {"uploaded": 0, "skipped": 0, "errors": 0}

        uploaded = skipped = errors = 0

        for md_file in wiki_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem.replace("-", " ").title()

                # Parse frontmatter for category/type
                category = None
                page_type = "concept"
                tags: list[str] = []
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].splitlines():
                            line = line.strip()
                            if line.startswith("category:"):
                                category = line.split(":", 1)[1].strip().upper()
                            elif line.startswith("type:"):
                                page_type = line.split(":", 1)[1].strip()
                            elif line.startswith("title:"):
                                title = line.split(":", 1)[1].strip().strip('"')

                # Check if content changed
                content_hash = self._content_hash(content)
                page_id = self._page_id(self.brain_id, title)
                existing = (
                    self.client.table("wiki_pages")
                    .select("content_hash")
                    .eq("id", page_id)
                    .maybe_single()
                    .execute()
                )
                if existing.data and existing.data.get("content_hash") == content_hash:
                    skipped += 1
                    continue

                self.upsert_page(
                    title=title,
                    content=content,
                    category=category,
                    page_type=page_type,
                    tags=tags,
                    source_file=str(md_file.relative_to(wiki_path)),
                )
                uploaded += 1
            except Exception as e:
                _log.debug("Failed to sync %s: %s", md_file, e)
                errors += 1

        return {"uploaded": uploaded, "skipped": skipped, "errors": errors}

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_page(row: dict) -> WikiPage:
        tags = row.get("tags", [])
        if isinstance(tags, str):
            tags = json.loads(tags)
        return WikiPage(
            id=row["id"],
            title=row["title"],
            category=row.get("category"),
            content=row.get("content", ""),
            page_type=row.get("page_type", "concept"),
            tags=tags,
        )


# ── Supabase RPC function for vector search ──────────────────────────

SEARCH_RPC_SQL = f"""
create or replace function wiki_search(
    query_embedding vector({EMBEDDING_DIM}),
    match_brain_id text,
    match_count int default 5
)
returns table (
    id text,
    title text,
    category text,
    content text,
    page_type text,
    tags jsonb,
    similarity float
)
language plpgsql
as $$
begin
    return query
    select
        wp.id,
        wp.title,
        wp.category,
        wp.content,
        wp.page_type,
        wp.tags,
        1 - (wp.embedding <=> query_embedding) as similarity
    from wiki_pages wp
    where wp.brain_id = match_brain_id
        and wp.embedding is not null
    order by wp.embedding <=> query_embedding
    limit match_count;
end;
$$;
"""
