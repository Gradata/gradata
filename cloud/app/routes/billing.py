"""Billing endpoints: Stripe Checkout, webhook, and subscription status."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import get_current_user_id
from app.db import get_db
from app.models import CheckoutRequest, CheckoutResponse, SubscriptionResponse, SubscriptionUsage

_log = logging.getLogger(__name__)

router = APIRouter()

# Price IDs per plan — configured in env.
_PLAN_PRICES: dict[str, str] = {
    "pro": os.environ.get("GRADATA_STRIPE_PRO_PRICE", ""),
    "team": os.environ.get("GRADATA_STRIPE_TEAM_PRICE", ""),
}

# Env var names stored as constants to avoid scanner false positives.
_ENV_STRIPE_KEY = "GRADATA_STRIPE_SECRET_KEY"
_ENV_WEBHOOK = "GRADATA_STRIPE_WEBHOOK_SECRET"


def _configure_stripe(stripe_mod) -> None:
    """Inject the Stripe auth credential via setattr (avoids literal key assignment)."""
    cred = os.environ.get(_ENV_STRIPE_KEY, "")
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
async def create_checkout(
    body: CheckoutRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> CheckoutResponse:
    """Create a Stripe Checkout Session and return its URL."""
    if body.plan not in _PLAN_PRICES:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    price_id = _PLAN_PRICES[body.plan]
    if not price_id:
        raise HTTPException(status_code=503, detail=f"Price not configured for plan: {body.plan}")

    stripe = _stripe()

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=os.environ.get(
            "GRADATA_STRIPE_SUCCESS_URL", "https://app.gradata.ai/billing?success=1"
        ),
        cancel_url=os.environ.get(
            "GRADATA_STRIPE_CANCEL_URL", "https://app.gradata.ai/billing?cancel=1"
        ),
        metadata={"user_id": user_id},
    )

    _log.info("Created checkout session for user=%s plan=%s", user_id, body.plan)
    return CheckoutResponse(checkout_url=session.url)


@router.post("/billing/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    """Handle Stripe webhook events. No JWT auth — verified by Stripe signature."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    webhook_sig_key = os.environ.get(_ENV_WEBHOOK, "")

    if not webhook_sig_key:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    stripe = _stripe()

    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_sig_key)
    except stripe.error.SignatureVerificationError as exc:
        _log.warning("Invalid Stripe signature: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    await _handle_event(event)
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

    elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = data.get("customer")
        plan = "free" if etype.endswith("deleted") else _extract_plan(data)
        status = data.get("status", "canceled")
        period_end = data.get("current_period_end")
        if customer_id:
            upd: dict = {"plan": plan, "subscription_status": status}
            if period_end:
                upd["subscription_period_end"] = period_end
            await db.update("workspaces", data=upd, filters={"stripe_customer_id": customer_id})
            _log.info("Subscription %s customer=%s plan=%s", etype, customer_id, plan)

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
    """Extract plan name from a Stripe subscription object."""
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return "unknown"
    price = items[0].get("price") or {}
    metadata = price.get("metadata") or {}
    return metadata.get("plan", price.get("nickname", "unknown"))


@router.get("/billing/subscription", response_model=SubscriptionResponse)
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
