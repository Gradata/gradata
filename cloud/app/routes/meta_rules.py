"""GET /brains/{brain_id}/meta-rules — universal principles from 3+ lessons.

When the marketplace cross-brain sharing path is enabled (Phase 4), meta-rule
rows are compressed behavioral fingerprints and vulnerable to Carlini-style
membership-inference extraction.  The optional differential-privacy scaffold
below (``_load_dp_config`` + :func:`apply_dp_to_export_row`) perturbs numerical
fields and suppresses raw text fields before release.  It is OFF BY DEFAULT;
marketplace ops must explicitly set ``GRADATA_DP_ENABLED=true`` to turn it on.

References:
    - Dwork & Roth 2014: https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf
    - Abadi et al. 2016: https://arxiv.org/abs/1607.00133
"""

from __future__ import annotations

import copy
import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from app.auth import get_brain_for_request
from app.db import get_db

# SDK-side scaffold: DPConfig + Laplace-mechanism row transformer.
from gradata.enhancements.meta_rules_storage import (
    DPConfig,
    apply_dp_to_export_row,
)

_log = logging.getLogger(__name__)
_audit_log = logging.getLogger("gradata.audit.dp_export")

router = APIRouter()


def _load_dp_config() -> DPConfig:
    """Read DP settings from env.  All vars prefixed ``GRADATA_DP_``.

    Off by default — only flipping ``GRADATA_DP_ENABLED=true`` turns on
    noise injection.  Epsilon/clip defaults match the DPConfig dataclass
    (ε=1.0, clip_norm=1.0).  Note: a per-brain ε-budget tracker is NOT
    yet implemented; see the COMPOSITION WARNING in meta_rules_storage.py.
    """
    enabled = os.environ.get("GRADATA_DP_ENABLED", "").lower() in {"1", "true", "yes"}
    try:
        epsilon = float(os.environ.get("GRADATA_DP_EPSILON", "1.0"))
    except ValueError:
        epsilon = 1.0
    try:
        clip_norm = float(os.environ.get("GRADATA_DP_CLIP_NORM", "1.0"))
    except ValueError:
        clip_norm = 1.0
    mechanism = os.environ.get("GRADATA_DP_MECHANISM", "laplace")
    return DPConfig(
        enabled=enabled,
        epsilon=epsilon,
        mechanism=mechanism,
        clip_norm=clip_norm,
    )


@router.get("/brains/{brain_id}/meta-rules")
async def list_meta_rules(
    brain: dict = Depends(get_brain_for_request),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List meta-rules for a brain.

    Returns the meta_rules table joined with source lesson counts. Does NOT
    return raw correction text — only synthesized principles (per privacy
    posture: raw corrections never leave the device).

    When ``GRADATA_DP_ENABLED=true``, each row is passed through
    :func:`apply_dp_to_export_row` before return: numerical fields get
    Laplace noise, raw text fields are suppressed, and an audit-log entry
    records the brain_id, epsilon, timestamp, and exported-row count.
    """
    db = get_db()
    rows = await db.select(
        "meta_rules",
        columns="id,brain_id,title,description,source_lesson_ids,created_at",
        filters={"brain_id": brain["id"]},
    )
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    page = rows[offset : offset + limit]

    dp_config = _load_dp_config()
    if dp_config.enabled:
        # Deep-copy so we never mutate the DB-layer cache / upstream objects.
        page = [apply_dp_to_export_row(copy.deepcopy(r), dp_config) for r in page]
        # Audit: record every DP-perturbed export so marketplace ops can
        # later reconstruct a per-brain ε-budget ledger (Dwork & Roth §3.5
        # basic composition).  Today we log; Phase 4 will persist + enforce.
        _audit_log.info(
            "dp_export",
            extra={
                "brain_id": brain["id"],
                "epsilon": dp_config.epsilon,
                "mechanism": dp_config.mechanism,
                "clip_norm": dp_config.clip_norm,
                "rows_exported": len(page),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    return page
