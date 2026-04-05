"""
Gradata CLI — Command-line interface for brain operations.

Usage:
    gradata init ./my-brain                    # Bootstrap new brain
    gradata init ./my-brain --domain Sales     # Bootstrap with domain
    gradata search "budget objections"         # Search brain
    gradata embed                              # Delta embed
    gradata embed --full                       # Full re-embed
    gradata manifest                           # Generate manifest
    gradata stats                              # Brain statistics
    gradata audit                              # Data flow audit
    gradata export                             # Export for marketplace
    gradata context "draft a follow-up email"   # Compile context
    gradata validate                           # Verify brain quality
    gradata validate --strict                  # Fail if trust < C
    gradata install brain-archive.zip          # Install from marketplace
    gradata install --list                     # List installed brains
"""

import argparse
import json
import sys
from pathlib import Path


def _get_brain(args):
    """Resolve brain directory from args or environment."""
    from gradata import Brain
    brain_dir = getattr(args, "brain_dir", None) or Path.cwd()
    return Brain(brain_dir)


def cmd_init(args):
    from gradata import Brain
    kwargs = {}
    if args.domain:
        kwargs["domain"] = args.domain
    if args.name:
        kwargs["name"] = args.name
    if args.company:
        kwargs["company"] = args.company
    if args.embedding:
        kwargs["embedding"] = args.embedding
    if args.no_interactive:
        kwargs["interactive"] = False
    Brain.init(args.path, **kwargs)


def cmd_search(args):
    brain = _get_brain(args)
    results = brain.search(args.query, mode=args.mode, top_k=args.top)
    if not results:
        print("No results found.")
        return
    for i, r in enumerate(results, 1):
        conf = r.get("confidence", "?")
        score = r.get("score", 0)
        src = r.get("source", "?")
        text = r.get("text", "")[:120]
        print(f"  {i}. [{conf}:{score:.2f}] {src}")
        print(f"     {text}")


def cmd_embed(args):
    brain = _get_brain(args)
    brain.embed(full=args.full)


def cmd_manifest(args):
    brain = _get_brain(args)
    m = brain.manifest()
    if args.json:
        print(json.dumps(m, indent=2, default=str))
    else:
        meta = m.get("metadata", {})
        quality = m.get("quality", {})
        rag = m.get("rag", {})
        print(f"Brain {meta.get('brain_version', '?')} | {meta.get('sessions_trained', 0)} sessions | {meta.get('maturity_phase', '?')}")
        print(f"  Quality: correction_rate={quality.get('correction_rate')}, lessons={quality.get('lessons_active', 0)} active / {quality.get('lessons_graduated', 0)} graduated")
        print(f"  RAG: {rag.get('provider', '?')} ({rag.get('chunks_indexed', 0)} chunks)")


def cmd_stats(args):
    brain = _get_brain(args)
    stats = brain.stats()
    print(f"Brain: {stats['brain_dir']}")
    print(f"  Markdown files: {stats['markdown_files']}")
    print(f"  Database: {stats['db_size_mb']} MB")
    print(f"  Embedding chunks: {stats['embedding_chunks']}")
    print(f"  Has manifest: {stats['has_manifest']}")
    print(f"  Has embeddings: {stats['has_embeddings']}")


def cmd_audit(args):
    try:
        from gradata._data_flow_audit import run_audit
        report = run_audit()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            status = "PASS" if report["score"] >= 80 else "WARN" if report["score"] >= 60 else "FAIL"
            print(f"{status}: {report['passed']}/{report['total']} checks ({report['score']}%)")
            failures = [c for c in report["checks"] if not c["passed"]]
            if failures:
                for f in failures:
                    print(f"  FAIL: {f['name']} -- {f['detail'][:80]}")
    except ImportError:
        print("Audit module not available.")


def cmd_export(args):
    brain = _get_brain(args)
    path = brain.export(mode=args.mode)
    print(f"Exported: {path}")


def cmd_context(args):
    brain = _get_brain(args)
    ctx = brain.context_for(args.message)
    if ctx:
        print(ctx)
    else:
        print("No relevant context found.")


def cmd_validate(args):
    brain = _get_brain(args)
    from gradata._validator import print_report, validate_brain
    manifest_path = Path(args.manifest) if args.manifest else brain.dir / "brain.manifest.json"
    report = validate_brain(manifest_path)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)
    if args.strict and report.get("trust", {}).get("grade", "F") in ("C", "D", "F"):
        sys.exit(1)


