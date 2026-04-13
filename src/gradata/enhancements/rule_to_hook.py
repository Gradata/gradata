"""Rule-to-Hook graduation — deterministic rules auto-generate enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class EnforcementType(StrEnum):
    """How a rule is enforced."""

    PROMPT_INJECTION = "prompt_injection"  # Default: injected into LLM context
    HOOK = "hook"  # Claude Code hook (shell script)
    MIDDLEWARE = "middleware"  # API wrapper (Python function)
    GUARDRAIL = "guardrail"  # LangChain/CrewAI guard


class DeterminismCheck(StrEnum):
    """Why a rule is or isn't deterministic."""

    REGEX_PATTERN = "regex_pattern"  # Can be checked with regex (e.g., no em dashes)
    FILE_CHECK = "file_check"  # Can verify file properties (size, existence)
    COMMAND_BLOCK = "command_block"  # Can block specific commands
    TEST_TRIGGER = "test_trigger"  # Can trigger test runs
    NOT_DETERMINISTIC = "not_deterministic"  # Requires LLM judgment


@dataclass
class HookCandidate:
    """A rule that could be promoted to a hook."""

    rule_description: str
    rule_confidence: float
    determinism: DeterminismCheck
    enforcement: EnforcementType
    hook_template: str  # Template name or inline script
    reason: str  # Why this rule is/isn't promotable
    block_pattern: str | None = None  # Literal regex pattern the hook blocks on


# Patterns that indicate a rule is deterministic.
# Each entry: (regex matching rule description, check type, hook template name, block pattern)
DETERMINISTIC_PATTERNS: list[tuple[str, DeterminismCheck, str, str | None]] = [
    (r"never use em.?dash", DeterminismCheck.REGEX_PATTERN, "regex_replace", "\u2014"),
    (r"no em.?dash", DeterminismCheck.REGEX_PATTERN, "regex_replace", "\u2014"),
    (r"don.t use em.?dash", DeterminismCheck.REGEX_PATTERN, "regex_replace", "\u2014"),
    (r"keep files? under \d+ lines?", DeterminismCheck.FILE_CHECK, "file_size_check", None),
    (r"files? under \d+ lines?", DeterminismCheck.FILE_CHECK, "file_size_check", None),
    (r"never (commit|push) secret", DeterminismCheck.COMMAND_BLOCK, "secret_scan", None),
    (r"no (hardcod|hardcode).+secret", DeterminismCheck.COMMAND_BLOCK, "secret_scan", None),
    (r"run tests? after", DeterminismCheck.TEST_TRIGGER, "auto_test", None),
    (r"always run tests?", DeterminismCheck.TEST_TRIGGER, "auto_test", None),
    (r"read.+before edit", DeterminismCheck.FILE_CHECK, "read_before_edit", None),
    (r"always read.+before", DeterminismCheck.FILE_CHECK, "read_before_edit", None),
    (r"never (rm|delete|remove).+rf", DeterminismCheck.COMMAND_BLOCK, "destructive_block", None),
    (r"never force.?push", DeterminismCheck.COMMAND_BLOCK, "destructive_block", None),
    (r"never.*format.*f.?string.*python.?-c", DeterminismCheck.COMMAND_BLOCK, "fstring_block", None),
]


