"""
Context Packet Builder.
=========================
Generates structured context briefs before agent spawn.
"""

import contextlib
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import gradata._paths as _p

if TYPE_CHECKING:
    from gradata._paths import BrainContext


# Lazy imports
def _fts_search(query_text: str, **kwargs):
    from gradata._query import fts_search

    return fts_search(query_text, **kwargs)


def _events_query(**kwargs):
    from gradata._events import query as eq

    return eq(**kwargs)


def _correction_rate(**kwargs):
    from gradata._events import correction_rate

    return correction_rate(**kwargs)


def _detect_session():
    from gradata._events import _detect_session as ds

    return ds()


def _safe_read(path: Path, limit_chars: int = 0) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:limit_chars] if limit_chars > 0 else text
    except Exception:
        return ""


def _safe_read_lines(path: Path, max_lines: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[:max_lines])
    except Exception:
        return ""


def _fuzzy_match_prospect(name: str, ctx: "BrainContext | None" = None) -> Path | None:
    prospects_dir = ctx.prospects_dir if ctx else _p.PROSPECTS_DIR
    if not prospects_dir.exists():
        return None
    name_lower = name.lower()
    candidates = [c for c in prospects_dir.glob("*.md") if c.name != "_TEMPLATE.md"]
    for c in candidates:
        if c.stem.lower().startswith(name_lower):
            return c
    for c in candidates:
        if name_lower in c.stem.lower():
            return c
    first_name = name_lower.split()[0] if name_lower.split() else name_lower
    for c in candidates:
        if c.stem.lower().startswith(first_name):
            return c
    return None


def _load_user_scope(ctx: "BrainContext | None" = None) -> dict:
    result = {"voice_summary": "", "recent_corrections": [], "frameworks": ""}
    domain_dir = ctx.domain_dir if ctx else _p.DOMAIN_DIR
    soul_path = domain_dir / "soul.md"
    result["voice_summary"] = _safe_read_lines(soul_path, 20)
    try:
        corrections = _events_query(event_type="CORRECTION", limit=3)
        result["recent_corrections"] = [
            {
                "session": e.get("session"),
                "category": e.get("data", {}).get("category", ""),
                "detail": e.get("data", {}).get("detail", "")[:120],
            }
            for e in corrections
        ]
    except Exception:
        pass
    patterns_file = ctx.patterns_file if ctx else _p.PATTERNS_FILE
    if patterns_file.exists():
        result["frameworks"] = _safe_read_lines(patterns_file, 15)
    return result


def _load_prospect_context(prospect_name: str, ctx: "BrainContext | None" = None) -> dict:
    result = {
        "file_content": "",
        "search_results": [],
        "recent_interactions": [],
        "stage": "",
        "company": "",
        "persona": "",
    }
    prospect_file = _fuzzy_match_prospect(prospect_name, ctx=ctx)
    if prospect_file:
        raw = _safe_read(prospect_file, limit_chars=300)
        result["file_content"] = raw
        for line in raw.splitlines():
            if "Stage:" in line or "stage:" in line:
                result["stage"] = line.split(":", 1)[-1].strip()
            if "Company:" in line or "company:" in line:
                result["company"] = line.split(":", 1)[-1].strip()
            if "Persona:" in line or "persona:" in line:
                result["persona"] = line.split(":", 1)[-1].strip()
    try:
        fts_results = _fts_search(prospect_name, top_k=2)
        result["search_results"] = [
            {"source": r.get("source", ""), "text": r.get("text", "")[:120]}
            for r in fts_results[:2]
        ]
    except Exception:
        pass
    try:
        from gradata._fact_extractor import query_facts

        facts = query_facts(prospect=prospect_name)
        if facts:
            result["structured_facts"] = [
                {"type": f["fact_type"], "value": f["fact_value"], "confidence": f["confidence"]}
                for f in facts[:5]
            ]
    except Exception:
        pass
    try:
        all_events = _events_query(limit=50)
        prospect_lower = prospect_name.lower()
        interactions = []
        for e in all_events:
            tags = e.get("tags", [])
            tag_str = " ".join(tags).lower()
            if prospect_lower.split()[0] in tag_str:
                interactions.append(
                    {
                        "type": e.get("type", ""),
                        "summary": json.dumps(e.get("data", {}))[:80],
                    }
                )
                if len(interactions) >= 2:
                    break
        result["recent_interactions"] = interactions
    except Exception:
        pass
    return result


