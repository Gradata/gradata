"""
Backfill historical events into system.db events table.
Sources: audit-log.md, session notes, brain/sessions, lessons.md
"""
import sqlite3
import json

DB_PATH = "C:/Users/olive/SpritesWork/brain/system.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check existing events to avoid duplicates
cur.execute("SELECT session, type, source FROM events")
existing = set((r[0], r[1], r[2]) for r in cur.fetchall())

def already_exists(session, etype, source):
    return (session, etype, source) in existing

inserted = 0

def emit(ts, session, etype, source, data, tags=None):
    global inserted
    if tags is None:
        tags = []
    # Check for exact duplicates (handle NULL session)
    if session is None:
        cur.execute(
            "SELECT COUNT(*) FROM events WHERE session IS NULL AND type=? AND source=? AND data_json=?",
            (etype, source, json.dumps(data))
        )
    else:
        cur.execute(
            "SELECT COUNT(*) FROM events WHERE session=? AND type=? AND source=? AND data_json=?",
            (session, etype, source, json.dumps(data))
        )
    if cur.fetchone()[0] > 0:
        print(f"  SKIP (dup): S{session} {etype} {source}")
        return
    cur.execute(
        "INSERT INTO events (ts, session, type, source, data_json, tags_json) VALUES (?, ?, ?, ?, ?, ?)",
        (ts, session, etype, source, json.dumps(data), json.dumps(tags))
    )
    inserted += 1
    print(f"  INSERT: S{session} {etype} — {source}")

# ============================================================
# 1. AUDIT_SCORE events from audit-log.md
# ============================================================
print("\n=== AUDIT_SCORE events ===")

audit_scores = [
    # (date, session, scores_dict)
    ("2026-03-18T12:00:00Z", 1, {"research": 6, "quality": 7, "process": 5, "learning": 9, "outcomes": 5, "combined_avg": 6.4}),
    ("2026-03-18T12:00:00Z", 2, {"research": 8, "quality": 8, "process": 9, "learning": 10, "outcomes": 7, "combined_avg": 8.4}),
    ("2026-03-18T12:00:00Z", 3, {"research": 8, "quality": 8, "process": 9, "learning": 10, "outcomes": 6, "combined_avg": 8.18, "note": "combined with loop avg"}),
    ("2026-03-18T12:00:00Z", 4, {"research": 8, "quality": 8, "process": 7, "learning": 9, "outcomes": 5, "combined_avg": 8.03, "note": "combined with loop avg"}),
    ("2026-03-19T12:00:00Z", 4.5, {"research": 8, "quality": 9, "process": 8, "learning": 10, "outcomes": 4, "combined_avg": 8.23}),
    ("2026-03-19T12:00:00Z", 5, {"research": 8, "quality": 7, "process": 7, "learning": 9, "outcomes": 8, "combined_avg": 7.65}),
    ("2026-03-19T12:00:00Z", 6, {"research": 7, "quality": 7, "process": 5, "learning": 8, "outcomes": 7, "combined_avg": 6.5, "note": "FAIL — below 8.0 gate"}),
    ("2026-03-19T12:00:00Z", 7, {"research": 8, "quality": 8, "process": 8, "learning": 8, "outcomes": 8, "combined_avg": 8.0}),
    ("2026-03-20T12:00:00Z", 10, {"research": 8, "quality": 8, "process": 9, "learning": 8, "outcomes": 8, "combined_avg": 8.3}),
    ("2026-03-20T12:00:00Z", 12, {"research": 8, "quality": 8, "process": 8, "learning": 9, "outcomes": 8, "combined_avg": 8.2}),
    # S8 self-score 7.6, S9/S11/S13 not recorded — self-scores only
    ("2026-03-20T12:00:00Z", 8, {"self_score": 7.6, "note": "revised self-score only, below 8.0"}),
    ("2026-03-20T12:00:00Z", 14, {"self_score": 8.1, "note": "loop-state mentions 8.1, not formally audited"}),
    ("2026-03-20T12:00:00Z", 15, {"self_score": 7.5, "note": "systems-only cap, not formally audited"}),
    ("2026-03-20T12:00:00Z", 16, {"self_score": 7.8, "note": "self-score only"}),
    ("2026-03-20T12:00:00Z", 17, {"self_score": 7.8, "note": "self-score only"}),
    ("2026-03-20T12:00:00Z", 18, {"self_score": 8.0, "note": "self-score only"}),
    ("2026-03-20T12:00:00Z", 19, {"self_score": 7.5, "note": "self-score only"}),
    ("2026-03-21T12:00:00Z", 20, {"research": 9, "quality": 9, "process": 9, "learning": 8, "outcomes": 8, "combined_avg": 8.8}),
    ("2026-03-21T12:00:00Z", 21, {"research": 8, "quality": 8, "process": 9, "combined_avg": 8.2, "note": "abbreviated"}),
    ("2026-03-21T12:00:00Z", 22, {"research": 9, "quality": 8, "process": 9, "combined_avg": 8.7, "note": "estimated"}),
    ("2026-03-21T12:00:00Z", 23, {"self_score": 7.5, "note": "minimal session"}),
    ("2026-03-21T12:00:00Z", 24, {"quality": 8, "process": 9, "combined_avg": 8.5, "note": "abbreviated"}),
    ("2026-03-21T12:00:00Z", 25, {"research": 8, "quality": 8, "process": 9, "combined_avg": 8.3, "note": "abbreviated, systems-only"}),
    ("2026-03-21T12:00:00Z", 26, {"self_score": 7.0, "note": "minimal or incomplete session"}),
    ("2026-03-21T12:00:00Z", 27, {"self_score": 8.5, "note": "self-score only, 0 corrections"}),
    ("2026-03-21T12:00:00Z", 28, {"research": 8, "quality": 8, "process": 7, "learning": 8, "outcomes": 8, "combined_avg": 7.8, "note": "below 8.0"}),
    ("2026-03-21T12:00:00Z", 29, {"self_score": 8.0, "note": "self-score avg"}),
    ("2026-03-21T12:00:00Z", 30, {"self_score": 8.5, "note": "systems-only session, self-score only"}),
    ("2026-03-22T12:00:00Z", 31, {"research": 8, "quality": 8, "process": 7, "learning": 8, "outcomes": 7, "combined_avg": 7.6, "note": "FAIL — below 8.0 gate"}),
    ("2026-03-22T12:00:00Z", 32, {"research": 9, "quality": 9, "process": 8, "learning": 8, "outcomes": 8, "combined_avg": 8.4, "note": "abbreviated, maintenance"}),
    ("2026-03-22T12:00:00Z", 33, {"research": 9, "quality": 9, "process": 8, "learning": 8, "outcomes": 8, "combined_avg": 8.4, "note": "abbreviated, systems-only"}),
    # S34 already has AUDIT_SCORE events — skip
]

