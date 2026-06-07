from __future__ import annotations

import pytest

from gradata import Brain, GradataAuthError
from gradata.brain import AUTH_ERROR_MESSAGE


def test_brain_constructor_without_api_key_raises_auth_error(tmp_path, monkeypatch):
    brain_dir = tmp_path / "brain"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)

    Brain.init(brain_dir, name="TestBrain", domain="Testing", embedding="local", interactive=False)

    with pytest.raises(GradataAuthError) as exc:
        Brain(brain_dir)

    assert "GRADATA_API_KEY" in str(exc.value)
    assert str(exc.value) == AUTH_ERROR_MESSAGE


def test_brain_constructor_accepts_explicit_api_key(tmp_path, monkeypatch):
    brain_dir = tmp_path / "brain"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    monkeypatch.setenv("GRADATA_DISABLE_WRITE_THROUGH", "1")

    Brain.init(brain_dir, name="TestBrain", domain="Testing", embedding="local", interactive=False)

    brain = Brain(brain_dir, api_key="gd_test")
    try:
        assert brain._api_key == "gd_test"
    finally:
        brain.close()
