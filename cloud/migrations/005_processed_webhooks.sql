-- Gradata Cloud: Stripe webhook idempotency
--
-- Every Stripe webhook event.id we successfully process lands here. A
-- duplicate delivery (Stripe retries up to 3 days) hits the PK conflict
-- and returns 200 without re-running the handler.
--
-- `created_at` is kept so we can prune old rows out-of-band if the table
-- grows unbounded (Stripe sends thousands of events/day at scale).

CREATE TABLE IF NOT EXISTS processed_webhooks (
    -- Stripe's event.id — "evt_..." — globally unique per account.
    event_id TEXT PRIMARY KEY,
    -- Event type, e.g. "customer.subscription.updated". Useful for audit.
    event_type TEXT NOT NULL,
    -- When we first saw (and successfully handled) this event.
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index on created_at so pruning ("delete where created_at < now() - 7d")
-- doesn't require a full table scan.
CREATE INDEX IF NOT EXISTS idx_processed_webhooks_created_at
    ON processed_webhooks (created_at);
