"""Golden test for the documented top-level gradata API.

Locks the current public surface to prevent accidental SemVer-breaking
exports. Update EXPECTED_PUBLIC_SURFACE intentionally — every change here
is a public API change.
"""

from __future__ import annotations

import json
import subprocess
import sys

import gradata

# Locked as of PR3 (2026-05-02). Anything added/removed from gradata's
# top-level __all__ must update this set in the same commit.
EXPECTED_PUBLIC_SURFACE = {
    "Brain",
    "BrainContext",
    "BrainError",
    "BrainLockedError",
    "BrainNotConfiguredError",
    "BrainNotFoundError",
    "EmbeddingError",
    "EventPersistenceError",
    "ExportError",
    "GradataError",
    "Lesson",
    "LessonState",
    "Notification",
    "RuleTransferScope",
    "ScopedBrain",
    "TaxonomyError",
    "ValidationError",
    "__version__",
    "brain_context",
    "compute_learning_velocity",
    "format_lessons",
    "graduate",
    "onboard",
    "parse_lessons",
    "update_confidence",
}


def test_top_level_public_api_surface_is_locked() -> None:
    code = """
import json
import gradata
public_names = sorted(
    name for name in dir(gradata)
    if not name.startswith("_") or name == "__version__"
)
print(json.dumps(public_names))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )

    actual_surface = set(json.loads(result.stdout))
    # `dir(gradata)` includes module attributes that aren't in __all__
    # (e.g. submodule names re-exported during import). The contract we
    # lock is __all__: that's what `from gradata import *` and
    # documentation promise.
    assert set(gradata.__all__) == EXPECTED_PUBLIC_SURFACE, (
        f"gradata.__all__ drifted from locked surface.\n"
        f"  added: {set(gradata.__all__) - EXPECTED_PUBLIC_SURFACE}\n"
        f"  removed: {EXPECTED_PUBLIC_SURFACE - set(gradata.__all__)}"
    )
    # Soft check: every name in __all__ must actually resolve.
    missing = EXPECTED_PUBLIC_SURFACE - actual_surface
    assert missing == set(), f"__all__ promises names that don't resolve: {missing}"
