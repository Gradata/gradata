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

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC
from pathlib import Path

from gradata._env import env_str

_log = logging.getLogger("gradata.cli")


def _get_brain(args):
    """Resolve brain directory from env, args, or cwd.

    Precedence mirrors :func:`_resolve_brain_root` exactly —
    explicit args > ``BRAIN_DIR`` env > ``GRADATA_BRAIN`` env > cwd — so both helpers
    always target the same brain (important for export, tests with tmp
    brains, etc.).
    """
    from gradata import Brain

    brain_dir = (
        getattr(args, "brain_dir", None)
        or getattr(args, "brain", None)
        or env_str("BRAIN_DIR")
        or env_str("GRADATA_BRAIN")
        or Path.cwd()
    )
    return Brain(brain_dir)


def cmd_init(args):
    from gradata import Brain, _telemetry

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

    # Opt-in telemetry prompt — only on first init (when the user has never
    # been asked). Stays silent in non-interactive mode so CI doesn't hang.
    if not args.no_interactive and not _telemetry.has_been_asked():
        try:
            cfg_path = _telemetry.config_path()
            enabled = _telemetry.prompt_and_persist()
            if enabled:
                _log.info("Telemetry enabled. Thanks for helping us improve Gradata.")
                _log.info("To disable later: edit %s or set GRADATA_TELEMETRY=0", cfg_path)
            else:
                _log.info("Telemetry disabled. You can enable it later in %s", cfg_path)
        except Exception as exc:
            # Prompting must never break init.
            _log.debug("telemetry prompt failed: %s", exc)

    # brain_initialized — once per machine, even across multiple `gradata init`
    # runs. ``send_once`` already gates on ``is_enabled()`` internally; the
    # try/except guards against a telemetry bug or DNS hiccup breaking init.
    try:
        _telemetry.send_once("brain_initialized")
    except Exception as exc:
        _log.debug("telemetry send_once(brain_initialized) failed: %s", exc)


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
        print(
            f"Brain {meta.get('brain_version', '?')} | {meta.get('sessions_trained', 0)} sessions | {meta.get('maturity_phase', '?')}"
        )
        print(
            f"  Quality: correction_rate={quality.get('correction_rate')}, lessons={quality.get('lessons_active', 0)} active / {quality.get('lessons_graduated', 0)} graduated"
        )
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


def cmd_status(args):
    """Single human-readable summary of brain health.

    Wraps stats + health + daemon probe + cloud-sync state into one
    terminal-renderable block. Designed for the user's daily "what's
    going on with my brain" check — `gradata status` and done.

    Output is plain text (no color codes, no Unicode boxes). Stays
    under ~40 lines for a typical brain.
    """
    import json as _json
    import sqlite3 as _sqlite3
    import time as _time
    import urllib.error as _urllib_error
    import urllib.request as _urllib_request
    from datetime import datetime

    brain = _get_brain(args)
    stats = brain.stats()
    brain_dir = stats["brain_dir"]

    print(f"Brain: {brain_dir}")
    print(f"  Database: {stats['db_size_mb']} MB  ({stats['markdown_files']} markdown files)")

    # Rules / lessons / corrections from events table
    db_path = f"{brain_dir}/system.db"
    rules_total = lessons_total = corr_total = 0
    last_correction_ts = None
    try:
        con = _sqlite3.connect(db_path)
        cur = con.cursor()
        rules_total = cur.execute(
            "SELECT COUNT(*) FROM events WHERE type='RULE_GRADUATED'"
        ).fetchone()[0]
        lessons_total = cur.execute(
            "SELECT COUNT(*) FROM events WHERE type IN ('LESSON_ADDED','LESSON_CHANGE')"
        ).fetchone()[0]
        corr_total = cur.execute("SELECT COUNT(*) FROM events WHERE type='CORRECTION'").fetchone()[
            0
        ]
        row = cur.execute("SELECT MAX(ts) FROM events WHERE type='CORRECTION'").fetchone()
        last_correction_ts = row[0] if row else None
        con.close()
    except (_sqlite3.OperationalError, OSError):
        # Fresh brain or schema drift — show zeros, don't crash.
        pass

    print(f"  Rules graduated: {rules_total}")
    print(f"  Lessons: {lessons_total}")
    print(f"  Corrections: {corr_total}")
    if last_correction_ts:
        print(f"  Last correction: {last_correction_ts}")

    # Sync queue state
    pending = total_q = 0
    try:
        con = _sqlite3.connect(db_path)
        pending = con.execute("SELECT COUNT(*) FROM sync_queue WHERE synced_at IS NULL").fetchone()[
            0
        ]
        total_q = con.execute("SELECT COUNT(*) FROM sync_queue").fetchone()[0]
        con.close()
    except _sqlite3.OperationalError:
        pass
    if total_q:
        if pending:
            print(f"  Sync queue: {pending} pending / {total_q} total")
        else:
            print(f"  Sync queue: drained ({total_q} synced)")

    # Daemon health (best-effort, never blocks)
    print()
    print("Daemon:")
    try:
        req = _urllib_request.Request(
            "http://127.0.0.1:8765/health",
            headers={"User-Agent": "gradata-status/1.0"},
        )
        with _urllib_request.urlopen(req, timeout=2) as r:
            data = _json.loads(r.read().decode())
        uptime = data.get("uptime_seconds", 0)
        hrs = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)
        print(f"  Status: up  (uptime {hrs}h{mins}m)")
        print(f"  Brain dir: {data.get('brain_dir', '?')}")
        print(f"  SDK version: {data.get('sdk_version', '?')}")
        if (data.get("brain_dir") or "").rstrip("/") != brain_dir.rstrip("/"):
            print(f"  WARNING: daemon brain dir != this brain ({brain_dir})")
    except (_urllib_error.URLError, _urllib_error.HTTPError, TimeoutError, OSError):
        print("  Status: not running  (run: systemctl --user start gradata-daemon)")

    # Cloud sync state (best-effort)
    print()
    print("Cloud:")
    try:
        from pathlib import Path as _Path

        key_path = _Path.home() / ".gradata" / "key"
        token = key_path.read_text(encoding="utf-8").strip() if key_path.is_file() else ""
        if not token:
            print("  Status: not configured  (run: gradata cloud enable --key <gd_live_...>)")
        else:
            req = _urllib_request.Request(
                "https://api.gradata.ai/api/v1/brains",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "gradata-status/1.0",
                },
            )
            with _urllib_request.urlopen(req, timeout=4) as r:
                brains = _json.loads(r.read().decode())
            b = brains[0] if isinstance(brains, list) else brains
            last_sync = b.get("last_sync") or "(never)"
            cloud_corr = b.get("correction_count") or 0
            cloud_lessons = b.get("lesson_count") or 0
            print(f"  Last sync: {last_sync}")
            print(f"  Corrections: {cloud_corr}  (local: {corr_total})")
            print(f"  Lessons: {cloud_lessons}  (local: {lessons_total})")
            # Lag warning
            if last_sync and last_sync != "(never)":
                try:
                    ls = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                    age_min = (datetime.now(UTC) - ls).total_seconds() / 60
                    if age_min > 60:
                        print(f"  WARNING: cloud is {int(age_min)}m behind")
                except ValueError:
                    pass
    except (_urllib_error.URLError, _urllib_error.HTTPError, TimeoutError, OSError) as exc:
        print(f"  Status: unreachable  ({type(exc).__name__})")

    # Convergence trend — corrections-per-session, last 7 days
    print()
    print("Convergence (last 7d):")
    try:
        con = _sqlite3.connect(db_path)
        cur = con.cursor()
        cutoff = int(_time.time()) - 7 * 86400
        # Sessions and corrections in the last 7 days
        sessions_with_data = cur.execute(
            """
            SELECT session, COUNT(*) AS n
              FROM events
             WHERE type='CORRECTION'
               AND strftime('%s', ts) >= ?
             GROUP BY session
            """,
            (str(cutoff),),
        ).fetchall()
        con.close()
        if sessions_with_data:
            sess_n = len(sessions_with_data)
            corr_n = sum(n for _, n in sessions_with_data)
            avg = corr_n / sess_n
            print(f"  Sessions: {sess_n}  ({corr_n} corrections, avg {avg:.1f}/session)")
        else:
            print("  No correction activity in the last 7 days")
    except _sqlite3.OperationalError:
        print("  (events schema not available)")


def cmd_audit(args):
    from gradata._audit import format_audit_text, run_audit

    brain_root = _resolve_brain_root(args)
    report = run_audit(brain_root)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_audit_text(report))


