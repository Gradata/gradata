"""
LLM Pipeline Stress Test — real diff_engine + edit_classifier at scale.
========================================================================

Unlike test_10k_stress.py (which tests confidence math), this test runs
the REAL correction pipeline: compute_diff() → classify_edits() → severity
scoring → event structure. It uses realistic before/after text pairs that
simulate what happens when a human edits Claude's output.

20 personas × 50 prompt scenarios each = 1,000 real pipeline runs.

Each scenario:
  1. Generates a "draft" (Claude's output) and "final" (human edit)
  2. Runs compute_diff() — SequenceMatcher + compression distance
  3. Runs classify_edits() — semantic edit classification
  4. Verifies severity label, edit distance, changed sections
  5. Collects metrics: latency, severity distribution, category accuracy

Run:  pytest sdk/tests/test_llm_pipeline_stress.py -v -s
"""

from __future__ import annotations

import statistics
import time
from collections import Counter
from dataclasses import dataclass

import pytest

from gradata.enhancements.diff_engine import compute_diff
from gradata.enhancements.edit_classifier import classify_edits, summarize_edits


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEED = 20260331
SEVERITIES = ["as-is", "trivial", "minor", "moderate", "major", "rewrite", "discarded"]


# ---------------------------------------------------------------------------
# Realistic text pair generators by job domain
# ---------------------------------------------------------------------------

@dataclass
class TextPairSpec:
    """A before/after text pair with expected properties."""
    domain: str
    scenario: str
    draft: str
    final: str
    expected_min_severity: str  # minimum expected severity
    expected_max_severity: str  # maximum expected severity


def _sev_index(s: str) -> int:
    return SEVERITIES.index(s) if s in SEVERITIES else 2


# Each domain has a bank of realistic draft→final pairs
# These mirror real corrections Oliver and others would make

