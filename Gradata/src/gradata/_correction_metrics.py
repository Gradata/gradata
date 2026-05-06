"""Shared correction metric helpers."""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def correction_rate(
    corrections: int | float,
    outputs: int | float,
    *,
    ndigits: int | None = None,
    empty: T = 0.0,
) -> float | T:
    """Return corrections divided by outputs with consistent zero handling."""
    if outputs <= 0:
        return empty

    rate = corrections / outputs
    if ndigits is not None:
        return round(rate, ndigits)
    return rate
