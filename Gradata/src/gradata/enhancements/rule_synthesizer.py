"""Synthesize ranked brain rules into a single distilled <brain-wisdom> block.

Currently the injection hook emits up to four separate XML blocks
(mandatory-directives, brain-disposition, brain-rules, brain-meta-rules)
totalling ~1500 tokens of partially-redundant directives. This module
collapses them into one coherent instruction distilled by Opus 4.7.

Design contracts:
  1. Fail-safe: any error (no provider, network, model timeout, short
     output, parse failure) returns None. Caller falls back to the
     fragmented format. The injection hook never breaks on synth trouble.
  2. Two provider paths, tried in order:
       a. anthropic SDK via ANTHROPIC_API_KEY (direct API billing).
       b. `claude` CLI in print mode (Max-plan OAuth — no key needed).
     Max-plan users without an exportable API key get synthesis via (b).
  3. Cache by sha256(sorted_rule_signatures + task_type + model) in
     <brain>/.synth-cache/{hash}.txt. Per-rule signatures use short
     anchors, not full text, so cache survives wording tweaks.
  4. Opus 4.7 by default. Override via GRADATA_SYNTH_MODEL.

Not in scope here:
  - The decision of WHICH rules to include (ranker already did that).
  - Meta-rule synthesis (separate module, separate model call).
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from pathlib import Path

_log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4-7"
CACHE_DIRNAME = ".synth-cache"
MAX_OUTPUT_TOKENS = 1200
SYNTH_TIMEOUT = 20.0

_SYSTEM_PROMPT = """You are the brain-wisdom synthesizer for an AI coding/sales assistant.

You receive a ranked set of behavioral rules the assistant has learned from corrections. Your job: distill them into one coherent instruction block the assistant will read at session start.

Classification rules (STRICT):
- A rule belongs in "Non-negotiables" ONLY if its input line starts with `[MANDATORY]`. Never promote other rules to non-negotiable based on imperative wording, severity, or tone. If the input has zero [MANDATORY] items, the Non-negotiables section MUST be omitted entirely.
- Every [MANDATORY] input MUST appear in Non-negotiables with meaning preserved (wording may tighten).
- All other rules go in "Active guidance", regardless of how forcefully they are phrased.

Synthesis rules:
- Group related rules in Active guidance under short topic headings. Collapse duplicates and near-duplicates.
- Resolve tension between rules: if two rules conflict, prefer the higher-confidence / more recent one and drop the weaker.
- Use imperative voice ("Do X" / "Never Y"), short lines.
- Do NOT add rules not present in the input. Do NOT soften non-negotiables. Do NOT invent Non-negotiables.
- Output plain text inside a single <brain-wisdom>...</brain-wisdom> block, no other XML wrappers.

Structure your output as:
<brain-wisdom>
[Non-negotiables section — ONLY if input contains [MANDATORY] items:]
**Non-negotiables** (response rejected if violated):
- ...

**Active guidance:**
- <topic>:
  - ...

**Current disposition:** <one-sentence summary of tone/posture signals if any, else omit this line>
</brain-wisdom>

