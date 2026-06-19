"""Local install-success measurement for Gradata agent integrations.

Records every `gradata install --agent ...` attempt to a user-level JSONL file
so distribution experiments can separate successful installs, code failures, and
docs/setup friction across the supported AI coding CLIs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from gradata._config_paths import get_config_file
from gradata.hooks.adapters._base import InstallResult

MEASURED_INSTALL_AGENTS: Final[tuple[str, ...]] = (
    "claude-code",
    "codex",
    "hermes",
    "cursor",
)
INSTALL_MEASUREMENTS_FILE: Final[str] = "install_measurements.jsonl"
FailureKind = Literal["none", "code_failure", "docs_friction"]


def measurement_path() -> Path:
    return get_config_file(INSTALL_MEASUREMENTS_FILE)


def classify_result(result: InstallResult) -> FailureKind:
    if result.action != "failed":
        return "none"
    return "code_failure"


def append_measurement(
    result: InstallResult,
    *,
    brain_dir: Path,
    source: str = "gradata install --agent",
    failure_kind: FailureKind | None = None,
) -> dict[str, object]:
    status = "success" if result.action != "failed" else "failure"
    payload: dict[str, object] = {
        "ts": datetime.now(UTC).isoformat(),
        "source": source,
        "agent": result.agent,
        "status": status,
        "action": result.action,
        "failure_kind": failure_kind or classify_result(result),
        "config_path": str(result.config_path),
        "brain_dir": str(brain_dir),
        "message": result.message,
    }
    path = measurement_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def append_docs_friction(
    agent: str,
    *,
    config_path: Path,
    brain_dir: Path,
    message: str,
    source: str = "gradata install --agent all",
) -> dict[str, object]:
    return append_measurement(
        InstallResult(agent, config_path, "failed", message),
        brain_dir=brain_dir,
        source=source,
        failure_kind="docs_friction",
    )