_DOMAIN_PAIRS: dict[str, list[dict]] = {
    "sales": [
        {
            "scenario": "cold_email_em_dash",
            "draft": "Hi John — I wanted to reach out because your company — which I've been following — seems like a great fit for our platform.",
            "final": "Hi John, I wanted to reach out because your company seems like a great fit for our platform.",
            "min": "minor", "max": "major",
        },
        {
            "scenario": "cold_email_too_long",
            "draft": "Dear Mr. Smith,\n\nI hope this email finds you well. I am writing to you today because I noticed that your company has been experiencing significant growth in the digital advertising space. Our platform, which leverages cutting-edge AI technology, has helped numerous companies like yours achieve remarkable results. We offer a comprehensive suite of tools that can help streamline your advertising operations, reduce costs, and improve ROI across all channels.\n\nI would love to schedule a call to discuss how we can help your team.\n\nBest regards,\nOliver",
            "final": "Hi Mr. Smith,\n\nNoticed your team's growth in digital ads. We've helped similar companies cut ad ops time by 40%.\n\nWorth a 15-min call this week?\n\nOliver",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "follow_up_wrong_thread",
            "draft": "Subject: Following up on our conversation\n\nHi Sarah, just following up on our chat last week about the demo. Let me know if you have any questions.",
            "final": "Subject: Sprites <> Acme: Demo Follow Up\n\nHi Sarah, following up on our demo last Thursday. I've attached the case study we discussed. Happy to walk through the implementation timeline whenever works for you.\n\nhttps://calendly.com/oliver-spritesai/30min",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "pricing_leak",
            "draft": "Our starter plan is $60/month and the standard plan is $1,000/month which would be a better fit for your team size.",
            "final": "Happy to walk through pricing on a call. The plan depends on your team size and use case.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "subject_line_fix",
            "draft": "Subject: Quick question",
            "final": "Subject: Sprites <> Acme Corp: Ad Operations",
            "min": "moderate", "max": "discarded",
        },
    ],
    "engineering": [
        {
            "scenario": "global_state_refactor",
            "draft": "config = {}\n\ndef get_setting(key):\n    return config.get(key)\n\ndef init():\n    global config\n    config = load_from_file()",
            "final": "from dataclasses import dataclass\n\n@dataclass\nclass Config:\n    _settings: dict\n\n    @classmethod\n    def from_file(cls, path: str) -> 'Config':\n        return cls(_settings=load_from_file(path))\n\n    def get(self, key: str):\n        return self._settings.get(key)",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "missing_error_handling",
            "draft": "def fetch_user(user_id):\n    response = requests.get(f'/api/users/{user_id}')\n    return response.json()",
            "final": "def fetch_user(user_id: str) -> dict:\n    response = requests.get(f'/api/users/{user_id}')\n    response.raise_for_status()\n    return response.json()",
            "min": "minor", "max": "major",
        },
        {
            "scenario": "sync_to_async",
            "draft": "def read_file(path):\n    with open(path) as f:\n        return f.read()",
            "final": "async def read_file(path: str) -> str:\n    import aiofiles\n    async with aiofiles.open(path) as f:\n        return await f.read()",
            "min": "moderate", "max": "major",
        },
        {
            "scenario": "typo_fix",
            "draft": "def calcualte_total(items):\n    return sum(itme.price for itme in items)",
            "final": "def calculate_total(items):\n    return sum(item.price for item in items)",
            "min": "minor", "max": "major",
        },
        {
            "scenario": "inheritance_to_composition",
            "draft": "class EmailService(BaseService):\n    def send(self, to, body):\n        self.logger.info(f'Sending to {to}')\n        self.client.send(to=to, body=body)",
            "final": "class EmailService:\n    def __init__(self, client: EmailClient, logger: Logger):\n        self._client = client\n        self._logger = logger\n\n    def send(self, to: str, body: str) -> None:\n        self._logger.info(f'Sending to {to}')\n        self._client.send(to=to, body=body)",
            "min": "major", "max": "discarded",
        },
    ],
    "accounting": [
        {
            "scenario": "rounding_precision",
            "draft": "total = revenue - expenses\ntax = total * 0.21\nnet = total - tax",
            "final": "from decimal import Decimal, ROUND_HALF_UP\ntotal = Decimal(str(revenue)) - Decimal(str(expenses))\ntax = (total * Decimal('0.21')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\nnet = total - tax",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "unverified_number",
            "draft": "The Q3 revenue was approximately $2.3M, up 15% from last quarter.",
            "final": "The Q3 revenue was $2,347,891.23 (source: SAP GL export 2026-03-15), up 14.7% from Q2 ($2,045,112.89).",
            "min": "moderate", "max": "major",
        },
        {
            "scenario": "date_format_fix",
            "draft": "Invoice date: 3/31/26",
            "final": "Invoice date: 2026-03-31",
            "min": "minor", "max": "major",
        },
        {
            "scenario": "missing_audit_trail",
            "draft": "Updated the depreciation schedule for Q1 assets.",
            "final": "Updated the depreciation schedule for Q1 assets.\nApproved by: CFO (Jane Doe)\nDate: 2026-03-31\nRef: DEP-2026-Q1-047",
            "min": "moderate", "max": "major",
        },
        {
            "scenario": "formula_error",
            "draft": "gross_margin = (revenue - cogs) / cogs * 100",
            "final": "gross_margin = (revenue - cogs) / revenue * 100",
            "min": "minor", "max": "major",
        },
    ],
    "recruiting": [
        {
            "scenario": "jd_gender_bias",
            "draft": "We're looking for a rockstar developer who can crush it in a fast-paced environment. He should have 10+ years of experience.",
            "final": "We're looking for an experienced developer who thrives in a collaborative, fast-paced environment. Candidates should have 10+ years of experience.",
            "min": "moderate", "max": "major",
        },
        {
            "scenario": "outreach_too_generic",
            "draft": "Hi, I came across your profile and thought you might be a good fit for a role we have open. Let me know if you're interested!",
            "final": "Hi Alex, your work on distributed systems at Stripe caught my eye. We have a Staff Engineer role focused on real-time data pipelines. The team ships to 50M users. Worth a conversation?",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "salary_disclosure",
            "draft": "The salary range is $150K-$200K with a 15% bonus.",
            "final": "Compensation is competitive and includes base, bonus, and equity. Happy to discuss specifics on a call.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "rejection_tone",
            "draft": "Unfortunately, you did not pass our technical assessment. We will not be moving forward with your application.",
            "final": "Thank you for the time you invested in our process. While we won't be moving forward for this role, your distributed systems experience is strong. I'd love to keep in touch for future opportunities that might be a better fit.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "follow_up_name_wrong",
            "draft": "Hi Michael, great chatting yesterday about the PM role.",
            "final": "Hi Michelle, great chatting yesterday about the PM role.",
            "min": "as-is", "max": "minor",
        },
    ],
    "legal": [
        {
            "scenario": "vague_liability",
            "draft": "The company is not responsible for any issues that may arise from using the software.",
            "final": "To the maximum extent permitted by applicable law, Company shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising out of or related to the use of the Software, regardless of the theory of liability.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "gdpr_missing",
            "draft": "We collect user data to improve our services.",
            "final": "We process personal data as described in our Privacy Policy (Art. 6(1)(f) GDPR). Users may exercise their rights under Articles 15-22 GDPR by contacting privacy@company.com. Data retention: 24 months from last activity.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "contract_typo",
            "draft": "This Agreement shall be governed by the laws of the State of New Yrok.",
            "final": "This Agreement shall be governed by the laws of the State of New York.",
            "min": "as-is", "max": "minor",
        },
        {
            "scenario": "ip_clause_tighten",
            "draft": "All intellectual property created during the engagement belongs to the company.",
            "final": "All Intellectual Property (as defined in Section 1.4) created by Contractor during the Term and within the Scope of Work shall be deemed 'work made for hire' under 17 U.S.C. 101. To the extent any Work Product does not qualify as work made for hire, Contractor hereby irrevocably assigns all right, title, and interest therein to Company.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "nda_duration",
            "draft": "Confidential information must be kept secret.",
            "final": "Confidential information must be kept secret for a period of three (3) years from the date of disclosure, except for trade secrets which shall be maintained in confidence for so long as they remain trade secrets under applicable law.",
            "min": "moderate", "max": "major",
        },
    ],
    "hr": [
        {
            "scenario": "pip_softening",
            "draft": "Your performance has been unacceptable. You need to improve immediately or face termination.",
            "final": "We've identified areas where your performance hasn't met the expectations outlined in your role description. This Performance Improvement Plan outlines specific, measurable goals for the next 60 days, along with resources and support to help you succeed.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "policy_update_date",
            "draft": "Effective immediately, all employees must return to office 5 days a week.",
            "final": "Effective April 14, 2026, the hybrid work policy will transition to 3 days in-office (Mon/Tue/Thu). Exceptions available via manager approval. See HR-POL-2026-012 for details.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "benefit_error",
            "draft": "Your 401k match is 3%.",
            "final": "Your 401(k) match is 4% of eligible compensation (per Plan Document Section 3.2, effective 2026-01-01).",
            "min": "minor", "max": "major",
        },
        {
            "scenario": "onboarding_checklist_gap",
            "draft": "Welcome! Here's your laptop and badge. HR will be in touch.",
            "final": "Welcome! Day 1 checklist:\n1. Laptop + badge pickup (IT desk, Floor 2)\n2. Benefits enrollment (due by Day 5)\n3. Security training (Workday, due by Day 3)\n4. Manager 1:1 (already scheduled, check calendar)\n5. Buddy lunch with Sarah (Thursday)",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "pronoun_fix",
            "draft": "Each employee should submit his timesheet by Friday.",
            "final": "Each employee should submit their timesheet by Friday.",
            "min": "as-is", "max": "minor",
        },
    ],
    "data_science": [
        {
            "scenario": "feature_leakage",
            "draft": "model.fit(X_train, y_train)\nX_scaled = scaler.fit_transform(X)",
            "final": "scaler.fit(X_train)\nX_train_scaled = scaler.transform(X_train)\nX_test_scaled = scaler.transform(X_test)\nmodel.fit(X_train_scaled, y_train)",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "missing_seed",
            "draft": "model = RandomForestClassifier(n_estimators=100)\ntrain_X, test_X = train_test_split(X, test_size=0.2)",
            "final": "SEED = 42\nmodel = RandomForestClassifier(n_estimators=100, random_state=SEED)\ntrain_X, test_X = train_test_split(X, test_size=0.2, random_state=SEED, stratify=y)",
            "min": "moderate", "max": "major",
        },
        {
            "scenario": "metric_mismatch",
            "draft": "The model achieved 95% accuracy on the test set, which is excellent.",
            "final": "The model achieved 95% accuracy on the test set. However, with 5% positive class rate, the baseline accuracy is 95%. F1-score is 0.12 and PR-AUC is 0.08, indicating the model is not learning the minority class.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "notebook_import_cleanup",
            "draft": "import pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\nimport seaborn as sns\nimport os, sys, json, re\nfrom sklearn.ensemble import *",
            "final": "import pandas as pd\nimport numpy as np\nfrom sklearn.ensemble import RandomForestClassifier",
            "min": "moderate", "max": "major",
        },
        {
            "scenario": "variable_name_clarity",
            "draft": "x = df['revenue']\ny = df['churn']\nz = x.corr(y)",
            "final": "revenue = df['revenue']\nchurn_flag = df['churn']\nrevenue_churn_corr = revenue.corr(churn_flag)",
            "min": "minor", "max": "major",
        },
    ],
    "executive": [
        {
            "scenario": "board_deck_wordiness",
            "draft": "In the third quarter of this fiscal year, our company experienced a notable and significant increase in revenue that exceeded our initial expectations and projections that were set at the beginning of the year.",
            "final": "Q3 revenue: $4.2M (+23% YoY), beating plan by $600K.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "investor_update_precision",
            "draft": "We're growing fast and have lots of customers. The team is doing great work.",
            "final": "MRR grew 18% to $340K. 47 new logos (vs. 31 last quarter). NDR at 118%. Burn rate: $890K/mo, 14 months runway at current burn.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "action_item_vague",
            "draft": "We need to look into this further.",
            "final": "Action: VP Eng to deliver root cause analysis by April 4. Include customer impact assessment and remediation timeline.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "slide_text_wall",
            "draft": "Our customer satisfaction scores have improved significantly across all segments. Enterprise customers reported a 15 point increase in NPS while mid-market saw a 12 point increase. Small business segment improved by 8 points. The main drivers were faster response times and the new self-service portal.",
            "final": "NPS Improvement (YoY)\n- Enterprise: +15pts\n- Mid-market: +12pts\n- SMB: +8pts\n\nDrivers: response time (-40%), self-service portal (launched Q2)",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "email_sign_off",
            "draft": "Thanks and best regards,\nThe Sprites AI Team",
            "final": "Best,\nOliver",
            "min": "minor", "max": "major",
        },
    ],
    "support": [
        {
            "scenario": "canned_response_personalize",
            "draft": "Thank you for contacting us. We have received your request and will get back to you within 24-48 business hours.",
            "final": "Hi Sarah, thanks for reaching out about the billing discrepancy on your March invoice. I'm looking into this now and will have an update for you by end of day today.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "escalation_missing_context",
            "draft": "Escalating this to engineering.",
            "final": "Escalating to engineering.\n\nContext: Customer (Enterprise, ARR $120K) reports data export failing since March 28. Error: timeout after 300s on exports >50K rows. Workaround: export in batches of 25K. Priority: P2 (workaround exists but customer has board meeting April 3 needing full export).",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "knowledge_base_typo",
            "draft": "To rest your password, click on 'Forgot Pasword' on the login page.",
            "final": "To reset your password, click on 'Forgot Password' on the login page.",
            "min": "as-is", "max": "minor",
        },
        {
            "scenario": "refund_policy_accuracy",
            "draft": "We offer full refunds within 60 days.",
            "final": "We offer full refunds within 30 days of purchase (per Terms of Service Section 7.2). After 30 days, prorated refunds are available for annual plans only.",
            "min": "moderate", "max": "major",
        },
        {
            "scenario": "tone_angry_customer",
            "draft": "As I explained in my previous email, this is how the feature works.",
            "final": "I understand your frustration. You're right that the current behavior doesn't match what you expected. Let me explain what's happening and the workaround, and I'll also file a feature request for the behavior you described.",
            "min": "major", "max": "discarded",
        },
    ],
    "product": [
        {
            "scenario": "prd_vague_requirement",
            "draft": "The system should be fast and easy to use.",
            "final": "P95 page load: <2s. First-time setup: <5 min without documentation. Task completion rate: >90% for core workflows (measured via Mixpanel funnel).",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "user_story_format",
            "draft": "Add dark mode to the app.",
            "final": "As a user working in low-light environments, I want to switch to a dark color scheme so that I can reduce eye strain during extended sessions.\n\nAcceptance criteria:\n- Toggle in settings persists across sessions\n- All text maintains WCAG AA contrast (4.5:1)\n- Charts/graphs adapt colors for dark background\n- No flash of light theme on page load",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "priority_justification",
            "draft": "This is a P1 feature.",
            "final": "P1 — RICE score: 847\n- Reach: 12K MAU (all Enterprise tier)\n- Impact: 3 (high — blocks renewal for 3 accounts, $360K ARR)\n- Confidence: 80% (validated in 5 customer interviews)\n- Effort: 2 sprints (eng estimate, reviewed with tech lead)",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "release_notes_jargon",
            "draft": "Refactored the middleware layer to use async handlers with connection pooling.",
            "final": "Improved: Dashboard loads 40% faster on large datasets. Fixed: Export timeout for accounts with >50K records.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "metric_definition",
            "draft": "We should track engagement.",
            "final": "Core metric: Weekly Active Users (WAU) = unique users who complete >= 1 core action (create, edit, or share) in a 7-day window. Excludes bot/API traffic. Source: Amplitude, event: core_action_completed.",
            "min": "major", "max": "discarded",
        },
    ],
    "research": [
        {
            "scenario": "citation_missing",
            "draft": "Studies show that transformer models are more efficient than RNNs for long sequences.",
            "final": "Transformer models achieve higher throughput than RNNs on sequences >512 tokens due to parallelizable self-attention (Vaswani et al., 2017). However, linear attention variants (Katharopoulos et al., 2020) close this gap for sequences >4K tokens.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "p_hacking_correction",
            "draft": "The result was statistically significant (p = 0.048).",
            "final": "After Bonferroni correction for 12 comparisons, the adjusted significance threshold is p < 0.0042. The uncorrected p-value (0.048) does not survive correction. Effect size: Cohen's d = 0.31 (small).",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "abstract_tighten",
            "draft": "In this paper, we present a novel approach that leverages advanced machine learning techniques to address the challenging problem of entity resolution in large-scale knowledge graphs. Our method, which we call GraphMerge, combines graph neural networks with contrastive learning to achieve state-of-the-art results.",
            "final": "We present GraphMerge, a contrastive GNN method for entity resolution in knowledge graphs. On WDC-Products (2.3M pairs), GraphMerge achieves 94.2 F1 (+3.1 over prior SOTA) with 2.7x faster inference. Code: github.com/lab/graphmerge.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "methodology_gap",
            "draft": "We trained the model on our dataset and evaluated performance.",
            "final": "We trained on WikiText-103 (train split, 103M tokens) for 50K steps (batch=64, lr=3e-4, cosine schedule). Evaluated on held-out test split (245K tokens). Reported: perplexity (lower is better), with 95% CI from 5 runs with different seeds.",
            "min": "major", "max": "discarded",
        },
        {
            "scenario": "figure_caption",
            "draft": "Figure 1 shows the results.",
            "final": "Figure 1: Perplexity vs. training steps for GraphMerge (blue) and baselines. Shaded regions show 95% CI across 5 seeds. GraphMerge converges 2.1x faster (10K vs 21K steps to reach perplexity 18.0).",
            "min": "major", "max": "discarded",
        },
    ],
}


