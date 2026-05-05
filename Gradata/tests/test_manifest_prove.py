"""Tests for prove() integration in brain manifest."""

from unittest.mock import patch

from gradata.brain import Brain


def test_manifest_includes_proof(tmp_path):
    """brain.manifest() should include a proof section."""
    brain = Brain(str(tmp_path))
    manifest = brain.manifest()
    assert "proof" in manifest
    assert "proven" in manifest["proof"]
    assert "confidence_level" in manifest["proof"]
    assert "summary" in manifest["proof"]


def test_manifest_proof_matches_prove(tmp_path):
    """Manifest proof should match standalone prove() output."""
    brain = Brain(str(tmp_path))
    manifest = brain.manifest()
    standalone = brain.prove()
    assert manifest["proof"]["proven"] == standalone["proven"]
    assert manifest["proof"]["confidence_level"] == standalone["confidence_level"]


def test_manifest_proof_survives_prove_failure(tmp_path):
    """If prove() raises, manifest still includes a fallback proof dict."""
    brain = Brain(str(tmp_path))
    with patch.object(brain, "prove", side_effect=RuntimeError("boom")):
        manifest = brain.manifest()
    assert manifest["proof"]["proven"] is False
    assert manifest["proof"]["confidence_level"] == "error"
    assert "failed" in manifest["proof"]["summary"].lower()


def test_manifest_proof_written_to_disk(tmp_path):
    """brain.manifest.json on disk should contain the proof key."""
    import json

    brain = Brain(str(tmp_path))
    brain.manifest()
    manifest_path = tmp_path / "brain.manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "proof" in data
    assert isinstance(data["proof"]["proven"], bool)
