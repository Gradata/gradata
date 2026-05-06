"""Deprecated shim for the Agent-Lightning tuning integration."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

warnings.warn(
    "gradata.integrations.agent_lightning is deprecated; "
    "import gradata.tuning.agent_lightning instead.",
    DeprecationWarning,
    stacklevel=2,
)

if TYPE_CHECKING:
    from gradata.tuning.agent_lightning import GradataLitAgent, gradata_reward, run_apo_tune

__all__ = [
    "GradataLitAgent",
    "gradata_reward",
    "run_apo_tune",
]


def __getattr__(name: str):
    if name == "GradataLitAgent":
        from gradata.tuning.agent_lightning import GradataLitAgent

        return GradataLitAgent
    if name == "gradata_reward":
        from gradata.tuning.agent_lightning import gradata_reward

        return gradata_reward
    if name == "run_apo_tune":
        from gradata.tuning.agent_lightning import run_apo_tune

        return run_apo_tune
    raise AttributeError(name)
