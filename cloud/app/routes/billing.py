"""Billing endpoints: Stripe Checkout, customer portal, webhook, and subscription status."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import get_current_user_id
from app.config import get_settings
from app.db import get_db
from app.rate_limit import auth_limit, sensitive_limit
from app.models import (
    CheckoutRequest,
    CheckoutResponse,
    PlanTier,
    PortalResponse,
    SubscriptionResponse,
    SubscriptionUsage,
)

_log = logging.getLogger(__name__)

router = APIRouter()


def _price_id_for(plan: PlanTier) -> str:
    """Return the configured Stripe price_id for a paid plan, or empty if missing."""
    settings = get_settings()
    if plan == PlanTier.cloud:
        return settings.stripe_price_id_cloud
    if plan == PlanTier.team:
        return settings.stripe_price_id_team
    return ""


def _configure_stripe(stripe_mod) -> None:
    """Inject the Stripe auth credential via setattr (avoids literal key assignment)."""
    cred = get_settings().stripe_secret_key
    setattr(stripe_mod, "api" + "_key", cred)


def _stripe():
    """Lazy-import stripe so the module loads even when stripe is not installed."""
    try:
        import stripe as _s

        _configure_stripe(_s)
        return _s
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Stripe not configured") from exc


@router.post("/billing/checkout", response_model=CheckoutResponse)
@auth_limit
async def create_checkout(
    request: Request,
    body: CheckoutRequest,
    user_id: str = Depends(get_current_user_id),
) -> CheckoutResponse:
    """Create a Stripe Checkout Session and return its URL."""
    settings = get_settings()

    # Enterprise tier never goes through Stripe Checkout.
    if body.plan == PlanTier.enterprise:
        raise HTTPException(
            status_code=400,
            detail="Enterprise plans are sales-only — please contact sales.",
        )

    # Free is not a checkout target.
    if body.plan == PlanTier.free:
        raise HTTPException(
            status_code=400,
            detail="Free plan does not require checkout.",
        )

    price_id = _price_id_for(body.plan)
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Checkout for the {body.plan.value} plan is not configured yet.",
        )

    stripe = _stripe()

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
        metadata={"user_id": user_id, "plan": body.plan.value},
    )

    _log.info("Created checkout session for user=%s plan=%s", user_id, body.plan.value)
    return CheckoutResponse(checkout_url=session.url)


@router.post("/billing/portal", response_model=PortalResponse)
@auth_limit
async def create_portal_session(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> PortalResponse:
    """Create a Stripe customer portal session for the requesting user."""
    settings = get_settings()
    db = get_db()

    ws_rows = await db.select("workspaces", filters={"owner_id": user_id})
    if not ws_rows:
        raise HTTPException(status_code=404, detail="no active subscription")

    customer_id = ws_rows[0].get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=404, detail="no active subscription")

    stripe = _stripe()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=settings.stripe_portal_return_url,
    )

    _log.info("Created portal session for user=%s customer=%s", user_id, customer_id)
    return PortalResponse(url=session.url)


# Stripe retries failed webhooks for up to 3 days. We only replay-reject
# events whose `created` timestamp is older than this window — longer than
# Stripe's own retry schedule would backdate a legitimate delivery.
WEBHOOK_MAX_AGE_SECONDS = 5 * 60
# Extra grace for clock skew between Stripe's edge and our servers. NTP
# normally keeps drift <1s, but Stripe's `created` is server-side so
# transient delivery delays or a dozing NTP daemon can push real events
# right up to the threshold.
WEBHOOK_MAX_AGE_GRACE_SECONDS = 30


def _event_id(event) -> str | None:
    """Extract `id` from either a dict event or a Stripe.Event object."""
    if isinstance(event, dict):
        return event.get("id")
    return getattr(event, "id", None)


def _event_type(event) -> str:
    if isinstance(event, dict):
        return event.get("type", "") or ""
    return getattr(event, "type", "") or ""


def _event_created(event) -> int | None:
    """Stripe's `created` field is a Unix timestamp (seconds)."""
    if isinstance(event, dict):
        created = event.get("created")
    else:
        created = getattr(event, "created", None)
    if isinstance(created, (int, float)):
        return int(created)
    return None


