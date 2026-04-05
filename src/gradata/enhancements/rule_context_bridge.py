"""Rule Context Bridge — Populates RuleContext from graduation events.

This is the bridge between the graduation pipeline (enhancements/) and the
pattern-facing RuleContext (patterns/). It:
1. Bootstraps RuleContext from existing graduated lessons at session start
2. Registers event triggers so new graduations publish in real-time

Lives in enhancements/ (Layer 1) because it imports from both:
- patterns/rule_context.py (Layer 0) — publishes to
- enhancements/self_improvement.py (Layer 1) — reads graduated lessons from
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("gradata")


def bootstrap_rule_context(
    lessons_path: Path | None = None,
    db_path: Path | None = None,
) -> int:
    """Load all existing graduated rules into RuleContext at session start.

    Reads from lessons.md for PATTERN/RULE tier lessons and from system.db
    for meta-rules. Returns count of rules loaded.

    Call once at Brain.__init__() or session start hook.
    """
    from gradata.rules.rule_context import GraduatedRule, get_rule_context

    ctx = get_rule_context()
    count = 0

    # Load from lessons.md
    if lessons_path and lessons_path.is_file():
        try:
            from gradata.enhancements.self_improvement import parse_lessons
            text = lessons_path.read_text(encoding="utf-8")
            lessons = parse_lessons(text)

            for lesson in lessons:
                if lesson.confidence < 0.60:
                    continue  # Only PATTERN+ tier

                scope = {}
                if lesson.scope_json:
                    try:
                        scope = json.loads(lesson.scope_json)
                    except (json.JSONDecodeError, TypeError):
                        pass

                rule_id = f"lesson:{lesson.category}:{lesson.description[:40]}"
                ctx.publish(GraduatedRule(
                    rule_id=rule_id,
                    category=lesson.category,
                    principle=lesson.description,
                    confidence=lesson.confidence,
                    scope=scope,
                    source_type="lesson",
                    agent_type=lesson.agent_type or "",
                ))
                count += 1

        except Exception as e:
            logger.warning("bootstrap_rule_context lessons failed: %s", e)

    # Load meta-rules from system.db
    if db_path and db_path.is_file():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT * FROM meta_rules WHERE status = 'active'"
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []  # Table may not exist yet
            finally:
                conn.close()
                # Force WAL checkpoint so Windows releases the file lock
                try:
                    c2 = sqlite3.connect(str(db_path))
                    c2.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    c2.close()
                except Exception:
                    pass

            for row in rows:
                rule_id = f"meta:{row['id']}"
                # sqlite3.Row supports [] access but not .get()
                try:
                    category = row["category"] if "category" in row.keys() else "META"
                except (KeyError, IndexError):
                    category = "META"
                try:
                    principle = row["principle"] if "principle" in row.keys() else str(row)
                except (KeyError, IndexError):
                    principle = str(row)
                ctx.publish(GraduatedRule(
                    rule_id=rule_id,
                    category=category,
                    principle=principle,
                    confidence=0.95,
                    source_type="meta_rule",
                ))
                count += 1

        except Exception as e:
            logger.debug("bootstrap_rule_context meta-rules: %s", e)

    if count > 0:
        logger.info("RuleContext bootstrapped: %d rules loaded", count)

    return count


def on_graduation_event(event: dict) -> None:
    """Event trigger: when a lesson graduates to PATTERN or RULE, publish.

    Register with: events.register_trigger("LESSON_CHANGE", on_graduation_event)
    """
    from gradata.rules.rule_context import GraduatedRule, get_rule_context

    data = event.get("data_json", event.get("data", {}))
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return

    new_state = data.get("new_state", "")
    if new_state not in ("PATTERN", "RULE"):
        return

    category = data.get("category", "GENERAL")
    description = data.get("description", "")
    if not description:
        return  # Skip events with no description
    confidence = data.get("new_confidence", 0.60)
    agent_type = data.get("agent_type", "")

    rule_id = f"lesson:{category}:{description[:40]}"
    ctx = get_rule_context()
    ctx.publish(GraduatedRule(
        rule_id=rule_id,
        category=category,
        principle=description,
        confidence=confidence,
        source_type="lesson",
        agent_type=agent_type,
    ))

    logger.debug("RuleContext: published %s [%s:%.2f]", category, new_state, confidence)


def on_meta_rule_event(event: dict) -> None:
    """Event trigger: when a meta-rule is discovered, publish."""
    from gradata.rules.rule_context import GraduatedRule, get_rule_context

    data = event.get("data_json", event.get("data", {}))
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return

    principle = data.get("principle", "")
    if not principle:
        return

    rule_id = f"meta:{hash(principle) & 0xFFFFFFFF}"
    ctx = get_rule_context()
    ctx.publish(GraduatedRule(
        rule_id=rule_id,
        category="META",
        principle=principle,
        confidence=0.95,
        source_type="meta_rule",
    ))
