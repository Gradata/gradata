"""Deprecated shim for gradata.tuning.agent_lightning.runner."""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.agent_lightning.runner is deprecated; "
    "import gradata.tuning.agent_lightning.runner instead.",
    DeprecationWarning,
    stacklevel=2,
)

from gradata.tuning.agent_lightning.runner import *  # noqa: F401,F403,E402
