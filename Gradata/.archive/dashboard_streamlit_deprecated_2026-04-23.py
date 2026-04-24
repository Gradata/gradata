"""
Gradata Dashboard — Your AI's fitness tracker.
===============================================
Run:  streamlit run C:/Users/olive/SpritesWork/brain/scripts/dashboard.py
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BRAIN_DIR = Path("C:/Users/olive/SpritesWork/brain")
DB_PATH = BRAIN_DIR / "system.db"
EVENTS_PATH = BRAIN_DIR / "events.jsonl"
LESSONS_PATH = BRAIN_DIR / "lessons.md"
PROSPECTS_DIR = BRAIN_DIR / "prospects"
BRIEF_PATH = BRAIN_DIR / "morning-brief.md"
TASKS_DIR = Path("C:/Users/olive/.claude/scheduled-tasks")

st.set_page_config(page_title="Gradata", layout="wide", page_icon=":brain:")

# Custom CSS for cleaner look
st.markdown(
    """
<style>
    .block-container { padding-top: 2rem; }
    .status-good { color: #22c55e; font-weight: 600; }
    .status-warn { color: #f59e0b; font-weight: 600; }
    .status-bad { color: #ef4444; font-weight: 600; }
    .big-number { font-size: 2.5rem; font-weight: 700; line-height: 1; }
    .label { font-size: 0.85rem; color: #888; margin-bottom: 0.25rem; }
    .insight { background: #1a1a2e; padding: 1rem; border-radius: 8px; border-left: 4px solid #4ECDC4; margin: 0.5rem 0; }
    div[data-testid="stMetric"] label { font-size: 0.85rem; color: #999; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data Layer (same as before, hidden complexity)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def q(sql, params=None):
    try:
        rows = get_db().execute(sql, params or ()).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def qdf(sql, params=None):
    rows = q(sql, params)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# --- Path B bridge: derive dashboard metrics live from events.jsonl -----------
# `session_metrics` and `correction_severity` tables haven't been written since
# 2026-03-30 (writer dropped out of the hook chain). Rather than restore a
# fragile CLI-script writer, derive the same columns live from the authoritative
# event log. Kept in dashboard.py (not imported from the SDK) because the SDK
# import chain has an ~11s cold-start penalty that would make every render slow.
# Tracked in WRITERS.md; replace with ProjectionRegistry (Path C) when Hermes
# observers need persisted historicals.
@st.cache_data(ttl=60)
def _derive_session_metrics_from_events() -> pd.DataFrame:
    if not EVENTS_PATH.exists():
        return pd.DataFrame()
    corrections: dict[int, int] = {}
    outputs: dict[int, int] = {}
    unedited: dict[int, int] = {}
    session_date: dict[int, str] = {}
    with EVENTS_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            sess = d.get("session")
            if sess is None:
                continue
            t = d.get("type")
            ts = d.get("ts", "")
            if isinstance(ts, str) and ts:
                session_date[sess] = ts[:10]
            if t == "CORRECTION":
                corrections[sess] = corrections.get(sess, 0) + 1
            elif t == "OUTPUT":
                outputs[sess] = outputs.get(sess, 0) + 1
                if not (d.get("data") or {}).get("edited_by_oliver"):
                    unedited[sess] = unedited.get(sess, 0) + 1
    rows = []
    for sess in sorted(set(corrections) | set(outputs)):
        outs = outputs.get(sess, 0)
        corr = corrections.get(sess, 0)
        une = unedited.get(sess, 0)
        rows.append(
            {
                "session": sess,
                "date": session_date.get(sess, ""),
                "corrections": corr,
                "outputs_produced": outs,
                "outputs_unedited": une,
                # Density requires outputs to be meaningful; leave NaN otherwise.
                "correction_density": (min(corr / outs, 1.0) if outs else None),
                "first_draft_acceptance": ((une / outs) if outs else None),
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def _derive_severity_from_events() -> pd.DataFrame:
    if not EVENTS_PATH.exists():
        return pd.DataFrame()
    counts: dict[tuple[int, str], int] = {}
    with EVENTS_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "CORRECTION":
                continue
            sess = d.get("session")
            sev = (d.get("data") or {}).get("severity")
            if sess is None or not sev:
                continue
            counts[(sess, str(sev).lower())] = counts.get((sess, str(sev).lower()), 0) + 1
    rows = [{"session": s, "severity_label": sev, "cnt": c} for (s, sev), c in counts.items()]
    return pd.DataFrame(rows).sort_values("session") if rows else pd.DataFrame()


def parse_lessons():
    if not LESSONS_PATH.exists():
        return []
    text = LESSONS_PATH.read_text(encoding="utf-8")
    lessons = []
    lines = text.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"\[(\d{4}-\d{2}-\d{2})\]\s+\[(\w+):([\d.]+)\]\s+(\w+):\s*(.*)", line)
        if m:
            lesson = {
                "date": m.group(1),
                "state": m.group(2),
                "confidence": float(m.group(3)),
                "category": m.group(4),
                "description": m.group(5)[:80],
            }
            if i + 1 < len(lines):
                fc = re.search(r"Fire count:\s*(\d+)", lines[i + 1])
                lesson["fire_count"] = int(fc.group(1)) if fc else 0
            else:
                lesson["fire_count"] = 0
            lessons.append(lesson)
        i += 1
    return lessons


def brief_age_hours():
    if not BRIEF_PATH.exists():
        return 9999
    return (
        datetime.now() - datetime.fromtimestamp(BRIEF_PATH.stat().st_mtime)
    ).total_seconds() / 3600


def status_dot(good, warn_threshold=None, value=None):
    """Returns a colored circle based on status."""
    if isinstance(good, bool):
        return "🟢" if good else "🔴"
    if value is not None and warn_threshold is not None:
        if value <= warn_threshold * 0.5:
            return "🟢"
        elif value <= warn_threshold:
            return "🟡"
        return "🔴"
    return "⚪"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
page = st.sidebar.radio(
    "",
    [
        "Today",
        "Is My AI Learning?",
        "My Deals",
        "Under the Hood",
    ],
)
st.sidebar.markdown("---")
if st.sidebar.button("Refresh"):
    st.cache_resource.clear()
    st.rerun()
st.sidebar.caption("Gradata v0.1 — Your AI's fitness tracker")


# ===================================================================
# PAGE 1: TODAY — "What do I need to know right now?"
# ===================================================================
if page == "Today":
    st.title("Good morning, Oliver.")

    # --- Overall Health Score ---
    lessons = parse_lessons()
    rules = len([l for l in lessons if l["state"] == "RULE"])
    patterns = len([l for l in lessons if l["state"] == "PATTERN"])
    instincts = len([l for l in lessons if l["state"] == "INSTINCT"])
    total_lessons = len(lessons)

    brief_hours = brief_age_hours()
    dm = q(
        "SELECT pipeline_value, deals_total, instantly_reply_rate, instantly_sent FROM daily_metrics ORDER BY date DESC LIMIT 1"
    )
    latest = dm[0] if dm else {}

    budgets = q("SELECT api_name, daily_limit, used_today FROM credit_budgets")
    total_credits_used = sum(b["used_today"] for b in budgets)

    # --- Quick Status Row ---
    st.markdown("### How's everything looking?")
    s1, s2, s3, s4 = st.columns(4)

    with s1:
        dot = status_dot(True, value=brief_hours, warn_threshold=24)
        if brief_hours < 12:
            st.markdown(f"#### {dot} Morning Brief")
            st.caption("Up to date")
        elif brief_hours < 48:
            st.markdown(f"#### {dot} Morning Brief")
            st.caption(f"Updated {brief_hours:.0f}h ago — getting stale")
        else:
            st.markdown(f"#### {dot} Morning Brief")
            st.caption(f"**{brief_hours / 24:.0f} days old** — not running")

    with s2:
        graduated = rules + patterns
        dot = "🟢" if graduated >= 3 else ("🟡" if graduated >= 1 else "🔴")
        st.markdown(f"#### {dot} AI Learning")
        if graduated == 0:
            st.caption(f"{total_lessons} lessons, **none graduated yet**")
        else:
            st.caption(f"{rules} rules, {patterns} patterns, {instincts} building")

    with s3:
        pipe_val = latest.get("pipeline_value", 0)
        deals = latest.get("deals_total", 0)
        st.markdown(f"#### {'🟢' if pipe_val > 5000 else '🟡'} Pipeline")
        st.caption(f"${pipe_val:,.0f} across {deals} deals")

    with s4:
        st.markdown(f"#### {'🟢' if total_credits_used < 50 else '🟡'} API Credits")
        st.caption(f"{total_credits_used} used today")

    st.markdown("---")

    # --- What Should You Do Right Now? ---
    st.markdown("### What needs your attention")

    actions = []

    # Stale deals
    stale_deals = q(
        "SELECT company, prospect_name, days_in_stage, stage FROM deals WHERE days_in_stage > 14"
    )
    for d in stale_deals:
        actions.append(
            (
                "🔴",
                f"**{d['company']}** — stuck in '{d['stage']}' for {d['days_in_stage']} days. Follow up or close it.",
            )
        )

    # Brief not running
    if brief_hours > 48:
        actions.append(
            (
                "🔴",
                f"Your morning brief hasn't updated in **{brief_hours / 24:.0f} days**. The scheduling system may be broken.",
            )
        )

    # No graduated lessons
    if rules + patterns == 0:
        actions.append(
            (
                "🟡",
                f"Your AI has {total_lessons} lessons but **none have graduated**. The learning pipeline needs attention.",
            )
        )

    # Hot credit APIs
    for b in budgets:
        if b["used_today"] > b["daily_limit"] * 0.8:
            actions.append(
                (
                    "🟡",
                    f"**{b['api_name']}** credits nearly exhausted ({b['used_today']}/{b['daily_limit']}).",
                )
            )

    # Deals needing attention (low health)
    sick_deals = q(
        "SELECT company, health_score, stage FROM deals WHERE health_score < 40 AND health_score > 0"
    )
    for d in sick_deals:
        actions.append(
            (
                "🟡",
                f"**{d['company']}** health score is {d['health_score']:.0f}/100 — needs a touch.",
            )
        )

    if actions:
        for dot, text in actions:
            st.markdown(f"{dot} {text}")
    else:
        st.success("Everything looks good. No urgent actions needed.")

    st.markdown("---")

    # --- Your Agents ---
    st.markdown("### Your agents")
    if TASKS_DIR.exists():
        task_dirs = sorted([d for d in TASKS_DIR.iterdir() if d.is_dir()])
        if task_dirs:
            for td in task_dirs:
                skill_file = td / "SKILL.md"
                if not skill_file.exists():
                    continue
                header = skill_file.read_text(encoding="utf-8")[:500]

                # Parse YAML frontmatter
                name = td.name
                desc_match = re.search(r"description:\s*(.+)", header)
                desc = desc_match.group(1).strip() if desc_match else ""

                # Determine status from description
                is_disabled = any(
                    tag in desc.upper() for tag in ["DISABLED", "DUPLICATE", "ARCHIVED"]
                )
                is_active = not is_disabled and desc != ""

                if is_disabled:
                    icon = "⏸️"
                    status = "Disabled"
                else:
                    icon = "🟢"
                    status = "Ready"

                with st.container(border=True):
                    ac1, ac2 = st.columns([3, 1])
                    ac1.markdown(f"{icon} **{name}**")
                    short_desc = (
                        desc[:80]
                        .replace("[DUPLICATE", "")
                        .replace("[ARCHIVED]", "")
                        .replace("[DISABLED]", "")
                        .strip(" —-")
                    )
                    ac1.caption(short_desc if short_desc else "No description")
                    ac2.markdown(f"**{status}**")
        else:
            st.caption("No scheduled agents found.")
    else:
        st.info("No scheduled tasks directory found. Agents will appear here once configured.")

    st.markdown("---")

    # --- Your Pipeline at a Glance ---
    st.markdown("### Pipeline snapshot")
    deals_df = qdf(
        "SELECT company, prospect_name, stage, value, health_score, days_in_stage FROM deals ORDER BY value DESC"
    )
    if not deals_df.empty:

        def row_style(row):
            if row.get("days_in_stage", 0) > 14:
                return ["background-color: #ef444422"] * len(row)
            if row.get("health_score", 100) < 40:
                return ["background-color: #f59e0b22"] * len(row)
            return [""] * len(row)

        st.dataframe(
            deals_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "company": "Company",
                "prospect_name": "Contact",
                "stage": "Stage",
                "value": st.column_config.NumberColumn("Deal Value", format="$%.0f"),
                "health_score": st.column_config.ProgressColumn(
                    "Health", min_value=0, max_value=100
                ),
                "days_in_stage": "Days in Stage",
            },
        )

    # --- Outreach Quick Stats ---
    st.markdown("### Outreach")
    if latest.get("instantly_sent"):
        oc1, oc2, oc3 = st.columns(3)
        oc1.metric("Emails Sent (All Time)", f"{latest['instantly_sent']:,}")
        oc2.metric("Reply Rate", f"{latest.get('instantly_reply_rate', 0):.0%}")
        replies = latest.get("replies_count") or q(
            "SELECT replies_count FROM daily_metrics ORDER BY date DESC LIMIT 1"
        )
        oc3.metric(
            "Total Replies",
            latest.get("replies_count", "N/A")
            if isinstance(latest.get("replies_count"), int)
            else "N/A",
        )
    else:
        st.caption("No outreach data yet.")


# ===================================================================
# PAGE 2: IS MY AI LEARNING? — The whole point of Gradata
# ===================================================================
elif page == "Is My AI Learning?":
    st.title("Is your AI actually learning?")

    # --- Live status block (Path B bridge) -----------------------------------
    # The projection tables (session_metrics, correction_severity) haven't been
    # written since 2026-03-30. Panels now derive from events.jsonl live.
    _sm_live = _derive_session_metrics_from_events()
    _current_session = int(_sm_live["session"].max()) if not _sm_live.empty else 0
    _today_iso = datetime.now().strftime("%Y-%m-%d")
    _corrections_today = 0
    if not _sm_live.empty and "date" in _sm_live.columns:
        _today_row = _sm_live[_sm_live["date"] == _today_iso]
        if not _today_row.empty:
            _corrections_today = int(_today_row["corrections"].sum())
    _transitions_df = qdf(
        "SELECT old_state, new_state, category, ROUND(confidence, 2) as confidence, session "
        "FROM lesson_transitions ORDER BY session DESC"
    )
    _promotions = 0
    _demotions = 0
    if not _transitions_df.empty:
        _promotions = int((_transitions_df["new_state"].isin(["PATTERN", "RULE"])).sum())
        _demotions = int(
            (_transitions_df["new_state"].isin(["INSTINCT", "UNTESTABLE", "KILLED"])).sum()
        )
    _heal_str = (
        f"Self-healing active — {_promotions} promotions, {_demotions} demotions"
        if not _transitions_df.empty
        else "Self-healing: no state changes yet"
    )
    st.info(
        f"**Live as of session {_current_session}, {_today_iso}** · "
        f"Learning pipeline: ALIVE ({_corrections_today} corrections today) · "
        f"{_heal_str}"
    )

    lessons = parse_lessons()
    rules = [l for l in lessons if l["state"] == "RULE"]
    patterns = [l for l in lessons if l["state"] == "PATTERN"]
    instincts = [l for l in lessons if l["state"] == "INSTINCT"]
    untestable = [l for l in lessons if l["state"] == "UNTESTABLE"]

    # --- The Big Answer ---
    graduated = len(rules) + len(patterns)
    if graduated == 0:
        st.error(
            "**Not yet.** You have lessons, but none have graduated. Your AI knows things but can't prove they work."
        )
        st.markdown("""
        **What this means:** Every time you correct your AI, it creates a "lesson." But lessons need to prove
        they actually help before they become permanent rules. Right now, none have proven themselves.

        **What to do:** Keep correcting outputs. The system needs to see the same lesson fire multiple times
        across different sessions before it trusts the pattern.
        """)
    elif graduated < 5:
        st.warning(
            f"**Getting there.** {graduated} lessons have graduated. Your AI is starting to learn your preferences."
        )
    else:
        st.success(f"**Yes.** {graduated} lessons graduated. Your AI is adapting to how you work.")

    st.markdown("---")

    # --- The Journey: How lessons become rules ---
    st.markdown("### How your AI learns")
    st.markdown("""
    Every correction you make creates a lesson. Lessons go through stages before your AI trusts them:

    **You correct something** → Lesson created (Untestable)
    → AI tries using it (Instinct) → It works multiple times (Pattern) → **Permanent rule**
    """)

    j1, j2, j3, j4 = st.columns(4)
    j1.metric(
        "Waiting to be tested",
        len(untestable),
        help="Lessons your AI learned but hasn't had a chance to apply yet",
    )
    j2.metric(
        "Being tested",
        len(instincts),
        help="Your AI is actively trying these. If they work, they'll promote.",
    )
    j3.metric(
        "Proven patterns",
        len(patterns),
        help="These worked multiple times. Almost permanent.",
    )
    j4.metric(
        "Permanent rules",
        len(rules),
        help="Your AI won't forget these. They're part of its DNA now.",
    )

    # Visual funnel
    fig = go.Figure(
        go.Funnel(
            y=["Waiting to test", "Being tested", "Proven", "Permanent"],
            x=[len(untestable), len(instincts), len(patterns), len(rules)],
            marker=dict(color=["#FF6B6B", "#FFD93D", "#6BCB77", "#4D96FF"]),
            textinfo="value",
        )
    )
    fig.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # --- Are corrections going down? ---
    st.markdown("### Are you correcting less over time?")
    st.caption("If this line goes down, your AI is getting better. If flat, something's stuck.")

    # Derive live from events.jsonl — session_metrics table is frozen at
    # session 76 (2026-03-30). See WRITERS.md for provenance.
    _cs_src = _derive_session_metrics_from_events()
    cs_df = (
        _cs_src[_cs_src["correction_density"].notna()][
            ["session", "date", "correction_density", "first_draft_acceptance"]
        ].sort_values("session")
        if not _cs_src.empty
        else _cs_src
    )
    if not cs_df.empty:
        st.caption(f"Last updated: live from events.jsonl · session {int(cs_df['session'].max())}")
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=cs_df["session"],
                y=cs_df["correction_density"],
                mode="lines+markers",
                name="How much you changed",
                line=dict(color="#FF6B6B", width=2),
                fill="tozeroy",
                fillcolor="rgba(255,107,107,0.1)",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=cs_df["session"],
                y=cs_df["first_draft_acceptance"],
                mode="lines+markers",
                name="Used as-is rate",
                line=dict(color="#4ECDC4", width=2),
            )
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=10, b=20),
            yaxis_title="Rate",
            xaxis_title="Session #",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No correction data yet. Start a few sessions and correct some outputs.")

    st.markdown("---")

    # --- What has your AI learned? ---
    st.markdown("### What your AI knows")

    # Show rules first (most important)
    if rules:
        st.markdown("**Permanent rules** (your AI follows these every time):")
        for l in rules:
            st.markdown(f"- {l['description']}")

    if patterns:
        st.markdown("**Proven patterns** (working well, almost permanent):")
        for l in patterns:
            st.markdown(f"- {l['description']}")

    if instincts:
        with st.expander(f"Being tested ({len(instincts)} lessons)"):
            for l in instincts:
                conf_pct = l["confidence"] * 100
                st.markdown(f"- {l['description']} — *{conf_pct:.0f}% confident*")

    if untestable:
        with st.expander(f"Waiting to be tested ({len(untestable)} lessons)"):
            for l in untestable[:15]:
                st.markdown(f"- {l['description']}")
            if len(untestable) > 15:
                st.caption(f"...and {len(untestable) - 15} more")

    st.markdown("---")

    # --- Meta-rules ---
    st.markdown("### Meta-rules")
    st.caption(
        "High-level principles synthesized automatically from clusters of related graduated rules."
    )
    meta_rows = q(
        "SELECT principle, confidence, source_categories, applies_when, never_when "
        "FROM meta_rules ORDER BY confidence DESC"
    )
    if not meta_rows:
        st.info(
            "No meta-rules yet. They emerge when 3+ related rules graduate and cluster "
            "semantically. Meta-rule discovery requires Gradata Cloud."
        )
    else:
        for mr in meta_rows:
            with st.expander(f"{mr['principle'][:80]}  ·  {mr['confidence']:.0%} confidence"):
                cols = st.columns(2)
                try:
                    applies = json.loads(mr["applies_when"] or "[]")
                except (json.JSONDecodeError, TypeError):
                    applies = []
                try:
                    never = json.loads(mr["never_when"] or "[]")
                except (json.JSONDecodeError, TypeError):
                    never = []
                try:
                    cats = json.loads(mr["source_categories"] or "[]")
                except (json.JSONDecodeError, TypeError):
                    cats = []
                cols[0].write("**Applies when:**")
                cols[0].write("\n".join(f"- {a}" for a in applies) if applies else "—")
                cols[1].write("**Never when:**")
                cols[1].write("\n".join(f"- {n}" for n in never) if never else "—")
                if cats:
                    st.caption(f"Source categories: {', '.join(cats)}")

    st.markdown("---")

    # --- Correction severity trend ---
    st.markdown("### Are corrections getting lighter?")
    st.caption(
        "If the bars shift from red (major rewrites) to green (small tweaks), your AI is improving on the hard stuff."
    )

    # Derive live from events.jsonl — correction_severity table also frozen.
    corr_df = _derive_severity_from_events()
    if corr_df.empty:
        st.warning(
            "Severity breakdown is paused — no CORRECTION events carry a "
            "`severity` field. Restoring via pipeline-revamp."
        )
    if not corr_df.empty:
        st.caption(
            f"Last updated: live from events.jsonl · session {int(corr_df['session'].max())}"
        )
        color_map = {
            "trivial": "#6BCB77",
            "minor": "#FFD93D",
            "moderate": "#FF9F43",
            "major": "#FF6B6B",
            "rewrite": "#EE5A24",
        }
        fig = go.Figure()
        for severity in ["rewrite", "major", "moderate", "minor", "trivial"]:
            sev_data = corr_df[corr_df["severity_label"] == severity]
            if not sev_data.empty:
                fig.add_trace(
                    go.Bar(
                        x=sev_data["session"],
                        y=sev_data["cnt"],
                        name=severity.title(),
                        marker_color=color_map.get(severity, "#888"),
                    )
                )
        fig.update_layout(
            barmode="stack",
            height=300,
            margin=dict(l=20, r=20, t=10, b=20),
            xaxis_title="Session #",
            yaxis_title="Corrections",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # --- State changes (self-healing) ---
    st.markdown("### State changes")
    st.caption(
        "Every time a lesson is promoted or demoted automatically, it appears here. "
        "Promotions build lasting knowledge; demotions prune what isn't working."
    )
    if _transitions_df.empty:
        st.info("No state changes recorded yet.")
    else:
        t1, t2 = st.columns(2)
        t1.metric(
            "Promotions",
            _promotions,
            help="Lessons that moved up (INSTINCT→PATTERN or PATTERN→RULE)",
        )
        t2.metric("Demotions / Kills", _demotions, help="Lessons pruned or reset")
        with st.expander(f"Recent state changes ({min(len(_transitions_df), 50)} shown)"):
            st.dataframe(
                _transitions_df.head(50),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "old_state": "From",
                    "new_state": "To",
                    "category": "Category",
                    "confidence": "Confidence",
                    "session": "Session",
                },
            )


# ===================================================================
# PAGE 3: MY DEALS — Pipeline without the jargon
# ===================================================================
elif page == "My Deals":
    st.title("Your deals")

    deals = q("SELECT * FROM deals ORDER BY value DESC")
    if not deals:
        st.info("No deals tracked yet.")
    else:
        # Summary
        total_val = sum(d.get("value", 0) or 0 for d in deals)
        active = [d for d in deals if d.get("stage") not in ("closed-won", "closed-lost")]
        stale = [d for d in active if (d.get("days_in_stage") or 0) > 14]

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Pipeline", f"${total_val:,.0f}")
        m2.metric("Active Deals", len(active))
        m3.metric(
            "Need Attention",
            len(stale),
            delta=f"{len(stale)} stale" if stale else "All good",
            delta_color="inverse",
        )

        st.markdown("---")

        # Each deal as a card
        for d in deals:
            health = d.get("health_score", 0) or 0
            days = d.get("days_in_stage", 0) or 0
            value = d.get("value", 0) or 0
            stage = d.get("stage", "unknown")

            # Status determination
            if stage in ("closed-won",):
                icon = "🏆"
            elif stage in ("closed-lost",):
                icon = "❌"
            elif days > 14:
                icon = "🔴"
            elif health < 40:
                icon = "🟡"
            else:
                icon = "🟢"

            with st.container(border=True):
                dc1, dc2, dc3, dc4 = st.columns([3, 1.5, 1.5, 2])

                dc1.markdown(f"### {icon} {d.get('company', '?')}")
                dc1.caption(f"{d.get('prospect_name', '?')} — {stage.replace('-', ' ').title()}")

                dc2.metric("Value", f"${value:,.0f}")
                dc3.metric("Health", f"{health:.0f}/100")

                # What to do
                if days > 14:
                    dc4.warning(f"Stuck {days} days. Follow up or kill it.")
                elif health < 40:
                    dc4.warning("Low health. Needs attention.")
                elif stage == "demo-done":
                    dc4.info("Send proposal or follow up.")
                elif stage == "proposal-made":
                    dc4.info("Check if they've reviewed it.")
                else:
                    dc4.success("On track.")

        st.markdown("---")

        # Pipeline over time
        st.markdown("### Pipeline trend")
        pipe_df = qdf("SELECT date, pipeline_value FROM daily_metrics ORDER BY date")
        if not pipe_df.empty:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=pipe_df["date"],
                    y=pipe_df["pipeline_value"],
                    mode="lines+markers",
                    fill="tozeroy",
                    line=dict(color="#4ECDC4", width=2),
                    fillcolor="rgba(78,205,196,0.1)",
                )
            )
            fig.update_layout(
                height=250,
                margin=dict(l=20, r=20, t=10, b=20),
                yaxis_title="Pipeline Value ($)",
            )
            st.plotly_chart(fig, use_container_width=True)

        # Outreach
        st.markdown("### Outreach performance")
        dm = q(
            "SELECT instantly_sent, instantly_reply_rate, replies_count FROM daily_metrics ORDER BY date DESC LIMIT 1"
        )
        if dm and dm[0].get("instantly_sent"):
            d = dm[0]
            oc1, oc2, oc3 = st.columns(3)
            oc1.metric("Emails Sent", f"{d['instantly_sent']:,}")
            rr = d.get("instantly_reply_rate", 0)
            oc2.metric(
                "Reply Rate",
                f"{rr:.0%}",
                delta="Good" if rr > 0.3 else "Low",
                delta_color="normal" if rr > 0.3 else "inverse",
            )
            oc3.metric("Replies", d.get("replies_count", 0))


# ===================================================================
# PAGE 4: UNDER THE HOOD — For when you want the details
# ===================================================================
elif page == "Under the Hood":
    st.title("Under the hood")
    st.caption("The technical details. You don't need this daily, but it's here when you want it.")

    # --- API Credit Usage ---
    st.markdown("### API credit usage")
    budgets = q("SELECT * FROM credit_budgets ORDER BY api_name")
    if budgets:
        for b in budgets:
            used = b["used_today"]
            limit = b["daily_limit"]
            pct = (used / limit * 100) if limit > 0 else 0
            col1, col2 = st.columns([1, 3])
            col1.markdown(f"**{b['api_name'].title()}**")
            col2.progress(min(pct / 100, 1.0), text=f"{used}/{limit} today ({pct:.0f}%)")

    st.markdown("---")

    # --- Session History ---
    st.markdown("### Recent sessions")
    # session_metrics is frozen at s76 (2026-03-30). Use the live bridge instead.
    _sm_hood = _derive_session_metrics_from_events()
    if not _sm_hood.empty:
        sess_df = (
            _sm_hood[
                ["session", "date", "corrections", "correction_density", "first_draft_acceptance"]
            ]
            .rename(
                columns={
                    "session": "Session",
                    "date": "Date",
                    "corrections": "Corrections",
                    "correction_density": "Correction Density",
                    "first_draft_acceptance": "First Draft Acceptance",
                }
            )
            .sort_values("Session", ascending=False)
            .head(20)
        )
        st.caption(f"Live from events.jsonl · {len(_sm_hood)} total sessions")
        st.dataframe(sess_df, use_container_width=True, hide_index=True)
    else:
        sess_df = qdf(
            "SELECT session as 'Session', date as 'Date', session_type as 'Type', "
            "corrections as 'Corrections', gate_pass_rate as 'Quality Score' "
            "FROM session_metrics ORDER BY session DESC LIMIT 20"
        )
        if not sess_df.empty:
            st.dataframe(sess_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- Event Activity ---
    st.markdown("### What's been happening")
    evt_df = qdf("SELECT type, COUNT(*) as count FROM events GROUP BY type ORDER BY count DESC")
    if not evt_df.empty:
        fig = go.Figure(
            go.Bar(
                x=evt_df["count"],
                y=evt_df["type"],
                orientation="h",
                marker_color="#4ECDC4",
            )
        )
        fig.update_layout(
            height=max(300, len(evt_df) * 30),
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # --- Recent Event Feed ---
    st.markdown("### Live event feed")
    if EVENTS_PATH.exists():
        with open(EVENTS_PATH, encoding="utf-8") as f:
            lines = f.readlines()
        recent = []
        for line in lines[-30:]:
            try:
                e = json.loads(line)
                recent.append(
                    {
                        "When": e.get("ts", "")[:19],
                        "What": e.get("type", ""),
                        "From": e.get("source", ""),
                    }
                )
            except json.JSONDecodeError:
                pass
        if recent:
            st.dataframe(
                pd.DataFrame(reversed(recent)),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("---")

    # --- Database Size ---
    st.markdown("### Brain storage")
    tables = q("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    if tables:
        total_rows = 0
        stats = []
        for t in tables:
            name = t["name"]
            if name.startswith("brain_fts") or name == "sqlite_sequence":
                continue
            cnt = q(f"SELECT COUNT(*) as c FROM [{name}]")
            rows = cnt[0]["c"] if cnt else 0
            total_rows += rows
            stats.append({"Table": name, "Records": rows})
        # Latest session number from events.jsonl (authoritative — DB events table is sparse)
        _sm_for_count = _derive_session_metrics_from_events()
        _latest_sess = int(_sm_for_count["session"].max()) if not _sm_for_count.empty else 0
        sc1, sc2 = st.columns(2)
        sc1.metric("Total Records", f"{total_rows:,}")
        sc2.metric("Session #", f"{_latest_sess:,}", help="Latest session number from events.jsonl")
        with st.expander("Table breakdown"):
            st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)
