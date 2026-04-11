"""
brain_benchmark.py — Replay events.jsonl into a fresh brain and score quality.

Objective function for optimization sims. Returns a composite score (0-100)
based on 7 dimensions of brain learning quality.

Usage:
    # As module
    from brain_benchmark import score_brain
    result = score_brain(brain_dir, events_path, use_llm_judge=False)

    # As CLI
    python brain_benchmark.py brain_dir events_path [--max-events N]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {
    "trivial": 1,
    "minor": 2,
    "moderate": 3,
    "major": 4,
    "rewrite": 5,
}

LESSON_STATES = {
    "INSTINCT": 0.40,
    "PATTERN": 0.60,
    "RULE": 0.90,
}

# Scoring weights (must sum to 100)
WEIGHTS = {
    "graduation_ratio": 20,
    "correction_rate_improvement": 20,
    "confidence_distribution": 15,
    "severity_trend": 15,
    "category_extinction": 10,
    "rule_count": 10,
    "graduation_speed": 10,
}


# ---------------------------------------------------------------------------
# Event replay
# ---------------------------------------------------------------------------


def _load_events(events_path: Path, max_events: int | None = None) -> list[dict]:
    """Load events from a JSONL file, optionally capping at max_events."""
    events = []
    with open(events_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if max_events and len(events) >= max_events:
                break
    return events


def _replay_into_db(db_path: Path, events: list[dict]) -> None:
    """Replay events into an SQLite database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            session INTEGER,
            type TEXT NOT NULL,
            source TEXT,
            data_json TEXT,
            tags_json TEXT,
            valid_from TEXT,
            valid_until TEXT,
            scope TEXT DEFAULT 'local'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
    conn.commit()

    for ev in events:
        conn.execute(
            """INSERT INTO events (ts, session, type, source, data_json, tags_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ev.get("ts", ""),
                ev.get("session"),
                ev.get("type", "UNKNOWN"),
                ev.get("source", ""),
                json.dumps(ev.get("data")) if ev.get("data") else None,
                json.dumps(ev.get("tags")) if ev.get("tags") else None,
            ),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Scoring dimensions
# ---------------------------------------------------------------------------


def _score_graduation_ratio(events: list[dict]) -> float:
    """Fraction of created lessons that reached RULE state. 0-1 scaled."""
    created = set()
    graduated_to_rule = set()

    for ev in events:
        data = ev.get("data") or {}
        if ev.get("type") == "LESSON_CREATED":
            lid = data.get("lesson_id") or data.get("id") or data.get("description", "")
            if lid:
                created.add(lid)
        elif ev.get("type") == "LESSON_GRADUATED":
            lid = data.get("lesson_id") or data.get("id") or data.get("description", "")
            new_state = data.get("new_state") or data.get("to_state") or ""
            if lid and new_state.upper() == "RULE":
                graduated_to_rule.add(lid)

    if not created:
        return 0.0
    return len(graduated_to_rule) / len(created)


def _score_correction_rate_improvement(events: list[dict]) -> float:
    """Slope of corrections-per-session over time. Declining = good. 0-1 scaled."""
    corrections_per_session: dict[int, int] = defaultdict(int)
    for ev in events:
        if ev.get("type") == "CORRECTION":
            sess = ev.get("session")
            if sess is not None:
                try:
                    corrections_per_session[int(sess)] += 1
                except (ValueError, TypeError):
                    pass

    if len(corrections_per_session) < 2:
        return 0.0

    sessions = sorted(corrections_per_session.keys())
    rates = [corrections_per_session[s] for s in sessions]

    # Simple linear regression slope
    n = len(rates)
    x_mean = (n - 1) / 2.0
    y_mean = sum(rates) / n
    numerator = sum((i - x_mean) * (r - y_mean) for i, r in enumerate(rates))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0

    slope = numerator / denominator
    # Negative slope is good (corrections declining). Normalize to 0-1.
    # Clamp slope to [-2, 2] range for normalization
    clamped = max(-2.0, min(2.0, slope))
    # Map: -2 -> 1.0, 0 -> 0.5, +2 -> 0.0
    return max(0.0, min(1.0, 0.5 - clamped / 4.0))


def _score_confidence_distribution(events: list[dict]) -> tuple[float, dict]:
    """Mean confidence and spread from lesson events. Returns (score, details)."""
    confidences = []
    for ev in events:
        data = ev.get("data") or {}
        conf = data.get("confidence")
        if conf is not None and ev.get("type") in (
            "LESSON_CREATED",
            "LESSON_UPDATED",
            "LESSON_GRADUATED",
        ):
            try:
                confidences.append(float(conf))
            except (ValueError, TypeError):
                pass

    if not confidences:
        return 0.0, {"mean": 0.0, "std": 0.0, "count": 0}

    mean = sum(confidences) / len(confidences)
    variance = sum((c - mean) ** 2 for c in confidences) / len(confidences)
    std = variance**0.5

    # High mean = good. Low std = good (consistent).
    # Score: weighted combo of mean and (1 - normalized std)
    std_score = max(0.0, 1.0 - std)  # std is in [0, 1] for confidence values
    score = 0.7 * mean + 0.3 * std_score

    return score, {"mean": round(mean, 3), "std": round(std, 3), "count": len(confidences)}


def _score_category_extinction(events: list[dict]) -> float:
    """Categories that stop appearing in corrections = extinction. 0-1 scaled."""
    if not events:
        return 0.0

    # Split events into first half and second half by order
    corrections = [e for e in events if e.get("type") == "CORRECTION"]
    if len(corrections) < 4:
        return 0.0

    mid = len(corrections) // 2
    first_half = corrections[:mid]
    second_half = corrections[mid:]

    cats_first = {(e.get("data") or {}).get("category", "UNKNOWN") for e in first_half}
    cats_second = {(e.get("data") or {}).get("category", "UNKNOWN") for e in second_half}

    if not cats_first:
        return 0.0

    extinct = cats_first - cats_second
    return len(extinct) / len(cats_first)


def _score_severity_trend(events: list[dict]) -> float:
    """Average severity decreasing over time = good. 0-1 scaled."""
    corrections = [e for e in events if e.get("type") == "CORRECTION"]
    if len(corrections) < 2:
        return 0.0

    mid = len(corrections) // 2
    first_half = corrections[:mid]
    second_half = corrections[mid:]

    def avg_severity(evts: list[dict]) -> float:
        weights = []
        for e in evts:
            sev = (e.get("data") or {}).get("severity", "moderate")
            weights.append(SEVERITY_WEIGHTS.get(sev, 3))
        return sum(weights) / len(weights) if weights else 3.0

    avg_first = avg_severity(first_half)
    avg_second = avg_severity(second_half)

    if avg_first == 0:
        return 0.0

    # Improvement ratio: how much severity decreased
    improvement = (avg_first - avg_second) / avg_first
    # Clamp to [0, 1]
    return max(0.0, min(1.0, improvement * 2 + 0.5))


def _score_rule_count(events: list[dict]) -> float:
    """Number of active RULE-state lessons. Scaled by target of 20 rules. 0-1."""
    rules = set()
    for ev in events:
        data = ev.get("data") or {}
        if ev.get("type") == "LESSON_GRADUATED":
            new_state = data.get("new_state") or data.get("to_state") or ""
            lid = data.get("lesson_id") or data.get("id") or data.get("description", "")
            if new_state.upper() == "RULE" and lid:
                rules.add(lid)

    target = 20  # reasonable target for a mature brain
    return min(1.0, len(rules) / target)


def _score_graduation_speed(events: list[dict]) -> tuple[float, int | None]:
    """Sessions to first RULE graduation. Faster = better. Returns (score, sessions)."""
    first_session = None
    first_rule_session = None

    for ev in events:
        sess = ev.get("session")
        if sess is None:
            continue
        try:
            sess = int(sess)
        except (ValueError, TypeError):
            continue
        if first_session is None or sess < first_session:
            first_session = sess

        data = ev.get("data") or {}
        if ev.get("type") == "LESSON_GRADUATED":
            new_state = data.get("new_state") or data.get("to_state") or ""
            if new_state.upper() == "RULE":
                if first_rule_session is None or sess < first_rule_session:
                    first_rule_session = sess

    if first_session is None or first_rule_session is None:
        return 0.0, None

    sessions_to_rule = first_rule_session - first_session
    # Target: rule graduation within 10 sessions is perfect
    target = 10
    if sessions_to_rule <= 0:
        return 1.0, 0
    score = max(0.0, 1.0 - (sessions_to_rule - target) / (target * 3))
    return min(1.0, score), sessions_to_rule


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def score_brain(
    brain_dir: str | Path,
    events_path: str | Path,
    *,
    max_events: int | None = None,
    use_llm_judge: bool = False,
) -> dict[str, Any]:
    """Replay events and compute a composite brain quality score.

    Args:
        brain_dir: Path to brain directory (must contain system.db).
        events_path: Path to events.jsonl file.
        max_events: Optional cap on events to replay.
        use_llm_judge: Whether to use LLM for qualitative scoring (not implemented).

    Returns:
        Dict with composite_score (0-100) and per-dimension breakdowns.
    """
    brain_dir = Path(brain_dir)
    events_path = Path(events_path)

    events = _load_events(events_path, max_events=max_events)

    if not events:
        return {
            "composite_score": 0.0,
            "events_replayed": 0,
            "graduation_ratio": 0.0,
            "correction_rate_improvement": 0.0,
            "confidence_distribution": {"mean": 0.0, "std": 0.0, "count": 0},
            "category_extinction": 0.0,
            "severity_trend": 0.0,
            "rule_count": 0,
            "graduation_speed": None,
            "dimensions": {},
        }

    # Replay into a temp copy of the DB (don't mutate the real brain)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / "benchmark.db"
        _replay_into_db(tmp_db, events)

    # Compute each dimension
    grad_ratio = _score_graduation_ratio(events)
    corr_improvement = _score_correction_rate_improvement(events)
    conf_score, conf_details = _score_confidence_distribution(events)
    extinction = _score_category_extinction(events)
    sev_trend = _score_severity_trend(events)
    rule_count_score = _score_rule_count(events)
    grad_speed_score, grad_speed_sessions = _score_graduation_speed(events)

    # Count raw metrics
    raw_rule_count = len(
        {
            (ev.get("data") or {}).get("lesson_id") or (ev.get("data") or {}).get("id", "")
            for ev in events
            if ev.get("type") == "LESSON_GRADUATED"
            and (
                (ev.get("data") or {}).get("new_state")
                or (ev.get("data") or {}).get("to_state", "")
            ).upper()
            == "RULE"
        }
    )

    dimensions = {
        "graduation_ratio": {"score": round(grad_ratio, 3), "weight": WEIGHTS["graduation_ratio"]},
        "correction_rate_improvement": {
            "score": round(corr_improvement, 3),
            "weight": WEIGHTS["correction_rate_improvement"],
        },
        "confidence_distribution": {
            "score": round(conf_score, 3),
            "weight": WEIGHTS["confidence_distribution"],
        },
        "severity_trend": {"score": round(sev_trend, 3), "weight": WEIGHTS["severity_trend"]},
        "category_extinction": {
            "score": round(extinction, 3),
            "weight": WEIGHTS["category_extinction"],
        },
        "rule_count": {"score": round(rule_count_score, 3), "weight": WEIGHTS["rule_count"]},
        "graduation_speed": {
            "score": round(grad_speed_score, 3),
            "weight": WEIGHTS["graduation_speed"],
        },
    }

    composite = sum(d["score"] * d["weight"] for d in dimensions.values())

    return {
        "composite_score": round(composite, 2),
        "events_replayed": len(events),
        "graduation_ratio": round(grad_ratio, 3),
        "correction_rate_improvement": round(corr_improvement, 3),
        "confidence_distribution": conf_details,
        "category_extinction": round(extinction, 3),
        "severity_trend": round(sev_trend, 3),
        "rule_count": raw_rule_count,
        "graduation_speed": grad_speed_sessions,
        "dimensions": dimensions,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Brain Benchmark — score brain quality from events"
    )
    parser.add_argument("brain_dir", help="Path to brain directory")
    parser.add_argument("events_path", help="Path to events.jsonl")
    parser.add_argument("--max-events", type=int, default=None, help="Max events to replay")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = score_brain(args.brain_dir, args.events_path, max_events=args.max_events)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f"  BRAIN BENCHMARK -- Composite Score: {result['composite_score']:.1f} / 100")
        print(f"{'=' * 60}")
        print(f"  Events replayed: {result['events_replayed']}")
        print(f"  Rules graduated: {result['rule_count']}")
        print(f"  Graduation speed: {result['graduation_speed'] or 'N/A'} sessions")
        print(
            f"  Confidence: mean={result['confidence_distribution']['mean']:.3f} std={result['confidence_distribution']['std']:.3f}"
        )
        print()
        print("  Dimension Scores (score x weight = points):")
        print(f"  {'-' * 50}")
        for name, d in result["dimensions"].items():
            pts = d["score"] * d["weight"]
            bar = "#" * int(d["score"] * 20) + "." * (20 - int(d["score"] * 20))
            print(f"  {name:<30s} {bar} {d['score']:.2f} x {d['weight']:>2d} = {pts:5.1f}")
        print(f"  {'-' * 50}")
        print(f"  {'TOTAL':<30s} {'':>20s} {'':>4s}   {'':>2s}   {result['composite_score']:5.1f}")
        print()


if __name__ == "__main__":
    main()
