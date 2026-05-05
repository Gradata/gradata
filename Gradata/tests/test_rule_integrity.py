"""Tests for rule_integrity.py — HMAC signing and tamper detection.

Tests cover:
- HMAC signature verifies correctly
- Tampered rule text fails verification
- Missing signature fails closed (returns False, not True)
- No key configured = unsigned mode (pass through)
- generate_key produces valid hex strings
- Canonical payload is deterministic (same inputs = same bytes)
- sign_lesson_file / verify_lesson_file roundtrip
- Confidence clamping before signing
"""

import pytest

import gradata.enhancements.rule_integrity as ri

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_KEY = "deadbeefcafe" * 5  # 60 hex chars, sufficient for testing


@pytest.fixture(autouse=True)
def _reset_module_key():
    """Reset the cached _SECRET_KEY before every test to ensure isolation."""
    original = ri._SECRET_KEY
    ri._SECRET_KEY = None
    yield
    ri._SECRET_KEY = original


@pytest.fixture
def with_key(monkeypatch):
    """Set GRADATA_RULE_SECRET env var and clear the cache."""
    monkeypatch.setenv("GRADATA_RULE_SECRET", TEST_KEY)
    ri._SECRET_KEY = None
    yield TEST_KEY
    ri._SECRET_KEY = None


# ---------------------------------------------------------------------------
# generate_key
# ---------------------------------------------------------------------------


class TestGenerateKey:
    def test_returns_64_char_hex_string(self):
        key = ri.generate_key()
        assert len(key) == 64
        int(key, 16)  # raises ValueError if not valid hex

    def test_two_calls_produce_different_keys(self):
        k1 = ri.generate_key()
        k2 = ri.generate_key()
        assert k1 != k2


# ---------------------------------------------------------------------------
# Unsigned mode (no key configured)
# ---------------------------------------------------------------------------


class TestUnsignedMode:
    def test_sign_rule_returns_empty_string_when_no_key(self):
        sig = ri.sign_rule("some rule text", "DRAFTING", 0.75)
        assert sig == ""

    def test_verify_rule_returns_true_when_no_key(self):
        # No key = unsigned mode, every rule passes
        assert ri.verify_rule("any text", "ANY", 0.5, "") is True
        assert ri.verify_rule("any text", "ANY", 0.5, "not_a_real_sig") is True


# ---------------------------------------------------------------------------
# Signed mode — sign + verify roundtrip
# ---------------------------------------------------------------------------


class TestSignedMode:
    def test_sign_and_verify_roundtrip(self, with_key):
        rule = "Always verify facts before citing numbers"
        category = "ACCURACY"
        confidence = 0.85
        sig = ri.sign_rule(rule, category, confidence)
        assert sig  # non-empty
        assert ri.verify_rule(rule, category, confidence, sig) is True

    def test_tampered_rule_text_fails_verification(self, with_key):
        rule = "Always verify facts before citing numbers"
        category = "ACCURACY"
        confidence = 0.85
        sig = ri.sign_rule(rule, category, confidence)
        tampered = rule + " [TAMPERED]"
        assert ri.verify_rule(tampered, category, confidence, sig) is False

    def test_tampered_category_fails_verification(self, with_key):
        rule = "Keep emails concise"
        sig = ri.sign_rule(rule, "DRAFTING", 0.70)
        # Change category
        assert ri.verify_rule(rule, "PRICING", 0.70, sig) is False

    def test_tampered_confidence_fails_verification(self, with_key):
        rule = "Keep emails concise"
        sig = ri.sign_rule(rule, "DRAFTING", 0.70)
        # Change confidence
        assert ri.verify_rule(rule, "DRAFTING", 0.99, sig) is False

    def test_missing_signature_fails_closed(self, with_key):
        """Key configured but signature empty → reject (fail closed, not open)."""
        assert ri.verify_rule("some rule", "CATEGORY", 0.80, "") is False

    def test_wrong_signature_fails(self, with_key):
        rule = "Never commit .env files"
        sig = ri.sign_rule(rule, "SECURITY", 0.90)
        garbage_sig = "a" * len(sig)
        assert ri.verify_rule(rule, "SECURITY", 0.90, garbage_sig) is False

    def test_confidence_clamped_below_zero_before_signing(self, with_key):
        """Confidence < 0 should be clamped to 0.0 for signing — verify should still match."""
        rule = "test"
        sig_clamped = ri.sign_rule(rule, "TEST", 0.0)  # explicitly 0.0
        sig_neg = ri.sign_rule(rule, "TEST", -0.5)  # should clamp to 0.0
        assert sig_clamped == sig_neg

    def test_confidence_clamped_above_one_before_signing(self, with_key):
        """Confidence > 1 should be clamped to 1.0 for signing."""
        rule = "test"
        sig_one = ri.sign_rule(rule, "TEST", 1.0)
        sig_over = ri.sign_rule(rule, "TEST", 1.5)
        assert sig_one == sig_over


