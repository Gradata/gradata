"""PoC corpus runner for Gradata prompt-injection guards.

Drives every payload in tests/security/fixtures/manifest.json against the two
existing guard layers:

  injection_detector        — regex guard (guardrails.py _RE_INJECTION)
  sanitize_lesson_content   — trust-boundary sanitizer (enhancements/_sanitize.py)

Tests are parametrized by payload ID and assert *expected_outcome*:

  block    → injection_detector must return result="fail"
  sanitize → sanitize_lesson_content must transform the dangerous chars
  pass     → all guards must let the payload through unchanged (benign control)

Payloads with ``detectable_by_current_guards=false`` are marked xfail(strict=False):
they document guard gaps without breaking CI. These gaps are the implementation
targets for _injection_guard.py (GRA-1367 → next engineering task).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gradata.contrib.patterns.guardrails import injection_detector
from gradata.enhancements._sanitize import sanitize_lesson_content

# ---------------------------------------------------------------------------
# Fixtures dir
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"
_MANIFEST = _FIXTURES / "manifest.json"

# Map attack class → sanitize_lesson_content context for "sanitize" payloads.
_CLASS_TO_SANITIZE_CTX: dict[str, str] = {
    "xml_inject": "xml",
    "js_template": "js_template",
}
_DEFAULT_SANITIZE_CTX = "llm_prompt"

# ---------------------------------------------------------------------------
# Parametrize helpers
# ---------------------------------------------------------------------------


def _load_params() -> list[tuple[str, dict[str, Any]]]:
    manifest = json.loads(_MANIFEST.read_text())
    return [(p["id"], p) for p in manifest["payloads"]]


def _pytest_id(val: tuple[str, dict[str, Any]]) -> str:
    pid, meta = val
    return f"{pid}[{meta['expected_outcome']}]"


ALL_PAYLOADS = _load_params()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_payload(meta: dict[str, Any]) -> str:
    return (_FIXTURES / meta["file"]).read_text()


def _is_gap(meta: dict[str, Any]) -> bool:
    return not meta["detectable_by_current_guards"]


def _xfail_if_gap(meta: dict[str, Any]) -> pytest.MarkDecorator | None:
    if _is_gap(meta):
        return pytest.mark.xfail(
            strict=False,
            reason=(
                f"Guard gap: {meta['description']} "
                f"(target surface: {meta['guard_surface']})"
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Block payloads — injection_detector must catch them
# ---------------------------------------------------------------------------


_BLOCK_PAYLOADS = [(pid, m) for pid, m in ALL_PAYLOADS if m["expected_outcome"] == "block"]


@pytest.mark.parametrize("payload_meta", _BLOCK_PAYLOADS, ids=[p for p, _ in _BLOCK_PAYLOADS])
def test_block_payload(payload_meta: tuple[str, dict[str, Any]]) -> None:
    """Block payloads must be caught by injection_detector OR sanitize_lesson_content.

    Many payloads are blocked by the sanitizer (llm_prompt context) rather than the
    regex guard — both are valid catch points.  We try injection_detector first, then
    fall back to sanitize_lesson_content to confirm the payload is transformed.
    """
    pid, meta = payload_meta
    text = _read_payload(meta)

    if _is_gap(meta):
        pytest.xfail(
            f"[gap] {meta['description']} — guard_surface: {meta['guard_surface']}"
        )

    injection_result = injection_detector.check(text)
    if injection_result.result == "fail":
        # Caught by regex guard — done.
        assert injection_result.action_taken == "blocked"
        return

    # Regex guard missed it — check the sanitizer layer.
    sanitized = sanitize_lesson_content(text, "llm_prompt")
    assert sanitized != text, (
        f"[{pid}] Neither injection_detector nor sanitize_lesson_content(llm_prompt) "
        f"blocked/transformed this payload.\n"
        f"Payload: {text[:120]!r}\n"
        f"Guard surface: {meta['guard_surface']}"
    )


# ---------------------------------------------------------------------------
# Sanitize payloads — sanitize_lesson_content must transform dangerous chars
# ---------------------------------------------------------------------------


_SANITIZE_PAYLOADS = [(pid, m) for pid, m in ALL_PAYLOADS if m["expected_outcome"] == "sanitize"]


@pytest.mark.parametrize(
    "payload_meta", _SANITIZE_PAYLOADS, ids=[p for p, _ in _SANITIZE_PAYLOADS]
)
def test_sanitize_payload(payload_meta: tuple[str, dict[str, Any]]) -> None:
    pid, meta = payload_meta
    text = _read_payload(meta)
    ctx = _CLASS_TO_SANITIZE_CTX.get(meta["class"], _DEFAULT_SANITIZE_CTX)

    mark = _xfail_if_gap(meta)
    if mark is not None:
        pytest.xfail(
            f"[gap] {meta['description']} — guard_surface: {meta['guard_surface']}"
        )

    result = sanitize_lesson_content(text, ctx)

    # Sanitization must have changed the text (dangerous chars escaped/stripped).
    assert result != text, (
        f"[{pid}] sanitize_lesson_content({ctx!r}) returned the input unchanged — "
        f"injection payload may have survived.\nPayload: {text[:120]!r}"
    )

    # Context-specific assertions.
    if ctx == "xml":
        assert "<" not in result or "&lt;" in result, (
            f"[{pid}] Raw '<' survived XML sanitization."
        )
        assert ">" not in result or "&gt;" in result, (
            f"[{pid}] Raw '>' survived XML sanitization."
        )
    elif ctx in ("js", "js_template"):
        assert "`" not in result, f"[{pid}] Backtick survived JS template sanitization."


# ---------------------------------------------------------------------------
# Pass payloads (benign controls) — guards must NOT block or alter them
# ---------------------------------------------------------------------------


_PASS_PAYLOADS = [(pid, m) for pid, m in ALL_PAYLOADS if m["expected_outcome"] == "pass"]


@pytest.mark.parametrize("payload_meta", _PASS_PAYLOADS, ids=[p for p, _ in _PASS_PAYLOADS])
def test_benign_control_passes(payload_meta: tuple[str, dict[str, Any]]) -> None:
    pid, meta = payload_meta
    text = _read_payload(meta)

    result = injection_detector.check(text)
    assert result.result == "pass", (
        f"[{pid}] injection_detector false-positived on benign content.\n"
        f"Payload: {text[:120]!r}\nDetails: {result.details}"
    )


# ---------------------------------------------------------------------------
# Corpus integrity: manifest IDs match files on disk
# ---------------------------------------------------------------------------


def test_corpus_manifest_completeness() -> None:
    manifest = json.loads(_MANIFEST.read_text())
    payloads = manifest["payloads"]

    assert len(payloads) >= 20, (
        f"Corpus must have ≥20 payloads, found {len(payloads)}"
    )

    missing: list[str] = []
    for p in payloads:
        fpath = _FIXTURES / p["file"]
        if not fpath.exists():
            missing.append(p["file"])
        elif fpath.stat().st_size == 0:
            missing.append(f"{p['file']} (empty)")

    assert not missing, f"Corpus files referenced in manifest but missing on disk: {missing}"


def test_corpus_required_classes() -> None:
    manifest = json.loads(_MANIFEST.read_text())
    classes_present = {p["class"] for p in manifest["payloads"]}
    required = {
        "direct_override", "role_hijack", "system_leak",
        "xml_inject", "js_template", "marker_inject",
        "encoding_bypass", "benign_control",
    }
    missing = required - classes_present
    assert not missing, f"Required attack classes missing from corpus: {missing}"
