import pytest; pytest.importorskip('gradata.enhancements.call_profile', reason='requires gradata_cloud')
import pytest
try:
    import gradata_cloud
    has_cloud = True
except ImportError:
    try:
        from gradata.enhancements import self_improvement
        has_cloud = True
    except ImportError:
        has_cloud = False

pytestmark = pytest.mark.skipif(not has_cloud, reason='requires gradata_cloud')

"""Tests for call profile — behavioral graduation from call transcripts."""
from gradata.enhancements.call_profile import (
    Utterance,
    CallFeatures,
    CallOutcome,
    CallProfile,
    parse_transcript,
    extract_call_features,
    build_call_profile,
    generate_cheat_sheet,
    post_call_audit,
    _discover_patterns,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transcript(user_turns: list[str], prospect_turns: list[str]) -> list[Utterance]:
    """Interleave user and prospect turns into a transcript."""
    utts = []
    t = 0.0
    for i in range(max(len(user_turns), len(prospect_turns))):
        if i < len(user_turns):
            utts.append(Utterance("Alice", user_turns[i], t, t + 5.0))
            t += 5.0
        if i < len(prospect_turns):
            utts.append(Utterance("Prospect", prospect_turns[i], t, t + 5.0))
            t += 5.0
    return utts


def _make_discovery_transcript() -> list[Utterance]:
    """A realistic discovery call transcript."""
    return _make_transcript(
        user_turns=[
            "Hey Tim, thanks for hopping on. How's your week going?",
            "So tell me, what does your current ad workflow look like?",
            "How does that impact your team's bandwidth?",
            "What would it mean for your team if that was solved?",
            "We had a client, an agency similar to yours, who was spending 20 hours a week on that. They cut it to 3.",
            "How much time would you estimate your team spends on manual optimization?",
            "That's significant. What have you tried so far to fix it?",
            "I hear you. Let me show you how our platform handles that. The way it works is...",
            "Does that make sense for your use case?",
            "Great. How about we set up a demo for Thursday at 2pm PT? I'll send over a calendar invite by end of day.",
        ],
        prospect_turns=[
            "Good, busy though. Lots of campaigns to manage.",
            "We run about 30 campaigns across Meta and Google. Mostly manual.",
            "It's killing us honestly. We're always behind on optimization.",
            "It would be huge. We could take on more clients without hiring.",
            "That's exactly our situation. Twenty hours sounds about right.",
            "At least 15-20 hours a week across the team.",
            "We looked at some tools but they're too expensive or don't integrate well.",
            "That looks pretty slick actually.",
            "Yeah that could work for our Meta campaigns for sure.",
            "Thursday works. Send it over.",
        ],
    )


# ---------------------------------------------------------------------------
# Transcript Parsing
# ---------------------------------------------------------------------------

class TestParseTranscript:
    def test_fireflies_format(self):
        sentences = [
            {"speaker_name": "Alice", "text": "Hey how are you?", "start_time": 0.5, "end_time": 2.0},
            {"speaker_name": "Tim", "text": "Good, thanks.", "start_time": 2.1, "end_time": 3.5},
        ]
        utts, user = parse_transcript(sentences, user_speaker="Alice")
        assert len(utts) == 2
        assert user == "Alice"
        assert utts[0].speaker == "Alice"
        assert utts[1].speaker == "Tim"

    def test_auto_detect_user(self):
        sentences = [
            {"speaker_name": "Alice", "text": "Welcome to the call.", "start_time": 0},
            {"speaker_name": "Alice", "text": "Let me start with introductions.", "start_time": 2},
            {"speaker_name": "Tim", "text": "Sure.", "start_time": 4},
            {"speaker_name": "Alice", "text": "Great.", "start_time": 5},
        ]
        utts, user = parse_transcript(sentences)
        assert user == "Alice"  # most turns in first 20%

    def test_empty_transcript(self):
        utts, user = parse_transcript([])
        assert len(utts) == 0

    def test_alternative_keys(self):
        sentences = [
            {"speaker": "Alice", "sentence": "Hello there.", "start_time": 0, "end_time": 1},
        ]
        utts, user = parse_transcript(sentences, user_speaker="Alice")
        assert len(utts) == 1
        assert utts[0].text == "Hello there."


# ---------------------------------------------------------------------------
# Feature Extraction
# ---------------------------------------------------------------------------

class TestExtractFeatures:
    def test_basic_features(self):
        utts = _make_discovery_transcript()
        f = extract_call_features(utts, "Alice", "discovery")
        assert f.call_type == "discovery"
        assert f.total_words > 0
        assert f.user_words > 0
        assert 0 < f.talk_ratio < 1
        assert f.question_count >= 5  # several questions in the transcript
        assert f.user_turns == 10
        assert f.turn_count == 20

    def test_pain_questions_detected(self):
        utts = _make_discovery_transcript()
        f = extract_call_features(utts, "Alice", "discovery")
        assert f.pain_question_count >= 2  # "how does that impact" + "what would it mean"

    def test_story_detected(self):
        utts = _make_discovery_transcript()
        f = extract_call_features(utts, "Alice", "discovery")
        assert f.story_count >= 1  # "We had a client, an agency similar to yours"

    def test_close_attempt_detected(self):
        utts = _make_discovery_transcript()
        f = extract_call_features(utts, "Alice", "discovery")
        assert f.close_attempts >= 1  # "set up a demo for Thursday"

    def test_specific_commitment(self):
        utts = _make_discovery_transcript()
        f = extract_call_features(utts, "Alice", "discovery")
        assert f.specific_commitments >= 1  # "Thursday at 2pm PT"

    def test_empty_transcript(self):
        f = extract_call_features([], "Alice", "discovery")
        assert f.total_words == 0
        assert f.talk_ratio == 0.0

    def test_objection_detection(self):
        utts = _make_transcript(
            user_turns=["What tools have you used?", "I hear that. Our pricing is actually lower than most."],
            prospect_turns=["They're too expensive.", "Hmm, tell me more."],
        )
        f = extract_call_features(utts, "Alice", "discovery")
        assert f.objection_count >= 1
        assert f.objection_responses >= 1

    def test_serialization(self):
        utts = _make_discovery_transcript()
        f = extract_call_features(utts, "Alice", "discovery")
        d = f.to_dict()
        f2 = CallFeatures.from_dict(d)
        assert f2.talk_ratio == round(f.talk_ratio, 2)
        assert f2.question_count == f.question_count


# ---------------------------------------------------------------------------
# Profile Building
# ---------------------------------------------------------------------------

class TestBuildProfile:
    def _make_outcome(self, talk_ratio, pain_qs, outcome):
        f = CallFeatures(
            call_type="discovery",
            talk_ratio=talk_ratio,
            pain_question_count=pain_qs,
            question_count=pain_qs + 3,
            open_question_ratio=0.7,
            story_count=1,
            close_attempts=1,
            discovery_minutes=8.0,
            duration_minutes=30.0,
        )
        return CallOutcome(features=f, outcome=outcome)

    def test_basic_profile(self):
        outcomes = [self._make_outcome(0.35, 3, "advanced")]
        profile = build_call_profile(outcomes, "discovery")
        assert profile.call_type == "discovery"
        assert profile.sample_count == 1
        assert profile.confidence > 0

    def test_confidence_scales(self):
        outcomes_5 = [self._make_outcome(0.35, 3, "advanced") for _ in range(5)]
        outcomes_20 = [self._make_outcome(0.35, 3, "advanced") for _ in range(20)]

        p5 = build_call_profile(outcomes_5, "discovery")
        p20 = build_call_profile(outcomes_20, "discovery")
        assert p20.confidence > p5.confidence

    def test_win_loss_split(self):
        wins = [self._make_outcome(0.35, 4, "advanced") for _ in range(5)]
        losses = [self._make_outcome(0.60, 1, "stalled") for _ in range(5)]
        profile = build_call_profile(wins + losses, "discovery")

        assert profile.win_features is not None
        assert profile.loss_features is not None
        assert profile.win_features.talk_ratio < profile.loss_features.talk_ratio
        assert profile.win_features.pain_question_count > profile.loss_features.pain_question_count

    def test_pattern_discovery(self):
        wins = [self._make_outcome(0.35, 4, "advanced") for _ in range(5)]
        losses = [self._make_outcome(0.60, 1, "stalled") for _ in range(5)]
        profile = build_call_profile(wins + losses, "discovery")

        assert len(profile.patterns) > 0
        pattern_text = " ".join(profile.patterns).lower()
        assert "talk" in pattern_text or "pain" in pattern_text

    def test_incremental_update(self):
        batch1 = [self._make_outcome(0.40, 3, "advanced") for _ in range(5)]
        profile = build_call_profile(batch1, "discovery")

        batch2 = [self._make_outcome(0.35, 4, "advanced") for _ in range(5)]
        updated = build_call_profile(batch2, "discovery", existing=profile)

        assert updated.sample_count == 10
        assert updated.confidence > profile.confidence


# ---------------------------------------------------------------------------
# Pattern Discovery
# ---------------------------------------------------------------------------

class TestPatternDiscovery:
    def test_talk_ratio_pattern(self):
        win = CallFeatures(talk_ratio=0.35)
        loss = CallFeatures(talk_ratio=0.55)
        patterns = _discover_patterns(win, loss, 10)
        assert any("talk" in p.lower() for p in patterns)

    def test_pain_question_pattern(self):
        win = CallFeatures(pain_question_count=4)
        loss = CallFeatures(pain_question_count=1)
        patterns = _discover_patterns(win, loss, 10)
        assert any("pain" in p.lower() for p in patterns)

    def test_no_patterns_below_threshold(self):
        win = CallFeatures(talk_ratio=0.40)
        loss = CallFeatures(talk_ratio=0.42)
        patterns = _discover_patterns(win, loss, 10)
        # Delta too small for talk_ratio pattern
        talk_patterns = [p for p in patterns if "talk" in p.lower()]
        assert len(talk_patterns) == 0

    def test_insufficient_data(self):
        win = CallFeatures(talk_ratio=0.35)
        loss = CallFeatures(talk_ratio=0.55)
        patterns = _discover_patterns(win, loss, 3)  # < 5
        assert len(patterns) == 0


# ---------------------------------------------------------------------------
# Cheat Sheet Generation
# ---------------------------------------------------------------------------

class TestCheatSheet:
    def test_empty_profile(self):
        profile = CallProfile(call_type="discovery")
        sheet = generate_cheat_sheet(profile)
        assert "No call data" in sheet

    def test_instinct_confidence(self):
        profile = CallProfile(
            call_type="discovery",
            sample_count=5,
            confidence=0.15,
            avg_features=CallFeatures(talk_ratio=0.35, question_count=8, pain_question_count=3),
            patterns=["Ask more pain questions"],
        )
        sheet = generate_cheat_sheet(profile)
        assert "CONSIDER" in sheet
        assert "Instinct" in sheet

    def test_rule_confidence(self):
        profile = CallProfile(
            call_type="discovery",
            sample_count=35,
            confidence=0.95,
            avg_features=CallFeatures(talk_ratio=0.35, question_count=8, pain_question_count=3),
            win_features=CallFeatures(talk_ratio=0.35, question_count=10, pain_question_count=4,
                                      discovery_minutes=10, story_count=2, close_attempts=2),
            patterns=["Ask 4+ pain questions", "Spend 10+ min in discovery"],
        )
        sheet = generate_cheat_sheet(profile)
        assert "REQUIRED" in sheet
        assert "Rule" in sheet

    def test_includes_prospect_context(self):
        profile = CallProfile(
            call_type="demo",
            sample_count=10,
            confidence=0.30,
            avg_features=CallFeatures(talk_ratio=0.50),
        )
        sheet = generate_cheat_sheet(profile, prospect_context="Tim Sok — Henge. Trial vs white label decision.")
        assert "Tim Sok" in sheet
        assert "Prospect Context" in sheet


# ---------------------------------------------------------------------------
# Post-Call Audit
# ---------------------------------------------------------------------------

class TestPostCallAudit:
    def test_insufficient_data(self):
        features = CallFeatures()
        profile = CallProfile(call_type="discovery", sample_count=3)
        audit = post_call_audit(features, profile)
        assert audit.score == 1.0
        assert "Not enough data" in audit.summary

    def test_all_checks_pass(self):
        features = CallFeatures(
            talk_ratio=0.35, pain_question_count=4, question_count=10,
            story_count=2, discovery_minutes=10, close_attempts=2,
            commitment_specificity=0.8, longest_monologue=80,
        )
        profile = CallProfile(
            call_type="discovery",
            sample_count=20,
            confidence=0.60,
            win_features=CallFeatures(
                talk_ratio=0.35, pain_question_count=3, question_count=8,
                story_count=1, discovery_minutes=8, close_attempts=1,
                commitment_specificity=0.6, longest_monologue=100,
            ),
        )
        audit = post_call_audit(features, profile)
        assert audit.score == 1.0
        assert "passed" in audit.summary.lower()

    def test_failed_checks(self):
        features = CallFeatures(
            talk_ratio=0.70,  # way too high
            pain_question_count=0,  # no pain questions
            question_count=2,
            story_count=0,
            close_attempts=0,
        )
        profile = CallProfile(
            call_type="discovery",
            sample_count=20,
            confidence=0.60,
            win_features=CallFeatures(
                talk_ratio=0.35, pain_question_count=3, question_count=8,
                story_count=2, discovery_minutes=8, close_attempts=1,
            ),
        )
        audit = post_call_audit(features, profile)
        assert audit.score < 1.0
        failed = [c for c in audit.checks if not c.passed]
        assert len(failed) >= 2  # talk ratio + pain questions at minimum

    def test_severity_scales_with_confidence(self):
        features = CallFeatures(talk_ratio=0.70, pain_question_count=0)
        low_conf = CallProfile(
            call_type="discovery", sample_count=8, confidence=0.24,
            win_features=CallFeatures(talk_ratio=0.35, pain_question_count=3),
        )
        high_conf = CallProfile(
            call_type="discovery", sample_count=35, confidence=0.95,
            win_features=CallFeatures(talk_ratio=0.35, pain_question_count=3),
        )

        audit_low = post_call_audit(features, low_conf)
        audit_high = post_call_audit(features, high_conf)

        low_severities = {c.severity for c in audit_low.checks if not c.passed}
        high_severities = {c.severity for c in audit_high.checks if not c.passed}

        assert "info" in low_severities
        assert "critical" in high_severities

    def test_audit_serialization(self):
        features = CallFeatures(talk_ratio=0.40, pain_question_count=3, question_count=8)
        profile = CallProfile(
            call_type="discovery", sample_count=10, confidence=0.30,
            win_features=CallFeatures(talk_ratio=0.35, pain_question_count=3),
        )
        audit = post_call_audit(features, profile)
        d = audit.to_dict()
        assert "score" in d
        assert "checks" in d
        assert isinstance(d["checks"], list)