for ts, session, scores in audit_scores:
    emit(ts, session, "AUDIT_SCORE", "backfill:audit_log", scores)

# ============================================================
# 2. CORRECTION events from session notes + brain/sessions
# ============================================================
print("\n=== CORRECTION events ===")

corrections = [
    # Session 1 (2026-03-18) — audit-log mentions avg 6.4, gaps include "gates built after violations"
    # No specific correction items enumerated for S1

    # Session 3 (2026-03-18) — thread matching correction
    ("2026-03-18T12:00:00Z", 3, "Thread matching was wrong on initial Kindle Point draft — caught and fixed"),

    # Session 4 (2026-03-19) — capture full strategic vision
    ("2026-03-19T12:00:00Z", 4, "Must capture full strategic vision immediately — partial capture = data loss"),

    # Session 5 (2026-03-19) — 8 corrections from Oliver
    ("2026-03-19T12:00:00Z", 5, "Don't re-sell after the close — operational only"),
    ("2026-03-19T12:00:00Z", 5, "Don't guess emails without checking Apollo first"),
    ("2026-03-19T12:00:00Z", 5, "Check Gmail sent before listing active items"),
    ("2026-03-19T12:00:00Z", 5, "Day 1-2 follow-ups are too needy — earliest follow-up is Day 3"),
    ("2026-03-19T12:00:00Z", 5, "Always fact-check Gmail for sent emails before claiming they're missing"),
    ("2026-03-19T12:00:00Z", 5, "Email drafts must use <p> tags for paragraph groups, not <br> per line"),
    ("2026-03-19T12:00:00Z", 5, "Every email required Oliver edits (Quality 7)"),
    ("2026-03-19T12:00:00Z", 5, "Lead filtering took 3 passes (Process 7)"),

    # Session 6 (2026-03-19) — multiple corrections, 3 fix cycles
    ("2026-03-19T12:00:00Z", 6, "Built pre-flight/waterfall/brain-mandatory rules then violated all three"),
    ("2026-03-19T12:00:00Z", 6, "4/6 wrap-up steps skipped"),
    ("2026-03-19T12:00:00Z", 6, "4 iterations on cheat sheet due to skipping vault/NLM on first pass"),
    ("2026-03-19T12:00:00Z", 6, "Never log FAIL and stop — keep fix-cycling to 8.0+"),

    # Session 7 (2026-03-19) — correction session post-S6
    # audit-log says corrections logged from S5+S6 fix, 0 new corrections in S7 itself

    # Session 15 (2026-03-20) — 4 corrections
    ("2026-03-20T12:00:00Z", 15, "startup-brief.md was stale — should refresh every session"),
    ("2026-03-20T12:00:00Z", 15, "session-start skill doesn't exist as registered skill — hook was calling it wrong"),
    ("2026-03-20T12:00:00Z", 15, "Only add NotebookLM pointers to operational files"),
    ("2026-03-20T12:00:00Z", 15, "Replace fallback-chains.md NotebookLM entry, don't keep both definitions"),

    # Session 18 (2026-03-20) — 1 correction
    ("2026-03-20T12:00:00Z", 18, "Wire existing tighter first and only add what's genuinely missing"),

    # Session 20 (2026-03-21) — 1 correction
    ("2026-03-21T12:00:00Z", 20, "VERIFY clause ambiguity between step 11 and 11b — Oliver caught"),

    # Session 23 (2026-03-21) — 1 correction
    ("2026-03-21T12:00:00Z", 23, "Desktop path wrong — wrote .bat to C:/Users/olive/Desktop/ but actual is OneDrive/Desktop/"),

    # Session 27-final (2026-03-21) — 3 corrections
    ("2026-03-21T12:00:00Z", 27, "Forgot wrap-up steps 8/9/9.5/10.5/11b on first pass"),
    ("2026-03-21T12:00:00Z", 27, "Dead weight assessment was wrong — data existed in external tools"),
    ("2026-03-21T12:00:00Z", 27, "Research should use professional sources only, not random blogs"),

    # Session 28 (2026-03-21) — 5 corrections (from brain/sessions/2026-03-21-S28.md)
    ("2026-03-21T12:00:00Z", 28, "Cold reply data != close-cycle effectiveness. Pain sells."),
    ("2026-03-21T12:00:00Z", 28, "Verify current workflow before recommending changes. No PDF proposals exist."),
    ("2026-03-21T12:00:00Z", 28, "Big picture first, file locations second."),
    ("2026-03-21T12:00:00Z", 28, "Filter CRM noise before analysis. Most Pipedrive deals are debris."),
    ("2026-03-21T12:00:00Z", 28, "Always verify dates against source data before listing upcoming activities."),

    # Session 29 (2026-03-21) — 3 corrections
    ("2026-03-21T12:00:00Z", 29, "Calendar showed next week's events without noting it's Saturday"),
    ("2026-03-21T12:00:00Z", 29, "Agency pricing implies expensive retainers — say fixed monthly subscription"),
    ("2026-03-21T12:00:00Z", 29, "Subject lines built from Gong only, not cross-referenced with Oliver's playbooks"),

    # Session 31 (2026-03-22) — 5 corrections
    ("2026-03-22T12:00:00Z", 31, "Presented FITFO options ambiguously"),
    ("2026-03-22T12:00:00Z", 31, "Proposed paid Composio solution — free only"),
    ("2026-03-22T12:00:00Z", 31, "Included 25/month trial-tier tools — trials are out"),
    ("2026-03-22T12:00:00Z", 31, "Included irrelevant GitHub data source for marketing ICP"),
    ("2026-03-22T12:00:00Z", 31, "Included Anna's campaign data in Oliver's delta — Oliver only"),

    # Session 33 (2026-03-22) — 1 correction
    ("2026-03-22T12:00:00Z", 33, "Weekend schedule: framed Saturday systems work as pipeline neglect"),
]

