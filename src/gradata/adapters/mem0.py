"""Opt-in Mem0 memory adapter (MemoryAdapter protocol).

Mirrors Gradata corrections to a Mem0 workspace. Install via
``pip install "gradata[adapters-mem0]"``. Never raises on backend failure:
writes return None, reads return []. Host brain stays up even if Mem0 is down.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Mem0Adapter:
    """MemoryAdapter backed by the Mem0 managed service.

    This class wraps the official `mem0ai` Python SDK's `MemoryClient`.
    It is deliberately a thin shim: all Gradata-specific enrichment lives
    in ``push_correction``; ``pull_memory_for_context`` and ``reconcile``
    are mostly passthroughs.

    Args:
        api_key: Mem0 API key. Required unless ``client`` is supplied.
        user_id: Default Mem0 user id to scope all operations to. Required.
        client: Optional pre-constructed Mem0 client. Used for tests and
            for callers who want custom Mem0 config. When supplied,
            ``api_key`` is ignored.

    Raises:
        ValueError: If ``user_id`` is empty.
        ImportError: If ``mem0ai`` is not installed AND no ``client`` is
            supplied.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        user_id: str,
        client: Any | None = None,
    ) -> None:
        if not user_id:
            raise ValueError("Mem0Adapter requires a non-empty user_id")

        self.user_id: str = user_id

        if client is not None:
            self._client = client
            return

        try:
            from mem0 import MemoryClient  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "Mem0Adapter requires the 'mem0ai' package. "
                "Install with: pip install 'gradata[adapters-mem0]'"
            ) from exc

        if not api_key:
            raise ValueError("Mem0Adapter requires an api_key when no client is supplied")
        self._client = MemoryClient(api_key=api_key)

    # ------------------------------------------------------------------
    # MemoryAdapter protocol
    # ------------------------------------------------------------------

    def push_correction(
        self,
        *,
        draft: str,
        final: str,
        summary: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Mirror a Gradata correction to Mem0.

        Builds a messages payload from the draft / final pair and calls
        ``client.add()``. Returns the first memory id Mem0 reports, or
        ``None`` on any failure.
        """
        messages = [
            {"role": "assistant", "content": draft},
            {"role": "user", "content": final},
        ]

        meta: dict[str, Any] = {}
        if metadata:
            meta.update(metadata)
        # Internal keys set AFTER caller metadata so they cannot be overridden.
        meta["source"] = "gradata"
        meta["kind"] = "correction"
        if summary:
            meta["summary"] = summary
        if tags:
            meta["tags"] = list(tags)

        try:
            response = self._client.add(
                messages,
                user_id=self.user_id,
                metadata=meta,
            )
        except Exception as exc:
            logger.warning("Mem0Adapter.push_correction failed: %s", exc)
            return None

        if response is None:
            return None
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            if isinstance(response.get("id"), str):
                return response["id"]
            _results = response.get("results")
            if isinstance(_results, list) and _results:
                _first = _results[0]
                if isinstance(_first, dict) and isinstance(_first.get("id"), str):
                    return _first["id"]
        if isinstance(response, list) and response:
            _first = response[0]
            if isinstance(_first, dict) and isinstance(_first.get("id"), str):
                return _first["id"]
        return None

    def pull_memory_for_context(
        self,
        query: str,
        *,
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search Mem0 for up to ``k`` memories relevant to ``query``.

        Returns a normalised ``list[dict]`` with keys ``text``, ``metadata``,
        ``score``. Returns ``[]`` on failure.
        """
        try:
            raw = self._client.search(
                query,
                user_id=self.user_id,
                limit=k,
                filters=filters,
            )
        except TypeError:
            # Older mem0ai versions don't accept `filters` kwarg.
            try:
                raw = self._client.search(query, user_id=self.user_id, limit=k)
            except Exception as exc:
                logger.warning("Mem0Adapter.pull_memory_for_context failed: %s", exc)
                return []
        except Exception as exc:
            logger.warning("Mem0Adapter.pull_memory_for_context failed: %s", exc)
            return []

        if raw is None:
            return []
        if isinstance(raw, dict):
            _items = raw.get("results")
            if not isinstance(_items, list):
                return []
        elif isinstance(raw, list):
            _items = raw
        else:
            return []
        _out: list[dict[str, Any]] = []
        for _item in _items:
            if not isinstance(_item, dict):
                continue
            _meta = _item.get("metadata") or {}
            _out.append(
                {
                    "text": _item.get("memory") or _item.get("text") or _item.get("content") or "",
                    "metadata": _meta if isinstance(_meta, dict) else {},
                    "score": _item.get("score"),
                }
            )
        return _out

    def reconcile(
        self,
        *,
        gradata_memory_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """List all Mem0 memories for this user and diff against the
        caller-supplied Gradata memory ids.

        Returns:
            ``{"only_local": [...], "only_remote": [...], "remote_count": N}``
            or ``{}`` on failure.
        """
        try:
            raw = self._client.get_all(user_id=self.user_id)
        except Exception as exc:
            logger.warning("Mem0Adapter.reconcile failed: %s", exc)
            return {}

        if raw is None:
            _items: list = []
        elif isinstance(raw, dict):
            _r = raw.get("results")
            _items = _r if isinstance(_r, list) else []
        elif isinstance(raw, list):
            _items = raw
        else:
            _items = []
        remote_set = {
            _item["id"]
            for _item in _items
            if isinstance(_item, dict) and isinstance(_item.get("id"), str)
        }
        local_ids = set(gradata_memory_ids or [])

        return {
            "only_local": sorted(local_ids - remote_set),
            "only_remote": sorted(remote_set - local_ids),
            "remote_count": len(remote_set),
        }
