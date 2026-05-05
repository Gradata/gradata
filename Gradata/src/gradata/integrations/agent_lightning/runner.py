"""APO runner for Gradata-backed prompt tuning."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from gradata import Brain

from .litagent import GradataLitAgent, RunnerFn
from .reward import gradata_reward

logger = logging.getLogger(__name__)


def run_apo_tune(
    brain_dir: str | Path,
    skill_name: str | None = None,
    *,
    prompt_template: str | None = None,
    runner_fn: RunnerFn | None = None,
    rounds: int = 2,
    beam_width: int = 2,
    branch_factor: int = 2,
    openai_api_base: str | None = None,
    openai_client: Any | None = None,
    trainer_cls: type | None = None,
    apo_cls: type | None = None,
) -> dict[str, Any]:
    """Run Agent-Lightning APO against Gradata correction history.

    ``skill_name`` is accepted for forward compatibility but v0.7.1 keeps prompt
    persistence caller-owned. Pass the actual prompt via ``prompt_template``.
    """
    prompt = prompt_template if prompt_template is not None else skill_name
    if not prompt:
        raise ValueError("prompt_template is required")
    if openai_api_base:
        os.environ["OPENAI_API_BASE"] = openai_api_base

    brain = Brain(brain_dir)
    dataset = _correction_dataset(brain.dir)
    if not dataset:
        return {
            "baseline_score": 0.5,
            "optimized_score": 0.5,
            "optimized_prompt": prompt,
            "rounds_completed": 0,
        }

    train, val = _split_dataset(dataset)
    effective_runner = runner_fn or _expected_runner
    baseline_score = _score_prompt(brain, prompt, val, effective_runner)

    if rounds <= 0:
        return {
            "baseline_score": baseline_score,
            "optimized_score": baseline_score,
            "optimized_prompt": prompt,
            "rounds_completed": 0,
        }

    agl = _load_agentlightning()
    async_client = openai_client or _new_async_openai()
    trainer_type = trainer_cls or agl["Trainer"]
    apo_type = apo_cls or agl["APO"]

    algorithm = apo_type(
        async_client,
        beam_rounds=rounds,
        beam_width=beam_width,
        branch_factor=branch_factor,
        gradient_batch_size=max(1, min(len(train), beam_width)),
        val_batch_size=max(1, len(val)),
        rollout_batch_timeout=30.0,
    )
    trainer = trainer_type(
        store=agl["InMemoryLightningStore"](),
        initial_resources={
            "prompt_template": agl["PromptTemplate"](template=prompt, engine="f-string"),
        },
        algorithm=algorithm,
        max_rollouts=max(1, len(train) + len(val)) * max(2, rounds * max(1, branch_factor)),
    )
    agent = GradataLitAgent(brain, prompt, effective_runner)
    trainer.fit(agent, train_dataset=train, val_dataset=val)

    best_prompt = _best_prompt_text(algorithm, fallback=prompt)
    optimized_score = _score_prompt(brain, best_prompt, val, effective_runner)
    return {
        "baseline_score": baseline_score,
        "optimized_score": optimized_score,
        "optimized_prompt": best_prompt,
        "rounds_completed": rounds,
    }


def _load_agentlightning() -> dict[str, Any]:
    try:
        from agentlightning.algorithm.apo import APO
        from agentlightning.store.memory import InMemoryLightningStore
        from agentlightning.trainer import Trainer
        from agentlightning.types import PromptTemplate
    except ImportError as exc:
        raise ImportError(
            "APO tuning requires Agent-Lightning. Install with `pip install gradata[tune-apo]`."
        ) from exc
    return {
        "APO": APO,
        "InMemoryLightningStore": InMemoryLightningStore,
        "PromptTemplate": PromptTemplate,
        "Trainer": Trainer,
    }


def _new_async_openai() -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise ImportError(
            "APO tuning requires the `openai` package from gradata[tune-apo]."
        ) from exc
    return AsyncOpenAI()


def _correction_dataset(brain_dir: Path) -> list[dict[str, Any]]:
    import json

    events_path = brain_dir / "events.jsonl"
    if not events_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with events_path.open(encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "CORRECTION":
                continue
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            draft = _first_text(data, ("draft_text", "draft", "task_input", "input"))
            final = _first_text(data, ("final_text", "final", "expected", "correction"))
            if not draft or not final:
                continue
            rows.append(
                {
                    "id": event.get("id") or f"event-{line_no}",
                    "task_input": draft,
                    "expected": final,
                }
            )
    return rows


def _first_text(data: dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _split_dataset(
    dataset: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(dataset) == 1:
        return dataset[:], dataset[:]
    midpoint = max(1, len(dataset) // 2)
    return dataset[:midpoint], dataset[midpoint:] or dataset[:midpoint]


def _score_prompt(
    brain: Brain,
    prompt_template: str,
    dataset: list[dict[str, Any]],
    runner_fn: Callable[[str, dict[str, Any]], str],
) -> float:
    if not dataset:
        return 0.5
    scores: list[float] = []
    for task in dataset:
        prompt = _render_prompt(prompt_template, task)
        output = runner_fn(prompt, task)
        scores.append(gradata_reward(brain, task, output))
    return float(sum(scores) / len(scores))


def _render_prompt(prompt_template: str, task: dict[str, Any]) -> str:
    try:
        return prompt_template.format(**task)
    except (KeyError, IndexError, ValueError):
        return prompt_template


def _expected_runner(prompt: str, task: dict[str, Any]) -> str:
    expected = task.get("expected")
    if isinstance(expected, str) and expected:
        return expected
    return prompt


def _best_prompt_text(algorithm: Any, *, fallback: str) -> str:
    try:
        best = algorithm.get_best_prompt()
    except Exception as exc:
        logger.debug("APO did not expose a best prompt, using seed prompt: %s", exc)
        return fallback
    text = getattr(best, "template", best)
    return str(text or fallback)
