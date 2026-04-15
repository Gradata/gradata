-- Gradata Cloud: Stripe webhook idempotency (atomic claim-first design)
--
-- Every Stripe webhook delivery first "claims" its event.id by inserting a
-- row here with status='processing'. Parallel deliveries of the same event
-- race on the PRIMARY KEY; the loser gets zero rows back and returns 200
-- without running the handler. The winner runs the handler, then updates
-- the row to status='processed' with processed_at.
--
-- This is stricter than "insert after success": it makes double-apply
-- impossible even when two workers pick up the same delivery concurrently.
--
-- `claimed_at` / `processed_at` are kept so we can prune old rows out-of-band
-- (Stripe sends thousands of events/day at scale) and audit stuck claims
-- where a worker crashed between claim and completion.

CREATE TABLE IF NOT EXISTS processed_webhooks (
    -- Stripe's event.id — "evt_..." — globally unique per account.
    event_id TEXT PRIMARY KEY,
    -- Event type, e.g. "customer.subscription.updated". Useful for audit.
    event_type TEXT NOT NULL,
    -- Claim lifecycle: 'processing' when claimed, 'processed' after handler
    -- completes successfully. Rows stuck in 'processing' for >10 min can be
    -- reaped by an out-of-band job if we ever need replay recovery.
    status TEXT NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing', 'processed')),
    -- When the claim was made (first insert).
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- When the handler finished successfully. NULL while status='processing'.
    processed_at TIMESTAMPTZ,
    -- Legacy/compat column — kept so existing queries still work. Mirrors
    -- claimed_at for new rows.
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index on claimed_at so pruning ("delete where claimed_at < now() - 7d")
-- doesn't require a full table scan.
CREATE INDEX IF NOT EXISTS idx_processed_webhooks_claimed_at
    ON processed_webhooks (claimed_at);

-- Historical index name (pre-hardening). Kept for environments that already
-- applied the old migration; new deployments only see idx_processed_webhooks_claimed_at.
CREATE INDEX IF NOT EXISTS idx_processed_webhooks_created_at
    ON processed_webhooks (created_at);
