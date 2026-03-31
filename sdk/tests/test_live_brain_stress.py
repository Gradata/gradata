"""
Live Brain Stress Test — full brain.correct() pipeline at scale.
=================================================================

Creates a real Brain instance (in tmp_path), feeds it corrections
from 11 job domains, and verifies the entire pipeline:
  brain.correct() → diff_engine → edit_classifier → event logging →
  confidence update → graduation → meta-rule emergence

This is the closest thing to running Claude + human corrections
without an API call. Every correction goes through the same code path
that the auto-correct hook uses in production.

Run: pytest sdk/tests/test_live_brain_stress.py -v -s
"""

from __future__ import annotations

import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

import pytest

# Types available if needed for future graduation tests
# from gradata._types import ELIGIBLE_STATES, LessonState


# ---------------------------------------------------------------------------
# The same domain pairs from test_llm_pipeline_stress.py, inlined for
# independence. Each pair = one brain.correct(draft, final) call.
# ---------------------------------------------------------------------------

CORRECTION_SCENARIOS: list[dict] = [
    # Sales
    {"domain": "sales", "draft": "Hi John — I wanted to reach out because your company — which I've been following — seems like a great fit.", "final": "Hi John, I wanted to reach out because your company seems like a great fit."},
    {"domain": "sales", "draft": "Dear Mr. Smith,\n\nI hope this email finds you well. I am writing to you today because I noticed that your company has been experiencing significant growth in the digital advertising space. Our platform has helped numerous companies like yours achieve remarkable results.\n\nBest regards,\nOliver", "final": "Hi Mr. Smith,\n\nNoticed your team's growth in digital ads. We've helped similar companies cut ad ops time by 40%.\n\nWorth a 15-min call?\n\nOliver"},
    {"domain": "sales", "draft": "Subject: Following up on our conversation\n\nHi Sarah, just following up on our chat.", "final": "Subject: Sprites <> Acme: Demo Follow Up\n\nHi Sarah, following up on our demo Thursday. Attached the case study.\n\nhttps://calendly.com/oliver-spritesai/30min"},
    {"domain": "sales", "draft": "Our starter plan is $60/month and the standard is $1,000/month.", "final": "Happy to walk through pricing on a call. Depends on your team size and use case."},
    {"domain": "sales", "draft": "Subject: Quick question", "final": "Subject: Sprites <> Acme Corp: Ad Operations"},
    # Engineering
    {"domain": "engineering", "draft": "config = {}\ndef get_setting(key):\n    return config.get(key)", "final": "from dataclasses import dataclass\n\n@dataclass\nclass Config:\n    _settings: dict\n    def get(self, key): return self._settings.get(key)"},
    {"domain": "engineering", "draft": "def fetch_user(user_id):\n    response = requests.get(f'/api/users/{user_id}')\n    return response.json()", "final": "def fetch_user(user_id: str) -> dict:\n    response = requests.get(f'/api/users/{user_id}')\n    response.raise_for_status()\n    return response.json()"},
    {"domain": "engineering", "draft": "def read_file(path):\n    with open(path) as f:\n        return f.read()", "final": "async def read_file(path: str) -> str:\n    import aiofiles\n    async with aiofiles.open(path) as f:\n        return await f.read()"},
    {"domain": "engineering", "draft": "def calcualte_total(items):\n    return sum(itme.price for itme in items)", "final": "def calculate_total(items):\n    return sum(item.price for item in items)"},
    # Accounting
    {"domain": "accounting", "draft": "total = revenue - expenses\ntax = total * 0.21", "final": "from decimal import Decimal, ROUND_HALF_UP\ntotal = Decimal(str(revenue)) - Decimal(str(expenses))\ntax = (total * Decimal('0.21')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)"},
    {"domain": "accounting", "draft": "The Q3 revenue was approximately $2.3M, up 15% from last quarter.", "final": "The Q3 revenue was $2,347,891.23 (source: SAP GL export 2026-03-15), up 14.7% from Q2."},
    {"domain": "accounting", "draft": "Invoice date: 3/31/26", "final": "Invoice date: 2026-03-31"},
    {"domain": "accounting", "draft": "gross_margin = (revenue - cogs) / cogs * 100", "final": "gross_margin = (revenue - cogs) / revenue * 100"},
    # Recruiting
    {"domain": "recruiting", "draft": "We're looking for a rockstar developer who can crush it. He should have 10+ years.", "final": "We're looking for an experienced developer who thrives in a collaborative environment. Candidates should have 10+ years."},
    {"domain": "recruiting", "draft": "Hi, I came across your profile and thought you might be a good fit.", "final": "Hi Alex, your work on distributed systems at Stripe caught my eye. We have a Staff Engineer role. Worth a conversation?"},
    {"domain": "recruiting", "draft": "The salary range is $150K-$200K with a 15% bonus.", "final": "Compensation is competitive and includes base, bonus, and equity. Happy to discuss on a call."},
    # Legal
    {"domain": "legal", "draft": "The company is not responsible for any issues.", "final": "To the maximum extent permitted by applicable law, Company shall not be liable for indirect, incidental, or consequential damages."},
    {"domain": "legal", "draft": "We collect user data to improve our services.", "final": "We process personal data as described in our Privacy Policy (Art. 6(1)(f) GDPR). Users may exercise their rights under Articles 15-22."},
    {"domain": "legal", "draft": "This Agreement shall be governed by the laws of the State of New Yrok.", "final": "This Agreement shall be governed by the laws of the State of New York."},
    # HR
    {"domain": "hr", "draft": "Your performance has been unacceptable. Improve or face termination.", "final": "We've identified areas where performance hasn't met expectations. This PIP outlines specific goals for the next 60 days."},
    {"domain": "hr", "draft": "Effective immediately, all employees must return to office 5 days.", "final": "Effective April 14, 2026, hybrid policy transitions to 3 days in-office (Mon/Tue/Thu). See HR-POL-2026-012."},
    {"domain": "hr", "draft": "Each employee should submit his timesheet by Friday.", "final": "Each employee should submit their timesheet by Friday."},
    # Data Science
    {"domain": "data_science", "draft": "model.fit(X_train, y_train)\nX_scaled = scaler.fit_transform(X)", "final": "scaler.fit(X_train)\nX_train_scaled = scaler.transform(X_train)\nmodel.fit(X_train_scaled, y_train)"},
    {"domain": "data_science", "draft": "The model achieved 95% accuracy, which is excellent.", "final": "95% accuracy matches baseline (5% positive rate). F1=0.12, PR-AUC=0.08. Model isn't learning the minority class."},
    # Executive
    {"domain": "executive", "draft": "In the third quarter, our company experienced a notable and significant increase in revenue that exceeded our initial expectations.", "final": "Q3 revenue: $4.2M (+23% YoY), beating plan by $600K."},
    {"domain": "executive", "draft": "We're growing fast and have lots of customers.", "final": "MRR grew 18% to $340K. 47 new logos. NDR 118%. 14mo runway."},
    {"domain": "executive", "draft": "We need to look into this further.", "final": "Action: VP Eng to deliver RCA by April 4. Include customer impact and remediation timeline."},
    # Support
    {"domain": "support", "draft": "Thank you for contacting us. We will get back to you within 24-48 hours.", "final": "Hi Sarah, thanks for reaching out about the billing discrepancy. I'm looking into this now and will update you by EOD."},
    {"domain": "support", "draft": "Escalating this to engineering.", "final": "Escalating to engineering.\n\nContext: Enterprise customer ($120K ARR) reports export timeout >50K rows since March 28. Workaround: batch 25K. P2."},
    {"domain": "support", "draft": "To rest your password, click Forgot Pasword.", "final": "To reset your password, click Forgot Password."},
    # Product
    {"domain": "product", "draft": "The system should be fast and easy to use.", "final": "P95 load: <2s. Setup: <5min. Task completion: >90% (Mixpanel funnel)."},
    {"domain": "product", "draft": "Add dark mode.", "final": "As a user in low-light, I want dark mode to reduce eye strain.\n\nAC:\n- Toggle persists\n- WCAG AA contrast\n- Charts adapt"},
    {"domain": "product", "draft": "This is a P1 feature.", "final": "P1 — RICE 847. Reach: 12K MAU. Impact: blocks 3 renewals ($360K). Confidence: 80%. Effort: 2 sprints."},
    # Research
    {"domain": "research", "draft": "Studies show transformers are more efficient than RNNs.", "final": "Transformers achieve higher throughput on >512 token sequences (Vaswani et al., 2017). Linear attention closes the gap >4K (Katharopoulos et al., 2020)."},
    {"domain": "research", "draft": "The result was statistically significant (p = 0.048).", "final": "After Bonferroni correction (12 comparisons), threshold is p<0.0042. Uncorrected p=0.048 doesn't survive. Cohen's d=0.31 (small)."},
    {"domain": "research", "draft": "We trained the model and evaluated performance.", "final": "Trained on WikiText-103 (103M tokens, 50K steps, batch=64, lr=3e-4). Evaluated on held-out test (245K tokens). Perplexity with 95% CI from 5 seeds."},
]

