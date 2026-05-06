"""Tune one prompt against a Gradata brain."""

from __future__ import annotations

from pathlib import Path

from gradata.tuning.agent_lightning import run_apo_tune


def main() -> None:
    brain_dir = Path("./my-brain")
    prompt = "You are a helpful assistant.\n\nTask: {task_input}\n\nAnswer:"

    def runner_fn(prompt_text: str, task: dict) -> str:
        # Replace this with your OpenAI-compatible client call. The default
        # example echoes held-out correction finals so the wiring is runnable.
        return str(task.get("expected") or prompt_text)

    result = run_apo_tune(
        brain_dir,
        prompt_template=prompt,
        runner_fn=runner_fn,
        rounds=2,
        beam_width=2,
    )

    print(f"baseline:  {result['baseline_score']:.3f}")
    print(f"optimized: {result['optimized_score']:.3f}")
    print(result["optimized_prompt"])


if __name__ == "__main__":
    main()
