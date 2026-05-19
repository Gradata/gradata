"""Contract tests for the host-adapter extraction protocol.

Each host adapter must satisfy these invariants:

INVARIANT 1 — Edit-class payloads MUST capture
    For payloads in the adapter's canonical edit/write shape, the
    adapter's ``extract_correction()`` returns the expected
    ``(draft, final)`` tuple, AND the top-level dispatcher routes to it.

INVARIANT 2 — Non-edit payloads MUST safely return None
    For payloads the host might pipe through stdin that are NOT edits
    (terminal/bash/search/etc), the dispatcher returns None. The owning
    adapter MAY claim the payload via ``detect()`` (since it's structurally
    a payload-from-that-host) but its ``extract_correction()`` MUST return
    None for non-edit tool names. False positives ("captured an ls command
    as a correction") would corrupt the brain.

INVARIANT 3 — Cross-host hygiene
    No adapter falsely claims another host's EDIT-class payload. (For
    non-edit payloads, false-claim is harmless because extract returns
    None — see Invariant 2.)

INVARIANT 4 — Dispatcher robustness
    Garbage input never crashes the dispatcher. A crashing adapter never
    breaks the dispatcher; subsequent adapters get tried.

This file is the structural guard against the May-2026 regression that
shipped an extractor matching only one host's edit shape — silent capture
failure across the other 5 hosts for 43h.
"""

from __future__ import annotations

import pytest

from gradata.hooks.adapters import _base
from gradata.hooks.auto_correct import _extract_correction

# ---- Corpus: per-host EDIT payloads (must capture) ------------------------
#
# Each entry: (payload, expected_correction, tool_output)
# expected_correction is the (draft, final) tuple that MUST come back.

EDIT_PAYLOADS: dict[str, list[tuple[dict, tuple[str, str], dict | None]]] = {
    "claude-code": [
        (
            {"tool_name": "Edit", "input": {"old_string": "Dear Sir", "new_string": "Hey"}},
            ("Dear Sir", "Hey"),
            None,
        ),
        (
            {"tool_name": "MultiEdit", "input": {"old_string": "foo", "new_string": "bar"}},
            ("foo", "bar"),
            None,
        ),
        (
            {"tool_name": "Write", "input": {"content": "new body"}},
            ("old body", "new body"),
            {"old_content": "old body"},
        ),
    ],
    "hermes": [
        (
            {
                "hook_event_name": "post_tool_call",
                "tool_name": "patch",
                "tool_input": {"old_string": "foo", "new_string": "bar"},
                "session_id": "s",
                "cwd": "/tmp",
                "extra": {},
            },
            ("foo", "bar"),
            None,
        ),
        (
            {
                "hook_event_name": "post_tool_call",
                "tool_name": "mcp_Patch",
                "tool_input": {"old_string": "a", "new_string": "b"},
            },
            ("a", "b"),
            None,
        ),
        (
            {
                "hook_event_name": "post_tool_call",
                "tool_name": "write_file",
                "tool_input": {"path": "/tmp/x", "content": "new"},
            },
            ("old", "new"),
            {"old_content": "old"},
        ),
    ],
    "codex": [
        (
            {"tool": "apply_patch", "input": {"old_string": "x", "new_string": "y"}},
            ("x", "y"),
            None,
        ),
    ],
    "gemini": [
        (
            {"tool": "Edit", "args": {"old_string": "draft", "new_string": "final"}},
            ("draft", "final"),
            None,
        ),
    ],
    "opencode": [
        (
            {"event": "preTool", "tool": "edit", "input": {"old_string": "a", "new_string": "b"}},
            ("a", "b"),
            None,
        ),
    ],
    # Cursor: no stdin payloads (MCP-only). Empty corpus is correct.
    "cursor": [],
}


# ---- Corpus: per-host NON-EDIT payloads (dispatcher must return None) -----
#
# These represent payloads the host might pipe through the hook
# subprocess but that don't represent file edits — terminal commands,
# search calls, etc. The dispatcher MUST NOT extract a correction from
# them. The owning adapter MAY ``detect()`` them as belonging to its
# host (that's a structural truth, not a bug); it MUST refuse to
# extract a correction in ``extract_correction()``.

NON_EDIT_PAYLOADS: dict[str, list[dict]] = {
    "claude-code": [
        {"tool_name": "Bash", "input": {"command": "ls"}},
        {"tool_name": "Read", "input": {"file_path": "/etc/hosts"}},
    ],
    "hermes": [
        {
            "hook_event_name": "post_tool_call",
            "tool_name": "terminal",
            "tool_input": {"command": "ls /tmp"},
        },
        {
            "hook_event_name": "pre_tool_call",
            "tool_name": "search_files",
            "tool_input": {"pattern": "TODO"},
        },
    ],
    "codex": [
        {"tool": "shell", "input": {"command": "echo hi"}},
    ],
    "gemini": [
        {"tool": "Search", "args": {"query": "ignored"}},
    ],
    "opencode": [
        {"event": "preTool", "tool": "shell", "input": {"command": "ls"}},
    ],
    "cursor": [],
}


