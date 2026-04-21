"""Stop hook: run brain maintenance tasks at session end."""

from __future__ import annotations

import os
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "Stop",
    "profile": Profile.STRICT,
    "timeout": 20000,
}


def _rebuild_fts(brain_dir: str, ctx=None) -> None:
    """Rebuild FTS index from brain content files."""
    try:
        from gradata._query import fts_index

        brain_path = Path(brain_dir)

        # Index lessons.md
        lessons = brain_path / "lessons.md"
        if lessons.is_file():
            text = lessons.read_text(encoding="utf-8")
            fts_index("lessons.md", "markdown", text, ctx=ctx)

        # Index any .md files in brain root
        for md_file in brain_path.glob("*.md"):
            if md_file.name == "lessons.md":
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
                fts_index(md_file.name, "markdown", text, ctx=ctx)
            except Exception:
                continue
    except Exception:
        pass


def _generate_manifest(ctx=None) -> None:
    """Generate brain manifest for quality tracking."""
    try:
        from gradata._brain_manifest import generate_manifest, write_manifest

        manifest = generate_manifest(ctx=ctx)
        write_manifest(manifest, ctx=ctx)
    except Exception:
        pass


def main(data: dict) -> dict | None:
    # Opt-out kill switch: projects with a superset JS brain_maintain disable this
    # hook to avoid double FTS rebuild + manifest (~8-20s per Stop).
    if os.environ.get("GRADATA_BRAIN_MAINTAIN", "1") == "0":
        return None
    try:
        brain_dir = resolve_brain_dir()
        if not brain_dir:
            return None

        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)

        _rebuild_fts(brain_dir, ctx=ctx)
        _generate_manifest(ctx=ctx)
    except Exception:
        pass
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
