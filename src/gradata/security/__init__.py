"""Security utilities for Gradata SDK."""

from __future__ import annotations

from gradata.security.brain_salt import (
    generate_brain_salt,
    load_or_create_salt,
    salt_threshold,
)
from gradata.security.correction_hash import (
    SOURCE_EXTERNAL_PASTE,
    SOURCE_UNKNOWN,
    SOURCE_USER_EDIT,
    build_provenance,
    classify_source_context,
    compute_correction_hash,
)
from gradata.security.correction_provenance import (
    create_provenance_record,
    verify_provenance,
)
from gradata.security.manifest_signing import sign_manifest, verify_manifest
from gradata.security.query_budget import QueryBudget
from gradata.security.score_obfuscation import (
    constant_time_pad,
    obfuscate_instruction,
    truncate_score,
)

__all__ = [
    "SOURCE_EXTERNAL_PASTE",
    "SOURCE_UNKNOWN",
    "SOURCE_USER_EDIT",
    "QueryBudget",
    "build_provenance",
    "classify_source_context",
    "compute_correction_hash",
    "constant_time_pad",
    "create_provenance_record",
    "generate_brain_salt",
    "load_or_create_salt",
    "obfuscate_instruction",
    "salt_threshold",
    "sign_manifest",
    "truncate_score",
    "verify_manifest",
    "verify_provenance",
]
