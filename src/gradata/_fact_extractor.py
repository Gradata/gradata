"""
Structured fact extraction pipeline.
=====================================
Reads brain entity files (prospects/, candidates/, etc.) and extracts
structured facts. Domain-agnostic: entity directory and fact types are
configurable.
"""

import json
import re
import sqlite3
from pathlib import Path

from . import _paths as _p
from ._paths import BrainContext

# Constants — domain-specific fact types can be extended via brain config
_DEFAULT_FACT_TYPES = (
    "company_size", "tech_stack", "objection", "decision_maker",
    "pain_point", "budget", "timeline",
)

VALID_FACT_TYPES: tuple = _DEFAULT_FACT_TYPES
_lft_path = _p.BRAIN_DIR / "taxonomy.json" if hasattr(_p, "BRAIN_DIR") and _p.BRAIN_DIR else None
if _lft_path and _lft_path.exists():
    try:
        with open(_lft_path, encoding="utf-8") as _lft_f:
            _lft_extra = json.load(_lft_f).get("fact_types", [])
        if _lft_extra:
            VALID_FACT_TYPES = tuple(set(_DEFAULT_FACT_TYPES) | set(_lft_extra))
    except Exception:
        pass
MIN_FACT_LENGTH = 3
CONF_EXPLICIT = 0.9
CONF_INFERRED = 0.6


