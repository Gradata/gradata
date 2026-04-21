"""Autoresearch verify script — measures Gradata per-session token emissions.

Simulates 3 scenarios (minimal / typical / heavy) and sums the tokens Gradata
emits into model context via its 10 identified emit surfaces (SessionStart,
UserPromptSubmit, PreToolUse, PostToolUse, PreCompact hooks). Counts tokens
with tiktoken cl100k_base.

Gates (all must pass for the sample to be valid):

1. correctness_gate — fast pytest subset passes
2. semantic_gate — no diff vs branch parent in frozen paths (domain/, lessons.md)
3. retrieval_integrity_gate — Jaccard of injected rule IDs vs baseline ≥ 0.8

Prints on success (exit 0)::

    weighted_tokens=<median_total>
    session_once=<tokens>
    per_turn=<tokens>
    samples=[...]

On gate failure prints the failing gate name and exits non-zero.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
TMP = REPO_ROOT / ".tmp" / "autoresearch"
TMP.mkdir(parents=True, exist_ok=True)

# Frozen paths — semantic gate fails if any of these have a diff vs branch parent.
FROZEN_GLOBS = [
    "domain/",
    "brain/lessons.md",
    "lessons.md",
]

# Branch parent — fork point of autoresearch/token-budget.
BRANCH_PARENT = "feat/token-optimization-autoresearch"

# Scenarios: (turns, edits, agents) per simulated session.
SCENARIOS = {
    "minimal": {"turns": 1, "edits": 1, "agents": 0},
    "typical": {"turns": 10, "edits": 10, "agents": 2},
    "heavy": {"turns": 40, "edits": 40, "agents": 5},
}

# Rule-ID pattern for retrieval-integrity gate. Matches lines like
# `[RULE:0.91 r:a3f2] CODE: ...` or `[CLUSTER:0.85 r:b1c2] ...`.
RULE_ID_PATTERN = re.compile(r"\br:([a-f0-9]{4,})\b")

# Enable optional injection paths so we measure the full blast radius.
HOOK_ENV = {
    "GRADATA_CONTEXT_INJECT": "1",
    "GRADATA_JIT_ENABLED": "1",
    "GRADATA_RULE_ENFORCEMENT": "1",
}


def _tiktoken_encoding():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def _count(text: str, enc) -> int:
    return len(enc.encode(text)) if text else 0


def _run_hook(module: str, data: dict) -> str:
    """Invoke a hook's `main(data)` in a subprocess; return the 'result' string."""
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT / 'src')!r})\n"
        f"from {module} import main\n"
        f"data = json.loads({json.dumps(json.dumps(data))})\n"
        "out = main(data)\n"
        "if out and isinstance(out, dict):\n"
        "    print(out.get('result', ''))\n"
    )
    env = {**os.environ, **HOOK_ENV}
    proc = subprocess.run(
        [PYTHON, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
        env=env,
    )
    return proc.stdout if proc.returncode == 0 else ""


def _collect_once_strings() -> dict[str, str]:
    """Return strings emitted once per session (SessionStart hooks)."""
    data = {
        "hook_event_name": "SessionStart",
        "session_id": "autoresearch",
        "source": "startup",
        "cwd": str(REPO_ROOT),
    }
    return {
        "inject_brain_rules": _run_hook("gradata.hooks.inject_brain_rules", data),
        "inject_handoff": _run_hook("gradata.hooks.inject_handoff", data),
    }


# Four prompt lengths probe the per-turn surface. Any threshold-gaming
# (raising MIN_MESSAGE_LEN / MIN_DRAFT_LEN so short prompts silently skip
# injection) now shows zero improvement because longer prompts still trigger.
_PROBE_PROMPTS = [
    # ~80 chars — short turn
    "fix this null pointer in the auth handler",
    # ~250 chars — medium
    (
        "Help me debug an authentication flow where tokens keep expiring before "
        "requests complete. I've already tried increasing the TTL but users still "
        "hit 401s intermittently — what could be causing this?"
    ),
    # ~700 chars — long
    (
        "Walk me through how the rule-graduation pipeline decides when an INSTINCT "
        "promotes to a PATTERN. I see the threshold is 0.60 but I'm seeing rules with "
        "confidence 0.62 stuck as INSTINCT for days. Is there a survival-count "
        "requirement on top? And if I force-graduate one manually through brain.patch_rule, "
        "does that re-enter the dedup pipeline or is it treated as hand-curated content "
        "that bypasses clustering? I want to make sure I don't accidentally create "
        "duplicates when I manually promote rules from the dashboard."
    ),
    # ~1800 chars — very long (multi-paragraph prompt)
    (
        "I'm designing a new cold-start path for Gradata where the first Brain() "
        "instantiation in a fresh temp dir needs to be under 200ms. Currently it's "
        "~250ms and the culprit is eager schema probes in _db.init_schema plus the "
        "module-level bm25s import which pulls in numpy. Questions: (1) Can I lazy-"
        "defer init_schema until the first DB read? The concern is that test fixtures "
        "create a Brain and immediately call .correct() — so 'first read' is essentially "
        "'first operation'. (2) For bm25s, is there a way to make its import side-effect-"
        "free on Windows? I noticed it spits diagnostic text to stdout during import on "
        "3.12. (3) More broadly — is there a pattern in the codebase where heavy "
        "enhancements register themselves via entry_points so the Brain doesn't have to "
        "eagerly import everything under enhancements/? I want to know if the SDK has "
        "a plugin protocol I should be using instead of the current hard imports. This "
        "matters because downstream projects have complained about import time and "
        "we've already shipped batch 7-10 performance fixes but import is still the "
        "long pole. Looking for architectural guidance not just micro-optimization."
    ),
]


def _collect_per_turn_strings() -> list[dict[str, str]]:
    """Return emissions for each probe prompt — preserves variance across lengths."""
    turns: list[dict[str, str]] = []
    for prompt in _PROBE_PROMPTS:
        data = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "autoresearch",
            "prompt": prompt,
        }
        turns.append(
            {
                "context_inject": _run_hook("gradata.hooks.context_inject", data),
                "implicit_feedback": _run_hook("gradata.hooks.implicit_feedback", data),
                "jit_inject": _run_hook("gradata.hooks.jit_inject", data),
            }
        )
    return turns


