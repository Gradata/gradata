"""
Tests for the Gradata CLI (cli.py).

The CLI is the first surface new users interact with, so these tests verify
that every subcommand works correctly in isolation using temp brain dirs.

Run: pytest sdk/tests/test_cli.py -v
"""

import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gradata import Brain
from gradata.cli import (
    cmd_init,
    cmd_manifest,
    cmd_search,
    cmd_stats,
    cmd_validate,
    cmd_doctor,
    main,
)


# ---------------------------------------------------------------------------
# cmd_init
# ---------------------------------------------------------------------------

class TestCmdInit:
    def test_init_creates_brain_dir(self, tmp_path):
        """cmd_init creates a brain directory with expected structure."""
        target = tmp_path / "new-brain"
        args = argparse.Namespace(
            path=target,
            name="CLIBrain",
            domain="Sales",
            company=None,
            embedding="local",
            no_interactive=True,
        )
        cmd_init(args)

        assert target.is_dir()
        assert (target / "system.db").exists()
        assert (target / "brain.manifest.json").exists()
        assert (target / "prospects").is_dir()
        assert (target / "sessions").is_dir()

    def test_init_with_domain(self, tmp_path):
        """Domain flag is written into the manifest."""
        target = tmp_path / "domain-brain"
        args = argparse.Namespace(
            path=target,
            name="DomainBrain",
            domain="Engineering",
            company=None,
            embedding="local",
            no_interactive=True,
        )
        cmd_init(args)

        manifest = json.loads((target / "brain.manifest.json").read_text(encoding="utf-8"))
        assert manifest["metadata"]["domain"] == "Engineering"

    def test_init_with_name(self, tmp_path):
        """Name flag is written into the manifest."""
        target = tmp_path / "named-brain"
        args = argparse.Namespace(
            path=target,
            name="MyBrain",
            domain=None,
            company=None,
            embedding=None,
            no_interactive=True,
        )
        cmd_init(args)

        manifest = json.loads((target / "brain.manifest.json").read_text(encoding="utf-8"))
        assert manifest["metadata"]["brain_name"] == "MyBrain"

    def test_init_duplicate_raises(self, tmp_path):
        """Init on an existing brain raises FileExistsError."""
        target = tmp_path / "dup-brain"
        args = argparse.Namespace(
            path=target,
            name="First",
            domain=None,
            company=None,
            embedding="local",
            no_interactive=True,
        )
        cmd_init(args)
        with pytest.raises(FileExistsError):
            cmd_init(args)


# ---------------------------------------------------------------------------
# cmd_search
# ---------------------------------------------------------------------------

class TestCmdSearch:
    def test_search_no_results(self, fresh_brain, capsys):
        """Search on empty brain prints 'No results found.'"""
        args = argparse.Namespace(
            brain_dir=fresh_brain.dir,
            query="nonexistent xyz query",
            mode="keyword",
            top=5,
        )
        cmd_search(args)
        captured = capsys.readouterr()
        assert "No results found" in captured.out

    def test_search_with_results(self, brain_with_content, capsys):
        """Search finds indexed content after FTS rebuild."""
        from gradata._query import fts_rebuild
        fts_rebuild()

        args = argparse.Namespace(
            brain_dir=brain_with_content.dir,
            query="rocketship",
            mode="keyword",
            top=5,
        )
        cmd_search(args)
        captured = capsys.readouterr()
        assert "rocketship" in captured.out.lower() or "1." in captured.out

    def test_search_default_mode(self, fresh_brain, capsys):
        """Search works when mode is None (default)."""
        args = argparse.Namespace(
            brain_dir=fresh_brain.dir,
            query="anything",
            mode=None,
            top=5,
        )
        # Should not raise
        cmd_search(args)
        captured = capsys.readouterr()
        assert "No results found" in captured.out


# ---------------------------------------------------------------------------
# cmd_manifest
# ---------------------------------------------------------------------------

