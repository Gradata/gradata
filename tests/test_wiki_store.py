"""Tests for cloud wiki store (wiki_store.py).

Tests the WikiStore logic with a mocked Supabase client since
we can't connect to a real Supabase instance in CI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class MockResponse:
    data: list | dict | None = None


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    with patch("gradata.cloud.wiki_store.WikiStore.__init__", return_value=None) as _:
        from gradata.cloud.wiki_store import WikiStore
        store = object.__new__(WikiStore)
        store.client = MagicMock()
        store.brain_id = "test-brain"
        store._embedder = None
        yield store


def test_page_id_deterministic():
    from gradata.cloud.wiki_store import WikiStore
    id1 = WikiStore._page_id("brain1", "My Title")
    id2 = WikiStore._page_id("brain1", "My Title")
    id3 = WikiStore._page_id("brain1", "Other Title")
    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("wp_")


def test_source_id_deterministic():
    from gradata.cloud.wiki_store import WikiStore
    id1 = WikiStore._source_id("brain1", "https://example.com")
    id2 = WikiStore._source_id("brain1", "https://example.com")
    assert id1 == id2
    assert id1.startswith("ws_")


def test_content_hash():
    from gradata.cloud.wiki_store import WikiStore
    h1 = WikiStore._content_hash("hello world")
    h2 = WikiStore._content_hash("hello world")
    h3 = WikiStore._content_hash("different")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16


def test_upsert_page(mock_supabase):
    mock_table = MagicMock()
    mock_table.upsert.return_value.execute.return_value = MockResponse()
    mock_supabase.client.table.return_value = mock_table

    page_id = mock_supabase.upsert_page(
        title="Test Page",
        content="Some content",
        category="CODE",
        embed=False,
    )

    assert page_id.startswith("wp_")
    mock_supabase.client.table.assert_called_with("wiki_pages")
    mock_table.upsert.assert_called_once()
    row = mock_table.upsert.call_args[0][0]
    assert row["brain_id"] == "test-brain"
    assert row["title"] == "Test Page"
    assert row["category"] == "CODE"


def test_get_page_found(mock_supabase):
    mock_chain = MagicMock()
    mock_chain.select.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.maybe_single.return_value = mock_chain
    mock_chain.execute.return_value = MockResponse(data={
        "id": "wp_abc", "title": "Test", "category": "CODE",
        "content": "hello", "page_type": "concept", "tags": "[]",
    })
    mock_supabase.client.table.return_value = mock_chain

    page = mock_supabase.get_page("Test")
    assert page is not None
    assert page.title == "Test"
    assert page.category == "CODE"


def test_get_page_not_found(mock_supabase):
    mock_chain = MagicMock()
    mock_chain.select.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.maybe_single.return_value = mock_chain
    mock_chain.execute.return_value = MockResponse(data=None)
    mock_supabase.client.table.return_value = mock_chain

    page = mock_supabase.get_page("Nonexistent")
    assert page is None


def test_search_categories(mock_supabase):
    mock_supabase.client.rpc.return_value.execute.return_value = MockResponse(data=[
        {"id": "wp_1", "title": "Rule: CODE", "category": "CODE",
         "content": "...", "page_type": "concept", "tags": "[]", "similarity": 0.9},
        {"id": "wp_2", "title": "Rule: TONE", "category": "TONE",
         "content": "...", "page_type": "concept", "tags": "[]", "similarity": 0.7},
    ])
    # Mock _embed to return a dummy vector
    mock_supabase._embed = lambda text: [0.0] * 384

    cats = mock_supabase.search_categories("code implementation")
    assert "CODE" in cats
    assert "TONE" in cats


def test_text_search_fallback(mock_supabase):
    mock_chain = MagicMock()
    mock_chain.select.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.ilike.return_value = mock_chain
    mock_chain.limit.return_value = mock_chain
    mock_chain.execute.return_value = MockResponse(data=[
        {"id": "wp_1", "title": "Test", "category": "CODE",
         "content": "code stuff", "page_type": "concept", "tags": []},
    ])
    mock_supabase.client.table.return_value = mock_chain

    results = mock_supabase._text_search("code", limit=5)
    assert len(results) == 1
    assert results[0].category == "CODE"


def test_add_source(mock_supabase):
    mock_table = MagicMock()
    mock_table.upsert.return_value.execute.return_value = MockResponse()
    mock_supabase.client.table.return_value = mock_table

    source_id = mock_supabase.add_source(
        title="Karpathy blog",
        source_type="article",
        source_url="https://example.com/blog",
        content_hash="abc123",
    )

    assert source_id.startswith("ws_")
    mock_supabase.client.table.assert_called_with("wiki_sources")


def test_sync_from_local(mock_supabase, tmp_path):
    # Create test wiki pages
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "rule-code.md").write_text(
        "---\ntitle: Graduated Rules: CODE\ncategory: CODE\ntype: concept\n---\nContent here",
        encoding="utf-8",
    )
    (concepts / "rule-tone.md").write_text(
        "---\ntitle: Graduated Rules: TONE\ncategory: TONE\n---\nTone rules",
        encoding="utf-8",
    )

    # Mock: no existing pages (all new)
    mock_chain = MagicMock()
    mock_chain.select.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.maybe_single.return_value = mock_chain
    mock_chain.execute.return_value = MockResponse(data=None)

    mock_upsert = MagicMock()
    mock_upsert.upsert.return_value.execute.return_value = MockResponse()

    def table_router(name):
        if name == "wiki_pages":
            return MagicMock(
                select=lambda *a: mock_chain,
                upsert=lambda row: mock_upsert.upsert(row),
            )
        return MagicMock()

    mock_supabase.client.table = table_router
    # Disable embedding for sync test
    mock_supabase.upsert_page = MagicMock(return_value="wp_test")

    result = mock_supabase.sync_from_local(tmp_path)
    assert result["uploaded"] == 2
    assert result["errors"] == 0


def test_schema_sql_valid():
    """Schema SQL should be well-formed (basic check)."""
    from gradata.cloud.wiki_store import SCHEMA_SQL, SEARCH_RPC_SQL
    assert "create table" in SCHEMA_SQL.lower()
    assert "wiki_pages" in SCHEMA_SQL
    assert "wiki_sources" in SCHEMA_SQL
    assert "vector" in SCHEMA_SQL
    assert "wiki_search" in SEARCH_RPC_SQL
    assert "vector" in SEARCH_RPC_SQL