def cmd_export(args):
    """Export brain. Two modes:

    - With --target: emit graduated RULE-tier lessons in a platform-specific
      rule file format (cursor/agents/aider).
    - Otherwise: marketplace archive export via Brain.export(mode=...).
    """
    target = getattr(args, "target", None)
    if target:
        from gradata.enhancements.rule_export import export_rules

        brain_root = _resolve_brain_root(args)
        # Prefer the canonical lessons path the rest of the SDK uses, rather
        # than hardcoding brain_root/"lessons.md" inside the exporter.
        lessons_path: Path | None = None
        try:
            brain = _get_brain(args)
            lessons_path = brain._find_lessons_path()
        except Exception:
            lessons_path = None
        try:
            text = export_rules(brain_root, target=target, lessons_path=lessons_path)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return
        output = getattr(args, "output", None)
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
            print(f"exported {text.count(chr(10))} lines to {out_path}")
        else:
            print(text, end="")
        return

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
    if getattr(args, "reconcile", False):
        from gradata._doctor import resolve_brain_path
        from gradata._events import reconcile_jsonl_to_sqlite

        brain_path = resolve_brain_path(brain_dir)
        if brain_path is None:
            print("reconcile: no brain dir resolved", file=sys.stderr)
            sys.exit(1)
        result = reconcile_jsonl_to_sqlite(brain_path)
        if getattr(args, "json", False):
            print(json.dumps({"reconcile": result}, indent=2))
        else:
            print(
                "reconcile: "
                f"drift={result.get('drift', 0)} "
                f"replayed={result.get('replayed', 0)} "
                f"jsonl={result.get('jsonl_events', 0)} "
                f"sqlite={result.get('sqlite_events_after', result.get('sqlite_events_before', 0))}"
            )
        return
    cloud_only = getattr(args, "cloud", False)
    include_cloud = not getattr(args, "no_cloud", False)
    report = diagnose(
        brain_dir=brain_dir,
        include_cloud=include_cloud,
        cloud_only=cloud_only,
    )
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        print_diagnosis(report)
    if report["status"] == "broken":
        sys.exit(1)


def cmd_install(args):
    if getattr(args, "systemd", False):
        _cmd_install_systemd(args)
        return

    if getattr(args, "agent", None):
        _cmd_install_agent(args)
        return

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


def _cmd_install_systemd(args) -> None:
    """Write the gradata-daemon systemd user unit (see `--systemd` flag)."""
    from gradata._systemd_installer import (
        DEFAULT_PORT,
        install_systemd_unit,
        post_install_message,
    )

    brain_dir = _resolve_brain_root(args)
    port = int(getattr(args, "port", None) or DEFAULT_PORT)
    try:
        target = install_systemd_unit(brain_dir=brain_dir, port=port)
    except RuntimeError as exc:
        print(f"✗ systemd install failed: {exc}")
        sys.exit(1)
    print(post_install_message(target))


def _cmd_install_agent(args) -> None:
    from gradata.hooks.adapters._base import AGENTS, adapter_config_path, get_adapter

    agent = args.agent
    brain_dir = _resolve_brain_root(args)
    agents = [a for a in AGENTS if adapter_config_path(a).exists()] if agent == "all" else [agent]

    if not agents:
        print("No agent config files detected.")
        return

    import os

    verify_install = os.environ.get("GRADATA_VERIFY_INSTALL", "").strip() in ("1", "true", "yes")

    had_failure = False
    for name in agents:
        try:
            adapter = get_adapter(name)
            config_path = adapter_config_path(name)
            result = adapter.install(brain_dir, config_path)
        except Exception as exc:
            print(f"✗ {name} → unknown (failed: {exc})")
            had_failure = True
            continue
        marker = "✓" if result.action != "failed" else "✗"
        if result.action == "failed":
            had_failure = True
        print(f"{marker} {result.agent} → {result.config_path} ({result.action})")

        # Record the install in ~/.gradata/install_manifest.json so that
        # `gradata uninstall --agent <host>` can safely reverse it later
        # (and detect user edits via SHA mismatch).
        if result.action in ("added", "already_present"):
            try:
                from gradata._install_manifest import record_install
                from gradata.hooks.adapters._base import hook_signature as _sig

                record_install(name, config_path, _sig(name, brain_dir))
            except Exception as exc:
                # Manifest write is best-effort; don't fail install on it.
                print(f"  ⚠ install manifest write failed: {exc}")

        # ▸ Flag-gated install verification: write + read a test rule
        if verify_install and result.action != "failed":
            try:
                import tempfile

                from gradata import Brain

                verification_marker = f"gradata-install-verify-{name}-{os.urandom(4).hex()}"
                with tempfile.TemporaryDirectory(prefix="gradata-verify-") as verification_tmp:
                    verification_dir = Path(verification_tmp) / "brain"
                    Brain.init(verification_dir)
                    verification_brain = Brain(verification_dir)
                    correction = verification_brain.correct(
                        draft=f"test draft for {name} install verification {verification_marker}",
                        final=f"test final for {name} install verification {verification_marker}",
                        dry_run=False,
                    )
                    results = verification_brain.search(verification_marker, mode="rules", top_k=3)
                    marker_found = any(
                        verification_marker in (r.get("text") or "").lower() for r in results
                    )
                    if not marker_found:
                        print(f"  ⚠ verify failed: test rule written but not readable for {name}")
                        had_failure = True
                    else:
                        print(f"  ✓ verify: {name} install confirmed (write+read)")
            except Exception as exc:
                print(f"  ✗ verify failed for {name}: {exc}")
                had_failure = True

    if had_failure:
        sys.exit(1)


def cmd_uninstall(args) -> None:
    """Reverse a prior ``gradata install --agent <host>``.

    For each requested host:

    - Look up the install manifest record (recorded by ``cmd_install`` at
      install time). If absent, fall back to the canonical config path so
      best-effort uninstall still works on installs that pre-date the
      manifest.
    - Compute the current SHA256 of the config file. If it differs from
      the SHA recorded at install time, print
      ``skipped <host> — modified since install`` and leave the file
      alone (preserve user edits).
    - Otherwise call the adapter's ``uninstall(brain_dir, config_path)``
      to symmetrically remove the entry the matching ``install()`` wrote.
    - Always idempotent — running twice doesn't error.

    Unknown hosts are rejected by argparse via the ``--agent`` choices
    list (matching how ``cmd_install`` handles unknown hosts).
    """
    from gradata._install_manifest import drop_record, file_sha256, get_record
    from gradata.hooks.adapters._base import AGENTS, adapter_config_path, get_adapter

    agent = args.agent
    brain_dir = _resolve_brain_root(args)
    agents = list(AGENTS) if agent == "all" else [agent]

    had_failure = False
    for name in agents:
        try:
            adapter = get_adapter(name)
        except ValueError as exc:
            # Shouldn't reach here because argparse choices guard this,
            # but be defensive in case the CLI is invoked programmatically.
            print(f"✗ {name} → unknown agent ({exc})")
            had_failure = True
            continue

        record = get_record(name)
        config_path = record.config_path if record else adapter_config_path(name)

        # User-edit guard: skip uninstall if the config file's checksum
        # differs from what was recorded at install time. Only meaningful
        # when we have a recorded SHA — fall through for legacy installs.
        if record and record.sha256_after_install:
            current = file_sha256(config_path)
            if current and current != record.sha256_after_install:
                print(f"skipped {name} — modified since install")
                continue

        try:
            result = adapter.uninstall(brain_dir, config_path)
        except Exception as exc:
            print(f"✗ {name} → unknown (failed: {exc})")
            had_failure = True
            continue

        marker = "✓" if result.action != "failed" else "✗"
        if result.action == "failed":
            had_failure = True
        print(f"{marker} {result.agent} → {result.config_path} ({result.action})")

        # Drop manifest record only when we actually removed an entry
        # (action == "added" in our adapter contract — "already_present"
        # means nothing was there to remove, so we leave the manifest
        # record alone in case the user re-installs).
        if result.action == "added":
            try:
                drop_record(name)
            except Exception as exc:
                print(f"  ⚠ install manifest update failed: {exc}")

    if had_failure:
        sys.exit(1)


def cmd_recall(args) -> None:
    from gradata.mcp_tools import gradata_recall

    brain_root = _resolve_brain_root(args)
    lessons_path: Path | None = None
    try:
        brain = _get_brain(args)
        lessons_path = brain._find_lessons_path()
    except Exception:
        lessons_path = None
    print(
        gradata_recall(
            args.situation,
            max_tokens=args.max_tokens,
            ranker=args.ranker,
            include_all_sources=args.include_all_sources,
            lessons_path=lessons_path or brain_root / "lessons.md",
            meta_rules_path=brain_root / "meta-rules.json",
        )
    )


