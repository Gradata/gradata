"""Tests for per-brain salt — non-deterministic graduation thresholds."""


class TestGenerateBrainSalt:
    """generate_brain_salt() returns a 32-byte random hex string."""

    def test_returns_64_char_hex(self):
        from gradata.security.brain_salt import generate_brain_salt

        salt = generate_brain_salt()
        assert len(salt) == 64
        assert all(c in "0123456789abcdef" for c in salt)

    def test_100_salts_unique(self):
        from gradata.security.brain_salt import generate_brain_salt

        salts = {generate_brain_salt() for _ in range(100)}
        assert len(salts) == 100


class TestLoadOrCreateSalt:
    """load_or_create_salt() persists and reloads .brain_salt."""

    def test_creates_file(self, tmp_path):
        from gradata.security.brain_salt import load_or_create_salt

        salt = load_or_create_salt(tmp_path)
        salt_file = tmp_path / ".brain_salt"
        assert salt_file.exists()
        assert len(salt) == 64

    def test_idempotent(self, tmp_path):
        from gradata.security.brain_salt import load_or_create_salt

        salt1 = load_or_create_salt(tmp_path)
        salt2 = load_or_create_salt(tmp_path)
        assert salt1 == salt2

    def test_reads_existing_file(self, tmp_path):
        salt_file = tmp_path / ".brain_salt"
        salt_file.write_text("aa" * 32)
        from gradata.security.brain_salt import load_or_create_salt

        assert load_or_create_salt(tmp_path) == "aa" * 32

    def test_creates_missing_parent_dir(self, tmp_path):
        """load_or_create_salt should create missing parent directories."""
        from gradata.security.brain_salt import load_or_create_salt

        nested = tmp_path / "missing_dir" / "deep"
        salt = load_or_create_salt(nested)
        assert len(salt) == 64
        assert (nested / ".brain_salt").exists()

    def test_handles_partial_salt_file(self, tmp_path):
        """Truncated .brain_salt should be detected and regenerated."""
        from gradata.security.brain_salt import load_or_create_salt

        salt_file = tmp_path / ".brain_salt"
        salt_file.write_text("abcd1234")  # Only 8 chars, not 64
        salt = load_or_create_salt(tmp_path)
        assert len(salt) == 64
        assert salt != "abcd1234"


class TestSaltThreshold:
    """salt_threshold() perturbs base within +/-5%."""

    def test_within_bounds(self):
        from gradata.security.brain_salt import generate_brain_salt, salt_threshold

        salt = generate_brain_salt()
        for base in [0.60, 0.90]:
            result = salt_threshold(base, salt, "PATTERN")
            lo = base * 0.95
            hi = base * 1.05
            assert lo <= result <= hi, f"{result} not in [{lo}, {hi}]"

    def test_deterministic_same_salt_and_tier(self):
        from gradata.security.brain_salt import generate_brain_salt, salt_threshold

        salt = generate_brain_salt()
        r1 = salt_threshold(0.60, salt, "PATTERN")
        r2 = salt_threshold(0.60, salt, "PATTERN")
        assert r1 == r2

    def test_different_salts_differ(self):
        from gradata.security.brain_salt import salt_threshold

        # Use known distinct salts
        s1 = "aa" * 32
        s2 = "bb" * 32
        r1 = salt_threshold(0.60, s1, "PATTERN")
        r2 = salt_threshold(0.60, s2, "PATTERN")
        assert r1 != r2

    def test_different_tiers_differ(self):
        from gradata.security.brain_salt import generate_brain_salt, salt_threshold

        salt = generate_brain_salt()
        r_pattern = salt_threshold(0.60, salt, "PATTERN")
        r_rule = salt_threshold(0.90, salt, "RULE")
        # Different base AND tier name -> almost certainly different
        assert r_pattern != r_rule

    def test_same_salt_different_tier_names_differ(self):
        """Same salt + same base but different tier names produce different jitter."""
        from gradata.security.brain_salt import salt_threshold

        salt = "cc" * 32
        r1 = salt_threshold(0.60, salt, "PATTERN")
        r2 = salt_threshold(0.60, salt, "RULE")
        assert r1 != r2

    def test_many_salts_distribution(self):
        """Over 50 salts, results should spread across the range, not cluster."""
        from gradata.security.brain_salt import generate_brain_salt, salt_threshold

        base = 0.60
        results = [salt_threshold(base, generate_brain_salt(), "PATTERN") for _ in range(50)]
        lo = base * 0.95
        hi = base * 1.05
        for r in results:
            assert lo <= r <= hi
        # At least 5 distinct values out of 50
        assert len(set(results)) >= 5
