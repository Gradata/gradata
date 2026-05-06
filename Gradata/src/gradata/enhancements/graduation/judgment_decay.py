"""Deprecated import shim for judgment decay algorithms."""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.enhancements.graduation.judgment_decay is deprecated; "
    "import gradata.enhancements.experimental.judgment_decay instead.",
    DeprecationWarning,
    stacklevel=2,
)

from gradata.enhancements.experimental.judgment_decay import *  # noqa: F401,F403,E402
