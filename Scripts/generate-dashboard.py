#!/usr/bin/env python3
"""
Sprites.ai Sales Agent — Dashboard Generator
=============================================
Reads from system.db (SQLite) and generates a static HTML dashboard.
Falls back to markdown files if database doesn't exist.

Usage:
    python generate-dashboard.py
    python generate-dashboard.py --db /path/to/system.db
    python generate-dashboard.py --output /path/to/dashboard.html
"""

import sqlite3
import os
import sys
import re
import argparse
from datetime import datetime
from pathlib import Path

# Defaults
DEFAULT_DB = r"C:\Users\olive\SpritesWork\brain\system.db"
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
SYSTEM_PATTERNS = r"C:\Users\olive\SpritesWork\brain\system-patterns.md"


def parse_args():
    parser = argparse.ArgumentParser(description="Generate Sprites.ai dashboard")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to system.db")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output HTML path")
    return parser.parse_args()


def try_read_db(db_path):
    """Try to read from SQLite database. Returns dict of data or None."""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        data = {}

        # Deals / Pipeline
        try:
            cur.execute("SELECT * FROM deals ORDER BY health_score DESC")
            data["deals"] = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            data["deals"] = []

        # Cross-wire performance
        try:
            cur.execute("SELECT * FROM cross_wires ORDER BY value_rate DESC")
            data["cross_wires"] = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            data["cross_wires"] = []

        # Convergence indicators
        try:
            cur.execute("SELECT * FROM convergence_indicators")
            data["convergence"] = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            data["convergence"] = []

        # Audit scores
        try:
            cur.execute("SELECT * FROM audit_scores ORDER BY session_date DESC LIMIT 20")
            data["audit_scores"] = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            data["audit_scores"] = []

        # Complexity budget
        try:
            cur.execute("SELECT * FROM complexity_budget")
            data["complexity"] = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            data["complexity"] = []

        # Framework effectiveness
        try:
            cur.execute("SELECT * FROM frameworks ORDER BY conversion_rate DESC")
            data["frameworks"] = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            data["frameworks"] = []

        conn.close()
        return data
    except Exception:
        return None


def parse_markdown_table(text, header_line_idx):
    """Parse a markdown table starting at header_line_idx. Returns list of dicts."""
    lines = text.split("\n")
    if header_line_idx >= len(lines):
        return []
    headers = [h.strip() for h in lines[header_line_idx].split("|") if h.strip()]
    rows = []
    for i in range(header_line_idx + 2, len(lines)):
        line = lines[i].strip()
        if not line or not line.startswith("|"):
            break
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def parse_system_patterns(path):
    """Parse system-patterns.md as fallback data source."""
    data = {
        "deals": [], "cross_wires": [], "convergence": [],
        "audit_scores": [], "complexity": [], "frameworks": []
    }
    if not os.path.exists(path):
        return data

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.split("\n")

    for i, line in enumerate(lines):
        # Deal Health Scores
        if "| Prospect |" in line and "Health Score" in line:
            rows = parse_markdown_table(text, i)
            for r in rows:
                data["deals"].append({
                    "prospect": r.get("Prospect", ""),
                    "company": r.get("Company", ""),
                    "health_score": r.get("Health Score", "—"),
                    "risk_flag": r.get("Risk Flag", "—"),
                    "stage": "Active",
                    "value": "—",
                    "next_touch": "—"
                })

        # Cross-Wire Performance
        if "| Connection |" in line and "Value Rate" in line:
            rows = parse_markdown_table(text, i)
            for r in rows:
                data["cross_wires"].append({
                    "connection": r.get("Connection", ""),
                    "rule": r.get("Rule", ""),
                    "fires": r.get("Fires", "0"),
                    "value_produced": r.get("Value Produced", "0"),
                    "value_rate": r.get("Value Rate", "—"),
                    "status": r.get("Status", "ACTIVE"),
                    "last_fired": r.get("Last Fired", "—")
                })

        # Convergence Indicators
        if "| Indicator |" in line and "Threshold" in line:
            rows = parse_markdown_table(text, i)
            for r in rows:
                data["convergence"].append({
                    "indicator": r.get("Indicator", ""),
                    "current": r.get("Current", "0"),
                    "threshold": r.get("Threshold", "—"),
                    "status": r.get("Status", "NOT CONVERGED")
                })

        # Audit Score Trends
        if "| Session |" in line and "Combined" in line:
            rows = parse_markdown_table(text, i)
            for r in rows:
                data["audit_scores"].append({
                    "session": r.get("Session", ""),
                    "date": r.get("Date", ""),
                    "auditor_avg": r.get("Auditor Avg", "0"),
                    "loop_avg": r.get("Loop Avg", "0"),
                    "combined": r.get("Combined", "0"),
                    "lowest_dim": r.get("Lowest Dim", "")
                })

        # Complexity Budget
        if "| Resource |" in line and "Limit" in line and "Usage" in line:
            rows = parse_markdown_table(text, i)
            for r in rows:
                data["complexity"].append({
                    "resource": r.get("Resource", ""),
                    "current": r.get("Current", "0"),
                    "limit": r.get("Limit", "0"),
                    "usage": r.get("Usage", "0%")
                })

        # Framework Effectiveness
        if "| Framework |" in line and "Conversion Rate" in line:
            rows = parse_markdown_table(text, i)
            for r in rows:
                data["frameworks"].append({
                    "framework": r.get("Framework", ""),
                    "times_used": r.get("Times Used", "0"),
                    "conversion_rate": r.get("Conversion Rate", "—"),
                    "best_persona": r.get("Best Persona", "—"),
                    "worst_persona": r.get("Worst Persona", "—"),
                    "confidence": r.get("Confidence", "—")
                })

    return data


