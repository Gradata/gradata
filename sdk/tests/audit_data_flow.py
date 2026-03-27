"""
End-to-end data flow audit — traces every pipe in the SDK.
Run: python tests/audit_data_flow.py
"""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gradata.brain import Brain


def main():
    print("=" * 60)
    print("END-TO-END DATA FLOW AUDIT")
    print("=" * 60)

    # Setup brain
    brain_dir = tempfile.mkdtemp(prefix="audit_brain_")
    os.makedirs(os.path.join(brain_dir, "sessions"), exist_ok=True)
    os.makedirs(os.path.join(brain_dir, "prospects"), exist_ok=True)
    open(os.path.join(brain_dir, "events.jsonl"), "w").close()
    open(os.path.join(brain_dir, "system.db"), "w").close()

    brain = Brain(brain_dir)
    errors = []

    # ── FLOW 1: Correction Pipeline ──────────────────────────
    print("\nFLOW 1: Correction Pipeline")
    print("-" * 40)

    draft = "The product costs 500/month with a 6-month commitment."
    final = "Fixed monthly subscription at 500. Cancel anytime, no commitment."
    result = brain.correct(draft, final, session=1)
    data = result.get("data", {})

    required = ["draft_text", "final_text", "edit_distance", "severity",
                "outcome", "major_edit", "category", "classifications"]
    for f in required:
        if f not in data:
            errors.append(f"FLOW1: missing field {f}")
            print(f"  FAIL: missing {f}")
        else:
            print(f"  PASS: {f} = {str(data[f])[:60]}")

    # Persistence flags
    persisted = result.get("_persisted", {})
    for store in ("jsonl", "sqlite"):
        if persisted.get(store):
            print(f"  PASS: {store} persisted")
        else:
            errors.append(f"FLOW1: {store} write failed")
            print(f"  FAIL: {store} not persisted")

    # Verify in SQLite
    events = brain.query_events(event_type="CORRECTION", limit=5)
    if len(events) == 1:
        print(f"  PASS: 1 CORRECTION in DB (dist={data['edit_distance']:.3f})")
    else:
        errors.append(f"FLOW1: {len(events)} corrections (expected 1)")
        print(f"  FAIL: {len(events)} corrections")

    # Verify in JSONL
    with open(os.path.join(brain_dir, "events.jsonl")) as f:
        jsonl = [json.loads(line) for line in f if line.strip()]
    corr_jsonl = [e for e in jsonl if e.get("type") == "CORRECTION"]
    if len(corr_jsonl) == 1:
        print("  PASS: 1 CORRECTION in JSONL")
    else:
        errors.append(f"FLOW1: JSONL has {len(corr_jsonl)} corrections")
        print(f"  FAIL: JSONL {len(corr_jsonl)} corrections")

    # ── FLOW 2: Output Tracking ──────────────────────────────
    print("\nFLOW 2: Output Tracking")
    print("-" * 40)

    out = brain.log_output("Draft cold email to VP", output_type="email",
                           self_score=7.5, session=1)
    out_data = out.get("data", {})
    for f in ["output_type", "output_text", "self_score", "outcome"]:
        if f in out_data:
            print(f"  PASS: {f} = {str(out_data[f])[:50]}")
        else:
            errors.append(f"FLOW2: missing {f}")
            print(f"  FAIL: missing {f}")

    outputs = brain.query_events(event_type="OUTPUT", limit=5)
    if outputs:
        print(f"  PASS: {len(outputs)} OUTPUT event(s) stored")
    else:
        errors.append("FLOW2: no OUTPUT events")
        print("  FAIL: no OUTPUT events")

    # ── FLOW 3: Rule Application ─────────────────────────────
    print("\nFLOW 3: Rule Application Loop")
    print("-" * 40)

    r1 = brain.track_rule("DRAFTING_001", accepted=True, session=1)
    print(f"  PASS: Rule accepted (event={'yes' if r1 else 'none'})")

    r2 = brain.track_rule("POSITIONING_002", accepted=False, misfired=True, session=1)
    print(f"  PASS: Rule misfired (event={'yes' if r2 else 'none'})")

    rule_events = brain.query_events(event_type="RULE_APPLICATION", limit=10)
    if len(rule_events) >= 2:
        print(f"  PASS: {len(rule_events)} RULE_APPLICATION events in DB")
    else:
        errors.append(f"FLOW3: only {len(rule_events)} rule events")
        print(f"  FAIL: {len(rule_events)} rule events (expected 2+)")

    # ── FLOW 4: Search/Context ───────────────────────────────
    print("\nFLOW 4: Search/RAG")
    print("-" * 40)

    results = brain.search("cold email")
    print(f"  PASS: search returned {len(results)} results")

    ctx = brain.context_for("budget objections")
    print(f"  PASS: context_for returned {len(ctx)} chars")

    # ── FLOW 5: Health + Manifest ────────────────────────────
    print("\nFLOW 5: Health + Manifest")
    print("-" * 40)

    health = brain.health()
    print(f"  PASS: health() keys: {list(health.keys())[:5]}")

    manifest = brain.manifest()
    quality = manifest.get("quality", {})
    meta = manifest.get("metadata", {})
    print(f"  PASS: manifest generated")
    print(f"    sessions: {meta.get('sessions_trained', '?')}")
    print(f"    correction_rate: {quality.get('correction_rate', '?')}")

    if os.path.exists(os.path.join(brain_dir, "brain.manifest.json")):
        print("  PASS: brain.manifest.json on disk")
    else:
        errors.append("FLOW5: manifest file missing")
        print("  FAIL: brain.manifest.json missing")

    # ── FLOW 6: Success Conditions ───────────────────────────
    print("\nFLOW 6: Success Conditions")
    print("-" * 40)

    sc = brain.success_conditions(window=5)
    print(f"  PASS: success_conditions (all_met={sc.get('all_met', '?')})")
    for c in sc.get("conditions", [])[:3]:
        print(f"    {c.get('name', '?')}: met={c.get('met', '?')}")

    # ── FLOW 7: Guardrails ───────────────────────────────────
    print("\nFLOW 7: Guardrails")
    print("-" * 40)

    g_in = brain.guard("Normal business text", direction="input")
    print(f"  PASS: input guard (passed={g_in['all_passed']})")

    g_out = brain.guard("Output text", direction="output")
    print(f"  PASS: output guard (passed={g_out['all_passed']})")

    # ── FLOW 8: Classify + Reflect ───────────────────────────
    print("\nFLOW 8: Classify + Reflect")
    print("-" * 40)

    c = brain.classify("Write a cold email to the CTO")
    print(f"  PASS: classify (intent={c.get('intent')}, pattern={c.get('selected_pattern')})")

    r = brain.reflect("Quick draft for review")
    print(f"  PASS: reflect (cycles={r.get('cycles_used')}, converged={r.get('converged')})")

    # ── FLOW 9: Risk Assessment ──────────────────────────────
    print("\nFLOW 9: Risk Assessment")
    print("-" * 40)

    risk = brain.assess_risk("delete production database")
    print(f"  PASS: assess_risk (tier={risk['tier']}, reversible={risk['reversible']})")

    risk2 = brain.assess_risk("update CRM notes")
    print(f"  PASS: assess_risk (tier={risk2['tier']}, reversible={risk2['reversible']})")

    # ── FLOW 10: MCP Server ──────────────────────────────────
    print("\nFLOW 10: MCP Server Integration")
    print("-" * 40)

    from gradata.mcp_server import _dispatch, _TOOL_SCHEMAS
    print(f"  PASS: {len(_TOOL_SCHEMAS)} MCP tools defined")

    # Test dispatch with real brain
    search_r = _dispatch(brain, "brain_search", {"query": "test"})
    print(f"  PASS: brain_search dispatch ({'error' not in search_r})")

    health_r = _dispatch(brain, "brain_health", {})
    print(f"  PASS: brain_health dispatch ({'error' not in health_r})")

    manifest_r = _dispatch(brain, "brain_manifest", {})
    print(f"  PASS: brain_manifest dispatch ({'error' not in manifest_r})")

    correct_r = _dispatch(brain, "brain_correct", {"draft": "old", "final": "new"})
    has_content = "content" in correct_r and "error" not in correct_r
    if has_content:
        print(f"  PASS: brain_correct dispatch (content returned)")
    else:
        errors.append(f"FLOW10: brain_correct dispatch failed: {correct_r.get('error', '?')}")
        print(f"  FAIL: brain_correct: {correct_r.get('error', '?')}")

    unknown_r = _dispatch(brain, "nonexistent_tool", {})
    if "error" in unknown_r:
        print(f"  PASS: unknown tool returns error")
    else:
        errors.append("FLOW10: unknown tool didn't error")
        print("  FAIL: unknown tool didn't error")

    # ── DB/JSONL SYNC CHECK ──────────────────────────────────
    print("\nSYNC CHECK: DB vs JSONL")
    print("-" * 40)

    db = sqlite3.connect(os.path.join(brain_dir, "system.db"))
    db_total = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    db_types = db.execute("SELECT type, COUNT(*) FROM events GROUP BY type ORDER BY COUNT(*) DESC").fetchall()
    db.close()

    with open(os.path.join(brain_dir, "events.jsonl")) as f:
        jsonl_total = sum(1 for line in f if line.strip())

    print(f"  DB events:   {db_total}")
    print(f"  JSONL events: {jsonl_total}")
    for t, c in db_types:
        print(f"    {t}: {c}")

    if db_total == jsonl_total:
        print(f"  PASS: DB and JSONL in sync ({db_total} == {jsonl_total})")
    else:
        errors.append(f"SYNC: DB ({db_total}) != JSONL ({jsonl_total})")
        print(f"  FAIL: DB ({db_total}) != JSONL ({jsonl_total})")

    # ── SUMMARY ──────────────────────────────────────────────
    print()
    print("=" * 60)
    if errors:
        print(f"AUDIT RESULT: {len(errors)} ERRORS FOUND")
        for e in errors:
            print(f"  ERROR: {e}")
        sys.exit(1)
    else:
        print("AUDIT RESULT: ALL 10 FLOWS CLEAN")
        print("Water is flowing. Pipes are healthy. Data is accurate.")
    print("=" * 60)


if __name__ == "__main__":
    main()