# ---------------------------------------------------------------------------
# _canonical_payload determinism
# ---------------------------------------------------------------------------


class TestCanonicalPayload:
    def test_same_inputs_produce_same_bytes(self):
        p1 = ri._canonical_payload("rule text", "DRAFTING", 0.75)
        p2 = ri._canonical_payload("rule text", "DRAFTING", 0.75)
        assert p1 == p2

    def test_category_normalized_to_uppercase(self):
        p_lower = ri._canonical_payload("rule", "drafting", 0.5)
        p_upper = ri._canonical_payload("rule", "DRAFTING", 0.5)
        assert p_lower == p_upper

    def test_rule_text_stripped(self):
        p_clean = ri._canonical_payload("rule text", "CAT", 0.5)
        p_spaces = ri._canonical_payload("  rule text  ", "CAT", 0.5)
        assert p_clean == p_spaces

    def test_different_inputs_produce_different_bytes(self):
        p1 = ri._canonical_payload("rule A", "DRAFTING", 0.75)
        p2 = ri._canonical_payload("rule B", "DRAFTING", 0.75)
        assert p1 != p2


# ---------------------------------------------------------------------------
# sign_lesson_file / verify_lesson_file roundtrip
# ---------------------------------------------------------------------------


class TestLessonFileSigningRoundtrip:
    LESSONS_CONTENT = """\
[INSTINCT:0.40] DRAFTING: Keep emails concise and peer-to-peer
[PATTERN:0.70] ACCURACY: Always verify numerical claims before sending
[RULE:0.95] PROCESS: Create a script if task has 2+ steps
"""

    def test_sign_lesson_file_returns_empty_when_no_key(self, tmp_path):
        lessons = tmp_path / "lessons.md"
        lessons.write_text(self.LESSONS_CONTENT, encoding="utf-8")
        sigs = ri.sign_lesson_file(lessons)
        assert sigs == {}

    def test_sign_lesson_file_returns_signatures_when_key_set(self, with_key, tmp_path):
        lessons = tmp_path / "lessons.md"
        lessons.write_text(self.LESSONS_CONTENT, encoding="utf-8")
        sigs = ri.sign_lesson_file(lessons)
        assert "DRAFTING" in sigs
        assert "ACCURACY" in sigs
        assert "PROCESS" in sigs

    def test_verify_lesson_file_clean_returns_empty_list(self, with_key, tmp_path):
        lessons = tmp_path / "lessons.md"
        lessons.write_text(self.LESSONS_CONTENT, encoding="utf-8")
        sigs = ri.sign_lesson_file(lessons)
        tampered = ri.verify_lesson_file(lessons, sigs)
        assert tampered == []

    def test_verify_lesson_file_detects_tampered_lesson(self, with_key, tmp_path):
        lessons = tmp_path / "lessons.md"
        lessons.write_text(self.LESSONS_CONTENT, encoding="utf-8")
        sigs = ri.sign_lesson_file(lessons)
        # Tamper with the DRAFTING lesson
        tampered_content = self.LESSONS_CONTENT.replace(
            "Keep emails concise and peer-to-peer",
            "Keep emails concise and peer-to-peer [INJECTED]",
        )
        lessons.write_text(tampered_content, encoding="utf-8")
        tampered_cats = ri.verify_lesson_file(lessons, sigs)
        assert "DRAFTING" in tampered_cats

    def test_sign_lesson_file_nonexistent_path_returns_empty(self, with_key, tmp_path):
        missing = tmp_path / "nonexistent.md"
        sigs = ri.sign_lesson_file(missing)
        assert sigs == {}

    def test_verify_lesson_file_unsigned_mode_returns_empty(self, tmp_path):
        lessons = tmp_path / "lessons.md"
        lessons.write_text(self.LESSONS_CONTENT, encoding="utf-8")
        # No key → unsigned mode
        result = ri.verify_lesson_file(lessons, {"DRAFTING": "fake_sig"})
        assert result == []
