"""Stop hook: run brain maintenance tasks at session end."""
from __future__ import annotations

from pathlib import Path

from ._base import resolve_brain_dir, run_hook
from ._profiles import Profile

HOOK_META = {
    "event": "Stop",
    "profile": Profile.STRICT,
    "timeout": 20000,
}


def _generate_manifest(ctx=None) -> None:
    """Generate brain manifest for quality tracking."""
    try:
        from .._brain_manifest import generate_manifest, write_manifest
        manifest = generate_manifest(ctx=ctx)
        write_manifest(manifest, ctx=ctx)
    except Exception:
        pass


def main(data: dict) -> dict | None:
    try:
        brain_dir = resolve_brain_dir()
        if not brain_dir:
            return None

        from .._paths import BrainContext
        ctx = BrainContext.from_brain_dir(brain_dir)

        try:
            from .._query import fts_index
            _bp = Path(brain_dir)
            _lf = _bp / "lessons.md"
            if _lf.is_file():
                fts_index("lessons.md", "markdown", _lf.read_text(encoding="utf-8"), ctx=ctx)
            for _md in _bp.glob("*.md"):
                if _md.name == "lessons.md":
                    continue
                try:
                    fts_index(_md.name, "markdown", _md.read_text(encoding="utf-8"), ctx=ctx)
                except Exception:
                    continue
        except Exception:
            pass
        _generate_manifest(ctx=ctx)
    except Exception:
        pass
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