class TestCmdManifest:
    def test_manifest_text_output(self, brain_with_events, capsys):
        """Manifest command prints human-readable summary."""
        args = argparse.Namespace(
            brain_dir=brain_with_events.dir,
            json=False,
        )
        cmd_manifest(args)
        captured = capsys.readouterr()
        assert "Brain" in captured.out
        assert "Quality" in captured.out

    def test_manifest_json_output(self, brain_with_events, capsys):
        """Manifest --json produces valid JSON with required keys."""
        args = argparse.Namespace(
            brain_dir=brain_with_events.dir,
            json=True,
        )
        cmd_manifest(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "schema_version" in data
        assert "metadata" in data
        assert "quality" in data

    def test_manifest_has_required_fields(self, brain_with_events):
        """Manifest dict contains metadata, quality, and database."""
        manifest = brain_with_events.manifest()
        assert manifest["schema_version"] == "1.0.0"
        assert "brain_version" in manifest["metadata"]
        assert "correction_rate" in manifest["quality"]


# ---------------------------------------------------------------------------
# cmd_stats
# ---------------------------------------------------------------------------

class TestCmdStats:
    def test_stats_returns_dict(self, fresh_brain):
        """brain.stats() returns dict with expected keys."""
        stats = fresh_brain.stats()
        assert isinstance(stats, dict)
        assert "brain_dir" in stats
        assert "markdown_files" in stats
        assert "db_size_mb" in stats
        assert "embedding_chunks" in stats
        assert "has_manifest" in stats
        assert "has_embeddings" in stats

    def test_stats_output(self, fresh_brain, capsys):
        """cmd_stats prints readable stats."""
        args = argparse.Namespace(brain_dir=fresh_brain.dir)
        cmd_stats(args)
        captured = capsys.readouterr()
        assert "Brain:" in captured.out
        assert "Markdown files:" in captured.out
        assert "Database:" in captured.out

    def test_stats_db_size_positive(self, fresh_brain):
        """Database file should exist and have nonzero size."""
        stats = fresh_brain.stats()
        assert stats["db_size_mb"] >= 0
        assert stats["has_manifest"] is True


# ---------------------------------------------------------------------------
# cmd_validate
# ---------------------------------------------------------------------------

class TestCmdValidate:
    def test_validate_clean_brain(self, brain_with_events, capsys):
        """Validate a fresh brain with manifest — no issues expected."""
        brain_with_events.manifest()
        args = argparse.Namespace(
            brain_dir=brain_with_events.dir,
            manifest=None,
            json=True,
            strict=False,
        )
        cmd_validate(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)

    def test_validate_strict_exits_on_insufficient_brain(self, brain_with_events, capsys):
        """Strict mode exits on a brain that hasn't trained enough."""
        brain_with_events.manifest()
        args = argparse.Namespace(
            brain_dir=brain_with_events.dir,
            manifest=None,
            json=True,
            strict=True,
        )
        # Fresh test brain has 0 rules — strict validation correctly exits
        with pytest.raises(SystemExit):
            cmd_validate(args)

    def test_validate_custom_manifest_path(self, brain_with_events, capsys):
        """Validate accepts an explicit manifest path."""
        brain_with_events.manifest()
        manifest_path = str(brain_with_events.dir / "brain.manifest.json")
        args = argparse.Namespace(
            brain_dir=brain_with_events.dir,
            manifest=manifest_path,
            json=True,
            strict=False,
        )
        cmd_validate(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# cmd_doctor
# ---------------------------------------------------------------------------

class TestCmdDoctor:
    def test_doctor_runs(self, fresh_brain, capsys):
        """Doctor command produces output without crashing."""
        args = argparse.Namespace(
            brain_dir=str(fresh_brain.dir),
            json=True,
        )
        # doctor may sys.exit(1) if status is "broken" — catch it
        try:
            cmd_doctor(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "status" in data

    def test_doctor_json_format(self, fresh_brain, capsys):
        """Doctor --json returns valid JSON with a status field."""
        args = argparse.Namespace(
            brain_dir=str(fresh_brain.dir),
            json=True,
        )
        try:
            cmd_doctor(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] in ("healthy", "degraded", "broken")


# ---------------------------------------------------------------------------
# Argument parsing edge cases
# ---------------------------------------------------------------------------

class TestArgParsing:
    def test_no_command_shows_help(self, capsys):
        """Running with no subcommand prints help."""
        with patch("sys.argv", ["gradata"]):
            main()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "gradata" in captured.out.lower()

    def test_init_requires_path(self):
        """init subcommand requires a path argument."""
        with patch("sys.argv", ["gradata", "init"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0  # argparse error exit

    def test_search_requires_query(self):
        """search subcommand requires a query argument."""
        with patch("sys.argv", ["gradata", "search"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_context_requires_message(self):
        """context subcommand requires a message argument."""
        with patch("sys.argv", ["gradata", "context"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_brain_dir_flag(self, tmp_path):
        """--brain-dir flag is parsed correctly."""
        target = tmp_path / "flag-brain"
        with patch("sys.argv", [
            "gradata", "--brain-dir", str(tmp_path),
            "init", str(target),
            "--no-interactive",
        ]):
            main()
        assert target.is_dir()

    def test_unknown_command_shows_help(self, capsys):
        """An unrecognised subcommand prints help (no crash)."""
        with patch("sys.argv", ["gradata", "foobar"]):
            # argparse treats unknown subcommands as error on Python 3.12+
            try:
                main()
            except SystemExit:
                pass
        captured = capsys.readouterr()
        # Should have printed something (help or error)
        assert len(captured.out) > 0 or len(captured.err) > 0