def _collect_per_edit_strings() -> dict[str, str]:
    pre = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "src/foo.py",
            "old_string": "x = 1",
            "new_string": "x = 2",
        },
    }
    post = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": pre["tool_input"],
        "tool_response": {"success": True},
    }
    return {
        "rule_enforcement": _run_hook("gradata.hooks.rule_enforcement", pre),
        "auto_correct": _run_hook("gradata.hooks.auto_correct", post),
    }


def _collect_per_agent_strings() -> dict[str, str]:
    data = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "general-purpose",
            "prompt": "Investigate why authentication tokens expire early.",
            "description": "auth token investigation",
        },
    }
    return {"agent_precontext": _run_hook("gradata.hooks.agent_precontext", data)}


def measure_weighted_tokens() -> dict:
    enc = _tiktoken_encoding()

    once = _collect_once_strings()
    turn = _collect_per_turn_strings()
    edit = _collect_per_edit_strings()
    agent = _collect_per_agent_strings()

    once_tokens = sum(_count(s, enc) for s in once.values())
    # turn is a list of dicts (one per probe prompt) — average across lengths
    # so threshold-gaming on one length doesn't dominate.
    per_prompt_turn_tokens = [
        sum(_count(s, enc) for s in prompt_group.values()) for prompt_group in turn
    ]
    turn_tokens = (
        sum(per_prompt_turn_tokens) / len(per_prompt_turn_tokens) if per_prompt_turn_tokens else 0
    )
    edit_tokens = sum(_count(s, enc) for s in edit.values())
    agent_tokens = sum(_count(s, enc) for s in agent.values())

    samples = []
    for name, cfg in SCENARIOS.items():
        total = (
            once_tokens
            + turn_tokens * cfg["turns"]
            + edit_tokens * cfg["edits"]
            + agent_tokens * cfg["agents"]
        )
        samples.append(
            {
                "scenario": name,
                "session_once": once_tokens,
                "turn_tokens": turn_tokens,
                "edit_tokens": edit_tokens,
                "agent_tokens": agent_tokens,
                "turns": cfg["turns"],
                "edits": cfg["edits"],
                "agents": cfg["agents"],
                "total": total,
            }
        )

    weighted_median = statistics.median(s["total"] for s in samples)
    return {
        "weighted_tokens": weighted_median,
        "samples": samples,
        "per_turn": turn_tokens,
        "per_edit": edit_tokens,
        "per_agent": agent_tokens,
        "once": once_tokens,
        "raw_strings": {
            "once": once,
            "turn": turn,
            "edit": edit,
            "agent": agent,
        },
    }