def cmd_doctor(args):
    from gradata._doctor import diagnose, print_diagnosis
    brain_dir = getattr(args, "brain_dir", None)
    report = diagnose(brain_dir=brain_dir)
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        print_diagnosis(report)
    if report["status"] == "broken":
        sys.exit(1)


def cmd_install(args):
    from gradata._installer import install, list_installed

    if args.list:
        brains = list_installed()
        if brains:
            print(f"Installed brains ({len(brains)}):")
            for b in brains:
                print(f"  {b.get('domain', '?')}/{b.get('version', '?')} — {b['path']}")
        else:
            print("No brains installed.")
        return

    if not args.archive:
        print("Archive path required (or use --list)")
        sys.exit(1)

    target = Path(args.target) if args.target else None
    report = install(Path(args.archive), target, dry_run=args.dry_run)
    if report["status"] == "failed":
        sys.exit(1)


def cmd_health(args):
    brain = _get_brain(args)
    try:
        try:
            from gradata_cloud.scoring.reports import format_health_report, generate_health_report
        except ImportError:
            from gradata.enhancements.reporting import format_health_report, generate_health_report
    except ImportError:
        print("Health reports require the reporting module. Cloud features require the Gradata cloud service (coming soon).")
        sys.exit(1)
    report = generate_health_report(brain.db_path)
    if getattr(args, "json", False):
        import dataclasses
        print(json.dumps(dataclasses.asdict(report), indent=2))
    else:
        print(format_health_report(report))
    if not report.healthy:
        sys.exit(1)


def cmd_report(args):
    brain = _get_brain(args)
    try:
        try:
            from gradata_cloud.scoring.reports import (
                export_session_csv,
                format_health_report,
                generate_health_report,
                generate_metrics_report,
                generate_rule_audit,
            )
        except ImportError:
            from gradata.enhancements.reporting import (
                export_session_csv,
                format_health_report,
                generate_health_report,
                generate_metrics_report,
                generate_rule_audit,
            )
    except ImportError:
        print("Reports require the reporting module. Cloud features require the Gradata cloud service (coming soon).")
        sys.exit(1)
    report_type = args.type
    if report_type == "csv":
        print(export_session_csv(brain.db_path))
    elif report_type == "metrics":
        print(generate_metrics_report(brain.db_path, window=args.window))
    elif report_type == "rules":
        print(generate_rule_audit(brain.db_path))
    elif report_type == "health":
        report = generate_health_report(brain.db_path)
        print(format_health_report(report))


def cmd_watch(args):
    """Watch a directory for file changes and emit CORRECTION events."""
    from gradata.sidecar.watcher import FileWatcher

    watch_dir = Path(args.dir).resolve()
    brain_path = Path(args.brain).resolve() if args.brain else Path.cwd().resolve()
    interval = max(0.5, args.interval)

    if not watch_dir.exists():
        print(f"Error: directory does not exist: {watch_dir}")
        sys.exit(1)

    print(f"Watching : {watch_dir}")
    print(f"Brain    : {brain_path}")
    print(f"Interval : {interval}s")
    print("Press Ctrl+C to stop.")

    watcher = FileWatcher(watch_dir, brain_db=brain_path)
    try:
        watcher.poll(interval=interval)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")


