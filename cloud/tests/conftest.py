"""Shared test fixtures."""

from __future__ import annotations

import os
from typing import Any
from collections import defaultdict

import pytest
from fastapi.testclient import TestClient


# Test-only env vars (placeholder values, not real credentials)
os.environ.setdefault("GRADATA_SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("GRADATA_SUPABASE_ANON_KEY", "TVAL")
os.environ.setdefault("GRADATA_SUPABASE_SERVICE_KEY", "TVAL")
os.environ.setdefault("GRADATA_SUPABASE_JWT_KEY", "test-only-hmac-not-a-real-credential-x")
os.environ.setdefault("GRADATA_ENVIRONMENT", "test")


class MockSupabaseClient:
    """Mock Supabase client for tests."""

    def __init__(self):
        self._responses: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
        self._inserts: list[dict] = []

    def add_response(self, table: str, operation: str, data: list[Any]):
        self._responses[table][operation] = data

    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: dict | None = None,
        in_: dict | None = None,
    ) -> list[dict]:
        rows = self._responses[table].get("select", [])
        if filters:
            rows = [r for r in rows if all(r.get(k) == v for k, v in filters.items())]
        if in_:
            rows = [r for r in rows if all(r.get(k) in vals for k, vals in in_.items())]
        return rows

    async def insert(self, table: str, data: dict | list[dict]) -> list[dict]:
        rows = data if isinstance(data, list) else [data]
        self._inserts.extend(rows)
        return rows

    async def upsert(self, table: str, data: dict | list[dict]) -> list[dict]:
        rows = data if isinstance(data, list) else [data]
        self._inserts.extend(rows)
        return rows

    async def update(self, table: str, data: dict, filters: dict | None = None) -> list[dict]:
        # Match prod wrapper semantics: empty list filter = no-op (returns []
        # rather than patching every row in the table).
        if filters:
            for val in filters.values():
                if isinstance(val, (list, tuple, set)) and not val:
                    return []
        return [data]

    async def delete(self, table: str, filters: dict | None = None) -> list[dict]:
        """Mock delete: returns pre-seeded delete response rows (treat as 'deleted rows')."""
        return list(self._responses[table].get("delete", []))


@pytest.fixture(autouse=True)
def mock_jwks(monkeypatch):
    """Auto-mock JWKS fetch so tests fall back to HS256 verification."""

    async def empty_jwks():
        return {"keys": []}

    try:
        from app import auth

        monkeypatch.setattr(auth, "_get_jwks", empty_jwks)
    except ImportError:
        pass


@pytest.fixture
def mock_supabase(monkeypatch):
    """Provide a mock Supabase client and patch it into app.db."""
    client = MockSupabaseClient()
    monkeypatch.setattr("app.db._client", client)
    return client


@pytest.fixture
def client():
    """FastAPI test client."""
    from app.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Headers with a valid test API key."""
    return {"Authorization": "Bearer gd_TVAL"}
