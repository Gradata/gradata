"""Tests for correction provenance authentication (HMAC-SHA256)."""

from gradata.security.correction_provenance import (
    create_provenance_record,
    verify_provenance,
)


class TestCreateProvenance:
    def test_returns_dict_with_required_fields(self):
        record = create_provenance_record(
            user_id="oliver",
            correction_hash="abc123",
            session=5,
            salt="test-salt",
        )
        assert isinstance(record, dict)
        assert record["user_id"] == "oliver"
        assert record["session"] == 5
        assert isinstance(record["hmac"], str)
        assert len(record["hmac"]) == 64  # SHA-256 hex digest

    def test_hmac_is_deterministic_for_same_timestamp(self):
        """Same inputs + same timestamp = same HMAC."""
        r1 = create_provenance_record(
            user_id="u",
            correction_hash="h",
            session=1,
            salt="s",
        )
        # Manually rebuild to verify
        import hashlib
        import hmac

        msg = f"u|h|1|{r1['timestamp']}"
        expected = hmac.new(b"s", msg.encode(), hashlib.sha256).hexdigest()
        assert r1["hmac"] == expected


class TestVerifyProvenance:
    def test_valid_record(self):
        salt = "my-brain-salt"
        record = create_provenance_record(
            user_id="oliver",
            correction_hash="deadbeef",
            session=10,
            salt=salt,
        )
        assert verify_provenance(record, salt) is True

    def test_tampered_user_id(self):
        salt = "salt"
        record = create_provenance_record(
            user_id="oliver",
            correction_hash="abc",
            session=1,
            salt=salt,
        )
        record["user_id"] = "attacker"
        assert verify_provenance(record, salt) is False

    def test_tampered_correction_hash(self):
        salt = "salt"
        record = create_provenance_record(
            user_id="oliver",
            correction_hash="abc",
            session=1,
            salt=salt,
        )
        record["correction_hash"] = "tampered"
        assert verify_provenance(record, salt) is False

    def test_tampered_session(self):
        salt = "salt"
        record = create_provenance_record(
            user_id="oliver",
            correction_hash="abc",
            session=1,
            salt=salt,
        )
        record["session"] = 999
        assert verify_provenance(record, salt) is False

    def test_wrong_salt(self):
        record = create_provenance_record(
            user_id="oliver",
            correction_hash="abc",
            session=1,
            salt="correct-salt",
        )
        assert verify_provenance(record, "wrong-salt") is False

    def test_missing_fields(self):
        assert verify_provenance({}, "salt") is False
        assert verify_provenance({"user_id": "x"}, "salt") is False