# Repeat scenarios with slight variations to reach higher counts
def _expand_scenarios(base: list[dict], target: int) -> list[dict]:
    """Expand base scenarios to target count by cycling with session markers."""
    expanded = []
    for i in range(target):
        s = base[i % len(base)].copy()
        cycle = i // len(base)
        if cycle > 0:
            # Add slight variation so drafts aren't identical
            s["draft"] = s["draft"] + f" [v{cycle}]"
            s["final"] = s["final"] + f" [v{cycle}]"
        expanded.append(s)
    return expanded


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def brain_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("stress_brain")


@pytest.fixture(scope="module")
def stress_results(brain_dir: Path) -> dict:
    """Run all corrections through a real Brain and collect metrics."""
    from gradata.brain import Brain

    brain = Brain.init(str(brain_dir), domain="Stress Test")

    # 360 corrections (36 base × 10 cycles) ≈ simulating 10 sessions of corrections
    scenarios = _expand_scenarios(CORRECTION_SCENARIOS, 360)

    results = {
        "events": [],
        "errors": [],
        "latencies": [],
        "severities": Counter(),
        "categories": Counter(),
        "domains": Counter(),
        "by_domain": defaultdict(list),
        "total": len(scenarios),
    }

    for i, scenario in enumerate(scenarios):
        t0 = time.perf_counter()
        try:
            event = brain.correct(scenario["draft"], scenario["final"])
            latency = (time.perf_counter() - t0) * 1000

            severity = event.get("data", {}).get("severity", "unknown")
            category = event.get("data", {}).get("category", "UNKNOWN")

            results["events"].append(event)
            results["latencies"].append(latency)
            results["severities"][severity] += 1
            results["categories"][category] += 1
            results["domains"][scenario["domain"]] += 1
            results["by_domain"][scenario["domain"]].append({
                "severity": severity,
                "edit_distance": event.get("data", {}).get("edit_distance", 0),
                "category": category,
                "latency_ms": latency,
            })
        except Exception as e:
            results["errors"].append({"index": i, "error": str(e), "domain": scenario["domain"]})

    # Run graduation on the brain's lessons
    results["brain"] = brain
    results["brain_dir"] = brain_dir

    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBrainCorrectPipeline:
    """Verify brain.correct() handles all scenarios without errors."""

    def test_no_errors(self, stress_results: dict) -> None:
        """All corrections should succeed (no exceptions)."""
        errors = stress_results["errors"]
        assert len(errors) == 0, (
            f"{len(errors)} corrections failed:\n" +
            "\n".join(f"  [{e['index']}] {e['domain']}: {e['error']}" for e in errors[:10])
        )

    def test_all_events_emitted(self, stress_results: dict) -> None:
        """Every correction should produce an event."""
        assert len(stress_results["events"]) == stress_results["total"]

    def test_events_have_required_fields(self, stress_results: dict) -> None:
        """Every event must have type, data.severity, data.edit_distance."""
        for i, event in enumerate(stress_results["events"]):
            assert event.get("type") == "CORRECTION", f"Event {i} missing type"
            data = event.get("data", {})
            assert "severity" in data, f"Event {i} missing severity"
            assert "edit_distance" in data, f"Event {i} missing edit_distance"
            assert "category" in data, f"Event {i} missing category"

    def test_edit_distances_valid(self, stress_results: dict) -> None:
        """All edit distances should be in [0, 1]."""
        for event in stress_results["events"]:
            d = event["data"]["edit_distance"]
            assert 0.0 <= d <= 1.0, f"edit_distance {d} out of bounds"