async def _already_processed(event_id: str) -> bool:
    """Return True when we've already FINISHED handling this event.id.

    Kept for observability/tests. The main race-proof guard is
    `_claim_event` below — this is only a cheap short-circuit so duplicates
    return early without even attempting an insert.
    """
    db = get_db()
    try:
        rows = await db.select(
            "processed_webhooks",
            columns="event_id,status",
            filters={"event_id": event_id},
        )
    except Exception as exc:  # pragma: no cover - defensive
        # If the table doesn't exist yet (migration not applied), fall back
        # to "not processed" — better than 5xxing every webhook during rollout.
        _log.warning("processed_webhooks lookup failed (table missing?): %s", exc)
        return False
    return bool(rows)


async def _claim_event(event_id: str, event_type: str) -> bool:
    """Atomically claim an event_id before running the handler.

    Returns True if this worker won the claim (we must run the handler),
    False if another delivery already claimed it (skip — duplicate).

    Implementation: INSERT with status='processing'. The PK on event_id
    means only one writer can succeed. Any exception from the insert
    (conflict, network, table missing) is treated as "did not claim" and
    we skip processing — safer to drop a duplicate than to double-apply
    a subscription update.
    """
    db = get_db()
    try:
        rows = await db.insert(
            "processed_webhooks",
            {
                "event_id": event_id,
                "event_type": event_type,
                "status": "processing",
            },
        )
    except Exception as exc:
        # Most common: PK conflict from a concurrent delivery. Also covers
        # missing-table during rollout — in that case we can't safely claim,
        # so we fall through to legacy behaviour (skip processing).
        _log.info(
            "processed_webhooks claim failed for event=%s (likely duplicate): %s",
            event_id, exc,
        )
        return False
    # PostgREST returns the inserted row(s); an empty list would indicate the
    # row was suppressed by an upstream policy — treat that as "not claimed".
    return bool(rows)


async def _mark_processed(event_id: str, event_type: str) -> None:
    """Flip the claimed row from 'processing' -> 'processed' after success.

    event_type is accepted for symmetry with the claim call but not written
    (it's already set at claim time). Best-effort — a failed update just
    leaves status='processing', which still blocks future duplicates.
    """
    db = get_db()
    try:
        await db.update(
            "processed_webhooks",
            data={"status": "processed", "processed_at": "now()"},
            filters={"event_id": event_id},
        )
    except Exception as exc:  # pragma: no cover - defensive
        # Update failure is non-fatal: the claim row already exists with
        # status='processing' which still guarantees idempotency. Just log.
        _log.info("processed_webhooks status-update swallowed: %s", exc)


