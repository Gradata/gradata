"""Operator (god-mode) admin endpoints.

All routes here are gated behind :func:`app.auth.require_operator`, which
enforces the ``@gradata.ai`` / ``@sprites.ai`` email allowlist. These power the
dashboard's /operator page (global KPIs, customer list, derived alerts).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_operator
from app.db import get_db
from app.models import AdminAlert, AdminCustomer, GlobalKpis

_log = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Plan -> monthly price (USD). Enterprise is custom/negotiated -> skipped in MRR.
# ---------------------------------------------------------------------------
_PLAN_MRR_USD: dict[str, float] = {
    "free": 0.0,
    "pro": 29.0,  # "cloud" tier in the public pricing — stored as "pro" in DB
    "team": 99.0,
    # "enterprise": custom -> excluded from automatic MRR
}

_HEALTHY_DAYS = 14
_AT_RISK_DAYS = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_ts(value: Any) -> datetime | None:
    """Parse an ISO timestamp string (or pass-through datetime) to aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        # Accept trailing Z + fractional seconds
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _classify_health(last_active: datetime | None, now: datetime) -> str:
    """healthy (<14d) | at-risk (14-30d) | churning (>30d or never)."""
    if last_active is None:
        return "churning"
    delta = now - last_active
    if delta <= timedelta(days=_HEALTHY_DAYS):
        return "healthy"
    if delta <= timedelta(days=_AT_RISK_DAYS):
        return "at-risk"
    return "churning"


def _plan_mrr(plan: str | None) -> float:
    return _PLAN_MRR_USD.get((plan or "free").lower(), 0.0)


async def _collect_brains_by_workspace(db) -> dict[str, list[dict]]:
    """Group all brains by workspace_id (single fetch)."""
    brains = await db.select("brains", columns="id,workspace_id,user_id,last_sync_at")
    grouped: dict[str, list[dict]] = {}
    for b in brains:
        ws = b.get("workspace_id")
        if ws:
            grouped.setdefault(ws, []).append(b)
    return grouped


def _latest_sync(brains: list[dict]) -> datetime | None:
    latest: datetime | None = None
    for b in brains:
        ts = _parse_ts(b.get("last_sync_at"))
        if ts and (latest is None or ts > latest):
            latest = ts
    return latest


# ---------------------------------------------------------------------------
# GET /admin/global-kpis
# ---------------------------------------------------------------------------


@router.get("/admin/global-kpis", response_model=GlobalKpis)
async def get_global_kpis(_: str = Depends(require_operator)) -> GlobalKpis:
    """Return cross-workspace KPI rollup."""
    db = get_db()
    now = datetime.now(timezone.utc)

    workspaces = await db.select(
        "workspaces",
        columns="id,plan,created_at,deleted_at",
    )

    # MRR: sum of tier prices across all non-enterprise workspaces.
    mrr = sum(_plan_mrr(w.get("plan")) for w in workspaces)
    arr = mrr * 12

    # MRR delta %: new workspaces this calendar month vs. previous month.
    # Rough proxy for growth until subscription-history is tracked.
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_end = this_month_start - timedelta(seconds=1)
    prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    this_count = 0
    prev_count = 0
    for w in workspaces:
        ts = _parse_ts(w.get("created_at"))
        if ts is None:
            continue
        if ts >= this_month_start:
            this_count += 1
        elif prev_month_start <= ts <= prev_month_end:
            prev_count += 1
    mrr_delta_pct = ((this_count - prev_count) / prev_count * 100.0) if prev_count else 0.0

    # Active customers: any brain in the workspace synced within HEALTHY_DAYS.
    brains_by_ws = await _collect_brains_by_workspace(db)
    active_cutoff = now - timedelta(days=_HEALTHY_DAYS)
    customers_active = 0
    for w in workspaces:
        latest = _latest_sync(brains_by_ws.get(w["id"], []))
        if latest and latest >= active_cutoff:
            customers_active += 1

    # Churn rate: workspaces deleted in last 30d / total at period start.
    # If deleted_at isn't tracked (column may not exist), this stays 0.0.
    churn_cutoff = now - timedelta(days=30)
    churned = 0
    for w in workspaces:
        deleted = _parse_ts(w.get("deleted_at"))
        if deleted and deleted >= churn_cutoff:
            churned += 1
    total_at_start = max(len(workspaces) + churned, 1)
    churn_rate = churned / total_at_start

    return GlobalKpis(
        mrr_usd=round(mrr, 2),
        arr_usd=round(arr, 2),
        mrr_delta_pct=round(mrr_delta_pct, 2),
        customers_total=len(workspaces),
        customers_active=customers_active,
        churn_rate=round(churn_rate, 4),
        # TODO: real NRR requires monthly subscription snapshots.
        net_revenue_retention=1.0,
    )


# ---------------------------------------------------------------------------
# GET /admin/customers
# ---------------------------------------------------------------------------


_CUSTOMER_SORT_KEYS = {"mrr", "active_users", "last_active"}