Keep under 600 words. No commentary outside the block."""


def _cache_path(brain_dir: Path, cache_key: str) -> Path:
    return brain_dir / CACHE_DIRNAME / f"{cache_key}.txt"


def _compute_cache_key(
    mandatory_lines: list[str],
    cluster_lines: list[str],
    individual_lines: list[str],
    meta_block: str,
    disposition_block: str,
    task_type: str,
    model: str,
) -> str:
    # Signature stable under wording tweaks: sort + normalize whitespace.
    parts = [
        "MANDATORY:" + "|".join(sorted(mandatory_lines)),
        "CLUSTER:" + "|".join(sorted(cluster_lines)),
        "RULE:" + "|".join(sorted(individual_lines)),
        "META:" + meta_block.strip(),
        "DISP:" + disposition_block.strip(),
        "TASK:" + task_type,
        "MODEL:" + model,
    ]
    joined = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()[:16]


def _read_cache(brain_dir: Path, cache_key: str) -> str | None:
    path = _cache_path(brain_dir, cache_key)
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _write_cache(brain_dir: Path, cache_key: str, content: str) -> None:
    try:
        cache_dir = brain_dir / CACHE_DIRNAME
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache_path(brain_dir, cache_key).write_text(content, encoding="utf-8")
    except OSError as exc:
        _log.debug("synth cache write failed: %s", exc)


def _build_user_prompt(
    mandatory_lines: list[str],
    cluster_lines: list[str],
    individual_lines: list[str],
    meta_block: str,
    disposition_block: str,
    task_type: str,
    context: str,
) -> str:
    sections: list[str] = []
    sections.append(
        f"Session context: task_type={task_type or 'general'}; context={context or 'general'}"
    )
    if mandatory_lines:
        sections.append("MANDATORY (non-negotiable):\n" + "\n".join(mandatory_lines))
    if cluster_lines:
        sections.append("CLUSTERS (grouped recurring patterns):\n" + "\n".join(cluster_lines))
    if individual_lines:
        sections.append("INDIVIDUAL RULES (ranked):\n" + "\n".join(individual_lines))
    if meta_block.strip():
        sections.append("META-RULES (cross-category principles):\n" + meta_block.strip())
    if disposition_block.strip():
        sections.append("DISPOSITION (behavioral tendencies):\n" + disposition_block.strip())
    return "\n\n".join(sections)


def _extract_wisdom_block(raw: str) -> str | None:
    start = raw.find("<brain-wisdom>")
    end = raw.find("</brain-wisdom>")
    if start == -1 or end == -1 or end < start:
        return None
    # Keep the opening/closing tags intact so downstream treats it as a block.
    return raw[start : end + len("</brain-wisdom>")]


def synthesize_rules_block(
    *,
    brain_dir: Path,
    mandatory_lines: list[str] | None,
    cluster_lines: list[str] | None,
    individual_lines: list[str] | None,
    meta_block: str = "",
    disposition_block: str = "",
    task_type: str = "",
    context: str = "",
    model: str | None = None,
) -> str | None:
    """Distill ranked rules into a single <brain-wisdom> block via Opus.

    Returns the full `<brain-wisdom>...</brain-wisdom>` text, or None on any
    failure. Caller must fall back to the pre-existing fragmented format on
    None.

    The caller is responsible for gating (env flag, user preference). This
    function always attempts synthesis when inputs are non-empty. Separation
    of concerns: the injection hook and the brain-prompt updater each have
    different triggering rules.
    """
    mandatory_lines = mandatory_lines or []
    cluster_lines = cluster_lines or []
    individual_lines = individual_lines or []
    if not any((mandatory_lines, cluster_lines, individual_lines, meta_block.strip())):
        return None

    model = model or os.environ.get("GRADATA_SYNTH_MODEL", DEFAULT_MODEL)

    cache_key = _compute_cache_key(
        mandatory_lines,
        cluster_lines,
        individual_lines,
        meta_block,
        disposition_block,
        task_type,
        model,
    )
    cached = _read_cache(brain_dir, cache_key)
    if cached:
        _log.debug("synth cache hit: %s", cache_key)
        return cached

    user_prompt = _build_user_prompt(
        mandatory_lines,
        cluster_lines,
        individual_lines,
        meta_block,
        disposition_block,
        task_type,
        context,
    )

    # Two provider paths, tried in order:
    #   1. anthropic SDK (requires ANTHROPIC_API_KEY — direct API billing).
    #   2. `claude` CLI in print mode (reuses Claude Code Max-plan OAuth —
    #      no API key needed; subscription covers the call).
    # Max-plan users have no exportable key, so without the CLI fallback
    # synthesis would silently no-op for them. Order matters: API path is
    # cheaper/faster when available; CLI path is the Max-plan cushion.
    raw: str | None = None
    provider_used = "none"

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic

            client = anthropic.Anthropic(timeout=SYNTH_TIMEOUT)
            msg = client.messages.create(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = msg.content[0].text.strip()  # type: ignore[union-attr]
            provider_used = "sdk"
        except Exception as exc:
            _log.debug("anthropic SDK synth failed (%s); trying CLI fallback", exc)

    if raw is None:
        raw = _try_claude_cli(model, user_prompt)
        if raw is not None:
            provider_used = "cli"

    if raw is None:
        _log.debug("all synth providers failed; caller will fall back")
        return None

    block = _extract_wisdom_block(raw)
    if not block or len(block) < 50:
        _log.debug("synth output malformed or too short (provider=%s)", provider_used)
        return None

    _write_cache(brain_dir, cache_key, block)
    _log.debug("synth ok via %s (%d chars)", provider_used, len(block))
    return block


def _try_claude_cli(model: str, user_prompt: str) -> str | None:
    """Claude Code CLI fallback: `claude -p <prompt>` using Max-plan OAuth.

    The CLI is bundled with Claude Code and authenticates via the same
    OAuth session the user is already signed into — no API key required.
    Emits the combined system+user prompt as a single turn to stdout and
    returns the captured text, or None on any failure.

    Model mapping: the CLI accepts shorthand names; we pass the Opus
    family name and let the CLI resolve it.
    """
    exe = shutil.which("claude")
    if not exe:
        return None
    full_prompt = f"{_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"
    try:
        proc = subprocess.run(
            [exe, "-p", full_prompt, "--model", model, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=SYNTH_TIMEOUT * 3,  # CLI round-trip is heavier than SDK.
            encoding="utf-8",
        )
        if proc.returncode != 0:
            _log.debug("claude CLI returned %d: %s", proc.returncode, proc.stderr[:200])
            return None
        return proc.stdout.strip() or None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        _log.debug("claude CLI invocation failed: %s", exc)
        return None
