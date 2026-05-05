"""LitAgent wrapper for Gradata-scored prompt rollouts."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .reward import gradata_reward

if TYPE_CHECKING:
    from gradata import Brain

logger = logging.getLogger(__name__)

RunnerFn = Callable[[str, dict[str, Any]], str]


def _load_litagent_type() -> type:
    try:
        from agentlightning.litagent import LitAgent
    except ImportError as exc:
        raise ImportError(
            "Agent-Lightning support requires the optional dependency. "
            "Install with `pip install gradata[tune]` or `pip install gradata[tune-apo]`."
        ) from exc
    return LitAgent


def _load_emit_reward() -> Callable[..., Any]:
    try:
        from agentlightning.emitter.reward import emit_reward
    except ImportError as exc:
        raise ImportError(
            "Agent-Lightning support requires the optional dependency. "
            "Install with `pip install gradata[tune]` or `pip install gradata[tune-apo]`."
        ) from exc
    return emit_reward


class _GradataLitAgentMixin:
    brain: Brain
    prompt_template: str
    runner_fn: RunnerFn
    last_output: str | None
    last_reward: float | None

    def _init_gradata(
        self,
        brain: Brain,
        prompt_template: str,
        runner_fn: RunnerFn,
    ) -> None:
        self.brain = brain
        self.prompt_template = prompt_template
        self.runner_fn = runner_fn
        self.last_output = None
        self.last_reward = None

    def rollout(self, task: dict[str, Any], resources: dict[str, Any], rollout: Any) -> float:
        return self.training_rollout(task, resources, rollout)

    def training_rollout(
        self,
        task: dict[str, Any],
        resources: dict[str, Any] | None = None,
        rollout: Any = None,
    ) -> float:
        prompt_template = self._resolve_prompt_template(resources or {}, rollout)
        prompt = self._render_prompt(prompt_template, task)
        output = self.runner_fn(prompt, task)
        reward = gradata_reward(self.brain, task, output)

        emit_reward = _load_emit_reward()
        emit_reward(reward)

        self.last_output = output
        self.last_reward = reward
        return reward

    def validation_rollout(
        self,
        task: dict[str, Any],
        resources: dict[str, Any] | None = None,
        rollout: Any = None,
    ) -> float:
        return self.training_rollout(task, resources, rollout)

    def _resolve_prompt_template(self, resources: dict[str, Any], rollout: Any) -> Any:
        candidate = resources.get("prompt_template")
        if candidate is not None:
            return candidate

        rollout_resources = getattr(rollout, "resources", None)
        if isinstance(rollout_resources, dict):
            candidate = rollout_resources.get("prompt_template")
            if candidate is not None:
                return candidate

        for value in resources.values():
            if hasattr(value, "template") or isinstance(value, str):
                return value
        return self.prompt_template

    def _render_prompt(self, prompt_template: Any, task: dict[str, Any]) -> str:
        if hasattr(prompt_template, "format") and hasattr(prompt_template, "template"):
            try:
                return str(prompt_template.format(**task))
            except Exception as exc:
                logger.debug("PromptTemplate.format failed, using raw template: %s", exc)
                return str(prompt_template.template)
        template = str(getattr(prompt_template, "template", prompt_template))
        try:
            return template.format(**task)
        except (KeyError, IndexError, ValueError):
            return template


class GradataLitAgent:
    """Factory class returning a runtime Agent-Lightning ``LitAgent`` subclass."""

    def __new__(
        cls,
        brain: Brain,
        prompt_template: str,
        runner_fn: RunnerFn,
    ) -> _GradataLitAgentMixin:
        litagent_type = _load_litagent_type()

        class _RuntimeGradataLitAgent(_GradataLitAgentMixin, litagent_type):  # type: ignore[misc, valid-type]
            pass

        instance = _RuntimeGradataLitAgent()
        instance._init_gradata(brain, prompt_template, runner_fn)
        return instance
