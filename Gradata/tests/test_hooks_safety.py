"""Tests for safety hooks: secret_scan, config_protection, rule_enforcement."""

import os
from pathlib import Path
from unittest.mock import patch

from gradata.hooks.config_protection import main as protect_main
from gradata.hooks.rule_enforcement import main as enforce_main
from gradata.hooks.secret_scan import main as scan_main

# ── secret_scan tests ──


def test_secret_scan_blocks_openai_key():
    data = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "config.py",
            "content": "key = 'sk-abc123def456ghi789jkl012mno345pqr'",
        },
    }
    result = scan_main(data)
    assert result is not None
    assert result["decision"] == "block"
    assert "SECRET" in result["reason"]


def test_secret_scan_blocks_aws_key():
    data = {
        "tool_name": "Edit",
        "tool_input": {"new_string": "AKIAIOSFODNN7EXAMPLE"},
    }
    result = scan_main(data)
    assert result is not None
    assert result["decision"] == "block"


def test_secret_scan_allows_clean_code():
    data = {
        "tool_name": "Write",
        "tool_input": {"file_path": "main.py", "content": "print('hello world')"},
    }
    result = scan_main(data)
    assert result is None


def test_secret_scan_no_content():
    data = {"tool_name": "Write", "tool_input": {"file_path": "empty.py"}}
    result = scan_main(data)
    assert result is None


def test_secret_scan_blocks_private_key():
    data = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "key.pem",
            "content": "-----BEGIN RSA PRIVATE KEY-----\nfoo\n-----END RSA PRIVATE KEY-----",
        },
    }
    result = scan_main(data)
    assert result is not None
    assert result["decision"] == "block"


def test_secret_scan_blocks_db_connection():
    data = {
        "tool_name": "Write",
        "tool_input": {"file_path": "db.py", "content": "postgres://user:s3cret@db.host.com/mydb"},
    }
    result = scan_main(data)
    assert result is not None
    assert result["decision"] == "block"


# ── config_protection tests ──


def test_config_protection_blocks_eslint():
    data = {"tool_input": {"file_path": "/project/.eslintrc.json"}}
    result = protect_main(data)
    assert result is not None
    assert result["decision"] == "block"


def test_config_protection_blocks_ruff():
    data = {"tool_input": {"file_path": "/project/ruff.toml"}}
    result = protect_main(data)
    assert result is not None
    assert result["decision"] == "block"


def test_config_protection_allows_source_code():
    data = {"tool_input": {"file_path": "/project/src/main.py"}}
    result = protect_main(data)
    assert result is None


def test_config_protection_no_file_path():
    data = {"tool_input": {}}
    result = protect_main(data)
    assert result is None


# ── rule_enforcement tests ──


def test_rule_enforcement_injects_rules(tmp_path):
    lessons = tmp_path / "lessons.md"
    lessons.write_text(
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n"
        "[2026-04-01] [PATTERN:0.65] TONE: Use casual tone\n"
        "[2026-04-01] [RULE:0.95] CODE: Never hardcode secrets\n",
        encoding="utf-8",
    )
    with patch.dict(
        os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path), "GRADATA_RULE_ENFORCEMENT": "1"}
    ):
        result = enforce_main({})
    assert result is not None
    assert "ACTIVE RULES" in result["result"]
    assert "Always plan" in result["result"]
    assert "Never hardcode" in result["result"]
    # PATTERN should NOT be included (only RULE)
    assert "casual tone" not in result["result"]


def test_rule_enforcement_no_rules(tmp_path):
    lessons = tmp_path / "lessons.md"
    lessons.write_text("[2026-04-01] [INSTINCT:0.35] CODE: Add docstrings\n", encoding="utf-8")
    with patch.dict(
        os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path), "GRADATA_RULE_ENFORCEMENT": "1"}
    ):
        result = enforce_main({})
    assert result is None


def test_rule_enforcement_truncates_long_descriptions(tmp_path):
    lessons = tmp_path / "lessons.md"
    long_desc = "A" * 200
    lessons.write_text(f"[2026-04-01] [RULE:0.90] CODE: {long_desc}\n", encoding="utf-8")
    with patch.dict(
        os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path), "GRADATA_RULE_ENFORCEMENT": "1"}
    ):
        result = enforce_main({})
    assert result is not None
    assert "..." in result["result"]


def test_rule_enforcement_no_brain():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("GRADATA_BRAIN_DIR", None)
        os.environ.pop("BRAIN_DIR", None)
        # Mock Path.home to avoid finding a real brain
        with patch("gradata.hooks._base.Path") as MockPath:
            MockPath.home.return_value = Path("/nonexistent")
            result = enforce_main({})
    assert result is None