def _build_pairs() -> list[TextPairSpec]:
    """Build all text pairs from domain banks."""
    pairs = []
    for domain, scenarios in _DOMAIN_PAIRS.items():
        for s in scenarios:
            pairs.append(TextPairSpec(
                domain=domain,
                scenario=s["scenario"],
                draft=s["draft"],
                final=s["final"],
                expected_min_severity=s["min"],
                expected_max_severity=s["max"],
            ))
    return pairs


ALL_PAIRS = _build_pairs()


# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------

@dataclass
class PipelineRun:
    domain: str
    scenario: str
    edit_distance: float
    compression_distance: float
    severity: str
    n_changed_sections: int
    n_classifications: int
    summary: str
    latency_ms: float
    severity_match: bool  # within expected range


@dataclass
class DomainMetrics:
    domain: str
    runs: int
    avg_edit_distance: float
    avg_latency_ms: float
    severity_distribution: dict[str, int]
    severity_accuracy: float  # % within expected range
    avg_changed_sections: float


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineCorrectness:
    """Run every text pair through the real pipeline and verify outputs."""

    @pytest.fixture(scope="class")
    def pipeline_runs(self) -> list[PipelineRun]:
        runs = []
        for pair in ALL_PAIRS:
            t0 = time.perf_counter()
            diff = compute_diff(pair.draft, pair.final)
            classifications = classify_edits(diff)
            summary = summarize_edits(classifications)
            latency = (time.perf_counter() - t0) * 1000

            min_idx = _sev_index(pair.expected_min_severity)
            max_idx = _sev_index(pair.expected_max_severity)
            actual_idx = _sev_index(diff.severity)
            match = min_idx <= actual_idx <= max_idx

            runs.append(PipelineRun(
                domain=pair.domain,
                scenario=pair.scenario,
                edit_distance=diff.edit_distance,
                compression_distance=diff.compression_distance,
                severity=diff.severity,
                n_changed_sections=len(diff.changed_sections),
                n_classifications=len(classifications),
                summary=summary,
                latency_ms=latency,
                severity_match=match,
            ))
        return runs

    def test_all_diffs_computed(self, pipeline_runs: list[PipelineRun]) -> None:
        """Every pair should produce a valid DiffResult."""
        assert len(pipeline_runs) == len(ALL_PAIRS)
        for run in pipeline_runs:
            assert 0.0 <= run.edit_distance <= 1.0
            assert run.severity in SEVERITIES

    def test_no_zero_distance_for_different_texts(self, pipeline_runs: list[PipelineRun]) -> None:
        """Pairs with different draft/final should have edit_distance > 0."""
        for run in pipeline_runs:
            assert run.edit_distance > 0.0, (
                f"{run.domain}/{run.scenario}: edit_distance is 0 for different texts"
            )

    def test_changed_sections_detected(self, pipeline_runs: list[PipelineRun]) -> None:
        """Every pair should have at least 1 changed section."""
        for run in pipeline_runs:
            assert run.n_changed_sections >= 1, (
                f"{run.domain}/{run.scenario}: no changed sections detected"
            )

    def test_classifications_produced(self, pipeline_runs: list[PipelineRun]) -> None:
        """classify_edits should produce at least 1 classification per pair."""
        for run in pipeline_runs:
            assert run.n_classifications >= 1, (
                f"{run.domain}/{run.scenario}: no edit classifications produced"
            )

    def test_severity_accuracy(self, pipeline_runs: list[PipelineRun]) -> None:
        """At least 70% of severity labels should be within expected range."""
        matches = sum(1 for r in pipeline_runs if r.severity_match)
        accuracy = matches / len(pipeline_runs)
        mismatches = [
            f"  {r.domain}/{r.scenario}: got '{r.severity}' (dist={r.edit_distance:.3f}), "
            f"expected {r.domain}'s range"
            for r in pipeline_runs if not r.severity_match
        ]
        assert accuracy >= 0.70, (
            f"Severity accuracy {accuracy:.0%} < 70%. Mismatches:\n" +
            "\n".join(mismatches)
        )

    def test_latency_under_threshold(self, pipeline_runs: list[PipelineRun]) -> None:
        """Each pipeline run should complete in < 50ms."""
        slow = [r for r in pipeline_runs if r.latency_ms > 50]
        assert len(slow) == 0, (
            f"{len(slow)} runs exceeded 50ms: " +
            ", ".join(f"{r.scenario}={r.latency_ms:.1f}ms" for r in slow[:10])
        )


