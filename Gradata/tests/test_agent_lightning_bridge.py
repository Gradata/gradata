"""Tests for the Agent-Lightning bridge."""

from __future__ import annotations

import os
import subprocess
import sys
import types
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    find_spec("agentlightning") is None,
    reason="agentlightning is not installed",
)

from gradata.integrations.agent_lightning import GradataLitAgent, gradata_reward, run_apo_tune


class FakePromptTemplate:
    def __init__(self, template: str, engine: str):
        self.template = template
        self.engine = engine

    def format(self, **kwargs):
        return self.template.format(**kwargs)


class FakeLitAgent:
    pass


def _install_fake_agentlightning(monkeypatch):
    package = types.ModuleType("agentlightning")
    algorithm_pkg = types.ModuleType("agentlightning.algorithm")
    emitter_pkg = types.ModuleType("agentlightning.emitter")
    store_pkg = types.ModuleType("agentlightning.store")
    litagent_mod = types.ModuleType("agentlightning.litagent")
    reward_mod = types.ModuleType("agentlightning.emitter.reward")
    apo_mod = types.ModuleType("agentlightning.algorithm.apo")
    store_mod = types.ModuleType("agentlightning.store.memory")
    trainer_mod = types.ModuleType("agentlightning.trainer")
    types_mod = types.ModuleType("agentlightning.types")

    emitted: list[float] = []
    litagent_mod.LitAgent = FakeLitAgent
    reward_mod.emit_reward = lambda value: emitted.append(value)
    apo_mod.APO = object
    store_mod.InMemoryLightningStore = object
    trainer_mod.Trainer = object
    types_mod.PromptTemplate = FakePromptTemplate

    monkeypatch.setitem(sys.modules, "agentlightning", package)
    monkeypatch.setitem(sys.modules, "agentlightning.algorithm", algorithm_pkg)
    monkeypatch.setitem(sys.modules, "agentlightning.emitter", emitter_pkg)
    monkeypatch.setitem(sys.modules, "agentlightning.store", store_pkg)
    monkeypatch.setitem(sys.modules, "agentlightning.litagent", litagent_mod)
    monkeypatch.setitem(sys.modules, "agentlightning.emitter.reward", reward_mod)
    monkeypatch.setitem(sys.modules, "agentlightning.algorithm.apo", apo_mod)
    monkeypatch.setitem(sys.modules, "agentlightning.store.memory", store_mod)
    monkeypatch.setitem(sys.modules, "agentlightning.trainer", trainer_mod)
    monkeypatch.setitem(sys.modules, "agentlightning.types", types_mod)
    return emitted


def test_gradata_reward_exact_match(fresh_brain):
    fresh_brain.correct("Write a formal launch note", "Hey, we shipped the thing.")

    reward = gradata_reward(
        fresh_brain,
        {"task_input": "Write a formal launch note"},
        "Hey, we shipped the thing.",
    )

    assert reward == 1.0


def test_gradata_reward_no_match(fresh_brain):
    reward = gradata_reward(
        fresh_brain,
        {"task_input": "No matching history"},
        "Any output",
    )

    assert reward == 0.5


def test_gradata_reward_partial_match(fresh_brain):
    fresh_brain.correct("Write a casual update", "Hey, we shipped the thing.")

    reward = gradata_reward(
        fresh_brain,
        {"task_input": "Write a casual update"},
        "Hey, we shipped thing.",
    )

    assert 0.5 < reward < 1.0


def test_litagent_rollout_emits_reward(fresh_brain, monkeypatch):
    emitted = _install_fake_agentlightning(monkeypatch)
    fresh_brain.correct("Draft customer update", "Customer update done.")

    agent = GradataLitAgent(
        fresh_brain,
        "Task: {task_input}",
        lambda _prompt, _task: "Customer update done.",
    )
    result = agent.training_rollout(
        {"task_input": "Draft customer update"},
        {"prompt_template": FakePromptTemplate(template="Task: {task_input}", engine="f-string")},
        SimpleNamespace(resources={}),
    )

    assert result == 1.0
    assert emitted == [1.0]
    assert agent.last_output == "Customer update done."


def test_run_apo_tune_smoke(fresh_brain, monkeypatch):
    _install_fake_agentlightning(monkeypatch)
    fresh_brain.correct("Make this concise", "Concise.")
    fresh_brain.correct("Make this direct", "Direct.")

    class FakeAPO:
        def __init__(self, *_args, **_kwargs):
            self.best = FakePromptTemplate(
                template="Optimized: {task_input}",
                engine="f-string",
            )

        def get_best_prompt(self):
            return self.best

    class FakeTrainer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def fit(self, agent, train_dataset=None, *, val_dataset=None):
            sample = (val_dataset or train_dataset)[0]
            agent.training_rollout(
                sample,
                self.kwargs["initial_resources"],
                SimpleNamespace(resources={}),
            )

    result = run_apo_tune(
        fresh_brain.dir,
        prompt_template="Seed: {task_input}",
        rounds=1,
        beam_width=1,
        branch_factor=1,
        openai_client=object(),
        trainer_cls=FakeTrainer,
        apo_cls=FakeAPO,
    )

    assert result["rounds_completed"] == 1
    assert result["optimized_prompt"] == "Optimized: {task_input}"
    assert result["baseline_score"] == pytest.approx(1.0)
    assert result["optimized_score"] == pytest.approx(1.0)


def test_cli_tune_smoke(tmp_path):
    brain_dir = tmp_path / "brain"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")

    init_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gradata.cli",
            "init",
            str(brain_dir),
            "--no-interactive",
            "--embedding",
            "local",
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    assert init_result.returncode == 0

    subprocess.run(
        [
            sys.executable,
            "-m",
            "gradata.cli",
            "--brain-dir",
            str(brain_dir),
            "correct",
            "--draft",
            "Rewrite this short",
            "--final",
            "Short.",
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    prompt_path = tmp_path / "prompt.md"
    out_path = tmp_path / "optimized.md"
    prompt_path.write_text("Prompt: {task_input}", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gradata.cli",
            "--brain-dir",
            str(brain_dir),
            "tune",
            str(prompt_path),
            "--rounds",
            "0",
            "--out",
            str(out_path),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert "optimized prompt written" in result.stdout
    assert out_path.read_text(encoding="utf-8") == "Prompt: {task_input}"