for ts, session, detail in corrections:
    emit(ts, session, "CORRECTION", "backfill:session_notes", {"detail": detail})

# ============================================================
# 3. LESSON_CHANGE events from lessons.md graduated index
# ============================================================
print("\n=== LESSON_CHANGE events ===")

# Graduated lessons by date (from lessons.md graduated index)
lesson_changes = [
    # 3/17 — lessons.md created with 9 initial lessons
    ("2026-03-17T12:00:00Z", None, "lessons.md created with 9 initial lessons from Session 1", "backfill:session_notes"),

    # 3/18 graduated lessons (bulk — from Sessions 1-3 work)
    ("2026-03-18T12:00:00Z", 3, "Graduated: #1 DRAFTING (no generic openers), #4 CTA (Calendly), #5 FORMAT (hyperlink), #6 TONE (5-8 sentences), #7 RESEARCH (internal first), #9 CRM (Oliver deals only), #10 CRM (no value updates), #11 PROCESS (save to Sprites Work), #12 PROCESS (HTML drafts), #13 STRATEGY (CCQ/Gap), #14 STRATEGY (inbound welcome), #15 STRATEGY (follow-up), #16 TONE (Hi First Name), #17 ACCURACY (verify pending), #18 ACCURACY (no double-dip), #19 ICP (multi-brand), #20 ICP (10-300 employees), #21 PROCESS (log without asking), #22 PROCESS (straight to Gmail), #23 SIGNATURE, #24 TOOL (Fireflies), #25 TOOL (Calendar)", "backfill:audit_log"),

    # 3/19 graduated lessons (Sessions 5-7)
    ("2026-03-19T12:00:00Z", 5, "Graduated: #26 ACCURACY (verify team size), #27 STRATEGY (don't disqualify visitors), #28 KNOWLEDGE (Apollo shared), #29 DRAFTING (TRAP sections), #30 STRATEGY (don't re-pitch rejected), #33 ACCURACY (build cost 500K+), #34 ACCURACY (fact-check transcripts), #35 CRM (no probability field), #36 TECHNICAL (subagents), #37 STRATEGY (white label), #38 STRATEGY (next steps), #40 DRAFTING (paywall), #41 LANGUAGE (their pain), #42 VAULT (brain compounds), #45 CORRECTION (Day 3 earliest), #47 FORMAT (p tags), #48 STRATEGY (Instantly read-only), #49 CORRECTION (Gmail thread matching), #50 PROCESS (capture full vision)", "backfill:audit_log"),

    # 3/20 graduated lessons (Sessions 9-19)
    ("2026-03-20T12:00:00Z", 13, "Graduated: #51 TONE (condescending fix), #52 HONESTY (don't claim Oliver watched), #53 FLOW (bridge sentence), #56 LEADS (filter before enrich), #57 TONE (no re-pitch after close), #58 FORMAT (numbered lists), #59 DETAIL (practical prep), #60 STYLE (imperative verbs), #62 DRAFTING (omnichannel scope), #63 DEMO PREP (Fireflies post-demo), #68 CRM (clean notes only), #69 DEMO PREP (research first), #70 DEMO PREP (all playbooks)", "backfill:audit_log"),

    # Session 9 graduation cycle (2026-03-20) — 33 active → 13 active, 16 retired
    ("2026-03-20T12:00:00Z", 9, "Graduation cycle: 33 active -> 13 active. 16 retired (redundant). 4 reclassified.", "backfill:session_notes"),

    # 3/21 new lessons confirmed/promoted (Sessions 20-29)
    ("2026-03-21T12:00:00Z", 20, "New lessons: DRAFTING (bullet lead-in), APIFY (harvestapi), LEADS (dedup), ACCURACY (system rubric), PROCESS (startup-brief refresh), ARCHITECTURE (no duplicate defs), COMMUNICATION (explain anomalies)", "backfill:audit_log"),
    ("2026-03-21T12:00:00Z", 28, "New lessons: CRM (filter unworked deals), STRATEGY (cold vs close), ACCURACY (verify current state), ARCHITECTURE (big picture first), PRESENTATION (calendar framing), POSITIONING (agency pricing), DRAFTING (cross-reference playbooks), PROCESS (parallelize), PROCESS (research before building), ACCURACY (filter metrics by session type)", "backfill:audit_log"),

    # 3/22 new instinct lessons (Sessions 31-34)
    ("2026-03-22T12:00:00Z", 31, "New instinct lessons: CONSTRAINT (check cost first), DATA_INTEGRITY (Oliver only for all measurement), PROCESS (never skip wrap-up)", "backfill:audit_log"),
    ("2026-03-22T12:00:00Z", 33, "New instinct lessons: CONTEXT (weekend schedule), THOROUGHNESS (never park as first response)", "backfill:audit_log"),

    # S33 promoted 18 lessons
    ("2026-03-22T12:00:00Z", 33, "18 lessons promoted during deep system audit", "backfill:session_notes"),
]

