"""Rule-to-Hook graduation — deterministic rules auto-generate enforcement."""

from __future__ import annotations

import contextlib
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
    template_arg: str | None = None  # Template-specific argument: regex literal, line count, sentinel, etc.


# Shared secret detection regex (API keys, tokens, private keys)
_SECRET_REGEX = r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY-----|xoxb-[A-Za-z0-9-]+)"

# Shared root-file regex (single-segment file path ending in common extensions)
_ROOT_FILE_REGEX = r"^[^/\\]+\.(py|md|json|txt|js|ts|yml|yaml)$"


# Patterns that indicate a rule is deterministic.
# Each entry: (compiled regex matching rule description, check type, hook template name, template arg)
DETERMINISTIC_PATTERNS: list[tuple[re.Pattern[str], DeterminismCheck, str, str | None]] = [
    # Em-dash regex replace
    (re.compile(r"never use em.?dash"), DeterminismCheck.REGEX_PATTERN, "regex_replace", "\u2014"),
    (re.compile(r"no em.?dash"), DeterminismCheck.REGEX_PATTERN, "regex_replace", "\u2014"),
    (re.compile(r"don.t use em.?dash"), DeterminismCheck.REGEX_PATTERN, "regex_replace", "\u2014"),
    (re.compile(r"(avoid|prefer not to use) em.?dash"), DeterminismCheck.REGEX_PATTERN, "regex_replace", "\u2014"),
    (re.compile(r"em.?dash.+(banned|forbidden|not allowed)"), DeterminismCheck.REGEX_PATTERN, "regex_replace", "\u2014"),
    # File size check — capture group 1 holds the line limit
    (re.compile(r"keep files? under (\d+) lines?"), DeterminismCheck.FILE_CHECK, "file_size_check", None),
    (re.compile(r"files? must be under (\d+) lines?"), DeterminismCheck.FILE_CHECK, "file_size_check", None),
    (re.compile(r"no files? over (\d+) lines?"), DeterminismCheck.FILE_CHECK, "file_size_check", None),
    (re.compile(r"files? under (\d+) lines?"), DeterminismCheck.FILE_CHECK, "file_size_check", None),
    # Secret scan
    (re.compile(r"never (commit|push) secret"), DeterminismCheck.COMMAND_BLOCK, "secret_scan", _SECRET_REGEX),
    (re.compile(r"no (hardcod|hardcode).+secret"), DeterminismCheck.COMMAND_BLOCK, "secret_scan", _SECRET_REGEX),
    (re.compile(r"never commit secret|no secret|never push secret"), DeterminismCheck.COMMAND_BLOCK, "secret_scan", _SECRET_REGEX),
    (re.compile(r"no hardcoded api key|never hardcode api key|no api key in code"), DeterminismCheck.COMMAND_BLOCK, "secret_scan", _SECRET_REGEX),
    # Auto test — PostToolUse, runs pytest against test_<basename>.py after edits.
    # template_arg is a sentinel ("auto_test") because render_hook gates on
    # template_arg being non-None; the template itself ignores it.
    (re.compile(r"run tests? after"), DeterminismCheck.TEST_TRIGGER, "auto_test", "auto_test"),
    (re.compile(r"always run tests?"), DeterminismCheck.TEST_TRIGGER, "auto_test", "auto_test"),
    # Read before edit (not shipped yet — stateful)
    (re.compile(r"read.+before edit"), DeterminismCheck.FILE_CHECK, "read_before_edit", None),
    (re.compile(r"always read.+before"), DeterminismCheck.FILE_CHECK, "read_before_edit", None),
    # Destructive command blocks
    (re.compile(r"never (rm|delete|remove).+-?rf"), DeterminismCheck.COMMAND_BLOCK, "destructive_block", r"rm\s+-[rf]+|rm\s+.*-[rf]+"),
    (re.compile(r"never force.?push|don.t force.?push|no force push"), DeterminismCheck.COMMAND_BLOCK, "destructive_block", r"git\s+push.*--force|git\s+push.*-f\b|git\s+push.*\+"),
    (re.compile(r"never drop.*table|no drop table"), DeterminismCheck.COMMAND_BLOCK, "destructive_block", r"DROP\s+TABLE"),
    (re.compile(r"never kubectl delete|don.t kubectl delete"), DeterminismCheck.COMMAND_BLOCK, "destructive_block", r"kubectl\s+delete"),
    (re.compile(r"never reset.+hard|no git reset.*hard"), DeterminismCheck.COMMAND_BLOCK, "destructive_block", r"git\s+reset.*--hard"),
    # f-string block
    (re.compile(r"never.*format.*f.?string.*python.?-c"), DeterminismCheck.COMMAND_BLOCK, "fstring_block", r"python\s+-c\s+[\"\'][^\"\']*f[\"\']"),
    (re.compile(r"never.*python.?-c.*f.?string"), DeterminismCheck.COMMAND_BLOCK, "fstring_block", r"python\s+-c\s+[\"\'][^\"\']*f[\"\']"),
    # Root-file save
    (re.compile(r"never save.+root|no files? (in|at) root|don.t save.+root"), DeterminismCheck.FILE_CHECK, "root_file_save", _ROOT_FILE_REGEX),
    (re.compile(r"(keep|put) (files|scripts) in (subfolder|subdir)"), DeterminismCheck.FILE_CHECK, "root_file_save", _ROOT_FILE_REGEX),
    (re.compile(r"never commit.+to root|no commits to root"), DeterminismCheck.FILE_CHECK, "root_file_save", _ROOT_FILE_REGEX),
]


