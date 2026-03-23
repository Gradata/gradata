"""
Tag Taxonomy — Closed vocabulary for brain event tagging (SDK Copy).
=====================================================================
Defines valid tag prefixes, their allowed values, and which event types
REQUIRE which tags. Portable — uses _paths for prospect directory.
"""

import re
from pathlib import Path

import aios_brain._paths as _p

# ── Tag Prefixes ───────────────────────────────────────────────────────

TAXONOMY = {
    "prospect": {
        "desc": "Prospect name (matched against brain/prospects/ filenames)",
        "mode": "dynamic",
        "required_on": ["OUTPUT", "DELTA_TAG", "CORRECTION"],
    },
    "output": {
        "desc": "Output type produced",
        "mode": "closed",
        "values": {"email", "cheat_sheet", "research", "cold_call_script",
                   "linkedin_message", "crm_note", "proposal", "sequence",
                   "report", "system_artifact"},
        "required_on": ["OUTPUT"],
    },
    "angle": {
        "desc": "Sales angle used in outreach",
        "mode": "closed",
        "values": {"direct", "pain-point", "time-savings", "roi",
                   "competitor-displacement", "social-proof", "curiosity",
                   "event-triggered", "referral", "break-up", "custom"},
        "required_on": [],
    },
    "tone": {
        "desc": "Communication tone",
        "mode": "closed",
        "values": {"direct", "casual", "consultative", "formal", "urgent"},
        "required_on": [],
    },
    "persona": {
        "desc": "Buyer persona type",
        "mode": "closed",
        "values": {"agency-owner", "founder", "ecom-director", "cmo",
                   "growth-lead", "fractional-cmo", "marketing-manager",
                   "vp-marketing", "other"},
        "required_on": [],
    },
    "framework": {
        "desc": "Sales/email framework applied",
        "mode": "closed",
        "values": {"ccq", "spin", "gap", "jolt", "challenger",
                   "great-demo", "sandler", "custom"},
        "required_on": [],
    },
    "gate": {
        "desc": "Gate that triggered",
        "mode": "open",
        "required_on": ["GATE_RESULT", "GATE_OVERRIDE"],
    },
    "category": {
        "desc": "Correction/lesson category",
        "mode": "closed",
        "values": {"DRAFTING", "ACCURACY", "PROCESS", "ARCHITECTURE",
                   "COMMUNICATION", "POSITIONING", "PRESENTATION",
                   "CRM", "STRATEGY", "APIFY", "LEADS", "CONTEXT",
                   "CONSTRAINT", "DATA_INTEGRITY", "STARTUP",
                   "THOROUGHNESS", "COST"},
        "required_on": ["CORRECTION"],
    },
    "channel": {
        "desc": "Communication channel",
        "mode": "closed",
        "values": {"email", "phone", "linkedin", "meeting", "demo",
                   "slack", "text"},
        "required_on": ["DELTA_TAG"],
    },
    "outcome": {
        "desc": "Interaction outcome",
        "mode": "closed",
        "values": {"reply", "no-reply", "positive-reply", "negative-reply",
                   "meeting-booked", "demo-completed", "deal-advanced",
                   "deal-lost", "ghosted", "objection-raised", "pending"},
        "required_on": [],
    },
    "session": {
        "desc": "Session number",
        "mode": "open",
        "required_on": [],
    },
    "session_type": {
        "desc": "Session classification",
        "mode": "closed",
        "values": {"pipeline", "systems", "mixed"},
        "required_on": [],
    },
}


# ── Validation ─────────────────────────────────────────────────────────

def _get_prospect_names() -> set[str]:
    """Get valid prospect names from brain/prospects/ directory."""
    names = set()
    prospects_dir = _p.PROSPECTS_DIR
    if not prospects_dir.exists():
        return names
    for f in prospects_dir.glob("*.md"):
        if f.name.startswith("_"):
            continue
        parts = re.split(r"\s*[—–-]\s*", f.stem, maxsplit=1)
        names.add(parts[0].strip())
    return names


def validate_tag(tag: str, strict: bool = False) -> tuple[bool, str]:
    if ":" not in tag:
        return False, f"Tag missing ':' separator: {tag}"
    prefix, value = tag.split(":", 1)
    if prefix not in TAXONOMY:
        if strict:
            return False, f"Unknown tag prefix: {prefix}"
        return True, f"Unknown prefix (allowed in non-strict): {prefix}"
    spec = TAXONOMY[prefix]
    if spec["mode"] == "closed":
        if value not in spec["values"]:
            return False, f"Invalid {prefix} value: {value}. Valid: {sorted(spec['values'])}"
    if spec["mode"] == "dynamic" and prefix == "prospect":
        known = _get_prospect_names()
        if known and value not in known:
            first_names = {n.split()[0] for n in known}
            if value not in first_names:
                return False, f"Unknown prospect: {value}. Known: {sorted(known)[:5]}..."
    return True, "ok"


def validate_tags(tags: list[str], event_type: str = None,
                  strict: bool = False) -> list[str]:
    issues = []
    for tag in tags:
        valid, msg = validate_tag(tag, strict=strict)
        if not valid:
            issues.append(msg)
    if event_type:
        present_prefixes = {t.split(":")[0] for t in tags if ":" in t}
        for prefix, spec in TAXONOMY.items():
            if event_type in spec.get("required_on", []):
                if prefix not in present_prefixes:
                    issues.append(f"Missing required tag '{prefix}:' for {event_type} events")
    return issues


def enrich_tags(tags: list[str], event_type: str = None,
                data: dict = None) -> list[str]:
    enriched = list(tags)
    prefixes = {t.split(":")[0] for t in enriched if ":" in t}
    data = data or {}

    if event_type == "CORRECTION" and "category" not in prefixes:
        cat = data.get("category", "")
        if cat:
            enriched.append(f"category:{cat}")
    if event_type == "OUTPUT" and "output" not in prefixes:
        ot = data.get("output_type", "")
        if ot:
            # Normalize common variants to taxonomy values
            output_map = {
                "email_draft": "email", "email_reply": "email", "follow_up": "email",
                "call_script": "cold_call_script", "call_prep": "cold_call_script",
                "demo_prep": "cheat_sheet", "meeting_prep": "cheat_sheet",
                "linkedin_dm": "linkedin_message", "linkedin_connect": "linkedin_message",
            }
            normalized = output_map.get(ot, ot)
            enriched.append(f"output:{normalized}")
    if event_type == "DELTA_TAG" and "prospect" not in prefixes:
        prospect = data.get("prospect", "")
        if prospect:
            enriched.append(f"prospect:{prospect}")
    if event_type == "DELTA_TAG" and "channel" not in prefixes:
        activity = data.get("activity_type", "")
        channel_map = {
            "email_sent": "email", "email_received": "email",
            "call": "phone", "meeting": "meeting",
            "demo": "demo", "linkedin": "linkedin",
        }
        if activity in channel_map:
            enriched.append(f"channel:{channel_map[activity]}")
    return enriched


def get_taxonomy_summary() -> dict:
    return {
        prefix: {
            "description": spec["desc"],
            "mode": spec["mode"],
            "values": sorted(spec["values"]) if spec["mode"] == "closed" else None,
            "required_on": spec.get("required_on", []),
        }
        for prefix, spec in TAXONOMY.items()
    }
