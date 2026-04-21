"""Tests for gradata.enhancements.rag.embedders."""

from __future__ import annotations

import math

import pytest

from gradata.enhancements.rag.embedders import (
    Modality,
    MultimodalEmbedder,
    MultimodalInput,
    TextOnlyEmbedder,
    embed_any,
)


class FakeMultimodalEmbedder:
    """Records calls and returns a fixed vector for supported modalities."""

    def __init__(self, supported: tuple[Modality, ...]) -> None:
        self._supported = supported
        self.calls: list[MultimodalInput] = []

    def supports(self, modality: Modality) -> bool:
        return modality in self._supported

    def embed(self, item: MultimodalInput) -> list[float]:
        self.calls.append(item)
        return [1.0, 0.0, 0.0]


class TestMultimodalInputValidation:
    def test_text_requires_text_field(self):
        with pytest.raises(ValueError, match="text modality requires"):
            MultimodalInput(modality="text")

    def test_text_rejects_path(self, tmp_path):
        with pytest.raises(ValueError, match="must not set 'path'"):
            MultimodalInput(modality="text", text="hi", path=tmp_path / "x.png")

    def test_image_requires_path(self):
        with pytest.raises(ValueError, match="image modality requires"):
            MultimodalInput(modality="image")

    def test_image_rejects_text(self, tmp_path):
        with pytest.raises(ValueError, match="must not set 'text'"):
            MultimodalInput(modality="image", text="caption", path=tmp_path / "x.png")

    def test_valid_text(self):
        item = MultimodalInput(modality="text", text="hello")
        assert item.text == "hello"

    def test_valid_image(self, tmp_path):
        p = tmp_path / "x.png"
        item = MultimodalInput(modality="image", path=p)
        assert item.path == p


class TestTextOnlyEmbedder:
    def test_supports_text_only(self):
        e = TextOnlyEmbedder()
        assert e.supports("text")
        assert not e.supports("image")
        assert not e.supports("audio")
        assert not e.supports("video")

    def test_embed_produces_normalised_vector(self):
        e = TextOnlyEmbedder()
        vec = e.embed(MultimodalInput(modality="text", text="hello world"))
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_embed_is_deterministic(self):
        e = TextOnlyEmbedder()
        v1 = e.embed(MultimodalInput(modality="text", text="same"))
        v2 = e.embed(MultimodalInput(modality="text", text="same"))
        assert v1 == v2

    def test_embed_differs_for_different_text(self):
        e = TextOnlyEmbedder()
        v1 = e.embed(MultimodalInput(modality="text", text="alpha"))
        v2 = e.embed(MultimodalInput(modality="text", text="beta"))
        assert v1 != v2

    def test_rejects_non_text(self, tmp_path):
        e = TextOnlyEmbedder()
        with pytest.raises(NotImplementedError):
            e.embed(MultimodalInput(modality="image", path=tmp_path / "x.png"))


class TestEmbedAny:
    def test_text_uses_fallback_when_no_multimodal(self):
        vec = embed_any(MultimodalInput(modality="text", text="hi"))
        assert len(vec) == 64

    def test_multimodal_takes_priority_when_supported(self):
        fake = FakeMultimodalEmbedder(supported=("text", "image"))
        vec = embed_any(MultimodalInput(modality="text", text="hi"), multimodal=fake)
        assert vec == [1.0, 0.0, 0.0]
        assert len(fake.calls) == 1

    def test_falls_back_to_text_when_multimodal_rejects_modality(self):
        fake = FakeMultimodalEmbedder(supported=("image",))
        vec = embed_any(MultimodalInput(modality="text", text="hi"), multimodal=fake)
        assert len(vec) == 64
        assert fake.calls == []

    def test_image_routes_to_multimodal(self, tmp_path):
        fake = FakeMultimodalEmbedder(supported=("image",))
        item = MultimodalInput(modality="image", path=tmp_path / "x.png")
        vec = embed_any(item, multimodal=fake)
        assert vec == [1.0, 0.0, 0.0]

    def test_image_without_multimodal_raises(self, tmp_path):
        item = MultimodalInput(modality="image", path=tmp_path / "x.png")
        with pytest.raises(NotImplementedError, match="No embedder configured"):
            embed_any(item)

    def test_audio_without_multimodal_raises(self, tmp_path):
        item = MultimodalInput(modality="audio", path=tmp_path / "x.wav")
        with pytest.raises(NotImplementedError):
            embed_any(item)

    def test_custom_text_fallback_honored(self):
        class Loud(TextOnlyEmbedder):
            def embed(self, item: MultimodalInput) -> list[float]:
                del item
                return [9.0]

        vec = embed_any(
            MultimodalInput(modality="text", text="hi"),
            text_fallback=Loud(),
        )
        assert vec == [9.0]


class TestProtocolRuntimeCheck:
    def test_textonly_is_embedder(self):
        assert isinstance(TextOnlyEmbedder(), MultimodalEmbedder)

    def test_fake_is_embedder(self):
        assert isinstance(FakeMultimodalEmbedder(("image",)), MultimodalEmbedder)
