"""Agent-Lightning integration for Gradata.

Provides:
- LitAgent wrapper that traces a Gradata-instrumented prompt rollout
- Reward function that scores rollouts by Gradata correction match
- gradata tune CLI wrapper that runs APO end-to-end

Optional dep: pip install gradata[tune] (basic) or gradata[tune-apo] (APO)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .litagent import GradataLitAgent
    from .reward import gradata_reward
    from .runner import run_apo_tune

__all__ = [
    "GradataLitAgent",
    "gradata_reward",
    "run_apo_tune",
]


def __getattr__(name: str):
    if name == "GradataLitAgent":
        from .litagent import GradataLitAgent

        return GradataLitAgent
    if name == "gradata_reward":
        from .reward import gradata_reward

        return gradata_reward
    if name == "run_apo_tune":
        from .runner import run_apo_tune

        return run_apo_tune
    raise AttributeError(name)