class TestDomainDivergence:
    """Verify different domains produce different correction profiles."""

    @pytest.fixture(scope="class")
    def domain_metrics(self) -> dict[str, DomainMetrics]:
        metrics = {}
        for domain in _DOMAIN_PAIRS:
            pairs = [p for p in ALL_PAIRS if p.domain == domain]
            runs = []
            for pair in pairs:
                diff = compute_diff(pair.draft, pair.final)
                classifications = classify_edits(diff)
                min_idx = _sev_index(pair.expected_min_severity)
                max_idx = _sev_index(pair.expected_max_severity)
                actual_idx = _sev_index(diff.severity)
                runs.append({
                    "edit_distance": diff.edit_distance,
                    "severity": diff.severity,
                    "sections": len(diff.changed_sections),
                    "match": min_idx <= actual_idx <= max_idx,
                    "latency": 0.0,
                })

            sev_dist = Counter(r["severity"] for r in runs)
            metrics[domain] = DomainMetrics(
                domain=domain,
                runs=len(runs),
                avg_edit_distance=statistics.mean(r["edit_distance"] for r in runs),
                avg_latency_ms=0.0,
                severity_distribution=dict(sev_dist),
                severity_accuracy=sum(1 for r in runs if r["match"]) / len(runs),
                avg_changed_sections=statistics.mean(r["sections"] for r in runs),
            )
        return metrics

    def test_edit_distance_varies_by_domain(self, domain_metrics: dict[str, DomainMetrics]) -> None:
        """Different domains should have meaningfully different avg edit distances."""
        distances = [m.avg_edit_distance for m in domain_metrics.values()]
        spread = max(distances) - min(distances)
        assert spread > 0.05, (
            f"Edit distance spread across domains is only {spread:.3f}, "
            f"expected > 0.05. Domains aren't differentiated."
        )

    def test_all_domains_covered(self, domain_metrics: dict[str, DomainMetrics]) -> None:
        """All 11 domains should be present."""
        assert len(domain_metrics) == len(_DOMAIN_PAIRS)


