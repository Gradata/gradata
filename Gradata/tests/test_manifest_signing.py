"""Tests for HMAC-SHA256 manifest signing and verification."""

import copy

from gradata.security.manifest_signing import sign_manifest, verify_manifest

SAMPLE_MANIFEST = {
    "brain_id": "test-brain-001",
    "version": "0.2.1",
    "rules_count": 42,
    "domains": ["sales", "engineering"],
}

SALT = "a" * 64  # deterministic test salt


class TestSignManifest:
    """sign_manifest() adds a 64-char hex signature."""

    def test_adds_64_char_hex_signature(self):
        signed = sign_manifest(SAMPLE_MANIFEST, SALT)
        assert "signature" in signed
        assert len(signed["signature"]) == 64
        assert all(c in "0123456789abcdef" for c in signed["signature"])

    def test_adds_signed_at(self):
        signed = sign_manifest(SAMPLE_MANIFEST, SALT)
        assert "signed_at" in signed

    def test_does_not_mutate_original(self):
        original = copy.deepcopy(SAMPLE_MANIFEST)
        sign_manifest(SAMPLE_MANIFEST, SALT)
        assert original == SAMPLE_MANIFEST
        assert "signature" not in SAMPLE_MANIFEST


class TestVerifyManifest:
    """verify_manifest() checks HMAC integrity."""

    def test_valid_signature_verifies(self):
        signed = sign_manifest(SAMPLE_MANIFEST, SALT)
        assert verify_manifest(signed, SALT) is True

    def test_tampered_content_fails(self):
        signed = sign_manifest(SAMPLE_MANIFEST, SALT)
        signed["rules_count"] = 999
        assert verify_manifest(signed, SALT) is False

    def test_wrong_salt_fails(self):
        signed = sign_manifest(SAMPLE_MANIFEST, SALT)
        assert verify_manifest(signed, "b" * 64) is False

    def test_missing_signature_returns_false(self):
        assert verify_manifest(SAMPLE_MANIFEST, SALT) is False

    def test_malformed_signature_type_returns_false(self):
        """Non-string signature types should fail closed."""
        for bad_sig in [42, {"key": "val"}, ["sig"], None, True]:
            manifest = dict(SAMPLE_MANIFEST, signature=bad_sig)
            assert verify_manifest(manifest, SALT) is False
