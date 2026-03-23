"""
Structured fact extraction pipeline (SDK Copy).
=================================================
Reads brain/prospects/*.md, extracts structured facts.
Portable — uses _paths for all directory references.
"""

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aios_brain._paths as _p

# Constants
VALID_FACT_TYPES = (
    "company_size", "tech_stack", "objection", "decision_maker",
    "pain_point", "budget", "timeline",
)
MIN_FACT_LENGTH = 3
CONF_EXPLICIT = 0.9
CONF_INFERRED = 0.6
CONF_GUESSED = 0.3


def _get_db():
    conn = sqlite3.connect(str(_p.DB_PATH))
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


def _get_prospect_names():
    names = set()
    prospects_dir = _p.PROSPECTS_DIR
    for f in prospects_dir.glob("*.md"):
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


def _quality_gate(fact_type, fact_value):
    if not fact_value or len(fact_value.strip()) < MIN_FACT_LENGTH:
        return False
    if fact_type not in VALID_FACT_TYPES:
        return False
    return True


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


def extract_all():
    all_facts = []
    valid_names = _get_prospect_names()
    prospects_dir = _p.PROSPECTS_DIR
    for f in sorted(prospects_dir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        file_facts = extract_from_file(f)
        for fact in file_facts:
            if fact["prospect"] in valid_names:
                all_facts.append(fact)
    return all_facts


def store_facts(facts_list):
    conn = _get_db()
    _init_tables(conn)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inserted = 0
    updated = 0
    for fact in facts_list:
        existing = conn.execute(
            "SELECT id, confidence FROM facts WHERE prospect=? AND fact_type=? AND fact_value=?",
            (fact["prospect"], fact["fact_type"], fact["fact_value"])
        ).fetchone()
        if existing:
            new_conf = max(existing["confidence"], fact["confidence"])
            conn.execute(
                "UPDATE facts SET confidence=?, last_verified=?, source=?, stale=0 WHERE id=?",
                (new_conf, now, fact["source"], existing["id"])
            )
            updated += 1
        else:
            conn.execute(
                """INSERT INTO facts (prospect, company, fact_type, fact_value, confidence,
                   source, extracted_at, last_verified, stale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (fact["prospect"], fact.get("company", ""), fact["fact_type"],
                 fact["fact_value"], fact["confidence"], fact["source"], now, now)
            )
            inserted += 1
    conn.commit()
    conn.close()
    return inserted, updated


def query_facts(prospect=None, fact_type=None, min_confidence=0.0):
    conn = _get_db()
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


def mark_stale(days=30):
    conn = _get_db()
    _init_tables(conn)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = conn.execute("UPDATE facts SET stale=1 WHERE last_verified < ? AND stale=0", (cutoff,))
    count = result.rowcount
    conn.commit()
    conn.close()
    return count


def decay_confidence(days=14):
    conn = _get_db()
    _init_tables(conn)
    now = datetime.now(timezone.utc)
    rows = conn.execute("SELECT id, confidence, last_verified FROM facts WHERE stale=0").fetchall()
    updated = 0
    for row in rows:
        if not row["last_verified"]:
            continue
        try:
            last = datetime.fromisoformat(row["last_verified"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        elapsed = (now - last).days
        periods = elapsed // days
        if periods > 0:
            decay = periods * 0.05
            new_conf = max(0.1, row["confidence"] - decay)
            if new_conf != row["confidence"]:
                conn.execute("UPDATE facts SET confidence=? WHERE id=?", (round(new_conf, 2), row["id"]))
                updated += 1
    conn.commit()
    conn.close()
    return updated


def get_stats():
    conn = _get_db()
    _init_tables(conn)
    rows = conn.execute(
        """SELECT fact_type, COUNT(*) as count,
           ROUND(AVG(confidence), 2) as avg_conf,
           SUM(CASE WHEN stale=1 THEN 1 ELSE 0 END) as stale_count
           FROM facts GROUP BY fact_type ORDER BY count DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