def cmd_health(args):
    brain = _get_brain(args)
    try:
        try:
            from gradata_cloud.scoring.reports import format_health_report, generate_health_report
        except ImportError:
            from gradata.enhancements.reporting import format_health_report, generate_health_report
    except ImportError:
        print(
            "Health reports require the reporting module. Cloud features require the Gradata cloud service (coming soon)."
        )
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
        print(
            "Reports require the reporting module. Cloud features require the Gradata cloud service (coming soon)."
        )
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

    print("\nRun 'gradata health' for a full brain health report.")


def cmd_prove(args):
    """Statistical evidence the brain is improving output quality.

    Reads CORRECTION + LESSON_CHANGE + RULE_FAILURE events from system.db
    and computes:
      - Corrections-per-session over time (linear regression slope —
        negative = converging = brain is doing its job)
      - Rule application rate trend
      - Top 5 most-applied rules (proves the brain is being USED)
      - Top 5 most-failed rules (with tune/forget recommendations)

    Returns exit 0 when the trend is healthy (negative slope), exit 1
    when it's not — usable as a CI signal: ``gradata prove && deploy``.
    """
    import sqlite3 as _sqlite3
    from collections import Counter, defaultdict
    from datetime import datetime, timedelta

    brain = _get_brain(args)
    window_arg = (getattr(args, "window", "30d") or "30d").lower()
    window_days = {"7d": 7, "30d": 30, "90d": 90, "all": 36500}.get(window_arg, 30)

    db_path = str(brain.db_path)
    try:
        con = _sqlite3.connect(db_path)
        cur = con.cursor()
    except _sqlite3.OperationalError as exc:
        print(f"Could not open brain db: {exc}")
        sys.exit(1)

    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    cutoff_iso = cutoff.isoformat()

    # Per-session correction counts in the window
    rows = cur.execute(
        """
        SELECT session, ts, type
          FROM events
         WHERE type IN ('CORRECTION', 'LESSON_APPLIED', 'RULE_FAILURE')
           AND ts >= ?
        """,
        (cutoff_iso,),
    ).fetchall()

    sessions_corr: dict[int, int] = defaultdict(int)
    sessions_first_ts: dict[int, str] = {}
    rule_apps_by_session: dict[int, int] = defaultdict(int)
    rule_failures: list[tuple[str, str]] = []
    for session, ts, etype in rows:
        if session is None:
            continue
        if etype == "CORRECTION":
            sessions_corr[session] += 1
            if session not in sessions_first_ts or ts < sessions_first_ts[session]:
                sessions_first_ts[session] = ts
        elif etype == "LESSON_APPLIED":
            rule_apps_by_session[session] += 1
        elif etype == "RULE_FAILURE":
            rule_failures.append((session, ts))

    # Header
    print(f"Brain: {brain.dir}")
    print(f"Window: {window_arg} ({window_days}d)")
    print()

    if not sessions_corr:
        print("No correction activity in this window — nothing to prove yet.")
        sys.exit(0)

    sessions_sorted = sorted(sessions_corr.keys(), key=lambda s: sessions_first_ts.get(s, ""))
    counts = [sessions_corr[s] for s in sessions_sorted]

    # Linear regression: y = slope * x + intercept, x = session index 0..N
    n = len(counts)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(counts) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, counts))
    den = sum((x - mean_x) ** 2 for x in xs) or 1.0
    slope = num / den

    print("Corrections per session:")
    print(f"  Sessions: {n}")
    print(f"  Total corrections: {sum(counts)}")
    print(f"  Mean: {mean_y:.1f}/session")
    if n >= 3:
        print(f"  Trend slope: {slope:+.3f} corrections/session")
        if slope < -0.05:
            print("  Verdict: CONVERGING (brain is learning — fewer corrections over time)")
        elif slope > 0.05:
            print("  Verdict: DIVERGING (corrections rising — brain may need tuning)")
        else:
            print("  Verdict: STABLE (flat trend)")
    else:
        print("  Trend: need >=3 sessions to estimate")

    # Rule application rate
    total_apps = sum(rule_apps_by_session.values())
    print()
    print(f"Rule applications: {total_apps} in window")
    if total_apps == 0 and sum(counts) > 5:
        print(
            "  WARNING: lots of corrections but zero rule applications — "
            "rules may not be reaching session-start injection. "
            "Run `gradata doctor` to debug."
        )

    # Top applied rules — group LESSON_APPLIED by lesson description
    app_rows = cur.execute(
        """
        SELECT data_json
          FROM events
         WHERE type='LESSON_APPLIED' AND ts >= ?
        """,
        (cutoff_iso,),
    ).fetchall()
    app_counter: Counter[str] = Counter()
    for (data_json,) in app_rows:
        try:
            d = json.loads(data_json or "{}")
            desc = (d.get("lesson_description") or d.get("description") or "")[:60]
            if desc:
                app_counter[desc] += 1
        except (ValueError, TypeError):
            continue
    if app_counter:
        print()
        print(f"Top {min(5, len(app_counter))} most-applied rules:")
        for desc, n_apps in app_counter.most_common(5):
            print(f"  {n_apps:4}  {desc}")

    # Failures
    fail_rows = cur.execute(
        """
        SELECT data_json
          FROM events
         WHERE type='RULE_FAILURE' AND ts >= ?
        """,
        (cutoff_iso,),
    ).fetchall()
    fail_counter: Counter[str] = Counter()
    for (data_json,) in fail_rows:
        try:
            d = json.loads(data_json or "{}")
            desc = (d.get("rule_description") or d.get("description") or "")[:60]
            if desc:
                fail_counter[desc] += 1
        except (ValueError, TypeError):
            continue
    if fail_counter:
        print()
        print(f"Top {min(5, len(fail_counter))} most-failed rules (consider tune/forget):")
        for desc, n_fails in fail_counter.most_common(5):
            print(f"  {n_fails:4}  {desc}")

    con.close()

    # Exit code = CI signal
    if n >= 3 and slope < -0.05:
        sys.exit(0)
    if n < 3:
        sys.exit(0)  # not enough data — don't fail CI
    if slope > 0.05:
        sys.exit(1)
    sys.exit(0)


def cmd_forget(args):
    """Undo one or more lessons from the brain.

    Selector syntax (passed as positional ``what`` arg):
      - ``last``           — undo most recent active lesson
      - ``last N``         — undo last N active lessons (e.g. ``last 3``)
      - ``all TONE``       — undo every active lesson in a category
      - ``<description>``  — fuzzy-match a single lesson by description

    By default the command prints matched lessons and asks for confirmation
    before applying. Pass ``--yes`` to skip the prompt (for scripts).

    The forget is a soft cancel: lessons are flipped to KILLED state, a
    LESSON_CHANGE event is emitted (so the sync pipeline replays it), and
    the rule cache is invalidated so the next ``apply_brain_rules()`` call
    reflects the change. No event is hard-deleted.
    """
    brain = _get_brain(args)
    what = (args.what or "last").strip()
    skip_confirm = bool(getattr(args, "yes", False))

    # Preview pass — peek at what the matcher would touch so we can show
    # the user before applying. We re-use brain.forget() with a tiny dance:
    # the heavy lifting is in Brain.forget; here we just want a confirm step.
    try:
        from gradata._types import LessonState
        from gradata.enhancements.self_improvement import parse_lessons
    except ImportError:
        print("Error: enhancements module not available — cannot forget lessons")
        sys.exit(1)

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        print("No lessons file found — nothing to forget.")
        sys.exit(0)

    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    active = [
        (i, l)
        for i, l in enumerate(lessons)
        if l.state in (LessonState.INSTINCT, LessonState.PATTERN, LessonState.RULE)
    ]
    if not active:
        print("No active lessons — nothing to forget.")
        sys.exit(0)

    wl = what.lower()
    preview: list = []
    if wl == "last" or wl.startswith("last "):
        parts = wl.split()
        n = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1
        preview = [l for _, l in active[-n:]]
    elif wl.startswith("all "):
        cat = what[4:].strip()
        preview = [l for _, l in active if l.category.upper() == cat.upper()]
    else:
        # Fuzzy single-target — let rollback's matcher decide
        matches = [l for _, l in active if what.lower() in (l.description or "").lower()]
        if not matches:
            print(f"No active lessons match: {what!r}")
            sys.exit(1)
        preview = matches[:1]

    if not preview:
        print(f"No matches for: {what!r}")
        sys.exit(1)

    print(f"Will forget {len(preview)} lesson{'s' if len(preview) != 1 else ''}:")
    for l in preview:
        desc = (l.description or "")[:80]
        print(f"  [{l.category:10}] {l.state.value:8} conf={l.confidence:.2f}  {desc}")

    if not skip_confirm:
        try:
            ans = input("\nProceed? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes"):
            print("Cancelled — no lessons forgotten.")
            sys.exit(0)

    # Delegate the actual work to Brain.forget — same semantics as the
    # public Python API.
    result = brain.forget(what)
    if isinstance(result, dict) and result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    items = result if isinstance(result, list) else [result]
    rolled_back = [r for r in items if r.get("rolled_back")]
    print(f"\nForgotten: {len(rolled_back)} lesson{'s' if len(rolled_back) != 1 else ''}.")
    if rolled_back:
        print("(LESSON_CHANGE events emitted — sync pipeline will replay.)")


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