def _edit_params():
    out = []
    for host, entries in EDIT_PAYLOADS.items():
        for i, (payload, expected, tool_output) in enumerate(entries):
            out.append(pytest.param(host, payload, expected, tool_output, id=f"{host}-edit-{i}"))
    return out


def _non_edit_params():
    out = []
    for host, entries in NON_EDIT_PAYLOADS.items():
        for i, payload in enumerate(entries):
            out.append(pytest.param(host, payload, id=f"{host}-nonedit-{i}"))
    return out


# ---- INVARIANT 1: edit payloads capture via owning adapter ----------------


@pytest.mark.parametrize("host,payload,expected,tool_output", _edit_params())
def test_owning_adapter_extracts_edit_payload(host, payload, expected, tool_output):
    """Each adapter's ``extract_correction`` MUST return the expected
    correction tuple for its host's canonical edit payloads."""
    adapter = _base.get_adapter(host)
    assert adapter.extract_correction(payload, tool_output) == expected, (
        f"{host}.extract_correction() failed on its own edit payload: {payload}"
    )


@pytest.mark.parametrize("host,payload,expected,tool_output", _edit_params())
def test_owning_adapter_detects_edit_payload(host, payload, expected, tool_output):
    """detect() must return True for the owning host's edit payloads
    (otherwise the dispatcher's priority loop can't route them)."""
    adapter = _base.get_adapter(host)
    assert adapter.detect(payload) is True, (
        f"{host}.detect() returned False on its own edit payload: {payload}"
    )


@pytest.mark.parametrize("host,payload,expected,tool_output", _edit_params())
def test_dispatcher_routes_edit_payload_correctly(host, payload, expected, tool_output):
    """The top-level dispatcher (``_extract_correction``) MUST return the
    expected correction for every edit payload in the corpus.

    This is the structural anti-regression test for the May-2026 bug.
    """
    assert _extract_correction(payload, tool_output) == expected


# ---- INVARIANT 2: non-edit payloads safely return None --------------------


@pytest.mark.parametrize("host,payload", _non_edit_params())
def test_owning_adapter_refuses_non_edit_payload(host, payload):
    """``extract_correction`` MUST return None for non-edit tool calls
    even when the payload is structurally from this host. Capturing a
    terminal/bash/search call as a correction would corrupt the brain."""
    adapter = _base.get_adapter(host)
    assert adapter.extract_correction(payload) is None, (
        f"{host}.extract_correction() falsely captured a non-edit payload: {payload}"
    )


@pytest.mark.parametrize("host,payload", _non_edit_params())
def test_dispatcher_returns_none_for_non_edit_payload(host, payload):
    """The dispatcher returns None for every non-edit payload (regardless
    of which adapter claims it via ``detect()``)."""
    assert _extract_correction(payload) is None


# ---- INVARIANT 3: cross-host hygiene on edit payloads ---------------------


@pytest.mark.parametrize("host,payload,expected,tool_output", _edit_params())
def test_other_adapters_do_not_falsely_claim_edit_payload(host, payload, expected, tool_output):
    """No adapter EXCEPT the owning one may detect this host's edit
    payload — that would mis-route the dispatcher and either return the
    wrong (draft, final) or None on a real correction."""
    for other_host in _base._DETECT_PRIORITY:
        if other_host == host:
            continue
        other = _base.get_adapter(other_host)
        assert other.detect(payload) is False, (
            f"{other_host}.detect() falsely claimed {host}'s edit payload: {payload}"
        )


# ---- INVARIANT 4: robustness ----------------------------------------------


@pytest.mark.parametrize(
    "junk",
    [
        None,
        "",
        [],
        42,
        {"random": "field"},
        {"tool_name": None},
        {"tool_name": "Edit", "input": "not a dict"},
        {"hook_event_name": "pre_tool_call", "tool_name": "patch", "tool_input": None},
    ],
)
def test_dispatcher_handles_garbage_safely(junk):
    """Any non-canonical input must return None, never crash."""
    assert _extract_correction(junk) is None


def test_dispatcher_survives_crashing_adapter(monkeypatch):
    """If one adapter's ``detect`` raises, the dispatcher must continue
    to the next adapter rather than propagating."""
    from gradata.hooks.adapters import hermes as hermes_adapter

    def boom(payload):
        raise RuntimeError("simulated adapter crash")

    monkeypatch.setattr(hermes_adapter, "detect", boom)

    # Claude-Code shape should still capture via the CC adapter.
    payload = {"tool_name": "Edit", "input": {"old_string": "x", "new_string": "y"}}
    assert _extract_correction(payload) == ("x", "y")
