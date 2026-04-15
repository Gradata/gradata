"""Tests for GET /public/proof — ablation-backed quality proof endpoint."""
from __future__ import annotations

import json
from pathlib import Path

import pytest  # noqa: F401 — fixture tests use client + monkeypatch


PROOF_PAYLOAD = {
    "available": True,
    "source": "gradata-ablation-v2-2026-04-14",
    "subjects": ["sonnet", "deepseek", "qwen14b"],
    "judge": "claude-haiku-4-5-20251001",
    "trials": 432,
    "dimensions": [
        {
            "dimension": "correctness",
            "baseline_mean": 0.72,
            "with_rules_mean": 0.80,
            "with_full_mean": 0.84,
            "best_mean": 0.84,
            "ci_low": 0.79,
            "ci_high": 0.89,
            "delta_pp": 12.0,
            "n_base": 144,
            "n_with": 144,
        },
    ],
    "per_model": [],
    "updated_at": "2026-04-14T03:00:00Z",
}


def test_proof_returns_unavailable_when_file_missing(client, monkeypatch, tmp_path):
    """No results file → honest empty state (not 500, not fabricated numbers)."""
    from app.routes import proof as proof_module
    monkeypatch.setattr(proof_module, "_PROOF_PATH", tmp_path / "missing.json")
    resp = client.get("/api/v1/public/proof")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["source"] is None


def test_proof_returns_payload_when_file_present(client, monkeypatch, tmp_path):
    """Valid JSON → endpoint serves it verbatim (plus `available: True`)."""
    f = tmp_path / "proof.json"
    f.write_text(json.dumps(PROOF_PAYLOAD), encoding="utf-8")
    from app.routes import proof as proof_module
    monkeypatch.setattr(proof_module, "_PROOF_PATH", f)
    resp = client.get("/api/v1/public/proof")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["source"] == "gradata-ablation-v2-2026-04-14"
    assert data["trials"] == 432
    assert len(data["dimensions"]) == 1
    assert data["dimensions"][0]["dimension"] == "correctness"


def test_proof_returns_unavailable_on_corrupt_file(client, monkeypatch, tmp_path):
    """Malformed JSON → graceful `unavailable`, no 500."""
    f = tmp_path / "corrupt.json"
    f.write_text("{not json", encoding="utf-8")
    from app.routes import proof as proof_module
    monkeypatch.setattr(proof_module, "_PROOF_PATH", f)
    resp = client.get("/api/v1/public/proof")
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_proof_returns_unavailable_on_wrong_json_shape(client, monkeypatch, tmp_path):
    """Valid JSON but wrong top-level shape (list, string, number) → graceful unavailable."""
    f = tmp_path / "wrong_shape.json"
    f.write_text("[]", encoding="utf-8")  # valid JSON, wrong shape (expected dict)
    from app.routes import proof as proof_module
    monkeypatch.setattr(proof_module, "_PROOF_PATH", f)
    resp = client.get("/api/v1/public/proof")
    assert resp.status_code == 200
    assert resp.json()["available"] is False


def test_proof_is_public_unauthenticated(client, monkeypatch, tmp_path):
    """No auth header required — this is a marketing surface."""
    from app.routes import proof as proof_module
    monkeypatch.setattr(proof_module, "_PROOF_PATH", tmp_path / "missing.json")
    resp = client.get("/api/v1/public/proof")  # no auth_headers fixture used
    assert resp.status_code == 200


def test_export_script_handles_empty_run_dir(tmp_path):
    """Invoking export with no judgments should yield unavailable, not crash."""
    # Manually invoke the builder
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "export_ab_proof",
        Path(__file__).resolve().parents[1] / "scripts" / "export_ab_proof.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    judgments = module.load_judgments(tmp_path)
    assert judgments == {}
