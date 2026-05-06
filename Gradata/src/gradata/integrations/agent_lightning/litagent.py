"""Deprecated shim for gradata.tuning.agent_lightning.litagent."""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.agent_lightning.litagent is deprecated; "
    "import gradata.tuning.agent_lightning.litagent instead.",
    DeprecationWarning,
    stacklevel=2,
)

from gradata.tuning.agent_lightning.litagent import *  # noqa: F401,F403,E402