def cmd_tune(args):
    """Tune a prompt file with Agent-Lightning APO and Gradata corrections."""
    from gradata.tuning.agent_lightning.runner import run_apo_tune

    prompt_path = Path(args.prompt_file)
    prompt = prompt_path.read_text(encoding="utf-8")
    result = run_apo_tune(
        _resolve_brain_root(args),
        prompt_template=prompt,
        rounds=args.rounds,
        beam_width=args.beam,
        branch_factor=args.branch,
        openai_api_base=args.openai_api_base,
    )
    optimized = str(result["optimized_prompt"])

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(optimized, encoding="utf-8")
        print(f"optimized prompt written to {out_path}")
    else:
        print(optimized)

    print(
        "baseline={baseline:.3f} optimized={optimized:.3f} rounds={rounds}".format(
            baseline=float(result.get("baseline_score", 0.0)),
            optimized=float(result.get("optimized_score", 0.0)),
            rounds=int(result.get("rounds_completed", 0)),
        )
    )


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
                if p.get("draft_text"):
                    print(f"    Draft:  {p['draft_text'][:80]}...")
                if p.get("final_text"):
                    print(f"    Final:  {p['final_text'][:80]}...")
                print()
            print("  gradata review --approve ID   Accept a lesson")
            print("  gradata review --reject ID    Reject a lesson")


def cmd_convergence(args):
    """Show corrections-per-session convergence as an ASCII chart."""
    brain = _get_brain(args)
    data = brain.convergence()

    sessions = data.get("sessions", [])
    counts = data.get("corrections_per_session", [])
    trend = data.get("trend", "insufficient_data")

    if not sessions:
        print("No session data yet. Make some corrections first.")
        return

    # ASCII bar chart
    max_count = max(counts) if counts else 1
    chart_width = 40
    print(f"\n  Corrections per Session (trend: {trend})")
    print(f"  {'─' * (chart_width + 15)}")

    for _i, (s, c) in enumerate(zip(sessions, counts, strict=False)):
        bar_len = int((c / max_count) * chart_width) if max_count > 0 else 0
        bar = "█" * bar_len
        print(f"  S{s:<4} │{bar} {c}")

    print(f"  {'─' * (chart_width + 15)}")
    print(
        f"  Total: {data.get('total_corrections', 0)} corrections across {data.get('total_sessions', 0)} sessions"
    )
    print(f"  Trend: {trend} (p={data.get('p_value', 1.0):.3f})")

    # Category breakdown
    by_cat = data.get("by_category", {})
    if by_cat:
        print("\n  By category:")
        for cat, info in sorted(by_cat.items()):
            cat_trend = info.get("trend", "?")
            cat_total = sum(info.get("corrections_per_session", []))
            print(f"    {cat:<20} {cat_total:>3} corrections  ({cat_trend})")
    print()


def cmd_demo(args):
    """Run the deterministic product demo."""
    from gradata._demo import run_demo

    run_demo(scenario=getattr(args, "scenario", "sdr"))


def _resolve_brain_root(args):
    """Figure out where brain lives using the same precedence as _get_brain."""
    brain_dir = getattr(args, "brain_dir", None)
    if brain_dir:
        return Path(brain_dir)
    brain = getattr(args, "brain", None)
    if brain:
        return Path(brain)
    override = env_str("BRAIN_DIR") or env_str("GRADATA_BRAIN")
    if override:
        return Path(override)
    return Path.cwd()


def cmd_config(args) -> None:
    """Manage brain-local Gradata configuration."""
    subcmd = getattr(args, "config_cmd", None)
    if subcmd != "set-llm":
        print("usage: gradata config set-llm {cli|api}")
        return

    brain_root = _resolve_brain_root(args)
    brain_root.mkdir(parents=True, exist_ok=True)
    config_path = brain_root / "brain-config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    mode = args.llm_mode
    if mode == "cli":
        data["llm_mode"] = "cli"
        data.pop("llm_vendor", None)
        data.pop("llm_api_key", None)
        data.pop("llm_model", None)
        config_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"LLM provider set to cli in {config_path}")
        return

    vendor = args.vendor
    if not vendor:
        print("error: --vendor is required for api mode", file=sys.stderr)
        sys.exit(2)
    key = args.key or _env_key_for_vendor(vendor)
    if not key:
        env_name = _env_name_for_vendor(vendor)
        print(f"error: --key or {env_name} is required for {vendor}", file=sys.stderr)
        sys.exit(2)

    data["llm_mode"] = "api"
    data["llm_vendor"] = vendor
    data["llm_api_key"] = key
    if args.model:
        data["llm_model"] = args.model
    else:
        data.pop("llm_model", None)
    config_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"LLM provider set to api/{vendor} in {config_path}")


def _env_name_for_vendor(vendor: str) -> str:
    return {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }[vendor]


def _env_key_for_vendor(vendor: str) -> str:
    import os

    return os.environ.get(_env_name_for_vendor(vendor), "")


def cmd_rule_add(args):
    """Fast-track a user-declared rule. Writes at RULE tier conf=1.0, tries to install a hook."""
    from gradata.enhancements import rule_to_hook

    text = " ".join(args.text).strip() if isinstance(args.text, list) else str(args.text).strip()
    if not text:
        print("error: rule text required", file=sys.stderr)
        return

    # Classify first to see if a hook is possible
    candidate = rule_to_hook.classify_rule(text, confidence=1.0)

    # Best-effort brain handle for event logging + add_rule API.  A user
    # running `gradata rule add` without an initialized brain should still
    # succeed; try_generate treats brain=None as "skip logging".
    brain = None
    try:
        brain = _get_brain(args)
    except Exception:
        brain = None

    result = rule_to_hook.try_generate(candidate, brain=brain, source="user_declared")

    # Persist to lessons.md via the canonical parse/format pipeline — the
    # same code path graduation uses, so any future lesson-schema change
    # automatically propagates here. Prefix description with [hooked]
    # marker if a hook was installed, so `gradata rule list` can show
    # hook status.
    if candidate.enforcement == rule_to_hook.EnforcementType.HOOK:
        category = candidate.determinism.value.upper()
    else:
        category = "USER"
    description = f"[hooked] {text}" if result.installed else text

    # Resolve the brain root the user intends (respects GRADATA_BRAIN env
    # + --brain-dir). Do NOT use _get_brain() here — that falls back to
    # CWD which would write to the wrong brain when running from a
    # project that happens to contain brain files.
    brain_root = _resolve_brain_root(args)
    brain_root.mkdir(parents=True, exist_ok=True)

    # Route through Brain.add_rule — the canonical parse/format pipeline.
    # Brain() works whether or not system.db exists (run_migrations no-ops
    # on a missing db), so we don't need a second hand-rolled write path.
    from gradata import Brain as _Brain

    add_result = _Brain(brain_root).add_rule(
        description=description,
        category=category,
        state="RULE",
        confidence=1.0,
    )
    if not add_result.get("added"):
        reason = add_result.get("reason", "unknown")
        print(f"error: failed to add rule: {reason}", file=sys.stderr)
        sys.exit(1)

    if result.installed:
        print(f"rule graduated to hook: installed at {result.hook_path}")
    else:
        print(f"rule added as soft injection ({result.reason})")


# Canonical starter rules — validated by the viral "7-line CLAUDE.md" carousel
# (yashserai19/TECHBITS). Seeded at RULE tier so they inject immediately, no
# correction loop required. Users still get learned rules on top.
_SEVEN_STARTER_RULES: list[tuple[str, str]] = [
    ("PATTERN", "Follow existing patterns before introducing new abstractions"),
    ("CODE", "Keep diffs small and focused"),
    ("PROCESS", "Run the smallest relevant test or lint after each change"),
    ("TRUTH", "State clearly when a command cannot be run — never pretend it ran"),
    ("PROCESS", "State assumptions before implementing"),
    ("PROCESS", "Update docs, tests, and types when behavior changes"),
    ("SECURITY", "Never expose secrets — no keys, tokens, or credentials in code or output"),
]