def classify_rule(description: str, confidence: float) -> HookCandidate:
    """Classify whether a graduated rule can become a hook.

    Returns a HookCandidate indicating if/how the rule can be enforced
    deterministically, or NOT_DETERMINISTIC if it requires LLM judgment.
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0.0, 1.0]")
    desc_lower = description.lower()

    for pattern, check_type, template, block_pat in DETERMINISTIC_PATTERNS:
        if re.search(pattern, desc_lower):
            return HookCandidate(
                rule_description=description,
                rule_confidence=confidence,
                determinism=check_type,
                enforcement=EnforcementType.HOOK,
                hook_template=template,
                block_pattern=block_pat,
                reason=f"Matches deterministic pattern: {pattern}",
            )

    return HookCandidate(
        rule_description=description,
        rule_confidence=confidence,
        determinism=DeterminismCheck.NOT_DETERMINISTIC,
        enforcement=EnforcementType.PROMPT_INJECTION,
        hook_template="",
        block_pattern=None,
        reason="Requires LLM judgment — stays as prompt injection",
    )


def find_hook_candidates(
    lessons: list[dict],
    min_confidence: float = 0.90,
) -> list[HookCandidate]:
    """Scan graduated rules and return those promotable to hooks.

    Only considers RULE and META-RULE state lessons above min_confidence.
    """
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be in [0.0, 1.0]")
    candidates: list[HookCandidate] = []
    for lesson in lessons:
        status = lesson.get("status", "").upper()
        if status not in ("RULE", "META-RULE", "META_RULE"):
            continue
        conf = lesson.get("confidence", 0.0)
        if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
            continue
        if conf < min_confidence:
            continue
        candidate = classify_rule(lesson.get("description", ""), conf)
        if candidate.determinism != DeterminismCheck.NOT_DETERMINISTIC:
            candidates.append(candidate)
    return candidates


_TEMPLATE_DIR = Path(__file__).parent.parent / "hooks" / "templates"
_IMPLEMENTED_TEMPLATES = {"regex_replace"}


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def render_hook(candidate: HookCandidate) -> str | None:
    """Render a HookCandidate into executable JS hook source.

    Returns None if the candidate is non-deterministic OR the candidate's
    template isn't implemented yet (v1 ships regex_replace only).
    """
    if candidate.enforcement != EnforcementType.HOOK:
        return None
    if candidate.hook_template not in _IMPLEMENTED_TEMPLATES:
        return None
    if candidate.block_pattern is None:
        return None

    template_path = _TEMPLATE_DIR / f"{candidate.hook_template}.js.tmpl"
    if not template_path.exists():
        return None

    # Read with explicit UTF-8; preserve LF endings (shebang requires LF on Unix)
    tmpl = template_path.read_text(encoding="utf-8")

    pattern_literal = f"new RegExp({json.dumps(candidate.block_pattern)})"
    safe_text = (
        candidate.rule_description
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
    )

    return (
        tmpl
        .replace("{{PATTERN_LITERAL}}", pattern_literal)
        .replace("{{RULE_TEXT}}", safe_text)
        .replace("{{SOURCE_HASH}}", _source_hash(candidate.rule_description))
    )


def self_test(
    hook_source: str | None,
    *,
    positive: str,
    tool_name: str = "Write",
) -> bool:
    """Run a rendered hook against a positive example.

    Returns True iff the hook exits with code 2 (block) on violating input.
    Safe to call with hook_source=None (returns False).
    """
    if not hook_source:
        return False

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
        newline="\n",
    ) as f:
        f.write(hook_source)
        hook_path = Path(f.name)
    try:
        tool_input_key = "command" if tool_name == "Bash" else "content"
        payload = {
            "tool_name": tool_name,
            "tool_input": {tool_input_key: positive},
        }
        proc = subprocess.run(
            ["node", str(hook_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return proc.returncode == 2
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    finally:
        try:
            hook_path.unlink()
        except Exception:
            pass


@dataclass
class GenerationResult:
    """Outcome of attempting to graduate a HookCandidate into an installed hook."""

    installed: bool
    reason: str
    hook_path: Path | None = None


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "rule"


def _hook_root() -> Path:
    """Where generated hooks get installed. Overridable via env for tests."""
    override = os.environ.get("GRADATA_HOOK_ROOT")
    if override:
        return Path(override)
    return Path(".claude/hooks/pre-tool/generated")


def install_hook(slug: str, hook_source: str) -> Path:
    """Write rendered hook source to GRADATA_HOOK_ROOT/<slug>.js.

    Creates the directory if needed. Chmods to 0o755 on platforms that support it.
    """
    root = _hook_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{slug}.js"
    # Preserve LF line endings regardless of platform
    path.write_text(hook_source, encoding="utf-8", newline="\n")
    try:
        path.chmod(0o755)
    except Exception:
        pass  # Windows or filesystem that doesn't support chmod
    return path


def _synthesize_positive(candidate: HookCandidate) -> str:
    """Produce a minimal string that should match the block_pattern for self-test
    when no captured violating text is supplied.
    """
    p = candidate.block_pattern or ""
    # Em-dash: the pattern IS the literal, wrap in ascii context
    if "\u2014" in p:
        return "hello \u2014 world"
    # Best-effort: embed the literal pattern
    return f"x{p}y"


def try_generate(
    candidate: HookCandidate,
    *,
    positive_example: str | None = None,
) -> GenerationResult:
    """Attempt to graduate a HookCandidate into an installed PreToolUse hook.

    Flow: render -> self-test -> install on pass.

    Args:
        candidate: A HookCandidate from classify_rule.
        positive_example: Optional captured violating text to self-test against.
            If None, a minimal example is synthesized from block_pattern.

    Returns a GenerationResult describing the outcome.
    """
    if candidate.enforcement != EnforcementType.HOOK:
        return GenerationResult(
            installed=False,
            reason="candidate is not a hook (advisory / not deterministic)",
        )

    rendered = render_hook(candidate)
    if rendered is None:
        return GenerationResult(
            installed=False,
            reason=f"render skipped: template '{candidate.hook_template}' not implemented or missing pattern",
        )

    positive = positive_example or _synthesize_positive(candidate)
    tool_name = "Bash" if candidate.hook_template in {"destructive_block", "fstring_block", "secret_scan"} else "Write"

    if not self_test(rendered, positive=positive, tool_name=tool_name):
        return GenerationResult(
            installed=False,
            reason=f"self-test did not block positive example: {positive!r}",
        )

    path = install_hook(_slug(candidate.rule_description), rendered)
    return GenerationResult(
        installed=True,
        reason=f"installed at {path}",
        hook_path=path,
    )