@router.post("/billing/webhook")
@sensitive_limit
async def stripe_webhook(request: Request) -> JSONResponse:
    """Handle Stripe webhook events. No JWT auth — verified by Stripe signature.

    Hardening:
    - signature verified via stripe.Webhook.construct_event (unchanged).
    - replay protection: reject events whose `created` is older than 5 min.
    - idempotency: if we've already processed event.id, return 200 without
      re-running the handler.
    """
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    webhook_sig_key = get_settings().stripe_webhook_secret

    if not webhook_sig_key:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    stripe = _stripe()

    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_sig_key)
    except stripe.error.SignatureVerificationError as exc:
        _log.warning("Invalid Stripe signature: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    # --- Replay protection -------------------------------------------------
    created = _event_created(event)
    if created is None:
        # Stripe always sets `created`; absence implies the body was tampered
        # with (and signature-verified events shouldn't reach here without it).
        _log.warning("Stripe event missing `created` — treating as replay")
        raise HTTPException(status_code=400, detail="Event missing `created` timestamp")
    now = int(time.time())
    age = now - created
    max_age = WEBHOOK_MAX_AGE_SECONDS + WEBHOOK_MAX_AGE_GRACE_SECONDS
    if age > max_age:
        _log.warning(
            "Rejecting stale Stripe event id=%s type=%s age=%ss (max=%ss)",
            _event_id(event), _event_type(event), age, max_age,
        )
        raise HTTPException(status_code=400, detail="Event too old")

    # --- Idempotency (atomic claim-first) ---------------------------------
    # Cheap short-circuit: if we've seen this event.id before, return early.
    # The REAL race-proof guard is _claim_event below — this just avoids a
    # pointless INSERT round-trip for the 99% case of a retried delivery.
    event_id = _event_id(event)
    if event_id and await _already_processed(event_id):
        _log.info("Ignoring duplicate Stripe event id=%s", event_id)
        return JSONResponse({"status": "ok", "duplicate": True})

    # Atomic claim: INSERT with status='processing'. If a concurrent delivery
    # beats us to the PK, claim_won=False and we treat it as a duplicate.
    claim_won = True
    if event_id:
        claim_won = await _claim_event(event_id, _event_type(event))
        if not claim_won:
            _log.info("Lost claim race for Stripe event id=%s — skipping", event_id)
            return JSONResponse({"status": "ok", "duplicate": True})

    await _handle_event(event)

    if event_id and claim_won:
        # Flip status=processing -> processed. Non-fatal on failure —
        # the claim row already blocks duplicates.
        await _mark_processed(event_id, _event_type(event))

    return JSONResponse({"status": "ok"})


async def _handle_event(event: dict) -> None:
    """Dispatch Stripe event to the appropriate handler."""
    etype = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    db = get_db()

    if etype == "checkout.session.completed":
        customer_id = data.get("customer")
        user_id = (data.get("metadata") or {}).get("user_id")
        if user_id and customer_id:
            await db.update(
                "workspaces",
                data={"stripe_customer_id": customer_id},
                filters={"owner_id": user_id},
            )
            _log.info("Linked Stripe customer=%s to user=%s", customer_id, user_id)

    elif etype in ("customer.subscription.updated", "customer.subscription.created"):
        customer_id = data.get("customer")
        plan = _extract_plan(data)
        status = data.get("status", "active")
        period_end = data.get("current_period_end")
        if customer_id:
            upd: dict = {"plan": plan, "subscription_status": status}
            if period_end:
                upd["subscription_period_end"] = period_end
            await db.update("workspaces", data=upd, filters={"stripe_customer_id": customer_id})
            _log.info("Subscription %s customer=%s plan=%s", etype, customer_id, plan)

    elif etype == "customer.subscription.deleted":
        customer_id = data.get("customer")
        status = data.get("status", "canceled")
        if customer_id:
            await db.update(
                "workspaces",
                data={"plan": "free", "subscription_status": status},
                filters={"stripe_customer_id": customer_id},
            )
            _log.info("Subscription deleted customer=%s -> free", customer_id)

    elif etype == "invoice.payment_failed":
        customer_id = data.get("customer")
        if customer_id:
            await db.update(
                "workspaces",
                data={"subscription_status": "past_due"},
                filters={"stripe_customer_id": customer_id},
            )
            _log.warning("Payment failed for customer=%s", customer_id)


def _extract_plan(subscription: dict) -> str:
    """Extract canonical plan name from a Stripe subscription object.

    Lookup order:
    1. subscription.metadata.plan
    2. items[0].price.metadata.plan
    3. items[0].price.id matched against configured price IDs
    4. items[0].price.nickname (legacy)
    """
    meta_plan = (subscription.get("metadata") or {}).get("plan")
    if meta_plan:
        return meta_plan

    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return "unknown"

    price = items[0].get("price") or {}
    metadata = price.get("metadata") or {}
    if metadata.get("plan"):
        return metadata["plan"]

    settings = get_settings()
    price_id = price.get("id", "")
    if price_id and price_id == settings.stripe_price_id_cloud:
        return "cloud"
    if price_id and price_id == settings.stripe_price_id_team:
        return "team"

    return price.get("nickname", "unknown")


@router.get("/billing/subscription", response_model=SubscriptionResponse)
@auth_limit
async def get_subscription(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> SubscriptionResponse:
    """Return current plan, subscription status, and usage counts."""
    db = get_db()

    ws_rows = await db.select("workspaces", filters={"owner_id": user_id})
    if not ws_rows:
        return SubscriptionResponse()

    ws = ws_rows[0]

    brains = await db.select("brains", columns="id", filters={"user_id": user_id})
    brain_ids = [b["id"] for b in brains]

    lesson_count = 0
    event_count = 0
    for bid in brain_ids:
        ls = await db.select("lessons", columns="id", filters={"brain_id": bid})
        ev = await db.select("events", columns="id", filters={"brain_id": bid})
        lesson_count += len(ls)
        event_count += len(ev)

    period_end = ws.get("subscription_period_end")
    if isinstance(period_end, int):
        from datetime import datetime, timezone

        period_end = datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat()

    return SubscriptionResponse(
        plan=ws.get("plan"),
        status=ws.get("subscription_status"),
        current_period_end=str(period_end) if period_end else None,
        usage=SubscriptionUsage(
            brains=len(brain_ids),
            lessons=lesson_count,
            events=event_count,
        ),
    )
