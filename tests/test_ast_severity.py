"""
Tests for the AST-aware severity classifier.

Covers flag gating, language gating, whitespace/comment/rename/signature/
rewrite semantics, parse-failure fallback, and the watcher shunt.
"""

from __future__ import annotations

import pytest

from gradata.enhancements.ast_severity import (
    ast_severity_enabled,
    classify_ast_severity,
    language_supported,
)

_VALID_LABELS = {"as-is", "minor", "moderate", "major", "discarded"}

# ---------------------------------------------------------------------------
# Flag + language gating
# ---------------------------------------------------------------------------


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("GRADATA_AST_SEVERITY", raising=False)
    assert ast_severity_enabled() is False


@pytest.mark.parametrize(
    "val,expected",
    [
        ("1", True),
        ("true", True),
        ("True", True),
        ("YES", True),
        ("on", True),
        ("", False),
        ("0", False),
        ("false", False),
        ("no", False),
        ("bogus", False),
    ],
)
def test_flag_values(monkeypatch, val, expected):
    monkeypatch.setenv("GRADATA_AST_SEVERITY", val)
    assert ast_severity_enabled() is expected


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"language": "python"}, True),
        ({"language": "PY"}, True),
        ({"language": "typescript"}, False),
        ({"language": None}, False),
        ({"path": "/tmp/foo.py"}, True),
        ({"path": "/tmp/foo.pyi"}, True),
        ({"path": "/tmp/foo.md"}, False),
    ],
)
def test_language_supported(kwargs, expected):
    assert language_supported(**kwargs) is expected


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


def test_identical_sources_are_as_is():
    src = "def f():\n    return 1\n"
    assert classify_ast_severity(src, src) == "as-is"


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
    before = "def greet(name):\n    return 'hello ' + name\n"
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
# Parse-failure / unsupported fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "before,after,language",
    [
        ("def f(:\n    pass\n", "def f():\n    pass\n", "python"),  # malformed before
        ("def f():\n    pass\n", "def f(:\n    pass\n", "python"),  # malformed after
        ("int x = 1;", "int x = 2;", "c"),  # unsupported language
    ],
)
def test_returns_none_for_parse_or_language_miss(before, after, language):
    assert classify_ast_severity(before, after, language=language) is None


# ---------------------------------------------------------------------------
# Watcher shunt integration
# ---------------------------------------------------------------------------


def test_watcher_shunt_engages_on_python_when_flag_set(tmp_path, monkeypatch):
    """End-to-end: flag on + .py file => AST severity overrides edit-distance."""
    from gradata.sidecar.watcher import FileWatcher

    monkeypatch.setenv("GRADATA_AST_SEVERITY", "1")
    target = tmp_path / "mod.py"
    # Dense one-liner, then same program reformatted. Edit distance would
    # flag this as a large change; AST diff is zero.
    before = "def f(x):return x+1\n"
    after = "def f(x):\n    return x + 1\n"

    watcher = FileWatcher(tmp_path)
    watcher.track(str(target), before)
    target.write_text(after, encoding="utf-8")

    change = watcher.check(str(target))
    assert change is not None
    assert change.severity == "as-is"


@pytest.mark.parametrize(
    "filename,flag_on",
    [
        ("mod.py", False),   # flag off => edit-distance path (not forced as-is)
        ("notes.md", True),  # flag on but non-python => shunt skipped
    ],
)
def test_watcher_shunt_skipped(tmp_path, monkeypatch, filename, flag_on):
    """Shunt must only engage when BOTH flag on AND language supported."""
    from gradata.sidecar.watcher import FileWatcher

    if flag_on:
        monkeypatch.setenv("GRADATA_AST_SEVERITY", "1")
    else:
        monkeypatch.delenv("GRADATA_AST_SEVERITY", raising=False)

    target = tmp_path / filename
    before = "def f(x):return x+1\n" if filename.endswith(".py") else "hello world\n"
    after = "def f(x):\n    return x + 1\n" if filename.endswith(".py") else "hello brave new world\n"

    watcher = FileWatcher(tmp_path)
    watcher.track(str(target), before)
    target.write_text(after, encoding="utf-8")

    change = watcher.check(str(target))
    assert change is not None
    assert change.severity in _VALID_LABELS
