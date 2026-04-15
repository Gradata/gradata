"""Regression tests for db.SupabaseClient guards against unfiltered writes."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.db import SupabaseClient


class _FakeHTTP:
    """Records HTTP calls so we can assert no request was fired."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def patch(self, path: str, params: dict | None = None, json: Any = None):
        self.calls.append(("PATCH", path, params or {}))
        raise AssertionError("PATCH must not be fired without filters")

    async def delete(self, path: str, params: dict | None = None):
        self.calls.append(("DELETE", path, params or {}))
        raise AssertionError("DELETE must not be fired without filters")

    async def get(self, path: str, params: dict | None = None):  # pragma: no cover
        raise AssertionError("unused")

    async def post(self, path: str, json: Any = None, headers: dict | None = None):  # pragma: no cover
        raise AssertionError("unused")

    async def aclose(self):
        return None


def _make_client() -> tuple[SupabaseClient, _FakeHTTP]:
    client = SupabaseClient.__new__(SupabaseClient)
    client.base_url = "http://unused"
    client._headers = {}
    fake = _FakeHTTP()
    client._http = fake
    return client, fake


@pytest.mark.asyncio
async def test_update_refuses_when_filters_is_none():
    """update(filters=None) must raise and NOT fire a PATCH."""
    client, fake = _make_client()
    with pytest.raises(HTTPException) as exc:
        await client.update("users", data={"x": 1}, filters=None)
    assert exc.value.status_code == 500
    assert fake.calls == []


@pytest.mark.asyncio
async def test_update_refuses_when_filters_is_empty_dict():
    """update(filters={}) must raise and NOT fire a PATCH."""
    client, fake = _make_client()
    with pytest.raises(HTTPException) as exc:
        await client.update("users", data={"x": 1}, filters={})
    assert exc.value.status_code == 500
    assert fake.calls == []


@pytest.mark.asyncio
async def test_update_returns_empty_for_empty_list_filter():
    """update(filters={id: []}) is a no-op returning [] without firing PATCH."""
    client, fake = _make_client()
    result = await client.update("users", data={"x": 1}, filters={"id": []})
    assert result == []
    assert fake.calls == []


@pytest.mark.asyncio
async def test_delete_refuses_when_filters_is_none():
    """delete(filters=None) must raise and NOT fire a DELETE."""
    client, fake = _make_client()
    with pytest.raises(HTTPException) as exc:
        await client.delete("users", filters=None)
    assert exc.value.status_code == 500
    assert fake.calls == []


@pytest.mark.asyncio
async def test_delete_refuses_when_filters_is_empty_dict():
    """delete(filters={}) must raise and NOT fire a DELETE."""
    client, fake = _make_client()
    with pytest.raises(HTTPException) as exc:
        await client.delete("users", filters={})
    assert exc.value.status_code == 500
    assert fake.calls == []
