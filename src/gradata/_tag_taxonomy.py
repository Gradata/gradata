"""Configurable tag vocabulary for brain events: valid prefixes, allowed values per prefix,
required-tag rules per event type. Brain ``taxonomy.json`` overrides SDK defaults."""

import json
import re

from . import _paths as _p

# ── Domain-Agnostic Core Tags (always present) ────────────────────────
# These tags apply to ALL domains — they describe the brain's learning
# system, not any specific business function.

_CORE_TAXONOMY = {
    "gate": {
        "desc": "Gate that triggered",
        "mode": "open",
        "required_on": ["GATE_RESULT", "GATE_OVERRIDE"],
    },
    "category": {
        "desc": "Correction/lesson category",
        "mode": "closed",
        "values": {
            # Core categories (from edit classifier: content/factual/tone/structure/style)
            "CONTENT",
            "FACTUAL",
            "TONE",
            "STRUCTURE",
            "STYLE",
            # Learning system categories
            "DRAFTING",
            "ACCURACY",
            "PROCESS",
            "ARCHITECTURE",
            "COMMUNICATION",
            "CONTEXT",
            "CONSTRAINT",
            "DATA_INTEGRITY",
            "THOROUGHNESS",
            "COST",
            # Rosch superordinate categories
            "VOICE",
            "QUALITY",
        },
        "required_on": ["CORRECTION"],
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
    "tone": {
        "desc": "Communication tone",
        "mode": "closed",
        "values": {"direct", "casual", "consultative", "formal", "urgent"},
        "required_on": [],
    },
    "cognitive_load": {
        "desc": "Cognitive load type (Sweller's CLT)",
        "mode": "closed",
        "values": {"intrinsic", "extraneous", "germane"},
        "required_on": [],
    },
}

# ── Rosch 6-Category Hierarchy ───────────────────────────────────────
# Superordinate categories that group fine-grained correction categories
# into broader cognitive buckets (inspired by Rosch's prototype theory).
# A subordinate may appear under multiple parents (e.g. ACCURACY is both
# PROCESS and QUALITY).

ROSCH_HIERARCHY: dict[str, set[str]] = {
    "CONTENT": {"FACTUAL", "DATA_INTEGRITY", "ENTITIES"},
    "VOICE": {"TONE", "STYLE", "COMMUNICATION", "PRESENTATION"},
    "STRUCTURE": {"ARCHITECTURE", "CONTEXT"},
    "PROCESS": {"DRAFTING", "ACCURACY", "THOROUGHNESS"},
    "CONSTRAINT": {"CRM", "STRATEGY", "POSITIONING", "COST", "STARTUP"},
    "QUALITY": {"DATA_INTEGRITY", "ACCURACY", "THOROUGHNESS"},
}

ROSCH_PARENTS: set[str] = set(ROSCH_HIERARCHY.keys())

_SUB_TO_PARENT: dict[str, str] = {}
for _parent, _subs in ROSCH_HIERARCHY.items():
    for _sub in _subs:
        _SUB_TO_PARENT.setdefault(_sub, _parent)
for _rp in ROSCH_PARENTS:
    _SUB_TO_PARENT[_rp] = _rp


# ── Domain-Specific Defaults (Sales) ──────────────────────────────────
# These ship as defaults because sales is the first domain.
# Other domains override via brain_dir/taxonomy.json.

_SALES_DOMAIN_TAXONOMY = {
    "entity": {
        "desc": "Primary entity (prospect, candidate, customer, etc.)",
        "mode": "dynamic",
        "required_on": ["OUTPUT", "DELTA_TAG", "CORRECTION"],
    },
    # Legacy alias — "prospect:" tags are accepted as "entity:" in sales domain
    "prospect": {
        "desc": "Prospect name (alias for entity in sales domain)",
        "mode": "dynamic",
        "required_on": [],
    },
    "output": {
        "desc": "Output type produced",
        "mode": "closed",
        "values": {
            "email",
            "cheat_sheet",
            "research",
            "cold_call_script",
            "linkedin_message",
            "crm_note",
            "proposal",
            "sequence",
            "report",
            "system_artifact",
        },
        "required_on": ["OUTPUT"],
    },
    "angle": {
        "desc": "Communication angle used in messaging",
        "mode": "closed",
        "values": {
            "direct",
            "pain-point",
            "time-savings",
            "roi",
            "competitor-displacement",
            "social-proof",
            "curiosity",
            "event-triggered",
            "referral",
            "break-up",
            "custom",
        },
        "required_on": [],
    },
    "persona": {
        "desc": "Buyer persona type",
        "mode": "closed",
        "values": {
            "agency-owner",
            "founder",
            "ecom-director",
            "cmo",
            "growth-lead",
            "fractional-cmo",
            "marketing-manager",
            "vp-marketing",
            "other",
        },
        "required_on": [],
    },
    "framework": {
        "desc": "Sales/email framework applied",
        "mode": "closed",
        "values": {"ccq", "spin", "gap", "jolt", "challenger", "great-demo", "sandler", "custom"},
        "required_on": [],
    },
    "channel": {
        "desc": "Communication channel",
        "mode": "closed",
        "values": {"email", "phone", "linkedin", "meeting", "demo", "slack", "text"},
        "required_on": ["DELTA_TAG"],
    },
    "outcome": {
        "desc": "Interaction outcome",
        "mode": "closed",
        "values": {
            "reply",
            "no-reply",
            "positive-reply",
            "negative-reply",
            "meeting-booked",
            "demo-completed",
            "deal-advanced",
            "deal-lost",
            "ghosted",
            "objection-raised",
            "pending",
        },
        "required_on": [],
    },
}

# Sales-specific correction categories (extend core set)
_DOMAIN_CATEGORIES = {"CRM", "STRATEGY", "ENTITIES", "POSITIONING", "PRESENTATION", "STARTUP"}


def _load_taxonomy() -> dict:
    """Build the active taxonomy: core + domain config (or sales defaults).

    Priority:
    1. Core tags (always present, immutable)
    2. brain_dir/taxonomy.json (if exists — user-defined domain taxonomy)
    3. Sales defaults (fallback when no taxonomy.json found)
    """
    taxonomy = dict(_CORE_TAXONOMY)

    # Try loading domain config from brain directory
    taxonomy_path = (
        _p.BRAIN_DIR / "taxonomy.json" if hasattr(_p, "BRAIN_DIR") and _p.BRAIN_DIR else None
    )
    if taxonomy_path and taxonomy_path.exists():
        try:
            with open(taxonomy_path, encoding="utf-8") as f:
                domain_taxonomy = json.load(f)
            # Merge domain taxonomy into core (domain can't override core tags)
            # Reserved config keys (not tag definitions)
            _META_KEYS = {"extra_categories", "fact_types", "domain", "version"}
            for key, spec in domain_taxonomy.items():
                if key in _META_KEYS or key in _CORE_TAXONOMY:
                    continue
                if not isinstance(spec, dict):
                    continue  # Skip non-dict entries
                # Convert value lists to sets for validation
                if "values" in spec and isinstance(spec["values"], list):
                    spec["values"] = set(spec["values"])
                # Ensure required_on is present
                spec.setdefault("required_on", [])
                spec.setdefault("mode", "closed")
                taxonomy[key] = spec
            # Extend core category values if domain provides extra categories
            if "extra_categories" in domain_taxonomy:
                taxonomy["category"]["values"] = taxonomy["category"]["values"] | set(
                    domain_taxonomy["extra_categories"]
                )
            return taxonomy
        except Exception:
            pass  # Fall through to defaults

    # Fallback: merge sales defaults
    taxonomy.update(_SALES_DOMAIN_TAXONOMY)
    # Extend core categories with sales-specific ones
    taxonomy["category"]["values"] = taxonomy["category"]["values"] | _DOMAIN_CATEGORIES
    return taxonomy


# Active taxonomy — loaded once at import, reloadable via reload_taxonomy()
TAXONOMY: dict = _load_taxonomy()


def reload_taxonomy() -> None:
    """Reload taxonomy from brain config. Call after set_brain_dir()."""
    global TAXONOMY
    TAXONOMY = _load_taxonomy()


# ── Validation ─────────────────────────────────────────────────────────


def _get_entity_names() -> set[str]:
    """Get valid entity names from brain's entity directory.

    In sales: brain/prospects/. In recruiting: brain/candidates/.
    Falls back to scanning prospects/ for backward compat.
    """
    names = set()
    # Try common entity directory names
    for dirname in ("prospects", "candidates", "customers", "entities"):
        entity_dir = _p.BRAIN_DIR / dirname if hasattr(_p, "BRAIN_DIR") and _p.BRAIN_DIR else None
        if entity_dir and entity_dir.exists():
            for f in entity_dir.glob("*.md"):
                if f.name.startswith("_"):
                    continue
                parts = re.split(r"\s*[—–-]\s*", f.stem, maxsplit=1)
                names.add(parts[0].strip())
    # Legacy fallback
    if not names and hasattr(_p, "PROSPECTS_DIR"):
        prospects_dir = _p.PROSPECTS_DIR
        if prospects_dir.exists():
            for f in prospects_dir.glob("*.md"):
                if f.name.startswith("_"):
                    continue
                parts = re.split(r"\s*[—–-]\s*", f.stem, maxsplit=1)
                names.add(parts[0].strip())
    return names


# Backward compat alias
_get_prospect_names = _get_entity_names


def validate_tag(tag: str, strict: bool = False) -> tuple[bool, str]:
    if ":" not in tag:
        return False, f"Tag missing ':' separator: {tag}"
    prefix, value = tag.split(":", 1)
    if prefix not in TAXONOMY:
        if strict:
            return False, f"Unknown tag prefix: {prefix}"
        return True, f"Unknown prefix (allowed in non-strict): {prefix}"
    spec = TAXONOMY[prefix]
    if spec["mode"] == "closed" and value not in spec["values"]:
        return False, f"Invalid {prefix} value: {value}. Valid: {sorted(spec['values'])}"
    if spec["mode"] == "dynamic" and prefix in ("prospect", "entity", "candidate", "customer"):
        known = _get_entity_names()
        if known and value not in known:
            first_names = {n.split()[0] for n in known}
            if value not in first_names:
                return False, f"Unknown {prefix}: {value}. Known: {sorted(known)[:5]}..."
    return True, "ok"


def validate_tags(
    tags: list[str], event_type: str | None = None, strict: bool = False
) -> list[str]:
    issues = []
    for tag in tags:
        valid, msg = validate_tag(tag, strict=strict)
        if not valid:
            issues.append(msg)
    if event_type:
        present_prefixes = {t.split(":")[0] for t in tags if ":" in t}
        for prefix, spec in TAXONOMY.items():
            if event_type in spec.get("required_on", []) and prefix not in present_prefixes:
                issues.append(f"Missing required tag '{prefix}:' for {event_type} events")
    return issues


def enrich_tags(
    tags: list[str], event_type: str | None = None, data: dict | None = None
) -> list[str]:
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
                "email_draft": "email",
                "email_reply": "email",
                "follow_up": "email",
                "call_script": "cold_call_script",
                "call_prep": "cold_call_script",
                "demo_prep": "cheat_sheet",
                "meeting_prep": "cheat_sheet",
                "linkedin_dm": "linkedin_message",
                "linkedin_connect": "linkedin_message",
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
            "email_sent": "email",
            "email_received": "email",
            "call": "phone",
            "meeting": "meeting",
            "demo": "demo",
            "linkedin": "linkedin",
        }
        if activity in channel_map:
            enriched.append(f"channel:{channel_map[activity]}")
    if event_type == "CORRECTION" and "cognitive_load" not in prefixes:
        cat = data.get("category", "").upper()
        _COGNITIVE_LOAD_MAP = {
            "FACTUAL": "intrinsic",
            "CONTENT": "intrinsic",
            "DATA_INTEGRITY": "intrinsic",
            "ENTITIES": "intrinsic",
            "CONTEXT": "intrinsic",
            "STYLE": "extraneous",
            "TONE": "extraneous",
            "COMMUNICATION": "extraneous",
            "PRESENTATION": "extraneous",
            "COST": "extraneous",
            "PROCESS": "germane",
            "DRAFTING": "germane",
            "ACCURACY": "germane",
            "THOROUGHNESS": "germane",
            "ARCHITECTURE": "germane",
            "CONSTRAINT": "germane",
            "STRATEGY": "germane",
            "POSITIONING": "germane",
        }
        cl = _COGNITIVE_LOAD_MAP.get(cat)
        if cl:
            enriched.append(f"cognitive_load:{cl}")
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
