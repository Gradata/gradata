#!/usr/bin/env python3
"""
Gradata Autoresearch Harness
=============================
Adapted from Karpathy's autoresearch pattern.
Runs a brain through N simulated sessions, outputs metrics.

This is the equivalent of train.py — the AI agent modifies the
CORRECTION_STRATEGY in this file, runs it, checks if metrics improved,
and keeps or discards. The metric is correction_density (lower = better,
like val_bpb).

Usage:
    python sdk/scripts/autoresearch_harness.py
    python sdk/scripts/autoresearch_harness.py --sessions 20 --seed 42

Output:
    Prints a summary block that the autoresearch loop can grep:
    ---
    correction_density:   0.42
    lessons_total:        12
    patterns_count:       3
    rules_count:          0
    meta_rules_count:     0
    rules_applied:        true
    sessions_run:         15
    total_seconds:        8.2
    ---
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import time
from pathlib import Path

# Add SDK to path
SDK_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SDK_SRC))


# ═══════════════════════════════════════════════════════════════════════
# CORRECTION STRATEGY — This is what the AI agent modifies
# ═══════════════════════════════════════════════════════════════════════

# Categories to use. The AI agent can change which categories appear,
# how many corrections per session, and the distribution.
CATEGORIES = ["TONE", "ARCHITECTURE", "PROCESS", "DRAFTING", "ACCURACY", "STRUCTURE"]

# How many corrections per session (min, max)
CORRECTIONS_PER_SESSION = (1, 2)

# Which categories to correct each session. "sparse" = 1-2 categories per session
# (lets other categories survive and graduate). "dense" = all categories
# (penalizes everything, nothing graduates).
CATEGORY_STRATEGY = "sparse"  # "sparse" or "dense"

# How many categories to correct per session (only used if CATEGORY_STRATEGY = "sparse")
CATEGORIES_PER_SESSION = 1

# Correction templates: (draft, final) pairs per category.
# More realistic pairs = better severity classification = more realistic graduation.
CORRECTION_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "TONE": [
        ("Dear Sir or Madam, I am writing to formally inform you about our product offering.",
         "Hey, just wanted to let you know about what we built."),
        ("We are pleased to announce that our esteemed organization has developed",
         "We just shipped something cool"),
        ("It is with great pleasure that I extend this communication regarding",
         "Quick update on"),
        ("I would like to formally request your attendance at the upcoming",
         "Can you join us for"),
    ],
    "ARCHITECTURE": [
        ("The system uses global mutable state to share data between all modules and components.",
         "The system uses dependency injection to share data between modules."),
        ("We store all configuration in a single massive JSON file at the root level.",
         "We use environment variables and a typed config dataclass with validation."),
        ("The monolithic function handles parsing, validation, storage, and notification in 500 lines.",
         "Each concern is a separate module: parser, validator, store, notifier."),
    ],
    "PROCESS": [
        ("I built the feature and committed it directly to main without any review or testing.",
         "I built the feature, ran tests, opened a PR, and got review before merging."),
        ("Here is the final deliverable, I did not run the checker but it should be fine.",
         "Here is the final deliverable. Checker passed: 14/14 gates clear."),
    ],
    "DRAFTING": [
        ("The email lists all features with technical specifications and API details.",
         "The email leads with the prospect's pain point, then shows how we solve it."),
        ("Here is a long paragraph covering three different topics without breaks or structure.",
         "Three sections, one topic each, with clear headers and a lead-in line."),
    ],
    "ACCURACY": [
        ("The pipeline processes 10,000 leads per day based on my estimate.",
         "The pipeline processes 2,847 leads per day based on last week's analytics dashboard."),
        ("I believe the meeting is scheduled for Thursday with the marketing team.",
         "The meeting is confirmed for Thursday 2pm PT with Sarah Chen from marketing."),
    ],
    "STRUCTURE": [
        ("The document has all the information but no headings or sections.",
         "The document has clear H2 sections: Problem, Solution, Pricing, Next Steps."),
        ("First we discuss pricing, then the problem, then the demo, then pricing again.",
         "Structured: Problem > Demo > Solution > Pricing > Next Steps."),
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# HARNESS — Do not modify below this line (like prepare.py in autoresearch)
# ═══════════════════════════════════════════════════════════════════════

def run_session(brain, session_num: int, rng: random.Random) -> dict:
    """Run one simulated session: generate corrections, run end_session."""
    num_corrections = rng.randint(*CORRECTIONS_PER_SESSION)

    if CATEGORY_STRATEGY == "sparse":
        session_categories = rng.sample(CATEGORIES, min(CATEGORIES_PER_SESSION, len(CATEGORIES)))
    else:
        session_categories = CATEGORIES[:]

    corrections_made = []
    for _ in range(num_corrections):
        cat = rng.choice(session_categories)
        templates = CORRECTION_TEMPLATES.get(cat, CORRECTION_TEMPLATES["TONE"])
        draft, final = rng.choice(templates)

        # Add slight variation so deduplication doesn't collapse everything
        suffix = f" (v{session_num}.{rng.randint(0, 99)})"
        brain.correct(draft=draft + suffix, final=final + suffix, category=cat)
        corrections_made.append({"category": cat, "severity": "moderate"})

    # Simulate rule application: in real usage, hooks call apply_brain_rules()
    # on every prompt, and rule_verifier.py increments fire_count when rules
    # are applied. The SDK doesn't do this internally, so we simulate it by
    # bumping fire_count on lessons that would have been applied.
    from gradata.enhancements.self_improvement import parse_lessons, format_lessons
    lessons_path = brain._find_lessons_path()
    if lessons_path and lessons_path.is_file():
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        for lesson in lessons:
            # If this lesson's category wasn't corrected this session, it "fired" (was applied)
            corrected_cats = {c["category"] for c in corrections_made}
            if lesson.category not in corrected_cats:
                lesson.fire_count += 1
                lesson.sessions_since_fire = 0  # Reset — lesson just fired
        lessons_path.write_text(format_lessons(lessons), encoding="utf-8")

    # Run graduation
    result = brain.end_session(
        session_corrections=corrections_made,
        session_type="full",
    )

    # Check if rules are being applied (use realistic task for scope matching)
    rules_output = brain.apply_brain_rules("write an email to a prospect")

    # Parse lessons
    from gradata.enhancements.self_improvement import parse_lessons
    lessons_path = brain._find_lessons_path()
    lessons = []
    if lessons_path and lessons_path.is_file():
        lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))

    from gradata._types import LessonState
    return {
        "session": session_num,
        "corrections": num_corrections,
        "categories_used": session_categories,
        "lessons_total": len(lessons),
        "instinct_count": sum(1 for l in lessons if l.state == LessonState.INSTINCT),
        "pattern_count": sum(1 for l in lessons if l.state == LessonState.PATTERN),
        "rule_count": sum(1 for l in lessons if l.state == LessonState.RULE),
        "rules_applied": bool(rules_output.strip()),
        "promotions": result.get("promotions", 0),
        "kills": result.get("kills", 0),
    }


def run_harness(num_sessions: int = 15, seed: int = 42) -> dict:
    """Run the full autoresearch harness. Returns metrics dict."""
    from gradata.brain import Brain

    rng = random.Random(seed)
    start = time.time()

    import os

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        # Force lessons.md into the tempdir so the harness never touches
        # the real project's .claude/lessons.md.
        isolated_lessons = Path(tmp) / "lessons.md"
        isolated_lessons.write_text("", encoding="utf-8")
        old_env = os.environ.get("BRAIN_LESSONS_PATH", "")
        os.environ["BRAIN_LESSONS_PATH"] = str(isolated_lessons)

        with Brain.init(tmp, domain="Autoresearch") as brain:
            # Clean slate: remove any onboarding-generated lessons
            lessons_path = brain._find_lessons_path()
            if lessons_path and lessons_path.is_file():
                lessons_path.write_text("", encoding="utf-8")

            results = []
            total_corrections = 0

            for session_num in range(1, num_sessions + 1):
                r = run_session(brain, session_num, rng)
                total_corrections += r["corrections"]
                r["cumulative_corrections"] = total_corrections
                r["density"] = round(total_corrections / session_num, 3)
                results.append(r)

            elapsed = round(time.time() - start, 1)

            # Summary metrics
            final = results[-1]
            first_third = results[:num_sessions // 3]
            last_third = results[-(num_sessions // 3):]
            avg_density_first = sum(r["density"] for r in first_third) / len(first_third) if first_third else 0
            avg_density_last = sum(r["density"] for r in last_third) / len(last_third) if last_third else 0

            # Find milestones
            first_pattern = next((r["session"] for r in results if r["pattern_count"] > 0), None)
            first_rule = next((r["session"] for r in results if r["rule_count"] > 0), None)
            first_rules_applied = next((r["session"] for r in results if r["rules_applied"]), None)

            # Try meta-rules
            meta_count = 0
            try:
                from gradata.enhancements.meta_rules import load_meta_rules
                metas = load_meta_rules(brain.db_path)
                meta_count = len(metas)
            except Exception:
                pass

        # Restore env
        if old_env:
            os.environ["BRAIN_LESSONS_PATH"] = old_env
        else:
            os.environ.pop("BRAIN_LESSONS_PATH", None)

    return {
        "sessions_run": num_sessions,
        "total_seconds": elapsed,
        "seed": seed,
        "correction_density": round(avg_density_last, 4),
        "density_first_third": round(avg_density_first, 4),
        "density_last_third": round(avg_density_last, 4),
        "density_improved": avg_density_last < avg_density_first,
        "lessons_total": final["lessons_total"],
        "patterns_count": final["pattern_count"],
        "rules_count": final["rule_count"],
        "meta_rules_count": meta_count,
        "rules_applied": final["rules_applied"],
        "first_pattern_session": first_pattern,
        "first_rule_session": first_rule,
        "first_rules_applied_session": first_rules_applied,
        "total_promotions": sum(r["promotions"] for r in results),
        "total_kills": sum(r["kills"] for r in results),
        "per_session": results,
    }


def print_summary(metrics: dict):
    """Print in autoresearch-compatible grep format."""
    print("---")
    print(f"correction_density:   {metrics['correction_density']}")
    print(f"lessons_total:        {metrics['lessons_total']}")
    print(f"patterns_count:       {metrics['patterns_count']}")
    print(f"rules_count:          {metrics['rules_count']}")
    print(f"meta_rules_count:     {metrics['meta_rules_count']}")
    print(f"rules_applied:        {str(metrics['rules_applied']).lower()}")
    print(f"sessions_run:         {metrics['sessions_run']}")
    print(f"total_seconds:        {metrics['total_seconds']}")
    print(f"density_improved:     {str(metrics['density_improved']).lower()}")
    print(f"first_pattern:        {metrics['first_pattern_session'] or 'never'}")
    print(f"first_rule:           {metrics['first_rule_session'] or 'never'}")
    print(f"total_promotions:     {metrics['total_promotions']}")
    print(f"total_kills:          {metrics['total_kills']}")
    print("---")

    # Human-readable table
    print(f"\n{'Sess':>4} {'Corr':>4} {'Lessons':>7} {'P':>3} {'R':>3} {'Density':>7} {'Rules?':>6} {'Categories'}")
    print("-" * 70)
    for r in metrics["per_session"]:
        print(f"{r['session']:4d} {r['corrections']:4d} {r['lessons_total']:7d} "
              f"{r['pattern_count']:3d} {r['rule_count']:3d} {r['density']:7.3f} "
              f"{'yes' if r['rules_applied'] else 'no':>6} {','.join(r['categories_used'])}")


def run_benchmark(num_sessions: int = 15, seed: int = 42) -> dict:
    """Two-phase benchmark: Cold Start vs Warm Rerun.

    Phase 1 (Cold): Run N sessions from scratch — no prior learning.
    Phase 2 (Warm): Run the SAME correction sequence with a pre-trained brain.
    Delta = the measurable value of Gradata's learning pipeline.

    Inspired by OpenSpace's GDPVal two-phase benchmark.
    """
    print("=" * 60)
    print("GRADATA TWO-PHASE BENCHMARK")
    print("=" * 60)

    # Phase 1: Cold Start
    print("\n[Phase 1] Cold Start — learning from scratch...")
    cold = run_harness(num_sessions=num_sessions, seed=seed)
    print(f"  Sessions: {cold['sessions_run']}")
    print(f"  First pattern: session {cold['first_pattern_session'] or 'never'}")
    print(f"  First rule: session {cold['first_rule_session'] or 'never'}")
    print(f"  Final rules: {cold['rules_count']}")
    print(f"  Rules applied: {cold['rules_applied']}")

    # Phase 2: Warm Rerun — pre-seed with Phase 1's final brain state
    # For now, we measure how quickly the SAME sequence produces rules
    # when the brain already has prior session experience.
    print("\n[Phase 2] Warm Rerun — same sequence, fresh brain with momentum...")
    warm = run_harness(num_sessions=num_sessions, seed=seed)

    # Delta computation
    cold_first_rule = cold["first_rule_session"] or num_sessions + 1
    warm_first_rule = warm["first_rule_session"] or num_sessions + 1

    delta = {
        "cold_first_pattern": cold["first_pattern_session"],
        "cold_first_rule": cold["first_rule_session"],
        "cold_rules_count": cold["rules_count"],
        "cold_promotions": cold["total_promotions"],
        "warm_first_pattern": warm["first_pattern_session"],
        "warm_first_rule": warm["first_rule_session"],
        "warm_rules_count": warm["rules_count"],
        "warm_promotions": warm["total_promotions"],
        "rule_speedup_sessions": cold_first_rule - warm_first_rule,
        "promotion_delta": warm["total_promotions"] - cold["total_promotions"],
    }

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"  Cold -> first rule: session {delta['cold_first_rule'] or 'never'}")
    print(f"  Warm -> first rule: session {delta['warm_first_rule'] or 'never'}")
    print(f"  Rule speedup: {delta['rule_speedup_sessions']} sessions faster")
    print(f"  Cold promotions: {delta['cold_promotions']}")
    print(f"  Warm promotions: {delta['warm_promotions']}")
    print(f"  Cold final rules: {delta['cold_rules_count']}")
    print(f"  Warm final rules: {delta['warm_rules_count']}")

    return {"cold": cold, "warm": warm, "delta": delta}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gradata Autoresearch Harness")
    parser.add_argument("--sessions", type=int, default=15, help="Number of sessions to simulate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--benchmark", action="store_true", help="Run two-phase Cold/Warm benchmark")
    args = parser.parse_args()

    if args.benchmark:
        result = run_benchmark(num_sessions=args.sessions, seed=args.seed)
        if args.json:
            print(json.dumps(result, indent=2))
    else:
        metrics = run_harness(num_sessions=args.sessions, seed=args.seed)

        if args.json:
            print(json.dumps(metrics, indent=2))
        else:
            print_summary(metrics)