def cmd_seed(args):
    """Pre-populate a brain with high-confidence starter rules.

    Gives new brains instant value on Day 0 before the correction loop has fired.
    Currently supports --7-lines (Claude Code 7-line CLAUDE.md starter).
    """
    from gradata import Brain as _Brain

    brain_root = _resolve_brain_root(args)
    brain_root.mkdir(parents=True, exist_ok=True)
    brain = _Brain(brain_root)

    if getattr(args, "seven_lines", False):
        rules = _SEVEN_STARTER_RULES
        label = "7-line CLAUDE.md starter"
    else:
        print("error: pick a seed set (e.g. --7-lines)", file=sys.stderr)
        sys.exit(2)

    added = 0
    skipped = 0
    for category, text in rules:
        result = brain.add_rule(
            description=text,
            category=category,
            state="RULE",
            confidence=1.0,
        )
        if result.get("added"):
            added += 1
        else:
            skipped += 1

    print(f"seeded {label}: {added} added, {skipped} already present")


def _mask_credential(value: str) -> str:
    """Return a masked representation of a credential string."""
    if not value:
        return "(none)"
    if len(value) <= 10:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def cmd_cloud(args):
    """Dispatcher for `gradata cloud <subcommand>`."""
    from gradata.cloud import _credentials as _creds
    from gradata.cloud.sync import load_config, save_config

    subcmd = getattr(args, "cloud_cmd", None)

    # Use the same resolution precedence as every other CLI command
    # (env GRADATA_BRAIN > --brain-dir > cwd) so `gradata cloud ...` and,
    # say, `gradata export` always target the same brain. The older
    # ``_resolve_brain_root`` helper defaulted to a relative ``./brain``
    # which diverged from ``_get_brain`` and caused cloud config to land
    # in a different directory than the rest of the CLI operated on.
    brain_root = Path(
        env_str("GRADATA_BRAIN") or getattr(args, "brain_dir", None) or Path.cwd()
    ).resolve()
    # Only create the brain dir for write-side subcommands. ``status``
    # and ``disconnect`` should be safe to run without side-effecting the
    # filesystem of a nonexistent target.
    if subcmd in ("enable", "rotate-key", "sync-pull"):
        brain_root.mkdir(parents=True, exist_ok=True)

    if subcmd == "enable":
        cred = args.key.strip()
        if not cred.startswith(_creds.KEY_PREFIX):
            print(
                f"Warning: credential does not begin with {_creds.KEY_PREFIX!r}. "
                "Proceeding anyway — verify this is a live cloud key."
            )
        path = _creds.write_to_keyfile(cred)
        cfg = load_config(brain_root)
        cfg.sync_enabled = True
        scope = getattr(args, "scope", "") or ""
        cfg.key_scope = scope
        save_config(brain_root, cfg)
        print(f"Cloud sync enabled. Credential stored at {path}.")
        if scope:
            print(f"Scope: {scope}")
        return

    if subcmd == "rotate-key":
        new_cred = args.key.strip()
        if not new_cred.startswith(_creds.KEY_PREFIX):
            print(
                f"Warning: credential does not begin with {_creds.KEY_PREFIX!r}. Rotating anyway."
            )
        path = _creds.write_to_keyfile(new_cred)
        print(f"Rotating cloud credential. New value stored at {path}.")
        return

    if subcmd == "status":
        cfg = load_config(brain_root)
        cred = _creds.resolve_credential()
        print(f"sync_enabled: {cfg.sync_enabled}")
        print(f"endpoint:     {_creds.resolve_endpoint(fallback=cfg.api_base)}")
        print(f"credential:   {_mask_credential(cred)}")
        if cfg.key_scope:
            print(f"scope:        {cfg.key_scope}")
        if cfg.last_sync_at:
            print(f"last_sync_at: {cfg.last_sync_at}")
        return

    if subcmd == "disconnect":
        removed = _creds.delete_keyfile()
        cfg = load_config(brain_root)
        cfg.sync_enabled = False
        save_config(brain_root, cfg)
        if removed:
            print("Cloud credential removed. Sync disabled.")
        else:
            print("no keyfile to remove. Sync disabled.")
        return

    if subcmd == "sync-pull":
        from gradata.cloud.pull import pull_events

        apply_flag = bool(getattr(args, "apply", False))
        rebuild_from = getattr(args, "rebuild_from", None) or None
        limit = int(getattr(args, "limit", 500) or 500)

        result = pull_events(
            brain_root,
            apply=apply_flag,
            rebuild_from=rebuild_from,
            limit=limit,
        )
        status = result.get("status")
        print(f"status:             {status}")
        if reason := result.get("reason"):
            print(f"reason:             {reason}")
            return
        print(f"events_pulled:      {result.get('events_pulled', 0)}")
        print(f"pages_fetched:      {result.get('pages_fetched', 0)}")
        print(f"rules_materialized: {result.get('rules_materialized', 0)}")
        print(f"conflicts:          {result.get('conflicts', 0)}")
        if (th := result.get("conflict_threshold")) is not None:
            print(f"threshold:          {th}")
        print(f"applied:            {result.get('applied', False)}")
        if not apply_flag and result.get("rules_materialized"):
            print("dry-run — re-run with --apply to merge into lessons.md")
        return

    print("usage: gradata cloud {enable|rotate-key|status|disconnect|sync-pull}")


def cmd_sync(args):
    """Run local-to-cloud event sync."""
    from gradata.cloud import _credentials as _creds
    from gradata.cloud.client import CloudClient
    from gradata.cloud.sync import load_config, save_config

    brain_root = Path(
        env_str("GRADATA_BRAIN") or getattr(args, "brain_dir", None) or Path.cwd()
    ).resolve()
    if not getattr(args, "full", False):
        print("usage: gradata sync --full")
        return

    cfg = load_config(brain_root)
    cfg.sync_mode = "full"
    save_config(brain_root, cfg)

    credential = _creds.resolve_credential(fallback=cfg.token)
    if not credential:
        print("error: no cloud credential found. Run `gradata cloud enable --key ...` first.")
        sys.exit(2)
    endpoint = _creds.resolve_endpoint(fallback=cfg.api_base) or None
    cloud = CloudClient(brain_dir=brain_root, api_key=credential, endpoint=endpoint)
    if not cloud.connect():
        print("error: cloud connection failed")
        sys.exit(1)
    ingested = cloud.sync()
    print("sync_mode: full")
    print(f"events_synced: {ingested}")


def cmd_mine(args):
    """Backfill brain from Claude Code transcript archive (~/.claude/projects)."""
    from gradata._mine_transcripts import run_mine

    run_mine(
        brain_root=_resolve_brain_root(args),
        projects_root=Path(args.projects_root) if args.projects_root else None,
        project=args.project,
        commit=args.commit,
        dry_run=args.dry_run,
    )


