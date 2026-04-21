"""Tests for :mod:`gradata.adapters.mem0`.

All tests use an injected fake client so the suite runs offline.
"""

from __future__ import annotations

from typing import Any

import pytest

from gradata.adapters import Mem0Adapter, MemoryAdapter

# ---------------------------------------------------------------------------
# Fake Mem0 client
# ---------------------------------------------------------------------------


class _FakeMem0Client:
    """Minimal stand-in for ``mem0.MemoryClient``.

    Records every call so tests can assert on payload shape. Returns
    canned responses that mirror the real SDK's dict envelopes.
    """

    def __init__(
        self,
        *,
        add_response: Any = None,
        search_response: Any = None,
        get_all_response: Any = None,
        raise_on: set[str] | None = None,
        accepts_filters: bool = True,
    ) -> None:
        self.add_response = add_response
        self.search_response = search_response
        self.get_all_response = get_all_response
        self._raise_on = raise_on or set()
        self._accepts_filters = accepts_filters
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def add(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append(("add", {"messages": messages, **kwargs}))
        if "add" in self._raise_on:
            raise RuntimeError("boom")
        return self.add_response

    def search(self, query: str, **kwargs: Any) -> Any:
        if not self._accepts_filters and "filters" in kwargs:
            raise TypeError("search() got unexpected keyword 'filters'")
        self.calls.append(("search", {"query": query, **kwargs}))
        if "search" in self._raise_on:
            raise RuntimeError("boom")
        return self.search_response

    def get_all(self, **kwargs: Any) -> Any:
        self.calls.append(("get_all", kwargs))
        if "get_all" in self._raise_on:
            raise RuntimeError("boom")
        return self.get_all_response


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_requires_user_id() -> None:
    with pytest.raises(ValueError, match="user_id"):
        Mem0Adapter(api_key="k", user_id="", client=_FakeMem0Client())


def test_accepts_injected_client_without_api_key() -> None:
    adapter = Mem0Adapter(user_id="oliver", client=_FakeMem0Client())
    assert adapter.user_id == "oliver"


def test_runtime_checkable_protocol() -> None:
    adapter = Mem0Adapter(user_id="oliver", client=_FakeMem0Client())
    assert isinstance(adapter, MemoryAdapter)


# ---------------------------------------------------------------------------
# push_correction
# ---------------------------------------------------------------------------


def test_push_correction_returns_id_from_results_envelope() -> None:
    fake = _FakeMem0Client(add_response={"results": [{"id": "mem-123"}, {"id": "mem-124"}]})
    adapter = Mem0Adapter(user_id="oliver", client=fake)

    memory_id = adapter.push_correction(
        draft="hey there",
        final="Hi Oliver,",
        summary="greeting style",
        tags=["email", "greeting"],
    )

    assert memory_id == "mem-123"
    assert len(fake.calls) == 1
    name, payload = fake.calls[0]
    assert name == "add"

    messages = payload["messages"]
    assert messages == [
        {"role": "assistant", "content": "hey there"},
        {"role": "user", "content": "Hi Oliver,"},
    ]
    assert payload["user_id"] == "oliver"

    meta = payload["metadata"]
    assert meta["source"] == "gradata"
    assert meta["kind"] == "correction"
    assert meta["summary"] == "greeting style"
    assert meta["tags"] == ["email", "greeting"]


@pytest.mark.parametrize(
    "add_response, expected_id",
    [
        ({"id": "mem-flat"}, "mem-flat"),
        ([{"id": "mem-list"}], "mem-list"),
        ("mem-str", "mem-str"),
        ({"no": "id"}, None),
    ],
    ids=["flat_id", "list_response", "string_response", "unknown_shape"],
)
def test_push_correction_handles_response_shapes(
    add_response: Any, expected_id: str | None
) -> None:
    fake = _FakeMem0Client(add_response=add_response)
    adapter = Mem0Adapter(user_id="oliver", client=fake)
    assert adapter.push_correction(draft="a", final="b") == expected_id


def test_push_correction_returns_none_and_logs_on_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = _FakeMem0Client(raise_on={"add"})
    adapter = Mem0Adapter(user_id="oliver", client=fake)

    with caplog.at_level("WARNING", logger="gradata.adapters.mem0"):
        result = adapter.push_correction(draft="a", final="b")

    assert result is None
    assert any("push_correction failed" in r.message for r in caplog.records)


def test_push_correction_merges_extra_metadata() -> None:
    fake = _FakeMem0Client(add_response={"id": "mem-1"})
    adapter = Mem0Adapter(user_id="oliver", client=fake)
    adapter.push_correction(
        draft="a",
        final="b",
        metadata={"session_id": "s42", "lesson_id": "L1"},
    )
    _, payload = fake.calls[0]
    meta = payload["metadata"]
    assert meta["session_id"] == "s42"
    assert meta["lesson_id"] == "L1"
    assert meta["source"] == "gradata"  # base metadata still present


def test_push_correction_caller_metadata_cannot_override_internal_keys() -> None:
    """Reserved internal keys (source, kind) must win over caller metadata.

    Regression guard for CodeRabbit review on PR #79: if caller metadata were
    merged AFTER the internal keys, a malicious or careless caller could
    impersonate gradata-origin records or hide the correction kind.
    """
    fake = _FakeMem0Client(add_response={"id": "mem-1"})
    adapter = Mem0Adapter(user_id="oliver", client=fake)
    adapter.push_correction(
        draft="a",
        final="b",
        summary="legit summary",
        tags=["legit"],
        metadata={
            "source": "evil",
            "kind": "evil",
            "summary": "evil summary",
            "tags": ["evil"],
            "session_id": "s42",  # non-reserved keys should still pass through
        },
    )
    _, payload = fake.calls[0]
    meta = payload["metadata"]
    # Reserved internal keys must be preserved.
    assert meta["source"] == "gradata"
    assert meta["kind"] == "correction"
    assert meta["summary"] == "legit summary"
    assert meta["tags"] == ["legit"]
    # Non-reserved caller keys still flow through.
    assert meta["session_id"] == "s42"


# ---------------------------------------------------------------------------
# pull_memory_for_context
# ---------------------------------------------------------------------------


def test_pull_memory_for_context_normalises_results() -> None:
    fake = _FakeMem0Client(
        search_response={
            "results": [
                {
                    "memory": "user prefers full names",
                    "metadata": {"tags": ["greeting"]},
                    "score": 0.91,
                },
                {
                    "memory": "no em dashes",
                    "metadata": {"tags": ["style"]},
                    "score": 0.77,
                },
            ]
        }
    )
    adapter = Mem0Adapter(user_id="oliver", client=fake)

    hits = adapter.pull_memory_for_context("draft cold email", k=5)

    assert len(hits) == 2
    assert hits[0] == {
        "text": "user prefers full names",
        "metadata": {"tags": ["greeting"]},
        "score": 0.91,
    }
    _, payload = fake.calls[0]
    assert payload["query"] == "draft cold email"
    assert payload["user_id"] == "oliver"
    assert payload["limit"] == 5


def test_pull_memory_for_context_handles_bare_list() -> None:
    fake = _FakeMem0Client(search_response=[{"text": "plain text memory", "score": 0.5}])
    adapter = Mem0Adapter(user_id="oliver", client=fake)
    hits = adapter.pull_memory_for_context("q")
    assert hits == [{"text": "plain text memory", "metadata": {}, "score": 0.5}]


def test_pull_memory_for_context_retries_without_filters_for_old_sdks() -> None:
    fake = _FakeMem0Client(
        search_response={"results": [{"memory": "x"}]},
        accepts_filters=False,
    )
    adapter = Mem0Adapter(user_id="oliver", client=fake)

    hits = adapter.pull_memory_for_context("q", k=3, filters={"tag": "email"})

    assert len(hits) == 1
    # Exactly one successful call: the retry without the filters kwarg.
    # (The TypeError path rejects before appending to calls.)
    assert len(fake.calls) == 1
    _, payload = fake.calls[0]
    assert "filters" not in payload


def test_pull_memory_for_context_returns_empty_on_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = _FakeMem0Client(raise_on={"search"})
    adapter = Mem0Adapter(user_id="oliver", client=fake)

    with caplog.at_level("WARNING", logger="gradata.adapters.mem0"):
        hits = adapter.pull_memory_for_context("q")

    assert hits == []
    assert any("pull_memory_for_context failed" in r.message for r in caplog.records)


def test_pull_memory_for_context_handles_none() -> None:
    fake = _FakeMem0Client(search_response=None)
    adapter = Mem0Adapter(user_id="oliver", client=fake)
    assert adapter.pull_memory_for_context("q") == []


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------


def test_reconcile_produces_diff() -> None:
    fake = _FakeMem0Client(
        get_all_response={
            "results": [
                {"id": "mem-1"},
                {"id": "mem-2"},
                {"id": "mem-3"},
            ]
        }
    )
    adapter = Mem0Adapter(user_id="oliver", client=fake)

    report = adapter.reconcile(gradata_memory_ids=["mem-2", "mem-local-only"])

    assert report["remote_count"] == 3
    assert report["only_local"] == ["mem-local-only"]
    assert report["only_remote"] == ["mem-1", "mem-3"]


def test_reconcile_handles_bare_list() -> None:
    fake = _FakeMem0Client(get_all_response=[{"id": "a"}, {"id": "b"}])
    adapter = Mem0Adapter(user_id="oliver", client=fake)
    report = adapter.reconcile(gradata_memory_ids=[])
    assert report["remote_count"] == 2
    assert report["only_remote"] == ["a", "b"]


def test_reconcile_returns_empty_on_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = _FakeMem0Client(raise_on={"get_all"})
    adapter = Mem0Adapter(user_id="oliver", client=fake)
    with caplog.at_level("WARNING", logger="gradata.adapters.mem0"):
        assert adapter.reconcile() == {}
    assert any("reconcile failed" in r.message for r in caplog.records)