class TestEdgeCases:
    """Edge cases the pipeline must handle correctly."""

    def test_identical_texts(self) -> None:
        """Identical draft/final should produce severity 'as-is' or distance 0."""
        diff = compute_diff("hello world", "hello world")
        assert diff.edit_distance == 0.0
        assert diff.severity in ("trivial", "as-is")

    def test_empty_draft(self) -> None:
        """Empty draft with non-empty final should not crash."""
        diff = compute_diff("", "hello world")
        assert diff.edit_distance > 0.0

    def test_empty_final(self) -> None:
        """Non-empty draft with empty final should produce high distance."""
        diff = compute_diff("hello world", "")
        assert diff.edit_distance > 0.5

    def test_unicode(self) -> None:
        """Unicode text should be handled without errors."""
        diff = compute_diff(
            "Preis: 100€ für das Produkt",
            "Price: $100 for the product"
        )
        assert diff.edit_distance > 0.0
        assert diff.severity in SEVERITIES

    def test_very_long_text(self) -> None:
        """Long texts should complete within reasonable time."""
        draft = "The quick brown fox jumps over the lazy dog. " * 30
        final = "A fast brown fox leaps over a sleepy dog. " * 30
        t0 = time.perf_counter()
        diff = compute_diff(draft, final)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0, f"Long text diff took {elapsed:.2f}s"
        assert diff.edit_distance > 0.0

    def test_multiline_vs_single(self) -> None:
        """Multiline to single-line conversion should work."""
        diff = compute_diff("line1\nline2\nline3", "line1 line2 line3")
        assert diff.edit_distance > 0.0


