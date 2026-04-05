"""Security utilities for Gradata SDK."""

from __future__ import annotations

from gradata.security.score_obfuscation import (
    obfuscate_instruction,
    truncate_score,
    constant_time_pad,
)
from gradata.security.brain_salt import (
    generate_brain_salt,
    load_or_create_salt,
    salt_threshold,
)
from gradata.security.query_budget import QueryBudget
from gradata.security.manifest_signing import sign_manifest, verify_manifest
from gradata.security.correction_provenance import (
    create_provenance_record,
    verify_provenance,
)

__all__ = [
    "truncate_score",
    "obfuscate_instruction",
    "constant_time_pad",
    "generate_brain_salt",
    "load_or_create_salt",
    "salt_threshold",
    "QueryBudget",
    "sign_manifest",
    "verify_manifest",
    "create_provenance_record",
    "verify_provenance",
]