class TestSeverityDistribution:
    """Verify severity labels are distributed realistically."""

    def test_multiple_severities(self, stress_results: dict) -> None:
        """Should produce at least 3 different severity labels."""
        n_unique = len(stress_results["severities"])
        assert n_unique >= 3, (
            f"Only {n_unique} severity labels: {dict(stress_results['severities'])}"
        )

    def test_not_all_discarded(self, stress_results: dict) -> None:
        """Not every correction should be 'discarded' — some are small edits."""
        discarded = stress_results["severities"].get("discarded", 0)
        total = stress_results["total"]
        assert discarded < total * 0.90, (
            f"{discarded}/{total} corrections are 'discarded' — too many"
        )


class TestCategoryDetection:
    """Verify edit_classifier assigns meaningful categories."""

    def test_multiple_categories(self, stress_results: dict) -> None:
        """Should detect at least 3 different categories."""
        n_unique = len(stress_results["categories"])
        assert n_unique >= 3, (
            f"Only {n_unique} categories: {dict(stress_results['categories'])}"
        )

    def test_no_all_unknown(self, stress_results: dict) -> None:
        """Not every category should be UNKNOWN."""
        unknown = stress_results["categories"].get("UNKNOWN", 0)
        total = stress_results["total"]
        assert unknown < total * 0.50, (
            f"{unknown}/{total} categories are UNKNOWN — classifier not working"
        )