@router.get("/admin/customers", response_model=list[AdminCustomer])
async def list_customers(
    sort: str = Query("mrr"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: str = Depends(require_operator),
) -> list[AdminCustomer]:
    """Paginated workspace list with activity-based health classification."""
    if sort not in _CUSTOMER_SORT_KEYS:
        raise HTTPException(status_code=400, detail=f"sort must be one of {sorted(_CUSTOMER_SORT_KEYS)}")
    if order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="order must be 'asc' or 'desc'")

    db = get_db()
    now = datetime.now(timezone.utc)

    workspaces = await db.select(
        "workspaces",
        columns="id,name,plan,created_at",
    )
    brains_by_ws = await _collect_brains_by_workspace(db)

    # Distinct members per workspace for "active users".
    members = await db.select(
        "workspace_members", columns="workspace_id,user_id"
    )
    members_by_ws: dict[str, set[str]] = {}
    for m in members:
        ws = m.get("workspace_id")
        if ws and m.get("user_id"):
            members_by_ws.setdefault(ws, set()).add(m["user_id"])

    rows: list[AdminCustomer] = []
    for w in workspaces:
        ws_id = w["id"]
        ws_brains = brains_by_ws.get(ws_id, [])
        last_active = _latest_sync(ws_brains)
        rows.append(
            AdminCustomer(
                id=ws_id,
                company=w.get("name") or "",
                plan=w.get("plan") or "free",
                mrr_usd=_plan_mrr(w.get("plan")),
                active_users=len(members_by_ws.get(ws_id, set())),
                brains=len(ws_brains),
                last_active=last_active.isoformat() if last_active else None,
                health=_classify_health(last_active, now),
            )
        )

    # Sort
    reverse = order == "desc"
    if sort == "mrr":
        rows.sort(key=lambda r: r.mrr_usd, reverse=reverse)
    elif sort == "active_users":
        rows.sort(key=lambda r: r.active_users, reverse=reverse)
    elif sort == "last_active":
        # None sorts to the end regardless of order direction.
        rows.sort(
            key=lambda r: (r.last_active is None, r.last_active or ""),
            reverse=reverse,
        )

    return rows[offset : offset + limit]


# ---------------------------------------------------------------------------
# GET /admin/alerts
# ---------------------------------------------------------------------------


@router.get("/admin/alerts", response_model=list[AdminAlert])
async def list_alerts(_: str = Depends(require_operator)) -> list[AdminAlert]:
    """Return a derived alert list (churn-risk, failed-payment, usage-spike)."""
    db = get_db()
    now = datetime.now(timezone.utc)
    alerts: list[AdminAlert] = []

    workspaces = await db.select(
        "workspaces",
        columns="id,name,plan,subscription_status",
    )
    brains_by_ws = await _collect_brains_by_workspace(db)
    stale_cutoff = now - timedelta(days=_HEALTHY_DAYS)

    for w in workspaces:
        ws_id = w["id"]
        company = w.get("name") or ws_id
        last_active = _latest_sync(brains_by_ws.get(ws_id, []))

        # churn-risk: 14+ days inactive
        if last_active is None or last_active < stale_cutoff:
            days_inactive = (
                int((now - last_active).total_seconds() // 86400) if last_active else None
            )
            detail = (
                f"Inactive for {days_inactive}d" if days_inactive is not None else "No sync on record"
            )
            alerts.append(
                AdminAlert(
                    id=f"churn-{ws_id}",
                    kind="churn-risk",
                    customer=company,
                    detail=detail,
                    created_at=now.isoformat(),
                )
            )

        # failed-payment: rely on the subscription_status column populated by
        # the Stripe webhook handler. If the column isn't present we skip.
        if (w.get("subscription_status") or "").lower() == "past_due":
            alerts.append(
                AdminAlert(
                    id=f"payment-{ws_id}",
                    kind="failed-payment",
                    customer=company,
                    detail="Subscription past_due",
                    created_at=now.isoformat(),
                )
            )

    # usage-spike: >3x weekly corrections vs. prior week per workspace.
    # Single DB fetch + in-process grouping — avoids an N+1 loop over brains.
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    brain_to_ws = {b["id"]: ws for ws, brains in brains_by_ws.items() for b in brains}
    all_corrections = await db.select("corrections", columns="brain_id,created_at")
    weekly_counts: dict[str, dict[str, int]] = {}
    for c in all_corrections:
        ws_id = brain_to_ws.get(c.get("brain_id"))
        if not ws_id:
            continue
        ts = _parse_ts(c.get("created_at"))
        if ts is None:
            continue
        bucket = weekly_counts.setdefault(ws_id, {"this": 0, "prior": 0})
        if ts >= week_ago:
            bucket["this"] += 1
        elif two_weeks_ago <= ts < week_ago:
            bucket["prior"] += 1
    for ws_id, counts in weekly_counts.items():
        this_week = counts["this"]
        prior_week = counts["prior"]
        if prior_week > 0 and this_week > prior_week * 3:
            company = next(
                (w.get("name") or ws_id for w in workspaces if w["id"] == ws_id), ws_id
            )
            alerts.append(
                AdminAlert(
                    id=f"spike-{ws_id}",
                    kind="usage-spike",
                    customer=company,
                    detail=f"{this_week} corrections this week (vs {prior_week} prior)",
                    created_at=now.isoformat(),
                )
            )

    # TODO: Stripe failed-payment fully lands once we mirror subscription_status
    # for every workspace. Current path relies on webhook-populated column.

    return alerts
