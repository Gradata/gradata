"""
Router Warm-Start — Bootstrap Q-Learning router from vault data.
=================================================================
Loads existing correction events from the brain's event database,
computes reward signals from severity, and pre-trains the router's
Q-table so it doesn't start cold.

Usage::

    from gradata.enhancements.router_warmstart import warm_start_router

    router = warm_start_router(
        db_path=Path("brain/system.db"),
        router_path=Path("brain/q_router.json"),
    )
    print(router.stats())  # Shows pre-trained Q-table
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.contrib.patterns.q_learning_router import QLearningRouter

_log = logging.getLogger(__name__)

__all__ = [
    "warm_start_from_brain",
    "warm_start_router",
]


def warm_start_router(
    db_path: Path | str,
    router_path: Path | str | None = None,
    max_events: int = 1000,
) -> QLearningRouter:
    """Bootstrap a Q-Learning router from historical correction events.

    Reads CORRECTION events from the brain database, extracts severity
    and category, and feeds them as reward signals to pre-train the
    router's Q-table.

    Args:
        db_path: Path to the brain's system.db.
        router_path: Optional path to save the trained router state.
        max_events: Maximum number of events to process.

    Returns:
        A pre-trained QLearningRouter instance.
    """
    from gradata.contrib.patterns.q_learning_router import QLearningRouter, RouterConfig

    router = QLearningRouter(
        RouterConfig(
            epsilon_start=0.5,  # Less exploration since we have data
            epsilon_min=0.05,
            epsilon_decay=0.99,
        )
    )

    # Load existing router state if available
    if router_path and Path(router_path).exists():
        router.load(router_path)

    db_path = Path(db_path)
    if not db_path.exists():
        _log.warning("Database not found: %s", db_path)
        return router

    import contextlib

    try:
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            conn.row_factory = sqlite3.Row

            # Fetch correction events with severity and category
            rows = conn.execute(
                """
                SELECT
                    json_extract(data_json, '$.severity') as severity,
                    json_extract(data_json, '$.category') as category,
                    json_extract(data_json, '$.outcome') as outcome
                FROM events
                WHERE type = 'CORRECTION'
                  AND json_extract(data_json, '$.severity') IS NOT NULL
                  AND json_extract(data_json, '$.category') IS NOT NULL
                ORDER BY rowid DESC
                LIMIT ?
            """,
                (max_events,),
            ).fetchall()

        if not rows:
            _log.info("No correction events found for warm-start")
            return router

        # Feed each correction as a route + reward
        trained = 0
        for row in rows:
            severity = row["severity"] or "moderate"
            category = row["category"] or "UNKNOWN"

            # Route using the category as task description
            decision = router.route(f"correction in {category.lower()} category")

            # Compute reward from severity
            reward = router.reward_from_severity(severity)
            router.update_reward(decision, reward)
            trained += 1

        _log.info("Warm-started router with %d corrections", trained)

        # Save the trained router
        if router_path:
            router.save(router_path)

    except Exception as e:
        _log.warning("Warm-start failed: %s", e)

    return router


def warm_start_from_brain(brain_dir: Path | str) -> QLearningRouter:
    """Convenience: warm-start from a brain directory.

    Args:
        brain_dir: Path to the brain directory (containing system.db).

    Returns:
        Pre-trained QLearningRouter.
    """
    brain_dir = Path(brain_dir)
    return warm_start_router(
        db_path=brain_dir / "system.db",
        router_path=brain_dir / "q_router.json",
    )