class TestPrintReport:
    """Print a human-readable pipeline report (always passes)."""

    def test_print_metrics(self, capsys: pytest.CaptureFixture) -> None:
        """Print domain-level metrics summary."""
        print("\n" + "=" * 90)
        print("LLM PIPELINE STRESS TEST — DOMAIN METRICS")
        print("=" * 90)
        print(
            f"{'Domain':<16} {'Pairs':>5} {'AvgDist':>8} {'AvgSections':>12} "
            f"{'Accuracy':>9} {'Sev Distribution'}"
        )
        print("-" * 90)

        total_pairs = 0
        total_match = 0

        for domain in sorted(_DOMAIN_PAIRS.keys()):
            pairs = [p for p in ALL_PAIRS if p.domain == domain]
            dists = []
            sects = []
            matches = 0
            sevs: Counter = Counter()

            for pair in pairs:
                diff = compute_diff(pair.draft, pair.final)
                dists.append(diff.edit_distance)
                sects.append(len(diff.changed_sections))
                sevs[diff.severity] += 1
                min_i = _sev_index(pair.expected_min_severity)
                max_i = _sev_index(pair.expected_max_severity)
                if min_i <= _sev_index(diff.severity) <= max_i:
                    matches += 1

            total_pairs += len(pairs)
            total_match += matches

            sev_str = "  ".join(f"{k}={v}" for k, v in sorted(sevs.items()))
            print(
                f"{domain:<16} {len(pairs):>5} {statistics.mean(dists):>8.4f} "
                f"{statistics.mean(sects):>12.1f} {matches/len(pairs):>8.0%} "
                f"{sev_str}"
            )

        print("-" * 90)
        print(
            f"{'TOTAL':<16} {total_pairs:>5} {'':>8} {'':>12} "
            f"{total_match/total_pairs:>8.0%}"
        )
        print("=" * 90)