def cmd_rule_list(args):
    """List RULE-tier lessons and their hook status."""
    import os
    import re as _re

    from gradata.enhancements.rule_to_hook import _slug

    brain_root = _resolve_brain_root(args)
    lessons_file = brain_root / "lessons.md"

    # Parse RULE-tier entries WITH [hooked] marker preserved
    rules: list[tuple[str, str, bool]] = []  # (category, description, hooked_marker_in_lessons)
    if lessons_file.exists():
        # Accept both modern layout (marker inside description) and the legacy
        # "[RULE:conf] [hooked] CATEGORY: desc" layout where the marker appears
        # between the state bracket and the category.
        lesson_re = _re.compile(r"^\[[\d-]+\]\s+\[RULE:[\d.]+\]\s+(?:\[hooked\]\s+)?(\w+):\s+(.+)$")
        for line in lessons_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            # Legacy marker position: remember it, then strip for regex.
            legacy_marker = bool(_re.search(r"\[RULE:[\d.]+\]\s+\[hooked\]\s+", stripped))
            m = lesson_re.match(stripped)
            if not m:
                continue
            category = m.group(1)
            desc = m.group(2).strip()
            modern_marker = desc.startswith("[hooked] ")
            clean_desc = desc[len("[hooked] ") :] if modern_marker else desc
            rules.append((category, clean_desc, modern_marker or legacy_marker))

    # Discover installed hook files (pre + post)
    pre_dir = Path(os.environ.get("GRADATA_HOOK_ROOT") or ".claude/hooks/pre-tool/generated")
    post_dir = Path(os.environ.get("GRADATA_HOOK_ROOT_POST") or ".claude/hooks/post-tool/generated")

    installed_files: dict[str, Path] = {}  # slug (file stem) -> path
    for d in (pre_dir, post_dir):
        if d.exists():
            for js in d.glob("*.js"):
                installed_files[js.stem] = js

    if not rules and not installed_files:
        print("No RULE-tier rules or installed hooks.")
        return

    print("RULE-tier lessons")
    print("-" * 17)

    hooked_count = 0
    matched_slugs: set[str] = set()
    for category, desc, marker in rules:
        slug = _slug(desc)
        file_exists = slug in installed_files
        if marker and file_exists:
            tag = "[hooked]"
            hooked_count += 1
            matched_slugs.add(slug)
        elif marker and not file_exists:
            tag = "[STALE] "
        else:
            tag = "        "
        print(f"{tag}  {category:<18} {desc}")

    orphan_slugs = [s for s in installed_files if s not in matched_slugs]

    print()
    print("Hook files installed:")
    for _slug_key, path in sorted(installed_files.items()):
        print(f"  {path}")

    if orphan_slugs:
        print()
        print("Orphan hook files (no matching lesson):")
        for slug in sorted(orphan_slugs):
            print(f"  [ORPHAN] {installed_files[slug]}")

    print()
    print(f"{hooked_count} hooked / {len(rules)} total rules")


def cmd_rule_remove(args):
    """Remove a graduated hook: delete the .js file and unmark (or purge) its lesson."""
    import os
    import re as _re

    # Reuse the canonical slug impl — single source of truth with cmd_rule_list
    # and the graduation pipeline.
    from gradata.enhancements.rule_to_hook import _slug

    slug = args.slug.strip()
    if not slug:
        print("error: slug required", file=sys.stderr)
        return

    brain_root = _resolve_brain_root(args)
    lessons_file = brain_root / "lessons.md"

    # 1. Delete hook file from whichever generated dir holds it
    pre_dir = Path(os.environ.get("GRADATA_HOOK_ROOT") or ".claude/hooks/pre-tool/generated")
    post_dir = Path(os.environ.get("GRADATA_HOOK_ROOT_POST") or ".claude/hooks/post-tool/generated")

    removed_file = None
    for d in (pre_dir, post_dir):
        candidate = d / f"{slug}.js"
        if candidate.exists():
            candidate.unlink()
            removed_file = candidate
            break

    # 2. Find matching lesson by slug → description
    # Also clear `metadata.how_enforced = "hooked"` from any structured
    # Metadata JSON line attached to this lesson, so the next graduation
    # pass treats the rule as ordinary prompt injection again.
    touched_lesson = False
    if lessons_file.exists():
        import json as _json_meta

        lines = lessons_file.read_text(encoding="utf-8").splitlines()
        out_lines: list[str] = []
        # Accept optional legacy "[hooked]" token between the state bracket
        # and the category (normalised out of the prefix so reformatted lines
        # carry the marker only in the description).
        lesson_re = _re.compile(
            r"^(\[[\d-]+\]\s+\[RULE:[\d.]+\])\s+(?:\[hooked\]\s+)?(\w+):\s+(.+)$"
        )
        # When purging, skip the lesson's trailing metadata block (indented
        # lines) so we don't leave orphans. When unmarking, we process each
        # indented line normally but rewrite the Metadata JSON.
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            m = lesson_re.match(stripped)
            if not m:
                out_lines.append(line)
                i += 1
                continue
            state_prefix = m.group(1)
            category = m.group(2)
            prefix = f"{state_prefix} {category}"
            desc = m.group(3).strip()
            legacy_marker = bool(_re.search(r"\[RULE:[\d.]+\]\s+\[hooked\]\s+", stripped))
            modern_marker = desc.startswith("[hooked] ")
            was_hooked = legacy_marker or modern_marker
            clean_desc = desc[len("[hooked] ") :] if modern_marker else desc
            match_this = _slug(clean_desc) == slug

            if not match_this:
                out_lines.append(line)
                i += 1
                continue

            if args.purge:
                # Drop header + all indented follow-on lines belonging to it.
                touched_lesson = True
                i += 1
                while i < len(lines) and lines[i].startswith("  "):
                    i += 1
                continue

            # Unmark path: rewrite the header (strip [hooked] prefix) and
            # rewrite any Metadata: JSON so how_enforced goes back to "injected".
            if was_hooked:
                touched_lesson = True
                out_lines.append(f"{prefix}: {clean_desc}")
            else:
                out_lines.append(line)
            i += 1
            while i < len(lines) and lines[i].startswith("  "):
                meta_line = lines[i]
                meta_stripped = meta_line.strip()
                if meta_stripped.startswith("Metadata:"):
                    payload = meta_stripped[len("Metadata:") :].strip()
                    try:
                        md = _json_meta.loads(payload)
                    except (ValueError, TypeError):
                        md = None
                    if isinstance(md, dict) and md.get("how_enforced") == "hooked":
                        md["how_enforced"] = "injected"
                        touched_lesson = True
                        out_lines.append(f"  Metadata: {_json_meta.dumps(md)}")
                        i += 1
                        continue
                out_lines.append(meta_line)
                i += 1
        if touched_lesson:
            lessons_file.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    # Emit a RULE_PATCH_REVERTED event when a human explicitly demotes a
    # hook-enforced rule back to text injection (or purges it). The
    # empirical promotion gate consumes this signal so a recently-reverted
    # rule cannot immediately re-promote.
    if removed_file or touched_lesson:
        try:
            from gradata import _events
            from gradata.enhancements.rule_to_hook import (
                HOOK_DEMOTED,
                RULE_PATCH_REVERTED,
            )

            _events.emit(
                RULE_PATCH_REVERTED,
                "cli:rule-remove",
                {
                    "slug": slug,
                    "purge": bool(getattr(args, "purge", False)),
                    "hook_removed": bool(removed_file),
                    "lesson_touched": bool(touched_lesson),
                },
            )
            if removed_file:
                _events.emit(
                    HOOK_DEMOTED,
                    "cli:rule-remove",
                    {"slug": slug, "hook_path": str(removed_file)},
                )
        except Exception:
            pass  # Event emission is best-effort; CLI output still succeeds.

    if removed_file:
        print(f"Removed hook: {removed_file}")
    if touched_lesson and args.purge:
        print("Deleted lesson from lessons.md")
    elif touched_lesson:
        print("Unmarked lesson in lessons.md (rule kept as soft injection)")
    if not removed_file and not touched_lesson:
        print(f"nothing to remove for slug: {slug}")


def cmd_rule(args):
    """Dispatch `gradata rule <subcommand>`."""
    sub = getattr(args, "rule_cmd", None)
    if sub == "add":
        cmd_rule_add(args)
    elif sub == "list":
        cmd_rule_list(args)
    elif sub == "remove":
        cmd_rule_remove(args)
    else:
        print(f"error: unknown rule subcommand: {sub}", file=sys.stderr)


def cmd_skill_export(args):
    """Export graduated rules as an Anthropic Claude Skill folder.

    Produces ``<output-dir>/<slug>/SKILL.md`` ready to drop into
    ``.claude/skills/`` or any Skills-aware harness.
    """
    from gradata import Brain
    from gradata.enhancements.skill_export import export_skill, write_skill

    brain_root = _resolve_brain_root(args)
    lessons_path: Path | None = None
    try:
        brain = Brain(brain_root)
        lessons_path = brain._find_lessons_path()
    except Exception:
        lessons_path = None

    name = args.name.strip()
    if not name:
        print("error: skill name required", file=sys.stderr)
        return

    output_dir = getattr(args, "output_dir", None)
    if output_dir:
        skill_md = write_skill(
            brain_root,
            name=name,
            output_dir=Path(output_dir),
            description=getattr(args, "description", None),
            category=getattr(args, "category", None),
            include_meta=not getattr(args, "no_meta", False),
            lessons_path=lessons_path,
        )
        print(f"Wrote skill to {skill_md}")
        return

    text = export_skill(
        brain_root,
        name=name,
        description=getattr(args, "description", None),
        category=getattr(args, "category", None),
        include_meta=not getattr(args, "no_meta", False),
        lessons_path=lessons_path,
    )
    print(text, end="")