def classify_rule(description: str, confidence: float) -> HookCandidate:
    """Classify whether a graduated rule can become a hook.

    Returns a HookCandidate indicating if/how the rule can be enforced
    deterministically, or NOT_DETERMINISTIC if it requires LLM judgment.
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0.0, 1.0]")
    desc_lower = description.lower()

    for pattern, check_type, template, tmpl_arg in DETERMINISTIC_PATTERNS:
        m = pattern.search(desc_lower)
        if m:
            # file_size_check: capture group 1 holds the line limit as a string
            if template == "file_size_check" and m.groups():
                tmpl_arg = m.group(1)
            return HookCandidate(
                rule_description=description,
                rule_confidence=confidence,
                determinism=check_type,
                enforcement=EnforcementType.HOOK,
                hook_template=template,
                template_arg=tmpl_arg,
                reason=f"Matches deterministic pattern: {pattern.pattern}",
            )

    return HookCandidate(
        rule_description=description,
        rule_confidence=confidence,
        determinism=DeterminismCheck.NOT_DETERMINISTIC,
        enforcement=EnforcementType.PROMPT_INJECTION,
        hook_template="",
        template_arg=None,
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
_IMPLEMENTED_TEMPLATES = {
    "regex_replace",
    "fstring_block",
    "root_file_save",
    "destructive_block",
    "secret_scan",
    "file_size_check",
    "auto_test",
}

# Templates that fire on PostToolUse (after an edit/write) rather than PreToolUse.
# install_hook routes these to GRADATA_HOOK_ROOT_POST instead of GRADATA_HOOK_ROOT.
_POST_TOOL_TEMPLATES = {"auto_test"}

# Templates whose self-test we skip during graduation. auto_test would need a
# real test file on disk to exit 2; synthesizing that during graduation is more
# noise than signal, so we trust the template and skip.
_TEMPLATES_SKIP_SELFTEST = {"auto_test"}

# Templates that receive the violating text as a Bash command rather than Write content.
_BASH_TEMPLATES = {"destructive_block", "fstring_block"}

# Templates that receive the violating text as a Write file_path rather than content.
_WRITE_PATH_TEMPLATES = {"root_file_save"}


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def render_hook(candidate: HookCandidate) -> str | None:
    """Render a HookCandidate into executable JS hook source.

    Returns None if the candidate is non-deterministic OR the template file
    isn't present.
    """
    if candidate.enforcement != EnforcementType.HOOK:
        return None
    if candidate.hook_template not in _IMPLEMENTED_TEMPLATES:
        return None
    if candidate.template_arg is None:
        return None

    template_path = _TEMPLATE_DIR / f"{candidate.hook_template}.js.tmpl"
    # Read with explicit UTF-8; preserve LF endings (shebang requires LF on Unix)
    try:
        tmpl = template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    safe_text = (
        candidate.rule_description
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
    )

    # file_size_check uses {{LINE_LIMIT}}; all other templates use {{PATTERN_LITERAL}}.
    if candidate.hook_template == "file_size_check":
        tmpl = tmpl.replace("{{LINE_LIMIT}}", candidate.template_arg or "500")
    else:
        pattern_literal = f"new RegExp({json.dumps(candidate.template_arg)})"
        tmpl = tmpl.replace("{{PATTERN_LITERAL}}", pattern_literal)

    return (
        tmpl
        .replace("{{RULE_TEXT}}", safe_text)
        .replace("{{SOURCE_HASH}}", _source_hash(candidate.rule_description))
    )


def self_test(
    hook_source: str | None,
    *,
    positive: str,
    tool_name: str = "Write",
    tool_input_key: str | None = None,
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
        if tool_input_key is None:
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
        with contextlib.suppress(Exception):
            hook_path.unlink()


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
    """Where generated hooks get installed. Overridable via env for tests.

    Delegates to the shared resolver in ``gradata.hooks._manifest`` so there
    is exactly one source of truth for the hook-root default path.
    """
    from gradata.hooks import _manifest as _mf
    return _mf._hook_root("pre")


def install_hook(
    slug: str,
    hook_source: str,
    *,
    template: str,
    candidate: HookCandidate | None = None,
) -> Path:
    """Write rendered hook source AND register the rule in the bundled manifest.

    PreToolUse hooks -> GRADATA_HOOK_ROOT (default .claude/hooks/pre-tool/generated/).
    PostToolUse hooks (e.g. auto_test) -> GRADATA_HOOK_ROOT_POST
    (default .claude/hooks/post-tool/generated/).

    Creates the directory if needed. Chmods to 0o755 on platforms that support it.

    Also upserts a manifest entry alongside the legacy .js file so the bundled
    dispatcher (_dispatcher.js) can evaluate this rule in one shared node
    process. The .js file is kept for backwards compatibility and for rules
    that the dispatcher doesn't implement inline (e.g. auto_test runs pytest).
    """
    if template in _POST_TOOL_TEMPLATES:
        # Delegate post-tool root to the shared resolver too — keeps the
        # default path in one place.
        from gradata.hooks import _manifest as _mf
        root = _mf._hook_root("post")
        kind = "post"
    else:
        root = _hook_root()
        kind = "pre"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{slug}.js"
    # Preserve LF line endings regardless of platform
    path.write_text(hook_source, encoding="utf-8", newline="\n")
    with contextlib.suppress(Exception):
        # Windows or filesystem that doesn't support chmod — never fatal.
        path.chmod(0o755)

    # Best-effort: update the bundled manifest. Never fail install on manifest
    # error — the legacy per-file runner still works as a fallback.
    try:
        from gradata.hooks import _manifest as mf

        rule_text = (
            candidate.rule_description if candidate is not None else slug.replace("-", " ")
        )
        template_arg = candidate.template_arg if candidate is not None else None
        mf.upsert_entry(
            slug=slug,
            template=template,
            template_arg=template_arg,
            rule_text=rule_text,
            kind=kind,
        )
    except Exception:
        pass

    return path


def _synthesize_positive(candidate: HookCandidate) -> str:
    """Produce a minimal string that should match the template_arg for self-test
    when no captured violating text is supplied.
    """
    p = candidate.template_arg or ""
    # Em-dash: the pattern IS the literal, wrap in ascii context
    if "\u2014" in p:
        return "hello \u2014 world"
    # Template-specific synthesis
    if candidate.hook_template == "fstring_block":
        return "python -c \"f'{x}'\""
    if candidate.hook_template == "root_file_save":
        return "foo.py"
    if candidate.hook_template == "destructive_block":
        # Cover rm -rf, force push, DROP TABLE, kubectl delete, git reset --hard
        if "rm" in p:
            return "rm -rf /tmp/foo"
        if "push" in p:
            return "git push --force origin main"
        if "DROP" in p:
            return "DROP TABLE users"
        if "kubectl" in p:
            return "kubectl delete pod foo"
        if "reset" in p:
            return "git reset --hard HEAD"
        return "rm -rf /tmp/foo"
    if candidate.hook_template == "secret_scan":
        # Clearly-fake synthetic test key — string-concatenated to slip past
        # naive secret scanners while still matching the regex (sk- + 20+
        # alphanumerics). NOT a real credential; self-test only.
        return "sk" + "-" + "FAKEGRADATASELFTESTKEY000000"
    if candidate.hook_template == "file_size_check":
        limit = int(candidate.template_arg or "500")
        return "x\n" * (limit + 10)
    # Best-effort: embed the literal pattern
    return f"x{p}y"


def _log_outcome(brain, source: str, candidate: HookCandidate, result: GenerationResult) -> None:
    """Emit a RULE_TO_HOOK_INSTALLED/_FAILED event when a brain is provided.

    Never raises — logging failures must not break graduation.
    """
    if brain is None:
        return
    try:
        if result.installed:
            brain.emit("RULE_TO_HOOK_INSTALLED", source, {
                "slug": result.hook_path.stem if result.hook_path else "",
                "rule_text": candidate.rule_description,
                "template": candidate.hook_template,
                "hook_path": str(result.hook_path) if result.hook_path else None,
            })
        else:
            brain.emit("RULE_TO_HOOK_FAILED", source, {
                "rule_text": candidate.rule_description,
                "template": candidate.hook_template,
                "reason": result.reason,
            })
    except Exception:
        pass  # never fail graduation on a logging error



def try_generate(
    candidate: HookCandidate,
    *,
    positive_example: str | None = None,
    brain=None,
    source: str = "graduate",
) -> GenerationResult:
    """Attempt to graduate a HookCandidate into an installed PreToolUse hook.

    Flow: render -> self-test -> install on pass.

    Args:
        candidate: A HookCandidate from classify_rule.
        positive_example: Optional captured violating text to self-test against.
            If None, a minimal example is synthesized from template_arg.
        brain: Optional Brain instance for event logging. When provided,
            emits RULE_TO_HOOK_INSTALLED or RULE_TO_HOOK_FAILED.
        source: Event source label ("graduate" for pipeline, "user_declared" for CLI).

    Returns a GenerationResult describing the outcome.
    """
    result = _compute_generation(candidate, positive_example=positive_example)
    _log_outcome(brain, source, candidate, result)
    return result


def _compute_generation(
    candidate: HookCandidate,
    *,
    positive_example: str | None = None,
) -> GenerationResult:
    """Pure generation logic (no side-effect logging).  Split from try_generate
    so outcome events are emitted in one place."""
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

    if candidate.hook_template not in _TEMPLATES_SKIP_SELFTEST:
        positive = positive_example or _synthesize_positive(candidate)

        if candidate.hook_template in _BASH_TEMPLATES:
            tool_name = "Bash"
            tool_input_key = "command"
        elif candidate.hook_template in _WRITE_PATH_TEMPLATES:
            tool_name = "Write"
            tool_input_key = "file_path"
        else:
            tool_name = "Write"
            tool_input_key = "content"

        if not self_test(rendered, positive=positive, tool_name=tool_name, tool_input_key=tool_input_key):
            return GenerationResult(
                installed=False,
                reason=f"self-test did not block positive example: {positive!r}",
            )

    path = install_hook(
        _slug(candidate.rule_description),
        rendered,
        template=candidate.hook_template,
        candidate=candidate,
    )
    return GenerationResult(
        installed=True,
        reason=f"installed at {path}",
        hook_path=path,
    )
