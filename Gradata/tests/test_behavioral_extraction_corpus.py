"""Corpus tests for correction -> behavioral lesson extraction.

GRA-2089 locks the desired lesson shape before changing extractor logic for
GRA-2061: durable lessons should be procedural/user-behavior rules, not raw
code-diff fragments copied from a one-off edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from gradata.enhancements.behavioral_extractor import extract_instruction


@dataclass(frozen=True)
class ExtractionFixture:
    name: str
    draft: str
    final: str
    expected_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...] = ()


_PROCEDURAL_START_RE = re.compile(
    r"^(always|never|don't|do not|use|include|exclude|check|verify|write|keep|"
    r"avoid|ensure|prefer|present|be|run|test|validate|remove|add)\b",
    re.IGNORECASE,
)
_CODE_FRAGMENT_RE = re.compile(
    r"("
    r"[{};]|"
    r"\b(return|const|let|var|def|class|import|from|async|await|function)\b|"
    r"=>|\.filter\(|\.map\(|json\.parse|open\(|with open\(|"
    r"```|\n\s{2,}|\$\{"
    r")",
    re.IGNORECASE,
)


PASSING_CORPUS = [
    ExtractionFixture(
        name="email_remove_hedging",
        draft="Hey Sam, just checking if you might have time to review this when you get a chance.",
        final="Hey Sam, please review this by Friday.",
        expected_terms=("hedging",),
        forbidden_terms=("just checking", "might have time"),
    ),
    ExtractionFixture(
        name="email_direct_cta_constraint",
        draft="Let me know if you want to see the pricing deck.",
        final="Always ask for a concrete next meeting time after sending the pricing deck.",
        expected_terms=("hedging", "let me know"),
    ),
    ExtractionFixture(
        name="style_bullets_instead_of_prose",
        draft="The launch plan has three steps. First publish the docs. Then send the email. Finally monitor signups.",
        final="The launch plan has three steps.\n- Publish the docs.\n- Send the email.\n- Monitor signups.",
        expected_terms=("list",),
    ),
    ExtractionFixture(
        name="style_concise_executive_summary",
        draft=(
            "The system appears to have several characteristics that could potentially be "
            "interpreted as positive, though there are also a number of nuanced caveats "
            "that may matter depending on the audience."
        ),
        final="The system is promising, but audience risk remains.",
        expected_terms=("hedging", "could potentially"),
        forbidden_terms=("nuanced caveats",),
    ),
    ExtractionFixture(
        name="prompt_add_output_contract",
        draft="Summarize the customer call.",
        final="Summarize the customer call. Always return sections for Pain, Budget, Timeline, and Next Step.",
        expected_terms=("return", "pain", "budget", "timeline", "next step"),
    ),
    ExtractionFixture(
        name="prompt_remove_roleplay",
        draft="Act as a pirate and summarize the support ticket with jokes before the answer.",
        final="Summarize the support ticket plainly before recommending the fix.",
        expected_terms=("summarize", "support ticket", "plainly"),
        forbidden_terms=("pirate", "jokes"),
    ),
    ExtractionFixture(
        name="factual_number_change_generalizes",
        draft="The benchmark improved by 12% on May 3.",
        final="The benchmark improved by 21% on May 4.",
        expected_terms=("verify", "facts", "numbers", "dates"),
        forbidden_terms=("12%", "21%", "May 3", "May 4"),
    ),
    ExtractionFixture(
        name="workflow_added_verification_step",
        draft="After editing the server source, restart Paperclip.",
        final="After editing the server source, run the build, restart Paperclip, and verify /api/health returns ok.",
        expected_terms=("build", "restart", "verify"),
    ),
]


@pytest.mark.parametrize("fixture", PASSING_CORPUS, ids=lambda f: f.name)
def test_extraction_corpus_returns_behavioral_lessons(fixture: ExtractionFixture) -> None:
    lesson = extract_instruction(fixture.draft, fixture.final)

    assert lesson, fixture.name
    assert _PROCEDURAL_START_RE.match(lesson), lesson
    lower = lesson.lower()
    for term in fixture.expected_terms:
        assert term.lower() in lower, lesson
    for term in fixture.forbidden_terms:
        assert term.lower() not in lower, lesson


CODE_FRAGMENT_REGRESSIONS = [
    ExtractionFixture(
        name="typescript_filter_boolean_generalizes",
        draft="const ids = rows.map((row) => row.id);",
        final="const ids = rows.map((row) => row.id).filter(Boolean);",
        expected_terms=("filter", "empty", "missing"),
        forbidden_terms=("row.id).filter(boolean);", "row.id);"),
    ),
    ExtractionFixture(
        name="python_context_manager_generalizes",
        draft="def load(path):\n    return open(path).read()",
        final='def load(path):\n    with open(path, encoding="utf-8") as f:\n        return f.read()',
        expected_terms=("context manager", "encoding"),
        forbidden_terms=("def load", "with open", "return f.read"),
    ),
    ExtractionFixture(
        name="typescript_json_parse_error_handling_generalizes",
        draft="function parse(input) { return JSON.parse(input); }",
        final="function parse(input) { try { return JSON.parse(input); } catch (err) { return null; } }",
        expected_terms=("handle", "parse", "error"),
        forbidden_terms=("JSON.parse", "catch (err)", "return null"),
    ),
]


@pytest.mark.xfail(
    reason="TODO GRA-2061: current deterministic extractor can copy code-diff fragments instead of procedural lessons",
    strict=True,
)
@pytest.mark.parametrize("fixture", CODE_FRAGMENT_REGRESSIONS, ids=lambda f: f.name)
def test_code_edit_corpus_rejects_raw_code_fragments(fixture: ExtractionFixture) -> None:
    lesson = extract_instruction(fixture.draft, fixture.final)

    assert lesson, fixture.name
    assert _PROCEDURAL_START_RE.match(lesson), lesson
    assert not _CODE_FRAGMENT_RE.search(lesson), lesson
    lower = lesson.lower()
    for term in fixture.expected_terms:
        assert term.lower() in lower, lesson
    for term in fixture.forbidden_terms:
        assert term.lower() not in lower, lesson
