"""Tests for behavioral instruction cache."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from gradata.enhancements.instruction_cache import InstructionCache


def test_cache_miss_returns_none():
    with tempfile.TemporaryDirectory() as d:
        cache = InstructionCache(Path(d) / "cache.json")
        assert cache.get("nonexistent_key") is None


def test_put_and_get():
    with tempfile.TemporaryDirectory() as d:
        cache = InstructionCache(Path(d) / "cache.json")
        cache.put("key1", "Use getattr() for safe attribute access")
        assert cache.get("key1") == "Use getattr() for safe attribute access"


def test_cache_persists_to_disk():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "cache.json"
        cache1 = InstructionCache(path)
        cache1.put("key1", "Always validate input at boundaries")

        cache2 = InstructionCache(path)
        assert cache2.get("key1") == "Always validate input at boundaries"


def test_cache_key_generation():
    assert InstructionCache.make_key("CODE", ["getattr"], []) != ""
    assert InstructionCache.make_key("CODE", ["getattr"], []) == InstructionCache.make_key("CODE", ["getattr"], [])
    assert InstructionCache.make_key("CODE", ["getattr"], []) != InstructionCache.make_key("TONE", ["getattr"], [])


def test_cache_handles_corrupt_file():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "cache.json"
        path.write_text("not valid json", encoding="utf-8")
        cache = InstructionCache(path)
        assert cache.get("anything") is None
        cache.put("key1", "test")
        assert cache.get("key1") == "test"
