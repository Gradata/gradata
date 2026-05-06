"""Deprecated shim for gradata.tuning.agent_lightning.reward."""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.agent_lightning.reward is deprecated; "
    "import gradata.tuning.agent_lightning.reward instead.",
    DeprecationWarning,
    stacklevel=2,
)

from gradata.tuning.agent_lightning.reward import *  # noqa: F401,F403,E402
