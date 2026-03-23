"""
AIOS Brain CLI — Command-line interface for brain operations.

Usage:
    aios-brain init ./my-brain                    # Bootstrap new brain
    aios-brain init ./my-brain --domain Sales     # Bootstrap with domain
    aios-brain search "budget objections"         # Search brain
    aios-brain embed                              # Delta embed
    aios-brain embed --full                       # Full re-embed
    aios-brain manifest                           # Generate manifest
    aios-brain stats                              # Brain statistics
    aios-brain audit                              # Data flow audit
    aios-brain export                             # Export for marketplace
    aios-brain context "draft email to Hassan"    # Compile context
"""

import argparse
import json
import sys
from pathlib import Path


def _get_brain(args):
    """Resolve brain directory from args or environment."""
    from aios_brain import Brain
    brain_dir = getattr(args, "brain_dir", None) or Path.cwd()
    return Brain(brain_dir)


def cmd_init(args):
    from aios_brain import Brain
    brain = Brain.init(args.path, domain=args.domain)
    print(f"Brain initialized at {brain.dir}")
    stats = brain.stats()
    print(f"  Files: {stats['markdown_files']} | DB: {stats['db_size_mb']}MB")


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
    print(f"  Vector store: {stats['vectorstore_size_mb']} MB")
    print(f"  Has manifest: {stats['has_manifest']}")
    print(f"  Has embeddings: {stats['has_embeddings']}")


def cmd_audit(args):
    brain = _get_brain(args)
    try:
        sys.path.insert(0, str(brain.dir / "scripts"))
        from data_flow_audit import run_audit
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
        print("Audit requires brain scripts in brain/scripts/")


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


def main():
    parser = argparse.ArgumentParser(
        prog="aios-brain",
        description="Personal AI Brain SDK",
    )
    parser.add_argument("--brain-dir", "-b", type=Path,
                        help="Brain directory (default: current dir)")
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Bootstrap a new brain")
    p_init.add_argument("path", type=Path, help="Directory to create brain in")
    p_init.add_argument("--domain", default="General", help="Brain domain (e.g., Sales)")

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
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
