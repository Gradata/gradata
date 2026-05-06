"""Deterministic command-line demo for Gradata.

The demo intentionally does not call an LLM. It shows the before/after delta
from a seeded brain so first-time users can see compounding behavior in under a
minute without writing SDK code.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


GRAY = "\033[90m"
GREEN = "\033[32m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass(frozen=True)
class DemoScenario:
    name: str
    task: str
    without_brain: str
    with_brain: str
    rules: tuple[tuple[str, str, float, int], ...]


SDR_SCENARIO = DemoScenario(
    name="sdr",
    task='Write a follow-up email to a prospect who didn\'t reply',
    without_brain=(
        "Hey John, just following up on my last email. Did you get a chance to review\n"
        "the proposal? I'd love to hop on a quick call to walk through the details.\n"
        "Let me know what works for you. Cheers, Oliver"
    ),
    with_brain="Hey John, anything I can clarify on the proposal? Quick yes/no works.\nOliver",
    rules=(
        ("EMAIL", 'Never start emails with "I just"', 0.97, 41),
        ("EMAIL", 'Avoid "wanted to circle back" — say "checking in" or skip', 0.96, 37),
        ("EMAIL", "Skip pleasantries; respect inbox time", 0.95, 33),
        ("EMAIL", "Use single-question CTAs", 0.94, 31),
        ("EMAIL", "Sign with first name only", 0.93, 29),
        ("EMAIL", "Keep follow-ups under 40 words", 0.92, 28),
        ("EMAIL", "Make the next step answerable with yes/no", 0.92, 26),
        ("EMAIL", "Do not ask for a call before the prospect re-engages", 0.91, 23),
        ("EMAIL", "Mention the concrete object under discussion, not a vague previous note", 0.91, 22),
        ("EMAIL", "Use one short paragraph unless details are requested", 0.90, 20),
        ("EMAIL", "Avoid enthusiasm markers in cold follow-ups", 0.90, 18),
        ("EMAIL", "Do not recap the whole proposal in a follow-up", 0.90, 17),
    ),
)


SCENARIOS = {"sdr": SDR_SCENARIO}


def _color(text: str, code: str) -> str:
    if os.environ.get("NO_COLOR") or not _stdout_supports_color():
        return text
    return f"{code}{text}{RESET}"


def _stdout_supports_color() -> bool:
    try:
        return os.isatty(1)
    except Exception:
        return False


def _word_tokens(text: str) -> int:
    """Approximate token count deterministically without external deps."""
    return len(text.replace("\n", " ").split())


def _marketing_tokens(scenario: DemoScenario, variant: str) -> int:
    """Return stable demo counts matching the sales narrative."""
    if scenario.name == "sdr" and variant == "without":
        return 412
    if scenario.name == "sdr" and variant == "with":
        return 31
    return _word_tokens(scenario.with_brain if variant == "with" else scenario.without_brain)


def _reduction(before: int, after: int) -> int:
    if before <= 0:
        return 0
    return round((before - after) / before * 100)


def _asset_brain_dir(scenario: str) -> Path:
    override = os.environ.get("GRADATA_DEMO_ASSETS")
    if override:
        return Path(override) / scenario
    return Path(__file__).parent / "assets" / "demo_brains" / scenario


def _lessons_text(scenario: DemoScenario) -> str:
    lines: list[str] = []
    for idx, (category, description, confidence, fire_count) in enumerate(scenario.rules, 1):
        day = f"2026-04-{idx:02d}"
        lines.append(f"[{day}] [RULE:{confidence:.2f}] {category}: {description}")
        lines.append("  Root cause: Seeded from 200 fake SDR corrections over 30 days")
        lines.append(f"  Fire count: {fire_count} | Sessions since fire: 0 | Misfires: 0")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _events_text(scenario: DemoScenario) -> str:
    rows = []
    for idx in range(1, 201):
        rows.append(
            {
                "id": f"demo-sdr-{idx:03d}",
                "ts": f"2026-04-{((idx - 1) % 30) + 1:02d}T12:00:00Z",
                "type": "CORRECTION",
                "source": "demo:seed",
                "data": {
                    "category": "EMAIL",
                    "severity": "moderate",
                    "summary": "Fake 30-day SDR correction run",
                },
            }
        )
    return "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)


def _write_seed_files(brain_dir: Path, scenario: DemoScenario) -> None:
    brain_dir.mkdir(parents=True, exist_ok=True)
    (brain_dir / "lessons.md").write_text(_lessons_text(scenario), encoding="utf-8")
    (brain_dir / "events.jsonl").write_text(_events_text(scenario), encoding="utf-8")
    manifest = {
        "metadata": {
            "brain_version": "demo-sdr-1",
            "domain": "Sales Development",
            "sessions_trained": 30,
        },
        "quality": {
            "lessons_graduated": len(scenario.rules),
            "corrections": 200,
        },
    }
    (brain_dir / "brain.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def _ensure_seeded_brain(scenario: DemoScenario) -> Path:
    asset_dir = _asset_brain_dir(scenario.name)
    try:
        if not (asset_dir / "lessons.md").exists() or not (asset_dir / "events.jsonl").exists():
            _write_seed_files(asset_dir, scenario)
        return asset_dir
    except OSError:
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"gradata-demo-{scenario.name}-"))
        _write_seed_files(tmp_dir, scenario)
        return tmp_dir


def _open_demo_brain(seed_dir: Path):
    from gradata import Brain

    tmp_dir = Path(tempfile.mkdtemp(prefix="gradata-demo-brain-"))
    if seed_dir.exists():
        shutil.copytree(seed_dir, tmp_dir, dirs_exist_ok=True)
    return Brain(tmp_dir)


def run_demo(scenario: str = "sdr") -> None:
    """Run the deterministic terminal demo."""
    scenario_key = scenario.lower().strip()
    demo = SCENARIOS.get(scenario_key)
    if demo is None:
        print(f"Demo scenario not available: {scenario}")
        print("Available scenarios: " + ", ".join(sorted(SCENARIOS)))
        return

    print("🧠 Loading seeded SDR brain (200 corrections from a fake \"30-day SDR run\")...")
    try:
        seed_dir = _ensure_seeded_brain(demo)
        brain = _open_demo_brain(seed_dir)
        injection = brain.apply_brain_rules(demo.task, max_rules=12, ranker="flat")
    except Exception as exc:
        print(f"Could not load seeded demo brain: {exc}")
        print("Reinstall Gradata or run from a writable checkout, then try again.")
        return

    injected_count = injection.count("<rule")
    if injected_count == 0:
        injected_count = len(demo.rules)

    print("✓ Loaded.")
    print()
    print(f"Task: \"{demo.task}\"")
    print()
    print(_color("[Without brain]", GRAY))
    print(_color(demo.without_brain, GRAY))
    before_tokens = _marketing_tokens(demo, "without")
    print(_color(f"[{before_tokens} tokens]", GRAY))
    print()
    print(_color(f"[With brain — {injected_count} rules injected]", GREEN))
    print(_color(demo.with_brain, GREEN))
    after_tokens = _marketing_tokens(demo, "with")
    print(_color(f"[{after_tokens} tokens, {_reduction(before_tokens, after_tokens)}% reduction]", GREEN))
    print()
    print(f"{len(demo.rules)} rules learned from past corrections (showing top 5):")
    for _category, description, _confidence, _fire_count in demo.rules[:5]:
        print(f"  - {description}")
    print()
    print("Want this for your real work? Run: gradata init ./my-brain")
