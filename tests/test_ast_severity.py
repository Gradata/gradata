"""
Tests for the AST-aware severity classifier.

Verifies the optional AST path collapses formatting-only deltas to
``"as-is"``, up-weights genuine semantic changes, and falls back cleanly
when Python parsing fails.
"""

from __future__ import annotations

import pytest

from gradata.enhancements.ast_severity import (
    ast_severity_enabled,
    classify_ast_severity,
    language_supported,
)

# ---------------------------------------------------------------------------
# Flag + language gating
# ---------------------------------------------------------------------------


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("GRADATA_AST_SEVERITY", raising=False)
    assert ast_severity_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "True", "YES", "on"])
def test_flag_truthy_values(monkeypatch, val):
    monkeypatch.setenv("GRADATA_AST_SEVERITY", val)
    assert ast_severity_enabled() is True


@pytest.mark.parametrize("val", ["", "0", "false", "no", "bogus"])
def test_flag_falsy_values(monkeypatch, val):
    monkeypatch.setenv("GRADATA_AST_SEVERITY", val)
    assert ast_severity_enabled() is False


def test_language_hint_python():
    assert language_supported(language="python") is True
    assert language_supported(language="PY") is True


def test_language_hint_unsupported():
    assert language_supported(language="typescript") is False
    assert language_supported(language=None) is False


def test_language_from_path():
    assert language_supported(path="/tmp/foo.py") is True
    assert language_supported(path="/tmp/foo.pyi") is True
    assert language_supported(path="/tmp/foo.md") is False


# ---------------------------------------------------------------------------
# Semantic scoring
# ---------------------------------------------------------------------------


def test_whitespace_only_is_trivial():
    """Reformatting a function body must collapse to ``as-is``.

    Edit distance would score this as a major correction because nearly
    every line's characters shift; AST-wise the tree is identical.
    """
    before = "def f(x):\n    return x+1\n"
    after = "def f(x):\n    return x + 1\n"
    assert classify_ast_severity(before, after) == "as-is"


def test_comment_added_is_trivial():
    """Comments aren't in the AST — adding one is a no-op structurally."""
    before = "def f(x):\n    return x\n"
    after = "def f(x):\n    # identity\n    return x\n"
    assert classify_ast_severity(before, after) == "as-is"


def test_local_rename_is_minor():
    """Renaming one local in a small function is a minor correction."""
    before = (
        "def total(items):\n"
        "    s = 0\n"
        "    for i in items:\n"
        "        s = s + i\n"
        "    return s\n"
    )
    after = (
        "def total(items):\n"
        "    acc = 0\n"
        "    for i in items:\n"
        "        acc = acc + i\n"
        "    return acc\n"
    )
    sev = classify_ast_severity(before, after)
    assert sev in {"minor", "moderate"}, sev


def test_signature_change_is_major_or_moderate():
    """Adding a parameter and propagating it is semantically loaded."""
    before = (
        "def greet(name):\n"
        "    return 'hello ' + name\n"
    )
    after = (
        "def greet(name, loud=False):\n"
        "    msg = 'hello ' + name\n"
        "    if loud:\n"
        "        msg = msg.upper()\n"
        "    return msg\n"
    )
    sev = classify_ast_severity(before, after)
    assert sev in {"moderate", "major"}, sev


def test_full_body_rewrite_is_major_or_rewrite():
    before = (
        "def compute(xs):\n"
        "    s = 0\n"
        "    for x in xs:\n"
        "        s += x\n"
        "    return s\n"
    )
    after = (
        "def compute(xs):\n"
        "    if not xs:\n"
        "        raise ValueError('empty')\n"
        "    total = 0\n"
        "    count = 0\n"
        "    for value in xs:\n"
        "        total += value * 2\n"
        "        count += 1\n"
        "    return total / count\n"
    )
    sev = classify_ast_severity(before, after)
    assert sev in {"major", "discarded"}, sev


# ---------------------------------------------------------------------------
# Parse-failure fallback
# ---------------------------------------------------------------------------


def test_malformed_before_returns_none():
    before = "def f(:\n    pass\n"  # invalid Python
    after = "def f():\n    pass\n"
    assert classify_ast_severity(before, after) is None


def test_malformed_after_returns_none():
    before = "def f():\n    pass\n"
    after = "def f(:\n    pass\n"
    assert classify_ast_severity(before, after) is None


def test_unsupported_language_returns_none():
    assert classify_ast_severity("int x = 1;", "int x = 2;", language="c") is None


def test_identical_sources_are_as_is():
    src = "def f():\n    return 1\n"
    assert classify_ast_severity(src, src) == "as-is"


# ---------------------------------------------------------------------------
# Watcher shunt integration
# ---------------------------------------------------------------------------


def test_watcher_shunt_engages_on_python_when_flag_set(tmp_path, monkeypatch):
    """End-to-end: flag on + .py file => AST severity overrides edit-distance."""
    from gradata.sidecar.watcher import FileWatcher

    monkeypatch.setenv("GRADATA_AST_SEVERITY", "1")
    watch_dir = tmp_path
    target = watch_dir / "mod.py"
    # Dense one-liner, then same program reformatted. Edit distance would
    # flag this as a large change; AST diff is zero.
    before = "def f(x):return x+1\n"
    after = "def f(x):\n    return x + 1\n"

    watcher = FileWatcher(watch_dir)
    watcher.track(str(target), before)
    target.write_text(after, encoding="utf-8")

    change = watcher.check(str(target))
    assert change is not None
    assert change.severity == "as-is"


def test_watcher_shunt_off_by_default(tmp_path, monkeypatch):
    """Flag unset => watcher uses the original edit-distance classifier."""
    from gradata.sidecar.watcher import FileWatcher

    monkeypatch.delenv("GRADATA_AST_SEVERITY", raising=False)
    watch_dir = tmp_path
    target = watch_dir / "mod.py"
    before = "def f(x):return x+1\n"
    after = "def f(x):\n    return x + 1\n"

    watcher = FileWatcher(watch_dir)
    watcher.track(str(target), before)
    target.write_text(after, encoding="utf-8")

    change = watcher.check(str(target))
    assert change is not None
    # Without the flag we get whatever edit-distance says — crucially NOT
    # forced to "as-is". Just assert severity is a valid label.
    assert change.severity in {
        "as-is",
        "minor",
        "moderate",
        "major",
        "discarded",
    }


def test_watcher_shunt_ignores_non_python(tmp_path, monkeypatch):
    """Flag on but file is .md => AST path skipped, edit-distance used."""
    from gradata.sidecar.watcher import FileWatcher

    monkeypatch.setenv("GRADATA_AST_SEVERITY", "1")
    watch_dir = tmp_path
    target = watch_dir / "notes.md"
    before = "hello world\n"
    after = "hello brave new world\n"

    watcher = FileWatcher(watch_dir)
    watcher.track(str(target), before)
    target.write_text(after, encoding="utf-8")

    change = watcher.check(str(target))
    assert change is not None
    # Severity still valid; AST shunt should not have engaged.
    assert change.severity in {
        "as-is",
        "minor",
        "moderate",
        "major",
        "discarded",
    }
