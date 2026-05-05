"""Reward helpers for the Agent-Lightning bridge."""

from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gradata import Brain

logger = logging.getLogger(__name__)


def gradata_reward(brain: Brain, task_input: dict[str, Any], agent_output: str) -> float:
    """Score an agent output against matching Gradata corrections.

    The reward is the highest string similarity between ``agent_output`` and a
    past correction's user-edited final text. If no matching correction exists,
    return neutral reward so sparse histories do not punish exploration.
    """
    query = _task_query(task_input)
    finals = _matching_correction_finals(brain, query)
    if not finals:
        return 0.5

    output = str(agent_output or "")
    best = max(SequenceMatcher(None, output, final).ratio() for final in finals)
    return max(0.0, min(1.0, float(best)))


def _task_query(task_input: dict[str, Any]) -> str:
    for key in ("task_input", "input", "draft", "prompt"):
        value = task_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(task_input, sort_keys=True, default=str)


def _matching_correction_finals(brain: Brain, query: str) -> list[str]:
    finals: list[str] = []
    seen: set[str] = set()

    for event in _search_correction_events(brain, query):
        final = _final_text(event)
        draft = _draft_text(event)
        if final and _matches_query(query, draft, event) and final not in seen:
            finals.append(final)
            seen.add(final)

    return finals


def _search_correction_events(brain: Brain, query: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        results = brain.search(query, mode="events", top_k=20)
    except Exception as exc:
        logger.debug("brain.search failed during reward lookup: %s", exc)
        results = []

    for result in results or []:
        event = _event_from_search_result(result)
        if event and event.get("type") == "CORRECTION":
            events.append(event)

    try:
        history = brain.query_events(event_type="CORRECTION", limit=200)
    except Exception as exc:
        logger.debug("brain.query_events failed during reward lookup: %s", exc)
        history = []
    events.extend(history or [])
    return events


def _event_from_search_result(result: dict[str, Any]) -> dict[str, Any] | None:
    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if "data" in data:
        return data
    return {"type": "CORRECTION", "data": data}


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    if isinstance(data, dict):
        return data
    raw = event.get("data_json")
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _final_text(event: dict[str, Any]) -> str:
    data = _event_data(event)
    for key in ("final_text", "final", "expected", "correction"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _draft_text(event: dict[str, Any]) -> str:
    data = _event_data(event)
    for key in ("draft_text", "draft", "task_input", "input"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _matches_query(query: str, draft: str, event: dict[str, Any]) -> bool:
    if not query:
        return True
    haystack = f"{draft} {json.dumps(_event_data(event), sort_keys=True, default=str)}".lower()
    terms = [term for term in query.lower().split() if term]
    return not terms or any(term in haystack for term in terms)