for ts, session, detail, source in lesson_changes:
    emit(ts, session, "LESSON_CHANGE", source, {"detail": detail})

# ============================================================
# 4. CALIBRATION events from audit-log.md Session 6
# ============================================================
print("\n=== CALIBRATION events ===")

calibrations = [
    ("2026-03-19T12:00:00Z", 6, {"output_type": "demo_prep", "self_score": 7, "oliver_score": 6, "delta": -1}),
    ("2026-03-19T12:00:00Z", 6, {"output_type": "demo_prep_v2", "self_score": 8, "oliver_score": 7, "delta": -1}),
    ("2026-03-19T12:00:00Z", 6, {"output_type": "demo_prep_v3", "self_score": 8, "oliver_score": 7.8, "delta": -0.2}),
    ("2026-03-19T12:00:00Z", 6, {"output_type": "session_overall", "self_score": 8.0, "oliver_score": 8, "delta": 0, "note": "after 3 fix cycles"}),
]

for ts, session, data in calibrations:
    emit(ts, session, "CALIBRATION", "backfill:audit_log", data)

# Commit
conn.commit()
print(f"\n=== DONE: {inserted} events inserted ===")

# Summary
cur.execute("SELECT type, COUNT(*) FROM events GROUP BY type ORDER BY type")
print("\nEvents table summary:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

cur.execute("SELECT COUNT(*) FROM events")
print(f"  TOTAL: {cur.fetchone()[0]}")

conn.close()
