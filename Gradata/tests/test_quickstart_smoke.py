from __future__ import annotations

from pathlib import Path
from typing import cast

from scripts.smoke_quickstart import smoke


def test_offline_quickstart_smoke(tmp_path: Path) -> None:
    result = smoke(tmp_path)
    commands = cast("list[str]", result["commands"])

    assert result["database_created"] is True
    assert result["sessions_trained"] is not None
    assert any("gradata.cli init" in cmd for cmd in commands)
    assert any("gradata.cli --brain-dir" in cmd and " correct " in cmd for cmd in commands)