def _get_db(ctx: "BrainContext | None" = None):
    db = ctx.db_path if ctx else _p.DB_PATH
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect TEXT NOT NULL, company TEXT,
            fact_type TEXT NOT NULL, fact_value TEXT NOT NULL,
            confidence REAL DEFAULT 0.5, source TEXT,
            extracted_at TEXT, last_verified TEXT,
            session INTEGER, stale BOOLEAN DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_facts_prospect ON facts(prospect);
        CREATE INDEX IF NOT EXISTS idx_facts_type ON facts(fact_type);
    """)
    conn.commit()


def _parse_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        match = re.match(r"^(\w[\w_]*):\s*(.*?)(?:\s*#.*)?$", line)
        if match:
            key = match.group(1).strip()
            val = match.group(2).strip()
            if val and val[0] in ('"', "'") and val[-1] == val[0]:
                val = val[1:-1]
            if val.startswith("[") and val.endswith("]"):
                val = val[1:-1].strip()
            fm[key] = val
    return fm


def _get_entity_names():
    """Get entity names from brain directory (prospects, candidates, etc.)."""
    names = set()
    for dirname in ("prospects", "candidates", "customers", "entities"):
        entity_dir = _p.BRAIN_DIR / dirname if hasattr(_p, 'BRAIN_DIR') and _p.BRAIN_DIR else None
        if not entity_dir or not entity_dir.exists():
            continue
        for f in entity_dir.glob("*.md"):
            if f.name.startswith("_"):
                continue
            stem = f.stem
            parts = re.split(r"\s*[—–]\s*|\s+--\s+", stem, maxsplit=1)
            if parts:
                names.add(parts[0].strip())
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                fm = _parse_frontmatter(text)
                if fm.get("name"):
                    names.add(fm["name"].strip())
            except Exception:
                pass
    return names


# Backward compat alias
_get_prospect_names = _get_entity_names


def _quality_gate(fact_type, fact_value):
    if not fact_value or len(fact_value.strip()) < MIN_FACT_LENGTH:
        return False
    return fact_type in VALID_FACT_TYPES


def _clean_value(val):
    if not val:
        return ""
    val = val.strip()
    val = re.sub(r"\*\*", "", val)
    return val.strip()


def extract_from_file(filepath):
    filepath = Path(filepath)
    if not filepath.exists():
        return []
    text = filepath.read_text(encoding="utf-8", errors="replace")
    fm = _parse_frontmatter(text)
    facts = []
    prospect = fm.get("name", "")
    company = fm.get("company", "")
    source = str(filepath)

    if not prospect:
        stem = filepath.stem
        parts = re.split(r"\s*[—–]\s*|\s+--\s+", stem, maxsplit=1)
        if parts:
            prospect = parts[0].strip()
    if not company and len(re.split(r"\s*[—–]\s*|\s+--\s+", filepath.stem, maxsplit=1)) > 1:
        company = re.split(r"\s*[—–]\s*|\s+--\s+", filepath.stem, maxsplit=1)[1].strip()

    def add_fact(ftype, fvalue, conf=CONF_EXPLICIT):
        fvalue = _clean_value(fvalue)
        if _quality_gate(ftype, fvalue):
            facts.append({
                "prospect": prospect, "company": company,
                "fact_type": ftype, "fact_value": fvalue,
                "confidence": conf, "source": source,
            })

    # Frontmatter extraction
    if fm.get("deal_value"):
        add_fact("budget", fm["deal_value"], CONF_EXPLICIT)
    if fm.get("next_touch"):
        add_fact("timeline", f"next_touch: {fm['next_touch']}", CONF_EXPLICIT)
    if fm.get("next_action"):
        add_fact("timeline", fm["next_action"], CONF_EXPLICIT)

    # Body extraction
    title_m = re.search(r"\*\*Title:\*\*\s*(.+)", text)
    if title_m:
        add_fact("decision_maker", title_m.group(1), CONF_EXPLICIT)

    emp_m = re.search(r"\*\*Employees:\*\*\s*(.+)", text)
    if emp_m:
        emp_val = emp_m.group(1).strip()
        if emp_val and not emp_val.startswith("- **"):
            add_fact("company_size", emp_val, CONF_EXPLICIT)

    for pattern in [r"^(?:employees|team_size|headcount):\s*(.+)", r"- \*\*(?:Team Size|Headcount):\*\*\s*(.+)"]:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            val = m.group(1).strip()
            if val and val != fm.get("name", ""):
                add_fact("company_size", val, CONF_INFERRED)

    tech_m = re.search(r"\*\*Tech Stack:\*\*\s*(.+)", text)
    if tech_m:
        tech_val = tech_m.group(1).strip()
        if tech_val and not tech_val.startswith("- **"):
            add_fact("tech_stack", tech_val, CONF_EXPLICIT)

    tech_keywords = [
        "Meta Pixel", "Google Ads", "Facebook Ads", "TikTok Ads",
        "Shopify", "WordPress", "HubSpot", "Salesforce", "Marketo",
        "Google Analytics", "GA4", "Klaviyo", "Mailchimp", "Segment",
        "BigQuery", "Looker", "Triple Whale", "Northbeam", "Hyros",
    ]
    for kw in tech_keywords:
        if kw.lower() in text.lower():
            add_fact("tech_stack", kw, CONF_INFERRED)

    obj_section = re.search(r"## Objections Encountered\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if obj_section:
        rows = obj_section.group(1).strip().splitlines()
        for row in rows:
            if row.startswith("|") and not re.match(r"\|\s*-+", row) and "Objection" not in row:
                cols = [c.strip() for c in row.split("|")]
                if len(cols) >= 3 and cols[2]:
                    add_fact("objection", cols[2], CONF_EXPLICIT)

    for pattern in [r"(?:objection|concern|pushback):\s*(.+)"]:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            add_fact("objection", m.group(1), CONF_INFERRED)

    demo_obj_m = re.search(r"\*\*Objections:\*\*\s*([^\n]+)", text)
    if demo_obj_m:
        val = demo_obj_m.group(1).strip()
        if val and not val.startswith("- **"):
            add_fact("pain_point", val, CONF_EXPLICIT)

    for pattern in [r"^(?:pain|challenge|problem):\s*(.+)"]:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            add_fact("pain_point", m.group(1), CONF_INFERRED)

    for pattern in [r"- \*\*(?:Pain|Challenge):\*\*\s*(.+)"]:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            add_fact("pain_point", m.group(1), CONF_INFERRED)

    ad_spend_m = re.search(r"\*\*Ad Spend:\*\*\s*([^\n]+)", text)
    if ad_spend_m:
        val = ad_spend_m.group(1).strip()
        if val and not val.startswith("- **") and val != fm.get("deal_value", ""):
            add_fact("budget", val, CONF_INFERRED)

    for pattern in [r"^(?:budget):\s*(.+)"]:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            val = m.group(1).strip()
            if val and val != fm.get("deal_value", ""):
                add_fact("budget", val, CONF_INFERRED)

    fm_next_touch = fm.get("next_touch", "")
    fm_next_action = fm.get("next_action", "")
    for pattern in [r"^(?:next_step|timeline):\s*(.+)"]:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            val = m.group(1).strip()
            if val and val != fm_next_touch and val != fm_next_action:
                add_fact("timeline", val, CONF_INFERRED)

    return facts




def query_facts(prospect=None, fact_type=None, min_confidence=0.0,
                ctx: "BrainContext | None" = None):
    conn = _get_db(ctx)
    _init_tables(conn)
    sql = "SELECT * FROM facts WHERE stale=0"
    params = []
    if prospect:
        sql += " AND prospect LIKE ?"
        params.append(f"%{prospect}%")
    if fact_type:
        sql += " AND fact_type=?"
        params.append(fact_type)
    if min_confidence > 0:
        sql += " AND confidence >= ?"
        params.append(min_confidence)
    sql += " ORDER BY confidence DESC, extracted_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]




def get_stats(ctx: BrainContext | None = None):
    conn = _get_db(ctx)
    _init_tables(conn)
    rows = conn.execute(
        """SELECT fact_type, COUNT(*) as count,
           ROUND(AVG(confidence), 2) as avg_conf,
           SUM(CASE WHEN stale=1 THEN 1 ELSE 0 END) as stale_count
           FROM facts GROUP BY fact_type ORDER BY count DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
