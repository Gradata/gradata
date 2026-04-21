"""Pluggable embedder layer for RAG evidence.

Text is the default; image / audio / video inputs route to an optional
multimodal embedder supplied by the user. Gradata never hosts the
embedding endpoint — the caller brings their own provider (Gemini,
Voyage-multimodal, local CLIP) and we call it via the Protocol.

See GitHub issue #128.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

Modality = Literal["text", "image", "audio", "video"]


@dataclass(frozen=True)
class MultimodalInput:
    """A single piece of evidence routed to an embedder.

    Exactly one of ``text`` or ``path`` must be set. ``modality`` is
    authoritative for routing; ``path`` suffix is only a hint.
    """

    modality: Modality
    text: str | None = None
    path: Path | None = None

    def __post_init__(self) -> None:
        if self.modality == "text":
            if not self.text:
                raise ValueError("text modality requires a non-empty 'text' field")
            if self.path is not None:
                raise ValueError("text modality must not set 'path'")
        else:
            if self.path is None:
                raise ValueError(f"{self.modality} modality requires 'path'")
            if self.text is not None:
                raise ValueError(f"{self.modality} modality must not set 'text'")


@runtime_checkable
class MultimodalEmbedder(Protocol):
    """User-supplied embedder for non-text modalities.

    Implementations are expected to return L2-normalised vectors so the
    caller can compute cosine similarity as a plain dot product. If a
    given modality isn't supported, raise :class:`NotImplementedError`
    and the caller will fall back.
    """

    def supports(self, modality: Modality) -> bool: ...

    def embed(self, item: MultimodalInput) -> list[float]: ...


class TextOnlyEmbedder:
    """Default embedder: text only, deterministic hash-based vectors.

    Intentionally simple — this is the zero-dependency fallback so RAG
    continues to function when no multimodal provider is configured.
    Production users supply a real text embedder via dependency
    injection; this class exists so the Protocol always has a concrete
    sentinel implementation.
    """

    _DIM = 64

    def supports(self, modality: Modality) -> bool:
        return modality == "text"

    def embed(self, item: MultimodalInput) -> list[float]:
        if item.modality != "text" or item.text is None:
            raise NotImplementedError(
                f"TextOnlyEmbedder cannot embed modality={item.modality!r}",
            )
        return _hash_vector(item.text, self._DIM)


def _hash_vector(text: str, dim: int) -> list[float]:
    """Produce a deterministic L2-normalised vector from text bytes."""
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=dim).digest()
    raw = [(b / 255.0) - 0.5 for b in digest]
    norm = math.sqrt(sum(x * x for x in raw))
    if norm == 0:
        return [0.0] * len(raw)
    return [x / norm for x in raw]


def embed_any(
    item: MultimodalInput,
    *,
    multimodal: MultimodalEmbedder | None = None,
    text_fallback: MultimodalEmbedder | None = None,
) -> list[float]:
    """Route *item* to the appropriate embedder.

    Policy:
        1. If ``multimodal`` is supplied and supports the modality, use it.
        2. Else if the modality is text, use ``text_fallback`` (default:
           :class:`TextOnlyEmbedder`).
        3. Else raise ``NotImplementedError`` — callers decide whether to
           degrade gracefully or surface the gap.
    """
    if multimodal is not None and multimodal.supports(item.modality):
        return multimodal.embed(item)

    if item.modality == "text":
        embedder = text_fallback or TextOnlyEmbedder()
        return embedder.embed(item)

    raise NotImplementedError(
        f"No embedder configured for modality={item.modality!r}. "
        "Supply a MultimodalEmbedder via `multimodal=` to support it.",
    )


__all__ = [
    "Modality",
    "MultimodalEmbedder",
    "MultimodalInput",
    "TextOnlyEmbedder",
    "embed_any",
]
