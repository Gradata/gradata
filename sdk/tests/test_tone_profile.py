import pytest; pytest.importorskip('gradata.enhancements.self_improvement', reason='requires gradata_cloud')
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

"""Tests for tone profile extraction, diffing, and graduation."""
import pytest
from gradata.enhancements.tone_profile import (
    ToneFeatures,
    ToneProfile,
    ToneDiff,
    extract_tone,
    build_tone_profile,
    compute_tone_diff,
    tone_diff_to_lesson,
    generate_tone_prompt,
)


# ---------------------------------------------------------------------------
# Feature Extraction
# ---------------------------------------------------------------------------

class TestExtractTone:
    def test_empty_text(self):
        f = extract_tone("")
        assert f.word_count == 0

    def test_casual_email(self):
        text = "Hey Tim,\n\nJust wanted to check in. Honestly, the demo was awesome and I think we should totally move forward.\n\nLet me know?"
        f = extract_tone(text)
        assert f.greeting_style == "hey"
        assert f.formality < 0.5  # casual markers present
        assert f.cta_style == "soft-close"
        assert f.word_count > 10

    def test_formal_email(self):
        text = "Hello Mr. Thompson,\n\nRegarding our previous discussion, I would like to furthermore clarify the proposal details. Accordingly, please find the revised terms.\n\nSincerely,\nOliver"
        f = extract_tone(text)
        assert f.greeting_style == "hello"
        assert f.formality > 0.5  # formal markers present

    def test_direct_opener(self):
        text = "Quick question: are you still evaluating tools for Q2?"
        f = extract_tone(text)
        assert f.opener_type == "direct"

    def test_empathy_opener(self):
        text = "I understand budget is tight this quarter. Here's how we can help."
        f = extract_tone(text)
        assert f.opener_type == "empathy"

    def test_question_opener(self):
        text = "Have you had a chance to review the proposal I sent last week?"
        f = extract_tone(text)
        assert f.opener_type == "question"

    def test_bullet_density(self):
        text = "On the call we'll cover:\n- Your current stack\n- Pain points\n- How we solve them\n- Pricing\n- Next steps"
        f = extract_tone(text)
        assert f.bullet_density > 0.5  # most lines are bullets

    def test_no_bullets(self):
        text = "Thanks for the great call. I'll send over the proposal by EOD. Looking forward to working together."
        f = extract_tone(text)
        assert f.bullet_density == 0.0

    def test_em_dash_detection(self):
        text = "The platform — which handles everything — costs $500/month."
        f = extract_tone(text)
        assert f.em_dash_count == 2

    def test_no_em_dashes(self):
        text = "The platform handles everything: ad creation, optimization, and reporting."
        f = extract_tone(text)
        assert f.em_dash_count == 0
        assert f.colon_count >= 1

    def test_exclamation_count(self):
        text = "Great news! The trial is live! Let me know if you have questions!"
        f = extract_tone(text)
        assert f.exclamation_count == 3

    def test_link_cta(self):
        text = "Book a time here: https://calendly.com/user/30min"
        f = extract_tone(text)
        assert f.cta_style == "link"

    def test_paragraph_count(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        f = extract_tone(text)
        assert f.paragraph_count == 3

    def test_serialization_roundtrip(self):
        f = extract_tone("Hey, just checking in. Let me know?")
        d = f.to_dict()
        f2 = ToneFeatures.from_dict(d)
        assert f2.greeting_style == f.greeting_style
        assert f2.word_count == f.word_count


# ---------------------------------------------------------------------------
# Tone Profile Building
# ---------------------------------------------------------------------------

class TestBuildProfile:
    def test_single_email(self):
        emails = ["Hey Tim, quick update on the proposal. Let me know if you have questions."]
        profile = build_tone_profile(emails, "follow_up")
        assert profile.task_type == "follow_up"
        assert profile.sample_count == 1
        assert profile.confidence > 0

    def test_multiple_emails_averages(self):
        emails = [
            "Short email. Done.",
            "This is a much longer email with several sentences. It covers multiple topics. The detail level is high. We should discuss further.",
        ]
        profile = build_tone_profile(emails, "cold_outreach")
        assert profile.sample_count == 2
        # Average should be between the two
        assert profile.features.avg_sentence_length > 0

    def test_confidence_scales_with_samples(self):
        emails_5 = ["Email text." for _ in range(5)]
        emails_20 = ["Email text." for _ in range(20)]

        p5 = build_tone_profile(emails_5, "test")
        p20 = build_tone_profile(emails_20, "test")

        assert p20.confidence > p5.confidence

    def test_incremental_update(self):
        emails_1 = ["Hey, first email here."]
        profile = build_tone_profile(emails_1, "follow_up")

        emails_2 = ["Hi, second batch of emails."]
        updated = build_tone_profile(emails_2, "follow_up", existing=profile)

        assert updated.sample_count == 2
        assert updated.confidence > profile.confidence

    def test_empty_emails(self):
        profile = build_tone_profile([], "test")
        assert profile.sample_count == 0

    def test_ema_blending(self):
        """Existing profile should influence new profile via EMA."""
        # Build a profile with many formal emails
        formal_emails = ["Regarding our discussion, I would like to clarify." for _ in range(10)]
        existing = build_tone_profile(formal_emails, "test")

        # Now add casual emails
        casual_emails = ["Hey, yeah totally, let's do it."]
        updated = build_tone_profile(casual_emails, "test", existing=existing)

        # Should be blended, not purely casual
        assert updated.features.formality > 0.2  # not fully casual


# ---------------------------------------------------------------------------
# Tone Diff
# ---------------------------------------------------------------------------

class TestToneDiff:
    def test_no_diff_identical(self):
        text = "Hey Tim, thanks for the call. Let me know if you have questions."
        diffs = compute_tone_diff(text, text)
        assert len(diffs) == 0

    def test_greeting_change(self):
        draft = "Hello Tim,\n\nFollowing up on our conversation."
        final = "Hey Tim,\n\nFollowing up on our conversation."
        diffs = compute_tone_diff(draft, final)
        greeting_diffs = [d for d in diffs if d.field == "greeting_style"]
        assert len(greeting_diffs) == 1
        assert greeting_diffs[0].draft_value == "hello"
        assert greeting_diffs[0].final_value == "hey"

    def test_em_dash_removal(self):
        draft = "The platform — which handles ads — saves you time."
        final = "The platform handles ads and saves you time."
        diffs = compute_tone_diff(draft, final)
        em_diffs = [d for d in diffs if d.field == "em_dash_count"]
        assert len(em_diffs) == 1
        assert em_diffs[0].delta < 0  # em dashes removed

    def test_word_count_change(self):
        draft = "Short."
        final = "This is a much longer version of the email with additional context and details that Oliver added because the original was too terse."
        diffs = compute_tone_diff(draft, final)
        wc_diffs = [d for d in diffs if d.field == "word_count"]
        assert len(wc_diffs) == 1
        assert wc_diffs[0].delta > 0

    def test_lesson_generation_from_major_diffs(self):
        draft = "Hello Tim,\n\nThe platform — which is amazing — does everything."
        final = "Hey Tim,\n\nThe platform does everything: ad creation, optimization, and reporting."
        diffs = compute_tone_diff(draft, final)
        lesson = tone_diff_to_lesson(diffs, "follow_up")
        assert lesson is not None
        assert "follow_up" in lesson

    def test_no_lesson_from_minor_diffs(self):
        draft = "Hey Tim, thanks for the call."
        final = "Hey Tim, thanks for the great call."
        diffs = compute_tone_diff(draft, final)
        lesson = tone_diff_to_lesson(diffs, "follow_up")
        assert lesson is None  # too minor


# ---------------------------------------------------------------------------
# Tone Prompt Generation
# ---------------------------------------------------------------------------

class TestGeneratePrompt:
    def test_empty_profile(self):
        profile = ToneProfile(task_type="test", sample_count=0)
        prompt = generate_tone_prompt(profile)
        assert prompt == ""

    def test_low_confidence_uses_consider(self):
        profile = ToneProfile(
            task_type="cold_outreach",
            sample_count=3,
            confidence=0.30,
            features=ToneFeatures(
                avg_sentence_length=10, greeting_style="hey",
                formality=0.2, cta_style="question",
            ),
        )
        prompt = generate_tone_prompt(profile)
        assert "Consider" in prompt
        assert "cold_outreach" in prompt

    def test_high_confidence_uses_always(self):
        profile = ToneProfile(
            task_type="follow_up",
            sample_count=35,
            confidence=0.95,
            features=ToneFeatures(
                avg_sentence_length=8, greeting_style="hey",
                formality=0.2, em_dash_count=0, exclamation_count=0,
                cta_style="soft-close", word_count=80,
            ),
        )
        prompt = generate_tone_prompt(profile)
        assert "Always" in prompt
        assert "Never" in prompt  # em dashes banned at RULE tier
        assert "follow_up" in prompt

    def test_em_dash_ban_at_pattern(self):
        profile = ToneProfile(
            task_type="test",
            sample_count=20,
            confidence=0.70,
            features=ToneFeatures(em_dash_count=0),
        )
        prompt = generate_tone_prompt(profile)
        assert "em dash" in prompt.lower() or "Avoid" in prompt

    def test_includes_word_count_target(self):
        profile = ToneProfile(
            task_type="test",
            sample_count=10,
            confidence=0.50,
            features=ToneFeatures(word_count=120),
        )
        prompt = generate_tone_prompt(profile)
        assert "120" in prompt
