"""Synthesize ranked brain rules into a single distilled <brain-wisdom> block.

Currently the injection hook emits up to four separate XML blocks
(mandatory-directives, brain-disposition, brain-rules, brain-meta-rules)
totalling ~1500 tokens of partially-redundant directives. This module
collapses them into one coherent instruction distilled by Opus 4.7.

Design contracts:
  1. Fail-safe: any error (no provider, network, model timeout, short
     output, parse failure) returns None. Caller falls back to the
     fragmented format. The injection hook never breaks on synth trouble.
  2. One provider path: anthropic SDK via ANTHROPIC_API_KEY. Returns None
     when the key is absent — no CLI subprocess fallback.
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
from pathlib import Path

_log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4-7"
CACHE_DIRNAME = ".synth-cache"
MAX_OUTPUT_TOKENS = 1200
SYNTH_TIMEOUT = 20.0
# Bump when cache format / synthesizer prompt changes so older entries are
# treated as invalid and re-synthesized.
SYNTHESIZER_VERSION = "v1"
_VERSION_HEADER_PREFIX = "# synthesizer-version: "

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


def _is_valid_cache_payload(payload: str) -> bool:
    """Return True iff payload is non-empty and carries the current
    synthesizer-version header AND a <brain-wisdom> block."""
    if not payload or not payload.strip():
        return False
    expected_header = f"{_VERSION_HEADER_PREFIX}{SYNTHESIZER_VERSION}"
    if not payload.startswith(expected_header):
        return False
    if "<brain-wisdom>" not in payload or "</brain-wisdom>" not in payload:
        return False
    return True


def _strip_cache_header(payload: str) -> str:
    """Drop the version header line from a cached payload."""
    nl = payload.find("\n")
    return payload[nl + 1 :] if nl != -1 else payload


def _read_cache(brain_dir: Path, cache_key: str) -> str | None:
    path = _cache_path(brain_dir, cache_key)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not _is_valid_cache_payload(raw):
        _log.debug("synth cache invalid (version/empty), ignoring: %s", path)
        return None
    return _strip_cache_header(raw)


def _write_cache(brain_dir: Path, cache_key: str, content: str) -> None:
    try:
        cache_dir = brain_dir / CACHE_DIRNAME
        cache_dir.mkdir(parents=True, exist_ok=True)
        header = f"{_VERSION_HEADER_PREFIX}{SYNTHESIZER_VERSION}\n"
        _cache_path(brain_dir, cache_key).write_text(header + content, encoding="utf-8")
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


def _call_anthropic(
    model: str, system: str, user_prompt: str, max_tokens: int, timeout: float
) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        _log.debug("synth: ANTHROPIC_API_KEY not set")
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key, timeout=timeout)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text.strip()  # type: ignore[union-attr]
    except Exception as exc:
        _log.debug("synth: anthropic SDK failed: %s", exc)
        return None


def _call_openai(
    model: str, system: str, user_prompt: str, max_tokens: int, timeout: float
) -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        _log.debug("synth: OPENAI_API_KEY not set")
        return None
    try:
        import openai

        client = openai.OpenAI(api_key=key, timeout=timeout)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = resp.choices[0].message.content
        return text.strip() if text else None
    except Exception as exc:
        _log.debug("synth: openai SDK failed: %s", exc)
        return None


def _call_gemini(
    model: str, system: str, user_prompt: str, max_tokens: int, timeout: float
) -> str | None:
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        _log.debug("synth: GOOGLE_API_KEY / GEMINI_API_KEY not set")
        return None
    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=key)
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        )
        resp = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=config,
        )
        text = resp.text
        return text.strip() if text else None
    except Exception as exc:
        _log.debug("synth: gemini SDK failed: %s", exc)
        return None


def _call_http(
    model: str, system: str, user_prompt: str, max_tokens: int, timeout: float
) -> str | None:
    """OpenAI-compatible HTTP endpoint. Model string IS the base URL.

    Set GRADATA_HTTP_API_KEY for auth, GRADATA_HTTP_MODEL for the model
    name to pass in the request body (defaults to 'default').
    """
    key = os.environ.get("GRADATA_HTTP_API_KEY", "dummy")
    model_name = os.environ.get("GRADATA_HTTP_MODEL", "default")
    try:
        import openai

        client = openai.OpenAI(api_key=key, base_url=model, timeout=timeout)
        resp = client.chat.completions.create(
            model=model_name,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = resp.choices[0].message.content
        return text.strip() if text else None
    except Exception as exc:
        _log.debug("synth: HTTP provider failed (%s): %s", model, exc)
        return None


def call_provider(
    model: str,
    system: str,
    user_prompt: str,
    max_tokens: int = MAX_OUTPUT_TOKENS,
    timeout: float = SYNTH_TIMEOUT,
) -> str | None:
    """Dispatch a synthesis call to the appropriate LLM provider.

    Routing by model prefix:
        claude-*        → Anthropic SDK (ANTHROPIC_API_KEY)
        gpt-* / o1* / o3*  → OpenAI SDK (OPENAI_API_KEY)
        gemini-*        → Google GenAI SDK (GOOGLE_API_KEY or GEMINI_API_KEY)
        http:// https:// → OpenAI-compatible HTTP (GRADATA_HTTP_API_KEY)
        <anything else> → Anthropic (default, same as claude-*)

    Returns the raw text response or None on any failure.
    """
    m = model.lower()
    if m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
        return _call_openai(model, system, user_prompt, max_tokens, timeout)
    if m.startswith("gemini-"):
        return _call_gemini(model, system, user_prompt, max_tokens, timeout)
    if m.startswith("http://") or m.startswith("https://"):
        return _call_http(model, system, user_prompt, max_tokens, timeout)
    # Default: Anthropic (covers claude-* and unknown prefixes).
    return _call_anthropic(model, system, user_prompt, max_tokens, timeout)


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

    raw = call_provider(model, _SYSTEM_PROMPT, user_prompt)
    if raw is None:
        _log.debug("synth skipped: all providers failed or no key set")
        return None

    block = _extract_wisdom_block(raw)
    if not block or len(block) < 50:
        _log.debug("synth output malformed or too short")
        return None

    _write_cache(brain_dir, cache_key, block)
    _log.debug("synth ok (%d chars)", len(block))
    return block