def correctness_gate() -> bool:
    proc = subprocess.run(
        [
            PYTHON,
            "-m",
            "pytest",
            "tests/test_brain.py",
            "tests/test_core_behavioral.py",
            "-q",
            "--tb=no",
            "-x",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-2000:])
        sys.stderr.write(proc.stderr[-2000:])
        return False
    return True


def semantic_gate() -> bool:
    for path in FROZEN_GLOBS:
        proc = subprocess.run(
            ["git", "diff", "--name-only", BRANCH_PARENT, "--", path],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if proc.stdout.strip():
            sys.stderr.write(f"semantic_gate violation in {path}:\n{proc.stdout}\n")
            return False
    return True


def _extract_rule_ids(raw_strings: dict) -> set[str]:
    ids: set[str] = set()
    for group in raw_strings.values():
        iterable = group if isinstance(group, list) else [group]
        for bucket in iterable:
            for emitted in bucket.values():
                ids.update(RULE_ID_PATTERN.findall(emitted))
    return ids


def retrieval_integrity_gate(raw_strings: dict) -> bool:
    baseline_path = TMP / "baseline_rules.json"
    current = _extract_rule_ids(raw_strings)
    if not baseline_path.exists():
        baseline_path.write_text(json.dumps(sorted(current)), encoding="utf-8")
        sys.stderr.write(f"baseline_rules captured ({len(current)} ids)\n")
        return True
    baseline = set(json.loads(baseline_path.read_text(encoding="utf-8")))
    if not baseline and not current:
        return True
    union = baseline | current
    inter = baseline & current
    jaccard = len(inter) / len(union) if union else 1.0
    if jaccard < 0.8:
        sys.stderr.write(
            f"retrieval_integrity_gate FAIL: jaccard={jaccard:.2f} "
            f"baseline={len(baseline)} current={len(current)} "
            f"intersection={len(inter)}\n"
        )
        return False
    return True


def main() -> int:
    if not correctness_gate():
        print("correctness_gate=FAIL")
        return 2
    if not semantic_gate():
        print("semantic_gate=FAIL")
        return 3
    result = measure_weighted_tokens()
    if not retrieval_integrity_gate(result["raw_strings"]):
        print("retrieval_integrity_gate=FAIL")
        return 4

    print(f"weighted_tokens={result['weighted_tokens']:.0f}")
    print(f"session_once={result['once']}")
    print(f"per_turn={result['per_turn']}")
    print(f"per_edit={result['per_edit']}")
    print(f"per_agent={result['per_agent']}")
    for s in result["samples"]:
        print(
            f"scenario={s['scenario']} total={s['total']} "
            f"once={s['session_once']} "
            f"turns={s['turns']}×{s['turn_tokens']} "
            f"edits={s['edits']}×{s['edit_tokens']} "
            f"agents={s['agents']}×{s['agent_tokens']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