def _load_drafting_context(ctx: "BrainContext | None" = None) -> dict:
    result = {"patterns": "", "voice_guidelines": "", "frameworks": ""}
    patterns_file = ctx.patterns_file if ctx else _p.PATTERNS_FILE
    if patterns_file.exists():
        try:
            content = patterns_file.read_text(encoding="utf-8", errors="replace")
            relevant = [
                line.strip()
                for line in content.splitlines()
                if "[PROVEN]" in line or "[EMERGING]" in line
            ]
            result["patterns"] = "\n".join(relevant[:10])
        except Exception:
            pass
    domain_dir = ctx.domain_dir if ctx else _p.DOMAIN_DIR
    soul_path = domain_dir / "soul.md"
    result["voice_guidelines"] = _safe_read_lines(soul_path, 20)
    return result


def _load_debug_context(topic: str, ctx: "BrainContext | None" = None) -> dict:
    result = {"search_results": [], "recent_failures": [], "corrections": []}
    try:
        fts_results = _fts_search(topic, top_k=5)
        result["search_results"] = [
            {"source": r.get("source", ""), "text": r.get("text", "")[:300]}
            for r in fts_results[:3]
        ]
    except Exception:
        pass
    try:
        failures = _events_query(event_type="TOOL_FAILURE", limit=3)
        result["recent_failures"] = [
            {
                "source": e.get("source", ""),
                "detail": json.dumps(e.get("data", {}))[:120],
            }
            for e in failures
        ]
    except Exception:
        pass
    try:
        corrections = _events_query(event_type="CORRECTION", limit=10)
        topic_lower = topic.lower()
        related = []
        for e in corrections:
            data_str = json.dumps(e.get("data", {})).lower()
            if any(word in data_str for word in topic_lower.split()):
                related.append(
                    {
                        "session": e.get("session"),
                        "detail": e.get("data", {}).get("detail", "")[:120],
                    }
                )
                if len(related) >= 3:
                    break
        result["corrections"] = related
    except Exception:
        pass
    return result


def _load_audit_context(session: int, ctx: "BrainContext | None" = None) -> dict:
    result = {"metrics": {}, "outputs": [], "gates": [], "correction_rate": {}}
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM session_metrics WHERE session = ?", (session,)).fetchone()
        if row:
            result["metrics"] = dict(row)
        conn.close()
    except Exception:
        pass
    try:
        outputs = _events_query(event_type="OUTPUT", session=session, limit=20)
        result["outputs"] = [
            {
                "data": {
                    k: v
                    for k, v in e.get("data", {}).items()
                    if k in ("type", "self_score", "major_edit")
                },
            }
            for e in outputs
        ]
    except Exception:
        pass
    try:
        gates = _events_query(event_type="GATE_RESULT", session=session, limit=20)
        result["gates"] = [
            {
                "gate": e.get("data", {}).get("gate", ""),
                "result": e.get("data", {}).get("result", ""),
            }
            for e in gates
        ]
    except Exception:
        pass
    with contextlib.suppress(Exception):
        result["correction_rate"] = _correction_rate(last_n_sessions=5)
    return result


def _load_wrapup_context(session: int, ctx: "BrainContext | None" = None) -> dict:
    result = {"session_events": [], "modified_prospects": [], "current_loop_state": ""}
    try:
        events = _events_query(session=session, limit=50)
        result["session_events"] = [
            {
                "type": e.get("type", ""),
                "source": e.get("source", ""),
            }
            for e in events
        ]
    except Exception:
        pass
    try:
        today_str = date.today().isoformat()
        prospects_dir = ctx.prospects_dir if ctx else _p.PROSPECTS_DIR
        if prospects_dir.exists():
            for f in prospects_dir.glob("*.md"):
                if f.name == "_TEMPLATE.md":
                    continue
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime).date().isoformat()
                    if mtime == today_str:
                        result["modified_prospects"].append(f.stem)
                except Exception:
                    continue
    except Exception:
        pass
    loop_state = ctx.loop_state if ctx else _p.LOOP_STATE
    if loop_state.exists():
        result["current_loop_state"] = _safe_read(loop_state, limit_chars=500)
    return result