def cmd_skill(args):
    """Dispatch `gradata skill <subcommand>`."""
    sub = getattr(args, "skill_cmd", None)
    if sub == "export":
        cmd_skill_export(args)
    else:
        print(f"error: unknown skill subcommand: {sub}", file=sys.stderr)


def cmd_hooks(args):
    """Manage Claude Code hook integration."""
    action = args.action
    if action == "install":
        from gradata.hooks.claude_code import install_hook

        project_dir = getattr(args, "project_dir", None)
        if project_dir:
            project_dir = Path(project_dir)
        elif getattr(args, "include_watchdog", False):
            # Watchdog needs an on-disk JS path; default to CWD when unset.
            project_dir = Path.cwd()

        install_hook(
            profile=getattr(args, "profile", "standard"),
            project_dir=project_dir,
            include_watchdog=getattr(args, "include_watchdog", False),
        )
    elif action == "uninstall":
        from gradata.hooks.claude_code import uninstall_hook

        uninstall_hook()
    elif action == "status":
        from gradata.hooks.claude_code import hook_status

        hook_status()


def cmd_project(args) -> None:
    """Project graduated rules into a Memory-tool-readable file tree.

    Default output is ``<brain>/memories/{voice,decisions,process,preferences,relations}.md``.
    The split is by ACTIVATION ENTROPY — voice rules fire on every draft and
    belong in the cached prefix, decision rubrics fire sparsely and want
    on-demand recall. Splitting by topic instead would defeat caching.
    """
    import json as _json

    from gradata._projector import project

    brain = _get_brain(args)
    output_dir = Path(args.output) if getattr(args, "output", None) else None
    result = project(brain, output_dir=output_dir, dry_run=getattr(args, "dry_run", False))

    if getattr(args, "json", False):
        print(
            _json.dumps(
                {
                    "memories_dir": str(result.memories_dir),
                    "files_written": list(result.files_written),
                    "files_unchanged": list(result.files_unchanged),
                    "rules_total": result.rules_total,
                    "rules_by_file": result.rules_by_file,
                    "digest": result.digest,
                    "dry_run": getattr(args, "dry_run", False),
                },
                indent=2,
            )
        )
        return

    print(f"projected → {result.memories_dir}")
    print(f"  rules: {result.rules_total} graduated")
    for name, count in result.rules_by_file.items():
        marker = "✓" if name in result.files_written else " "
        print(f"  {marker} {name:<16} {count:>4} rules")
    if result.files_unchanged:
        print(f"  ({len(result.files_unchanged)} files unchanged — caches stay hot)")
    print(f"  digest: {result.digest[:16]}…")


