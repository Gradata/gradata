"""Rule-to-Hook graduation — deterministic rules auto-generate enforcement."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event type constants (emitted from CLI + future manifest.demote paths)
# ---------------------------------------------------------------------------

# Emitted when a hook-enforced rule gets a human-authored text patch that
# reverts to soft prompt injection (manifest.demote path, cmd_rule_remove).
RULE_PATCH_REVERTED = "RULE_PATCH_REVERTED"
# Emitted when an installed generated hook is removed (demote path).
HOOK_DEMOTED = "HOOK_DEMOTED"


# ---------------------------------------------------------------------------
# Empirical promotion gate (council verdict, Phase 5)
# ---------------------------------------------------------------------------

PROMOTION_MIN_FIRE_COUNT = 10
PROMOTION_MIN_DISTINCT_SESSIONS = 3
PROMOTION_REVERSAL_LOOKBACK_DAYS = 30


def _resolve_events_path() -> Path | None:
    """Best-effort events.jsonl resolution (None when no brain is configured)."""
    try:
        from gradata import _paths as _p
        p = Path(_p.EVENTS_JSONL)
        return p if p.is_file() else None
    except Exception:
        return None


def count_distinct_sessions(lesson) -> int:
    """Count distinct sessions this lesson's correction chain spans.

    Uses the proof-chain IDs on the lesson (``correction_event_ids``) as the
    activation trail — matches the existing audit.py contract. Falls back to
    0 when no chain exists or events.jsonl is unreachable.
    """
    ids = list(getattr(lesson, "correction_event_ids", []) or [])
    if not ids:
        return 0
    events_path = _resolve_events_path()
    if events_path is None:
        return 0
    target = set(ids)
    sessions: set[int] = set()
    try:
        with events_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(evt.get("id")) in target or evt.get("id") in target:
                    s = evt.get("session")
                    if s is not None:
                        sessions.add(s)
    except OSError as exc:
        _log.debug("count_distinct_sessions: %s", exc)
        return 0
    return len(sessions)


def count_human_reversals(rule_id: str, since_days: int = PROMOTION_REVERSAL_LOOKBACK_DAYS) -> int:
    """Count RULE_PATCH_REVERTED + HOOK_DEMOTED events tied to ``rule_id`` in the window.

    Scans events.jsonl directly so the helper works even when SQLite is
    unavailable. Missing event file => 0 (no reversals recorded yet).
    """
    if not rule_id:
        return 0
    events_path = _resolve_events_path()
    if events_path is None:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    count = 0
    try:
        with events_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if evt.get("type") not in (RULE_PATCH_REVERTED, HOOK_DEMOTED):
                    continue
                data = evt.get("data") or {}
                if data.get("rule_id") != rule_id:
                    continue
                ts = evt.get("ts")
                if ts:
                    try:
                        evt_time = datetime.fromisoformat(ts)
                    except ValueError:
                        continue
                    if evt_time < cutoff:
                        continue
                count += 1
    except OSError as exc:
        _log.debug("count_human_reversals: %s", exc)
        return 0
    return count


def _passes_empirical_gate(lesson) -> tuple[bool, str]:
    """Council verdict gate: promotion requires empirical track record.

    Checks:
      - ``lesson.fire_count >= PROMOTION_MIN_FIRE_COUNT``
      - distinct sessions across ``correction_event_ids`` >= PROMOTION_MIN_DISTINCT_SESSIONS
      - zero human reversals in the last PROMOTION_REVERSAL_LOOKBACK_DAYS days

    Returns ``(passed, reason)``. The reason is populated on failure.
    """
    if lesson is None:
        return False, "no lesson provided to empirical gate"
    fire_count = int(getattr(lesson, "fire_count", 0) or 0)
    if fire_count < PROMOTION_MIN_FIRE_COUNT:
        return False, (
            f"fire_count {fire_count} < {PROMOTION_MIN_FIRE_COUNT} "
            "(council empirical gate)"
        )
    sessions = count_distinct_sessions(lesson)
    if sessions < PROMOTION_MIN_DISTINCT_SESSIONS:
        return False, (
            f"distinct sessions {sessions} < {PROMOTION_MIN_DISTINCT_SESSIONS} "
            "(council empirical gate)"
        )
    # Derive the rule_id the same way rule_engine does.
    try:
        from gradata.rules.rule_engine import _make_rule_id
        rule_id = _make_rule_id(lesson)
    except Exception:
        rule_id = ""
    reversals = count_human_reversals(rule_id, since_days=PROMOTION_REVERSAL_LOOKBACK_DAYS)
    if reversals > 0:
        return False, (
            f"{reversals} human reversal(s) in last "
            f"{PROMOTION_REVERSAL_LOOKBACK_DAYS}d (council empirical gate)"
        )
    return True, "empirical gate passed"


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
    SESSION_DIRECTIVE = "session_directive"  # Positive session-start directive (use X, OODA, etc.)
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
    # Tighter variant: require an anchoring preposition + target noun so generic
    # phrases like "there's no secret sauce" don't collide with the secret rule.
    (re.compile(r"\bno secrets?\b.*\b(in|to|into)\b.*\b(code|commit|commits|repo|source)\b"), DeterminismCheck.COMMAND_BLOCK, "secret_scan", _SECRET_REGEX),
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
    # Positive session directives — "always use X", "use X before Y", "start with X"
    (re.compile(r"(always |must )?(use|run|invoke|apply|start with|begin with) (superpowers|council|worktree|brainstorm|parallel)"), DeterminismCheck.SESSION_DIRECTIVE, "session_directive", "positive_directive"),
    (re.compile(r"before (building|implementing|coding|creating|planning).*(use|run|invoke|apply)"), DeterminismCheck.SESSION_DIRECTIVE, "session_directive", "positive_directive"),
    (re.compile(r"(use|run|invoke|apply).*(before|prior to) (building|implementing|coding|creating|planning)"), DeterminismCheck.SESSION_DIRECTIVE, "session_directive", "positive_directive"),
    # OODA / autonomous mode
    (re.compile(r"(ooda|godmode|autonomous|never stop to ask|never ask permission|keep building)"), DeterminismCheck.SESSION_DIRECTIVE, "session_directive", "positive_directive"),
    # Parallel agents
    (re.compile(r"(spawn|use) parallel (agents?|tasks?|workers?)"), DeterminismCheck.SESSION_DIRECTIVE, "session_directive", "positive_directive"),
    (re.compile(r"never work sequential"), DeterminismCheck.SESSION_DIRECTIVE, "session_directive", "positive_directive"),
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
    "session_directive",
}

# Templates that fire on PostToolUse (after an edit/write) rather than PreToolUse.
# install_hook routes these to GRADATA_HOOK_ROOT_POST instead of GRADATA_HOOK_ROOT.
_POST_TOOL_TEMPLATES = {"auto_test"}

# Templates that fire on SessionStart rather than PreToolUse.
# install_hook routes these to GRADATA_HOOK_ROOT_SESSION instead of GRADATA_HOOK_ROOT.
_SESSION_START_TEMPLATES = {"session_directive"}

# Templates whose self-test we skip during graduation. auto_test would need a
# real test file on disk to exit 2; synthesizing that during graduation is more
# noise than signal, so we trust the template and skip. session_directive hooks
# output JSON to stdout (no blocking) so there is nothing to self-test against.
_TEMPLATES_SKIP_SELFTEST = {"auto_test", "session_directive"}

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

    # session_directive: self-contained JS — no template file needed
    if candidate.hook_template == "session_directive":
        # Sanitize before embedding in JS.  json.dumps() handles backslash and
        # double-quote but NOT backtick (template-literal injection) or
        # </script>-style breakouts.  Apply js_template escaping after dumps.
        from gradata.enhancements._sanitize import sanitize_lesson_content

        # Neutralize prompt-injection markers in the text that will surface to
        # the LLM via the mandatory-directive wrapper.
        clean_description = sanitize_lesson_content(
            candidate.rule_description, "llm_prompt"
        )
        # json.dumps produces a valid JSON string literal including surrounding
        # quotes.  Then strip residual template-literal / script-breakout
        # characters that json.dumps does not touch.
        js_literal = json.dumps(clean_description)
        js_literal = sanitize_lesson_content(js_literal, "js_template")

        directive_js = (
            "#!/usr/bin/env node\n"
            "// Auto-generated session-start directive hook\n"
            f"// Source hash: {_source_hash(candidate.rule_description)}\n"
            "const data = JSON.parse(require('fs').readFileSync(0, 'utf-8') || '{}');\n"
            "const directive = {\n"
            "  result: [\n"
            "    '<mandatory-directive>',\n"
            f"    {js_literal},\n"
            "    '</mandatory-directive>',\n"
            "  ].join('\\n')\n"
            "};\n"
            "process.stdout.write(JSON.stringify(directive) + '\\n');\n"
        )
        return directive_js

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

    # file_size_check: template_arg holds the line limit as a string
    if candidate.hook_template == "file_size_check":
        limit = candidate.template_arg or "500"
        return (
            tmpl
            .replace("{{LINE_LIMIT}}", limit)
            .replace("{{RULE_TEXT}}", safe_text)
            .replace("{{SOURCE_HASH}}", _source_hash(candidate.rule_description))
        )

    pattern_literal = f"new RegExp({json.dumps(candidate.template_arg)})"
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
            encoding="utf-8",
            errors="replace",
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
    """Where generated hooks get installed. Overridable via env for tests."""
    override = os.environ.get("GRADATA_HOOK_ROOT")
    if override:
        return Path(override)
    return Path(".claude/hooks/pre-tool/generated")


def install_hook(slug: str, hook_source: str, *, template: str) -> Path:
    """Write rendered hook source. Routes to post-tool dir for PostToolUse templates.

    PreToolUse hooks -> GRADATA_HOOK_ROOT (default .claude/hooks/pre-tool/generated/).
    PostToolUse hooks (e.g. auto_test) -> GRADATA_HOOK_ROOT_POST
    (default .claude/hooks/post-tool/generated/).
    SessionStart hooks (e.g. session_directive) -> GRADATA_HOOK_ROOT_SESSION
    (default .claude/hooks/session-start/generated/).

    Creates the directory if needed. Chmods to 0o755 on platforms that support it.
    """
    if template in _SESSION_START_TEMPLATES:
        override = os.environ.get("GRADATA_HOOK_ROOT_SESSION")
        root = Path(override) if override else Path(".claude/hooks/session-start/generated")
    elif template in _POST_TOOL_TEMPLATES:
        override = os.environ.get("GRADATA_HOOK_ROOT_POST")
        root = Path(override) if override else Path(".claude/hooks/post-tool/generated")
    else:
        root = _hook_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{slug}.js"
    # Preserve LF line endings regardless of platform
    path.write_text(hook_source, encoding="utf-8", newline="\n")
    # Windows or filesystem that doesn't support chmod will raise; suppress.
    with contextlib.suppress(Exception):
        path.chmod(0o755)
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


def promote(
    description: str,
    confidence: float,
    *,
    brain=None,
    positive_example: str | None = None,
    source: str = "promote",
    lesson=None,
) -> GenerationResult:
    """Public entry point: classify + generate + install a hook for a rule.

    Phase 5 auto-promotion: a convenience wrapper around classify_rule +
    try_generate that callers outside the graduation pipeline (CLI,
    tests, external tooling) can use to promote a single rule. Callers
    that need lesson-state round-tripping (setting ``metadata.how_enforced``
    on the source Lesson) should mutate the lesson themselves after checking
    ``result.installed`` — promote() intentionally does not touch lessons.md
    so it stays composable with the graduation loop's own persistence step.

    When ``lesson`` is provided, the council empirical gate runs BEFORE
    generation: ``fire_count >= 10``, distinct sessions across the
    correction proof-chain >= 3, and zero human reversals in the last
    30 days. Failing the gate returns ``installed=False`` with a
    ``reason`` explaining which check blocked promotion.

    Returns a GenerationResult. Not-deterministic rules return
    ``installed=False`` with an explanatory reason; callers should fall back
    to prompt injection.
    """
    candidate = classify_rule(description, confidence)
    if candidate.determinism == DeterminismCheck.NOT_DETERMINISTIC:
        return GenerationResult(
            installed=False,
            reason=candidate.reason,
        )
    if lesson is not None:
        passed, reason = _passes_empirical_gate(lesson)
        if not passed:
            _log.debug("promote blocked by empirical gate: %s", reason)
            return GenerationResult(installed=False, reason=reason)
    return try_generate(
        candidate,
        positive_example=positive_example,
        brain=brain,
        source=source,
    )


def demote(slug: str, *, brain=None, source: str = "demote") -> GenerationResult:
    """Remove an installed hook file. Inverse of promote().

    Looks in both pre-tool and post-tool generated directories. Returns a
    GenerationResult whose ``installed`` field is True iff the file existed
    and was removed, with ``hook_path`` set to the removed path.

    Does not touch lessons.md — callers should clear
    ``metadata.how_enforced`` on the matching lesson themselves to re-enable
    text injection at the next graduation pass.
    """
    roots = [_hook_root()]
    post_override = os.environ.get("GRADATA_HOOK_ROOT_POST")
    post_root = Path(post_override) if post_override else Path(".claude/hooks/post-tool/generated")
    roots.append(post_root)

    for root in roots:
        target = root / f"{slug}.js"
        if target.exists():
            try:
                target.unlink()
            except OSError as exc:
                return GenerationResult(
                    installed=False,
                    reason=f"unlink failed: {exc}",
                    hook_path=target,
                )
            if brain is not None:
                with contextlib.suppress(Exception):
                    brain.emit("RULE_TO_HOOK_REMOVED", source, {
                        "slug": slug,
                        "hook_path": str(target),
                    })
                # Mirror the removal as a HOOK_DEMOTED event so the
                # empirical gate's reversal counter can see it. rule_id
                # is unknown at this layer (callers that have it should
                # emit RULE_PATCH_REVERTED separately); we tag with slug
                # so CLI-level emits can correlate.
                with contextlib.suppress(Exception):
                    brain.emit(HOOK_DEMOTED, source, {
                        "slug": slug,
                        "hook_path": str(target),
                    })
            return GenerationResult(
                installed=True,
                reason=f"removed {target}",
                hook_path=target,
            )
    return GenerationResult(
        installed=False,
        reason=f"no hook file found for slug: {slug}",
    )


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
    )
    return GenerationResult(
        installed=True,
        reason=f"installed at {path}",
        hook_path=path,
    )