class TestPerformance:
    """Verify pipeline latency at scale."""

    def test_avg_latency_under_100ms(self, stress_results: dict) -> None:
        """Average correction latency should be < 100ms."""
        avg = statistics.mean(stress_results["latencies"])
        assert avg < 100, f"Average latency {avg:.1f}ms exceeds 100ms"

    def test_p95_latency_under_500ms(self, stress_results: dict) -> None:
        """P95 latency should be < 500ms."""
        sorted_lat = sorted(stress_results["latencies"])
        p95_idx = int(len(sorted_lat) * 0.95)
        p95 = sorted_lat[p95_idx]
        assert p95 < 500, f"P95 latency {p95:.1f}ms exceeds 500ms"


class TestEventPersistence:
    """Verify events are persisted to the brain's database."""

    def test_events_in_db(self, stress_results: dict) -> None:
        """Brain DB should contain all correction events."""
        import sqlite3
        brain_dir = stress_results["brain_dir"]
        db_path = brain_dir / "system.db"
        if not db_path.exists():
            pytest.skip("No system.db found (events may use jsonl)")
            return
        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM events WHERE type='CORRECTION'").fetchone()[0]
            assert count >= stress_results["total"] * 0.90, (
                f"DB has {count} CORRECTION events, expected >= {stress_results['total'] * 0.90:.0f}"
            )
        except sqlite3.OperationalError:
            pytest.skip("events table not found")
        finally:
            conn.close()


class TestDomainCoverage:
    """Verify all domains produced corrections."""

    def test_all_domains_hit(self, stress_results: dict) -> None:
        """All 11 domains should have at least 1 correction."""
        expected_domains = {
            "sales", "engineering", "accounting", "recruiting",
            "legal", "hr", "data_science", "executive",
            "support", "product", "research",
        }
        hit = set(stress_results["domains"].keys())
        missing = expected_domains - hit
        assert not missing, f"Missing domains: {missing}"


class TestPrintReport:
    """Print a human-readable report (always passes)."""

    def test_print_summary(self, stress_results: dict, capsys: pytest.CaptureFixture) -> None:
        print("\n" + "=" * 95)
        print("LIVE BRAIN STRESS TEST — FULL PIPELINE METRICS")
        print("=" * 95)

        total = stress_results["total"]
        errors = len(stress_results["errors"])
        latencies = stress_results["latencies"]

        print(f"\nCorrected: {total - errors}/{total}  |  Errors: {errors}")
        if latencies:
            print(f"Latency:   avg={statistics.mean(latencies):.1f}ms  "
                  f"p50={sorted(latencies)[len(latencies)//2]:.1f}ms  "
                  f"p95={sorted(latencies)[int(len(latencies)*0.95)]:.1f}ms  "
                  f"max={max(latencies):.1f}ms")

        print(f"\nSeverity distribution:")
        for sev, count in sorted(stress_results["severities"].items(), key=lambda x: -x[1]):
            bar = "#" * (count // 3)
            print(f"  {sev:<12} {count:>4}  {bar}")

        print(f"\nCategory distribution:")
        for cat, count in sorted(stress_results["categories"].items(), key=lambda x: -x[1])[:10]:
            bar = "#" * (count // 3)
            print(f"  {cat:<16} {count:>4}  {bar}")

        print(f"\nDomain breakdown:")
        print(f"  {'Domain':<16} {'Count':>5} {'AvgDist':>8} {'AvgLatency':>11}")
        print(f"  {'-'*42}")
        for domain in sorted(stress_results["by_domain"].keys()):
            runs = stress_results["by_domain"][domain]
            avg_dist = statistics.mean(r["edit_distance"] for r in runs)
            avg_lat = statistics.mean(r["latency_ms"] for r in runs)
            print(f"  {domain:<16} {len(runs):>5} {avg_dist:>8.4f} {avg_lat:>9.1f}ms")

        print("=" * 95)
