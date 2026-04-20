"""Tests for session-scoped rule cache."""

from gradata.rules.cache import RuleCache


class TestRuleCache:
    def test_starts_dirty(self):
        cache = RuleCache()
        assert cache.is_dirty
        assert cache.get("key") is None

    def test_put_clears_dirty(self):
        cache = RuleCache()
        cache.put("key", ["rule1"])
        assert not cache.is_dirty
        assert cache.get("key") == ["rule1"]

    def test_invalidate_clears_cache(self):
        cache = RuleCache()
        cache.put("key", ["rule1"])
        cache.invalidate()
        assert cache.is_dirty
        assert cache.get("key") is None

    def test_different_keys_independent(self):
        cache = RuleCache()
        cache.put("a", [1])
        cache.put("b", [2])
        assert cache.get("a") == [1]
        assert cache.get("b") == [2]

    def test_make_key_deterministic(self):
        k1 = RuleCache.make_key("email", "sales", "vp")
        k2 = RuleCache.make_key("email", "sales", "vp")
        assert k1 == k2

    def test_make_key_different_inputs(self):
        k1 = RuleCache.make_key("email", "sales", "vp")
        k2 = RuleCache.make_key("code", "eng", "ic")
        assert k1 != k2