def main():
    parser = argparse.ArgumentParser(
        prog="gradata",
        description="Personal AI Brain SDK",
    )
    parser.add_argument(
        "--brain-dir", "-b", type=Path, help="Brain directory (default: current dir)"
    )
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Bootstrap a new brain")
    p_init.add_argument("path", type=Path, help="Directory to create brain in")
    p_init.add_argument("--name", default=None, help="Brain name (default: directory name)")
    p_init.add_argument("--domain", default=None, help="Brain domain (e.g., Sales, Engineering)")
    p_init.add_argument("--company", default=None, help="Company name (creates company.md)")
    p_init.add_argument(
        "--embedding",
        choices=["local", "gemini"],
        default=None,
        help="Embedding provider: local (default) or gemini",
    )
    p_init.add_argument(
        "--no-interactive", action="store_true", help="Skip interactive prompts, use defaults"
    )

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

    # status (umbrella health check: stats + daemon + cloud + convergence)
    sub.add_parser("status", help="Single-page brain/daemon/cloud summary")

    # audit
    p_audit = sub.add_parser("audit", help="Data flow audit")
    p_audit.add_argument("--json", action="store_true")

    # sync
    p_sync = sub.add_parser("sync", help="Sync local events to Gradata Cloud")
    p_sync.add_argument("--full", action="store_true", help="Backfill unsynced events/corrections")

    # recall
    p_recall = sub.add_parser("recall", help="Recall relevant brain rules as XML")
    p_recall.add_argument("situation", help="Current situation or task")
    p_recall.add_argument("--max-tokens", type=int, default=None)
    p_recall.add_argument("--ranker", choices=["hybrid", "flat", "tree_only"], default=None)
    p_recall.add_argument(
        "--include-all-sources",
        action="store_true",
        help="Debug: include meta-rules from non-injectable sources",
    )

    # export — marketplace archive OR platform-specific rule export
    p_export = sub.add_parser(
        "export",
        help="Export brain (marketplace archive, or graduated rules for cursor/agents/aider)",
    )
    p_export.add_argument("--mode", choices=["full", "no-prospects", "domain-only"], default="full")
    p_export.add_argument(
        "--target",
        choices=["cursor", "agents", "aider", "codex", "cline", "continue"],
        help="Emit graduated RULE-tier lessons in platform-specific format",
    )
    p_export.add_argument(
        "--output", "-o", help="Output file when using --target (default: stdout)"
    )

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
    p_doctor.add_argument("--cloud", action="store_true", help="Only run cloud checks")
    p_doctor.add_argument("--no-cloud", action="store_true", help="Skip cloud checks (offline)")
    p_doctor.add_argument(
        "--reconcile",
        action="store_true",
        help="Replay events.jsonl into system.db and report healed drift",
    )

    # install
    p_install = sub.add_parser("install", help="Install a brain archive or configure an agent")
    p_install.add_argument("archive", nargs="?", help="Path to brain archive (.zip)")
    p_install.add_argument("--target", type=str, help="Installation directory")
    p_install.add_argument("--dry-run", action="store_true")
    p_install.add_argument("--list", action="store_true", help="List installed brains")
    p_install.add_argument(
        "--agent",
        choices=["claude-code", "codex", "gemini", "cursor", "hermes", "opencode", "all"],
        help="Install Gradata recall hook/MCP config for an agent",
    )
    p_install.add_argument(
        "--brain",
        type=str,
        default=None,
        help="Brain directory for agent hook config (default: BRAIN_DIR or ./brain)",
    )
    p_install.add_argument(
        "--systemd",
        action="store_true",
        help=(
            "Install a systemd --user unit (~/.config/systemd/user/"
            "gradata-daemon.service) so the daemon survives shell exit "
            "and restarts on failure."
        ),
    )
    p_install.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for the daemon when used with --systemd (default: 8765)",
    )

    # uninstall — symmetrical reverse of `install --agent <host>` (GRA-1241)
    p_uninstall = sub.add_parser(
        "uninstall",
        help="Reverse `gradata install --agent <host>` — remove agent hook/MCP config",
    )
    p_uninstall.add_argument(
        "--agent",
        required=True,
        choices=["claude-code", "codex", "gemini", "cursor", "hermes", "opencode", "all"],
        help="Agent whose hook/MCP config to uninstall",
    )
    p_uninstall.add_argument(
        "--brain",
        type=str,
        default=None,
        help="Brain directory the hook points at (default: BRAIN_DIR or ./brain)",
    )

    # health
    p_health = sub.add_parser("health", help="Brain health report")
    p_health.add_argument("--json", action="store_true")

    # report
    p_report = sub.add_parser("report", help="Generate reports (csv, metrics, rules)")
    p_report.add_argument("type", choices=["csv", "metrics", "rules", "health"], help="Report type")
    p_report.add_argument("--window", type=int, default=20, help="Rolling window size")

    # watch — sidecar file watcher
    p_watch = sub.add_parser("watch", help="Watch a directory for AI-generated file edits")
    p_watch.add_argument(
        "--dir", required=True, type=str, help="Directory to watch for file changes"
    )
    p_watch.add_argument(
        "--brain", default=None, type=str, help="Path to brain directory (default: current dir)"
    )
    p_watch.add_argument(
        "--interval", type=float, default=5.0, help="Poll interval in seconds (default: 5)"
    )

    # diagnose — free correction pattern diagnostic (no graduation needed)
    sub.add_parser("diagnose", help="Analyze correction patterns (free diagnostic)")

    # review — human-in-the-loop approval
    p_review = sub.add_parser("review", help="Review pending lessons for approval")
    p_review.add_argument(
        "--approve", type=int, metavar="ID", help="Approve a pending lesson by ID"
    )
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

    # prove — statistical evidence the brain is improving
    p_prove = sub.add_parser(
        "prove",
        help="Statistical evidence the brain improves output quality (CI signal)",
    )
    p_prove.add_argument(
        "--window",
        choices=["7d", "30d", "90d", "all"],
        default="30d",
        help="Time window to analyse (default: 30d)",
    )

    # forget — undo lessons by selector
    p_forget = sub.add_parser("forget", help="Undo one or more lessons from the brain")
    p_forget.add_argument(
        "what",
        nargs="?",
        default="last",
        help=(
            "Selector: 'last', 'last N', 'all CATEGORY', or fuzzy description "
            "substring. Default: 'last'."
        ),
    )
    p_forget.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip interactive confirmation (for scripts)",
    )
    # tune — optimize a prompt against correction history
    p_tune = sub.add_parser("tune", help="Tune a prompt with Agent-Lightning APO")
    p_tune.add_argument("prompt_file", help="Prompt template file")
    p_tune.add_argument("--rounds", type=int, default=2, help="APO beam-search rounds")
    p_tune.add_argument("--beam", type=int, default=2, help="APO beam width")
    p_tune.add_argument("--branch", type=int, default=2, help="APO branch factor")
    p_tune.add_argument("--brain", type=str, default=None, help="Brain directory")
    p_tune.add_argument("--out", type=str, default=None, help="Optimized prompt output path")
    p_tune.add_argument(
        "--openai-api-base", type=str, default=None, help="OpenAI-compatible API base"
    )

    sub.add_parser("convergence", help="Show corrections-per-session convergence chart")

    p_demo = sub.add_parser("demo", help="Show a 60-second Gradata before/after demo")
    p_demo.add_argument(
        "--scenario",
        choices=["sdr", "coding"],
        default="sdr",
        help="Demo scenario to run (default: sdr)",
    )

    p_hooks = sub.add_parser("hooks", help="Manage Claude Code hook integration")
    p_hooks.add_argument("action", choices=["install", "uninstall", "status"], help="Hook action")
    p_hooks.add_argument(
        "--profile",
        choices=["minimal", "standard", "strict"],
        default="standard",
        help="Hook profile tier (default: standard)",
    )
    p_hooks.add_argument(
        "--project-dir",
        default=None,
        help="Project directory whose .claude/hooks/ should receive bundled JS hook assets",
    )
    p_hooks.add_argument(
        "--include-watchdog",
        action="store_true",
        help="Force-install the JS handoff watchdog hooks (#127) regardless of profile",
    )

    # config — brain-local SDK configuration
    p_config = sub.add_parser("config", help="Manage brain-local SDK config")
    config_sub = p_config.add_subparsers(dest="config_cmd")
    p_set_llm = config_sub.add_parser("set-llm", help="Configure LLM provider mode")
    p_set_llm.add_argument("llm_mode", choices=["cli", "api"], help="LLM mode")
    p_set_llm.add_argument(
        "--vendor",
        choices=["anthropic", "openai", "google"],
        help="API vendor for api mode",
    )
    p_set_llm.add_argument("--key", default=None, help="API key; defaults to vendor env var")
    p_set_llm.add_argument("--model", default=None, help="Optional model override")

    # seed — pre-populate brain with high-confidence starter rules
    p_seed = sub.add_parser(
        "seed",
        help="Seed brain with starter rules at RULE tier (instant Day-0 value)",
    )
    p_seed.add_argument(
        "--7-lines",
        dest="seven_lines",
        action="store_true",
        help="Seed the 7-line CLAUDE.md starter (patterns, diffs, tests, truth, assumptions, docs, secrets)",
    )

    # mine — backfill brain from Claude Code transcript archive
    p_mine = sub.add_parser(
        "mine",
        help="Backfill brain from ~/.claude/projects transcript archive",
    )
    p_mine.add_argument(
        "--commit",
        action="store_true",
        help="Append to live events.jsonl (default: shadow file only)",
    )
    p_mine.add_argument("--dry-run", action="store_true", help="Report counts only, write nothing")
    p_mine.add_argument("--project", default=None, help="Only scan one project dir (default: all)")
    p_mine.add_argument(
        "--projects-root",
        default=None,
        help="Override transcript root (default: ~/.claude/projects)",
    )

    # cloud — unified keyfile-backed cloud credential management
    p_cloud = sub.add_parser("cloud", help="Manage Gradata Cloud connection")
    cloud_sub = p_cloud.add_subparsers(dest="cloud_cmd")
    p_cloud_enable = cloud_sub.add_parser("enable", help="Enable cloud sync")
    p_cloud_enable.add_argument("--key", required=True, help="Cloud credential (gk_live_...)")
    p_cloud_enable.add_argument("--scope", default="", help="Optional scope tag")
    p_cloud_rotate = cloud_sub.add_parser("rotate-key", help="Rotate cloud credential")
    p_cloud_rotate.add_argument("--key", required=True, help="New cloud credential")
    cloud_sub.add_parser("status", help="Show cloud sync status")
    cloud_sub.add_parser("disconnect", help="Disconnect cloud sync")
    p_cloud_pull = cloud_sub.add_parser(
        "sync-pull", help="Pull pending cloud events (dry-run by default)"
    )
    p_cloud_pull.add_argument(
        "--apply",
        action="store_true",
        help="Merge materialized state into lessons.md and emit RULE_CONFLICT events",
    )
    p_cloud_pull.add_argument(
        "--rebuild-from",
        dest="rebuild_from",
        default=None,
        help="Force-resume from a specific watermark (bypasses persisted cursor)",
    )
    p_cloud_pull.add_argument(
        "--limit", type=int, default=500, help="Max events per page (1..1000)"
    )

    # skill — export graduated rules as an Anthropic Claude Skill folder
    p_skill = sub.add_parser("skill", help="Export brain as a Claude Skill folder")
    skill_sub = p_skill.add_subparsers(dest="skill_cmd", required=True)
    p_skill_export = skill_sub.add_parser(
        "export", help="Export graduated rules as a Claude Skill (SKILL.md)"
    )
    p_skill_export.add_argument("name", help="Skill name (becomes folder name + frontmatter name)")
    p_skill_export.add_argument(
        "--output-dir",
        "-o",
        help="Write Skill folder under this dir (default: print SKILL.md to stdout)",
    )
    p_skill_export.add_argument(
        "--description",
        help="Frontmatter description (default: auto-generated from rule categories)",
    )
    p_skill_export.add_argument("--category", help="Only include rules in this category")
    p_skill_export.add_argument(
        "--no-meta",
        action="store_true",
        help="Skip injectable meta-principles section",
    )

    # rule — user-declared rules (fast-track to RULE tier, try hook install)
    p_rule = sub.add_parser("rule", help="Manage user-declared rules")
    rule_sub = p_rule.add_subparsers(dest="rule_cmd", required=True)
    p_rule_add = rule_sub.add_parser("add", help="Declare a rule at RULE tier (fast-track)")
    p_rule_add.add_argument("text", nargs="+", help="Rule text")
    rule_sub.add_parser("list", help="List RULE-tier lessons and hook status")
    p_rule_remove = rule_sub.add_parser("remove", help="Remove a graduated hook by slug")
    p_rule_remove.add_argument("slug", help="Hook slug (from `gradata rule list`)")
    p_rule_remove.add_argument(
        "--purge",
        action="store_true",
        help="Also delete the lesson (default: keep as soft injection)",
    )

    # project — emit memories/ file tree for LLM Memory tool consumption
    p_project = sub.add_parser(
        "project",
        help="Project graduated rules to memories/ file tree (Anthropic Memory tool, etc.)",
    )
    p_project.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output dir (default: <brain>/memories/). Use for per-persona rentable namespaces.",
    )
    p_project.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and report what would be written without touching disk.",
    )
    p_project.add_argument(
        "--json",
        action="store_true",
        help="Emit ProjectionResult as JSON (digest, counts, files written).",
    )

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "search": cmd_search,
        "embed": cmd_embed,
        "manifest": cmd_manifest,
        "stats": cmd_stats,
        "status": cmd_status,
        "audit": cmd_audit,
        "sync": cmd_sync,
        "recall": cmd_recall,
        "export": cmd_export,
        "context": cmd_context,
        "validate": cmd_validate,
        "doctor": cmd_doctor,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "health": cmd_health,
        "report": cmd_report,
        "watch": cmd_watch,
        "correct": cmd_correct,
        "prove": cmd_prove,
        "forget": cmd_forget,
        "tune": cmd_tune,
        "review": cmd_review,
        "diagnose": cmd_diagnose,
    }

    commands["convergence"] = cmd_convergence
    commands["demo"] = cmd_demo
    commands["hooks"] = cmd_hooks
    commands["config"] = cmd_config
    commands["rule"] = cmd_rule
    commands["skill"] = cmd_skill
    commands["seed"] = cmd_seed
    commands["mine"] = cmd_mine
    commands["cloud"] = cmd_cloud
    commands["project"] = cmd_project

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