def cmd_diagnose(args):
    """Analyze correction patterns — free diagnostic, no graduation needed."""
    brain = _get_brain(args)
    import json
    from collections import Counter

    # Read events
    events_path = brain.dir / "events.jsonl"
    if not events_path.exists():
        print("No events found. Run some corrections first:")
        print("  gradata correct --draft 'original' --final 'edited version'")
        return

    corrections = []
    outputs = []
    with open(events_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                if e.get("type") == "CORRECTION":
                    corrections.append(e)
                elif e.get("type") == "OUTPUT":
                    outputs.append(e)
            except (json.JSONDecodeError, KeyError):
                continue

    print(f"Correction Diagnostic for: {brain.dir.name}")
    print(f"{'=' * 50}")
    print(f"Total corrections: {len(corrections)}")
    print(f"Total outputs: {len(outputs)}")
    if outputs:
        rate = len(corrections) / len(outputs)
        print(f"Correction rate: {rate:.1%}")
    print()

    # Category breakdown
    cats = Counter(c.get("data", {}).get("category", "UNKNOWN") for c in corrections)
    if cats:
        print("Top correction categories:")
        for cat, count in cats.most_common(10):
            print(f"  {cat}: {count}")
        print()

    # Severity breakdown
    sevs = Counter(c.get("data", {}).get("severity", "unknown") for c in corrections)
    if sevs:
        print("Severity distribution:")
        for sev, count in sevs.most_common():
            print(f"  {sev}: {count}")
        print()

    # Lessons
    lessons_path = brain.dir / "lessons.md"
    if lessons_path.exists():
        try:
            from gradata.enhancements.self_improvement import parse_lessons
            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            states = Counter(lesson.state.value for lesson in lessons)
            print(f"Lessons: {len(lessons)}")
            for state, count in states.most_common():
                print(f"  {state}: {count}")
        except Exception:
            print("Lessons: could not parse")
    else:
        print("No lessons yet — need more corrections to start building procedural memory.")

    print(f"\nRun 'gradata health' for a full brain health report.")


def cmd_correct(args):
    """Record a correction: the user edited an AI draft."""
    brain = _get_brain(args)
    draft = args.draft
    final = args.final
    if args.draft_file:
        draft = Path(args.draft_file).read_text(encoding="utf-8")
    if args.final_file:
        final = Path(args.final_file).read_text(encoding="utf-8")
    if not draft or not final:
        print("Error: both --draft and --final (or --draft-file and --final-file) required")
        sys.exit(1)
    result = brain.correct(draft, final, category=args.category, session=args.session)
    severity = result.get("data", {}).get("severity", "?")
    distance = result.get("data", {}).get("edit_distance", 0)
    summary = result.get("data", {}).get("summary", "")
    print(f"Correction logged: severity={severity}, edit_distance={distance:.2f}")
    if summary:
        print(f"  {summary}")


def cmd_review(args):
    brain = _get_brain(args)
    import json as _json
    if args.approve:
        result = brain.approve_lesson(args.approve)
        if args.json:
            print(_json.dumps(result, indent=2))
        elif result.get("approved"):
            print(f"Approved: [{result['category']}] {result['description'][:80]}")
        else:
            print(f"Failed: {result.get('reason', 'unknown')}")
    elif args.reject:
        result = brain.reject_lesson(args.reject, reason=args.reason)
        if args.json:
            print(_json.dumps(result, indent=2))
        elif result.get("rejected"):
            print(f"Rejected: [{result['category']}] {result['description'][:80]}")
        else:
            print(f"Failed: {result.get('reason', 'unknown')}")
    else:
        pending = brain.review_pending()
        if args.json:
            print(_json.dumps(pending, indent=2))
        elif not pending:
            print("No lessons pending approval.")
        else:
            print(f"\n{len(pending)} lesson(s) pending approval:\n")
            for p in pending:
                print(f"  ID {p['id']}  [{p['lesson_category']}]  {p['lesson_description'][:60]}")
                print(f"    Severity: {p.get('severity', '?')}  |  Created: {p['created_at']}")
                if p.get('draft_text'):
                    print(f"    Draft:  {p['draft_text'][:80]}...")
                if p.get('final_text'):
                    print(f"    Final:  {p['final_text'][:80]}...")
                print()
            print("  gradata review --approve ID   Accept a lesson")
            print("  gradata review --reject ID    Reject a lesson")


def main():
    parser = argparse.ArgumentParser(
        prog="gradata",
        description="Personal AI Brain SDK",
    )
    parser.add_argument("--brain-dir", "-b", type=Path,
                        help="Brain directory (default: current dir)")
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Bootstrap a new brain")
    p_init.add_argument("path", type=Path, help="Directory to create brain in")
    p_init.add_argument("--name", default=None, help="Brain name (default: directory name)")
    p_init.add_argument("--domain", default=None, help="Brain domain (e.g., Sales, Engineering)")
    p_init.add_argument("--company", default=None, help="Company name (creates company.md)")
    p_init.add_argument("--embedding", choices=["local", "gemini"], default=None,
                         help="Embedding provider: local (default) or gemini")
    p_init.add_argument("--no-interactive", action="store_true",
                         help="Skip interactive prompts, use defaults")

    # search
    p_search = sub.add_parser("search", help="Search the brain")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--mode", choices=["keyword", "semantic", "hybrid"])
    p_search.add_argument("--top", type=int, default=5)

    # embed
    p_embed = sub.add_parser("embed", help="Embed brain files")
    p_embed.add_argument("--full", action="store_true", help="Full re-embed")

    # manifest
    p_manifest = sub.add_parser("manifest", help="Generate brain manifest")
    p_manifest.add_argument("--json", action="store_true")

    # stats
    sub.add_parser("stats", help="Brain statistics")

    # audit
    p_audit = sub.add_parser("audit", help="Data flow audit")
    p_audit.add_argument("--json", action="store_true")

    # export
    p_export = sub.add_parser("export", help="Export brain for marketplace")
    p_export.add_argument("--mode", choices=["full", "no-prospects", "domain-only"],
                          default="full")

    # context
    p_ctx = sub.add_parser("context", help="Compile context for a message")
    p_ctx.add_argument("message", help="User message")

    # validate
    p_validate = sub.add_parser("validate", help="Verify brain quality independently")
    p_validate.add_argument("--manifest", type=str, help="Path to brain.manifest.json")
    p_validate.add_argument("--json", action="store_true")
    p_validate.add_argument("--strict", action="store_true", help="Exit 1 on trust grade D or F")

    # doctor
    p_doctor = sub.add_parser("doctor", help="Check environment and brain health")
    p_doctor.add_argument("--json", action="store_true", help="Output as JSON")

    # install
    p_install = sub.add_parser("install", help="Install a brain from marketplace archive")
    p_install.add_argument("archive", nargs="?", help="Path to brain archive (.zip)")
    p_install.add_argument("--target", type=str, help="Installation directory")
    p_install.add_argument("--dry-run", action="store_true")
    p_install.add_argument("--list", action="store_true", help="List installed brains")

    # health
    p_health = sub.add_parser("health", help="Brain health report")
    p_health.add_argument("--json", action="store_true")

    # report
    p_report = sub.add_parser("report", help="Generate reports (csv, metrics, rules)")
    p_report.add_argument("type", choices=["csv", "metrics", "rules", "health"],
                          help="Report type")
    p_report.add_argument("--window", type=int, default=20, help="Rolling window size")

    # watch — sidecar file watcher
    p_watch = sub.add_parser("watch", help="Watch a directory for AI-generated file edits")
    p_watch.add_argument("--dir", required=True, type=str,
                         help="Directory to watch for file changes")
    p_watch.add_argument("--brain", default=None, type=str,
                         help="Path to brain directory (default: current dir)")
    p_watch.add_argument("--interval", type=float, default=5.0,
                         help="Poll interval in seconds (default: 5)")

    # diagnose — free correction pattern diagnostic (no graduation needed)
    p_diagnose = sub.add_parser("diagnose", help="Analyze correction patterns (free diagnostic)")

    # review — human-in-the-loop approval
    p_review = sub.add_parser("review", help="Review pending lessons for approval")
    p_review.add_argument("--approve", type=int, metavar="ID", help="Approve a pending lesson by ID")
    p_review.add_argument("--reject", type=int, metavar="ID", help="Reject a pending lesson by ID")
    p_review.add_argument("--reason", type=str, default="", help="Reason for rejection")
    p_review.add_argument("--json", action="store_true", help="Output as JSON")

    # correct — core correction loop
    p_correct = sub.add_parser("correct", help="Record a correction (draft -> final)")
    p_correct.add_argument("--draft", type=str, help="Original AI draft text")
    p_correct.add_argument("--final", type=str, help="User-edited final text")
    p_correct.add_argument("--draft-file", type=str, help="File containing draft")
    p_correct.add_argument("--final-file", type=str, help="File containing final")
    p_correct.add_argument("--category", type=str, help="Correction category override")
    p_correct.add_argument("--session", type=int, help="Session number")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "search": cmd_search,
        "embed": cmd_embed,
        "manifest": cmd_manifest,
        "stats": cmd_stats,
        "audit": cmd_audit,
        "export": cmd_export,
        "context": cmd_context,
        "validate": cmd_validate,
        "doctor": cmd_doctor,
        "install": cmd_install,
        "health": cmd_health,
        "report": cmd_report,
        "watch": cmd_watch,
        "correct": cmd_correct,
        "review": cmd_review,
        "diagnose": cmd_diagnose,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