def parse_usage_pct(usage_str):
    """Extract numeric percentage from strings like '70%' or '~60%'."""
    match = re.search(r"(\d+)", str(usage_str))
    return int(match.group(1)) if match else 0


def convergence_progress(current_str, threshold_str):
    """Calculate progress percentage toward threshold."""
    try:
        current = float(re.search(r"[\d.]+", str(current_str)).group())
        threshold = float(re.search(r"[\d.]+", str(threshold_str)).group())
        if threshold == 0:
            return 0
        return min(100, int((current / threshold) * 100))
    except (AttributeError, ValueError, ZeroDivisionError):
        return 0


def status_color(status):
    """Map status strings to CSS colors."""
    s = str(status).upper()
    if s in ("ACTIVE", "CONVERGED", "CLEAN"):
        return "#4ecca3"
    elif s in ("DORMANT", "NOT CONVERGED", "NEAR LIMIT"):
        return "#e84545"
    else:
        return "#ffe66d"


def generate_html(data, generated_at):
    """Generate the full HTML dashboard string."""

    # --- Deal rows ---
    deal_rows = ""
    for d in data["deals"]:
        hs = d.get("health_score", "—")
        deal_rows += f"""
        <tr>
            <td>{d.get('prospect','—')}</td>
            <td>{d.get('company','—')}</td>
            <td>{hs}</td>
            <td>{d.get('stage','—')}</td>
            <td>{d.get('value','—')}</td>
            <td>{d.get('next_touch','—')}</td>
            <td>{d.get('risk_flag','—')}</td>
        </tr>"""
    if not deal_rows:
        deal_rows = '<tr><td colspan="7" style="text-align:center;color:#888;">No deals in pipeline</td></tr>'

    # --- Cross-wire rows ---
    cw_rows = ""
    for cw in data["cross_wires"]:
        color = status_color(cw.get("status", ""))
        cw_rows += f"""
        <tr>
            <td>{cw.get('connection','')}</td>
            <td>{cw.get('rule','')}</td>
            <td>{cw.get('fires','0')}</td>
            <td>{cw.get('value_produced','0')}</td>
            <td>{cw.get('value_rate','—')}</td>
            <td style="color:{color};font-weight:600;">{cw.get('status','')}</td>
            <td>{cw.get('last_fired','—')}</td>
        </tr>"""
    if not cw_rows:
        cw_rows = '<tr><td colspan="7" style="text-align:center;color:#888;">No event connection data</td></tr>'

    # --- Convergence rows ---
    conv_rows = ""
    for c in data["convergence"]:
        pct = convergence_progress(c.get("current", "0"), c.get("threshold", "1"))
        color = "#4ecca3" if c.get("status", "").upper() == "CONVERGED" else "#e84545"
        conv_rows += f"""
        <tr>
            <td>{c.get('indicator','')}</td>
            <td>{c.get('current','')}</td>
            <td>{c.get('threshold','')}</td>
            <td>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:{pct}%;background:{color};"></div>
                </div>
            </td>
            <td style="color:{color};font-weight:600;">{c.get('status','')}</td>
        </tr>"""
    if not conv_rows:
        conv_rows = '<tr><td colspan="5" style="text-align:center;color:#888;">No convergence data</td></tr>'

    # --- Audit score bars ---
    audit_bars = ""
    for a in reversed(data["audit_scores"]):
        try:
            score = float(a.get("combined", "0"))
        except ValueError:
            score = 0
        bar_h = max(5, int(score * 10))
        color = "#4ecca3" if score >= 8.0 else "#ffe66d" if score >= 7.0 else "#e84545"
        audit_bars += f"""
            <div class="bar-group">
                <div class="bar" style="height:{bar_h}px;background:{color};" title="Score: {score}"></div>
                <div class="bar-label">S{a.get('session','?')}</div>
                <div class="bar-value">{score}</div>
            </div>"""
    if not audit_bars:
        audit_bars = '<div style="color:#888;text-align:center;padding:40px;">No audit data yet</div>'

    # --- Complexity budget bars ---
    complexity_bars = ""
    for cb in data["complexity"]:
        pct = parse_usage_pct(cb.get("usage", "0%"))
        color = "#4ecca3" if pct < 70 else "#ffe66d" if pct < 90 else "#e84545"
        complexity_bars += f"""
        <div class="budget-item">
            <div class="budget-header">
                <span>{cb.get('resource','')}</span>
                <span>{cb.get('current','')}/{cb.get('limit','')}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width:{pct}%;background:{color};"></div>
            </div>
            <div class="budget-pct">{cb.get('usage','0%')}</div>
        </div>"""
    if not complexity_bars:
        complexity_bars = '<div style="color:#888;text-align:center;padding:20px;">No budget data</div>'

    # --- Framework rows ---
    fw_rows = ""
    for fw in data["frameworks"]:
        fw_rows += f"""
        <tr>
            <td>{fw.get('framework','')}</td>
            <td>{fw.get('times_used','0')}</td>
            <td>{fw.get('conversion_rate','—')}</td>
            <td>{fw.get('best_persona','—')}</td>
            <td>{fw.get('worst_persona','—')}</td>
            <td>{fw.get('confidence','—')}</td>
        </tr>"""
    if not fw_rows:
        fw_rows = '<tr><td colspan="6" style="text-align:center;color:#888;">No framework data</td></tr>'

    # --- Assemble HTML ---
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sprites.ai Sales Agent Dashboard</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: #1a1a2e;
        color: #eee;
        padding: 24px;
        line-height: 1.5;
    }}
    .header {{
        text-align: center;
        margin-bottom: 32px;
        padding-bottom: 16px;
        border-bottom: 1px solid #333;
    }}
    .header h1 {{
        font-size: 28px;
        color: #4ecca3;
        margin-bottom: 4px;
    }}
    .header .subtitle {{
        color: #888;
        font-size: 14px;
    }}
    .grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 24px;
        margin-bottom: 24px;
    }}
    .grid-full {{
        grid-column: 1 / -1;
    }}
    .card {{
        background: #16213e;
        border-radius: 8px;
        padding: 20px;
        border: 1px solid #2a2a4a;
    }}
    .card h2 {{
        font-size: 16px;
        color: #4ecca3;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid #2a2a4a;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }}
    th {{
        text-align: left;
        padding: 8px 12px;
        background: #0f3460;
        color: #4ecca3;
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    td {{
        padding: 8px 12px;
        border-bottom: 1px solid #1a1a3e;
    }}
    tr:hover td {{
        background: #1a1a3e;
    }}
    .progress-bar {{
        width: 100%;
        height: 8px;
        background: #2a2a4a;
        border-radius: 4px;
        overflow: hidden;
    }}
    .progress-fill {{
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s;
    }}
    .bar-chart {{
        display: flex;
        align-items: flex-end;
        gap: 12px;
        height: 120px;
        padding: 0 8px;
    }}
    .bar-group {{
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 1;
    }}
    .bar {{
        width: 32px;
        border-radius: 4px 4px 0 0;
        min-height: 5px;
    }}
    .bar-label {{
        font-size: 11px;
        color: #888;
        margin-top: 4px;
    }}
    .bar-value {{
        font-size: 11px;
        color: #ccc;
        font-weight: 600;
    }}
    .budget-item {{
        margin-bottom: 16px;
    }}
    .budget-header {{
        display: flex;
        justify-content: space-between;
        font-size: 13px;
        margin-bottom: 4px;
    }}
    .budget-pct {{
        text-align: right;
        font-size: 11px;
        color: #888;
        margin-top: 2px;
    }}
    .status-badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
    }}
    .threshold-line {{
        border-left: 2px dashed #e84545;
        position: relative;
    }}
    .footer {{
        text-align: center;
        color: #555;
        font-size: 12px;
        margin-top: 24px;
        padding-top: 16px;
        border-top: 1px solid #2a2a4a;
    }}
</style>
</head>
<body>

<div class="header">
    <h1>Sprites.ai Sales Agent Dashboard</h1>
    <div class="subtitle">Generated: {generated_at} | System State: FORMING (0/5 converged)</div>
</div>

<div class="grid">

    <!-- Pipeline Overview (full width) -->
    <div class="card grid-full">
        <h2>Pipeline Overview</h2>
        <table>
            <thead>
                <tr>
                    <th>Prospect</th>
                    <th>Company</th>
                    <th>Health Score</th>
                    <th>Stage</th>
                    <th>Value</th>
                    <th>Next Touch</th>
                    <th>Risk Flag</th>
                </tr>
            </thead>
            <tbody>
                {deal_rows}
            </tbody>
        </table>
    </div>

    <!-- Cross-Wire Status (full width) -->
    <div class="card grid-full">
        <h2>Cross-Wire Status (Layer 3)</h2>
        <table>
            <thead>
                <tr>
                    <th>Connection</th>
                    <th>Rule</th>
                    <th>Fires</th>
                    <th>Value Produced</th>
                    <th>Value Rate</th>
                    <th>Status</th>
                    <th>Last Fired</th>
                </tr>
            </thead>
            <tbody>
                {cw_rows}
            </tbody>
        </table>
    </div>

    <!-- Convergence Monitor -->
    <div class="card">
        <h2>Convergence Monitor (Layer 5)</h2>
        <table>
            <thead>
                <tr>
                    <th>Indicator</th>
                    <th>Current</th>
                    <th>Threshold</th>
                    <th>Progress</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {conv_rows}
            </tbody>
        </table>
    </div>

    <!-- Audit Score Trend -->
    <div class="card">
        <h2>Audit Score Trend</h2>
        <div style="text-align:center;margin-bottom:8px;font-size:11px;color:#888;">
            8.0 minimum gate &mdash; Green = pass, Yellow = warning, Red = fail
        </div>
        <div class="bar-chart">
            {audit_bars}
        </div>
    </div>

    <!-- Complexity Budget -->
    <div class="card">
        <h2>Complexity Budget</h2>
        {complexity_bars}
    </div>

    <!-- Framework Effectiveness -->
    <div class="card">
        <h2>Framework Effectiveness</h2>
        <table>
            <thead>
                <tr>
                    <th>Framework</th>
                    <th>Uses</th>
                    <th>Conv. Rate</th>
                    <th>Best Persona</th>
                    <th>Worst Persona</th>
                    <th>Confidence</th>
                </tr>
            </thead>
            <tbody>
                {fw_rows}
            </tbody>
        </table>
    </div>

</div>

<div class="footer">
    Sprites.ai Sales Agent &mdash; Autonomous Dashboard &mdash; Regenerate with: python tools/generate-dashboard.py
</div>

</body>
</html>"""

    return html


def main():
    args = parse_args()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Try database first, fall back to markdown
    data = try_read_db(args.db)
    source = "SQLite database"

    if data is None:
        print(f"[INFO] Database not found at {args.db}, falling back to system-patterns.md")
        data = parse_system_patterns(SYSTEM_PATTERNS)
        source = "system-patterns.md (markdown fallback)"

    # Generate HTML
    html = generate_html(data, generated_at)

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] Dashboard generated: {args.output}")
    print(f"[OK] Data source: {source}")
    print(f"[OK] Deals: {len(data['deals'])}, Cross-wires: {len(data['cross_wires'])}, "
          f"Frameworks: {len(data['frameworks'])}")


if __name__ == "__main__":
    main()
