"""Deprecated compatibility shim for :mod:`gradata.enhancements.prompt_compactor`."""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.enhancements.prompt_synthesizer is deprecated; use "
    "gradata.enhancements.prompt_compactor instead. The old module name will "
    "be removed in v0.9.0.",
    DeprecationWarning,
    stacklevel=2,
)

from gradata.enhancements.prompt_compactor import *  # noqa: F403
