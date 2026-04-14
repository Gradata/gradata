"""Supabase client wrapper using httpx for async Postgres access."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import get_settings

_log = logging.getLogger(__name__)
_client: Any = None  # Replaced by mock in tests


def _raise_db_error(op: str, table: str, resp: httpx.Response) -> None:
    """Log full Supabase error detail, raise a generic HTTP 500 to the caller.

    Prevents internal PostgREST error messages, constraint names, and row
    counts from leaking to user-facing responses.
    """
    try:
        detail = resp.json()
    except ValueError:
        detail = resp.text
    _log.error("Supabase %s %s failed (%d): %s", op, table, resp.status_code, detail)
    # PostgREST auth errors (401) should pass through; they indicate bad token.
    status = 401 if resp.status_code == 401 else 500
    raise HTTPException(status_code=status, detail="Database error")


class SupabaseClient:
    """Thin async wrapper around Supabase REST API (PostgREST)."""

    def __init__(self, url: str, service_key: str):
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=10.0,
        )

    async def select(
        self, table: str, columns: str = "*", filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        """SELECT rows from a table with optional eq filters."""
        params: dict[str, str] = {"select": columns}
        if filters:
            for key, val in filters.items():
                params[key] = f"eq.{val}"
        resp = await self._http.get(f"/{table}", params=params)
        if resp.is_error:
            _raise_db_error("select", table, resp)
        return resp.json()

    async def insert(self, table: str, data: dict | list[dict]) -> list[dict]:
        """INSERT rows into a table."""
        resp = await self._http.post(f"/{table}", json=data)
        if resp.is_error:
            _raise_db_error("insert", table, resp)
        return resp.json()

    async def upsert(self, table: str, data: dict | list[dict]) -> list[dict]:
        """UPSERT rows (INSERT ... ON CONFLICT DO UPDATE)."""
        headers = {**self._headers, "Prefer": "return=representation,resolution=merge-duplicates"}
        resp = await self._http.post(f"/{table}", json=data, headers=headers)
        if resp.is_error:
            _raise_db_error("upsert", table, resp)
        return resp.json()

    async def update(
        self, table: str, data: dict[str, Any], filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        """UPDATE rows matching eq filters."""
        params: dict[str, str] = {}
        if filters:
            for key, val in filters.items():
                params[key] = f"eq.{val}"
        resp = await self._http.patch(f"/{table}", params=params, json=data)
        if resp.is_error:
            _raise_db_error("update", table, resp)
        return resp.json()

    async def delete(
        self, table: str, filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        """DELETE rows matching eq filters. Returns deleted rows when PostgREST sends them back."""
        params: dict[str, str] = {}
        if filters:
            for key, val in filters.items():
                params[key] = f"eq.{val}"
        resp = await self._http.delete(f"/{table}", params=params)
        if resp.is_error:
            _raise_db_error("delete", table, resp)
        try:
            return resp.json()
        except ValueError:
            return []

    async def close(self):
        await self._http.aclose()


def get_db() -> SupabaseClient | Any:
    """Get or create the Supabase client singleton."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = SupabaseClient(settings.supabase_url, settings.supabase_service_key)
    return _client