def format_as_prompt(packet: dict, task_type: str) -> str:
    sections = [
        f"# Context: {task_type or 'general'}",
    ]

    if "user_scope" in packet:
        us = packet["user_scope"]
        sections.append("## Preferences")
        if us.get("voice_summary"):
            sections.append(f"Voice: {us['voice_summary'][:200]}")
        if us.get("recent_corrections"):
            sections.append("Avoid:")
            for c in us["recent_corrections"][:3]:
                sections.append(f"- {c.get('category', '')}: {c.get('detail', '')[:80]}")
        sections.append("")

    if "prospect" in packet:
        pc = packet["prospect"]
        sections.append("## Prospect")
        if pc.get("company"):
            sections.append(f"Company: {pc['company']}")
        if pc.get("stage"):
            sections.append(f"Stage: {pc['stage']}")
        if pc.get("file_content"):
            sections.append(f"```\n{pc['file_content'][:250]}\n```")
        if pc.get("search_results"):
            for sr in pc["search_results"][:2]:
                sections.append(f"- [{sr.get('source', '')}] {sr.get('text', '')[:100]}")
        if pc.get("structured_facts"):
            sections.append("**Known facts:**")
            for f in pc["structured_facts"]:
                conf = f.get("confidence", 0)
                tag = "verified" if conf >= 0.8 else "inferred" if conf >= 0.5 else "guess"
                sections.append(f"- {f['type']}: {f['value']} [{tag}]")
        sections.append("")

    if "drafting" in packet:
        dc = packet["drafting"]
        sections.append("## Drafting")
        if dc.get("patterns"):
            for line in dc["patterns"].splitlines()[:5]:
                sections.append(f"- {line}")
        sections.append("")

    if "debug" in packet:
        dbg = packet["debug"]
        sections.append("## Debug")
        if dbg.get("search_results"):
            for sr in dbg["search_results"][:2]:
                sections.append(f"- [{sr.get('source', '')}] {sr.get('text', '')[:100]}")
        sections.append("")

    if "audit" in packet:
        ac = packet["audit"]
        sections.append("## Audit")
        if ac.get("metrics"):
            sections.append(json.dumps(ac["metrics"], default=str)[:300])
        sections.append("")

    if "wrapup" in packet:
        wc = packet["wrapup"]
        sections.append("## Wrap-Up")
        if wc.get("session_events"):
            type_counts: dict[str, int] = {}
            for e in wc["session_events"]:
                t = e.get("type", "UNKNOWN")
                type_counts[t] = type_counts.get(t, 0) + 1
            sections.append(json.dumps(type_counts))
        sections.append("")

    return "\n".join(sections)


def build_packet(
    prospect: str | None = None,
    task_type: str | None = None,
    topic: str | None = None,
    session: int | None = None,
    ctx: "BrainContext | None" = None,
) -> str:
    packet = {}
    if session is None:
        session = _detect_session()

    if task_type in ("prospecting", "meeting_prep"):
        packet["user_scope"] = _load_user_scope(ctx=ctx)
        if prospect:
            packet["prospect"] = _load_prospect_context(prospect, ctx=ctx)
    elif task_type == "drafting":
        packet["user_scope"] = _load_user_scope(ctx=ctx)
        if prospect:
            packet["prospect"] = _load_prospect_context(prospect, ctx=ctx)
        packet["drafting"] = _load_drafting_context(ctx=ctx)
    elif task_type == "critique":
        if prospect:
            packet["prospect"] = _load_prospect_context(prospect, ctx=ctx)
        packet["drafting"] = _load_drafting_context(ctx=ctx)
    elif task_type == "debug":
        packet["debug"] = _load_debug_context(topic or "", ctx=ctx)
    elif task_type == "audit":
        packet["audit"] = _load_audit_context(session, ctx=ctx)
    elif task_type in ("wrap-up", "wrapup"):
        packet["wrapup"] = _load_wrapup_context(session, ctx=ctx)
    else:
        packet["user_scope"] = _load_user_scope(ctx=ctx)

    return format_as_prompt(packet, task_type or "general")
