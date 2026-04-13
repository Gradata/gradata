# Incident response runbook — Gradata Cloud

This is the on-call runbook for common production incidents. Everything here is
actionable — no aspirational prose. If a step fails, escalate in Slack
`#gradata-incidents` and tag `@oncall`.

> Status: DRAFT — pending operational review. Update this file whenever a
> real incident exposes a gap.

## 0. First 5 minutes (any incident)

1. **Acknowledge.** Post in `#gradata-incidents`:
   `INCIDENT <sev> — <one-line symptom> — IC: <you>`.
2. **Open the status page.** `status.gradata.ai` — flip the affected component
   to "investigating" within 15 minutes (SLA commitment).
3. **Start a doc.** Use the template in `cloud/OPS.md` — timestamp each step.
4. **Page help if needed.** Sev1/Sev0 pages the secondary on-call.

Severity quick-reference:

| Sev | Definition | Example |
|-----|-----------|---------|
| Sev0 | Total outage, all customers | api.gradata.ai DNS gone |
| Sev1 | Major degradation, most customers | 50%+ requests returning 5xx |
| Sev2 | Partial outage or single feature | Stripe webhooks failing |
| Sev3 | Single-customer issue | One workspace can't login |

---

## 1. api.gradata.ai returning 500s

**Symptoms:** synthetic monitor failing; Sentry spike in 5xx; customer
reports "dashboard won't load".

```bash
# 1. Confirm from outside Railway
curl -sS -o /dev/null -w "%{http_code}\n" https://api.gradata.ai/health
# Expected: 200

# 2. Check Railway logs (last 10 min)
railway logs --service gradata --tail 500

# 3. Check recent deploys — most 500 storms follow a deploy
railway deployments list --service gradata | head -5
```

**Common causes & fixes:**

- **Recent deploy broke boot.** Rollback via Railway UI → Deployments →
  click last-known-good → "Redeploy". Typical RTO: 3 minutes.
- **Missing env var.** `railway variables` — diff against `RAILWAY-ENV.md`.
  Add the missing var, Railway auto-redeploys.
- **Supabase unreachable.** Jump to section 3.
- **Sentry DSN misconfigured causing boot crash.** Unset
  `GRADATA_SENTRY_DSN` temporarily; app should boot since it's optional.

**Communicate:** update status page every 30 minutes until resolved.

---

## 2. Railway platform outage

**Symptoms:** Railway dashboard unreachable OR all services in a region
showing "deployment failed" without code change.

```bash
# 1. Check Railway status
curl -sS https://status.railway.com/api/v2/status.json | jq .status
```

**Steps:**

1. Post to status page: "Hosting provider outage — we're monitoring".
2. **Do not attempt to redeploy** during a Railway incident; you'll queue
   failed builds that clog the queue once they recover.
3. If outage >1h, consider failing over (future work — not yet wired).
4. Post-incident: snapshot any affected customer data by exporting from
   Supabase directly (`supabase db dump`).

---

## 3. Supabase connection pool exhausted

**Symptoms:** Sentry shows `httpx.ReadTimeout` or `502 Bad Gateway` from
PostgREST; metrics show request latency >5s.

```bash
# 1. Check Supabase project dashboard → Database → Connection pooling
# 2. Look for "pool saturated" or "max connections reached" log lines
```

**Common causes & fixes:**

- **Runaway query.** Supabase dashboard → Reports → Slow queries.
  Kill long-running queries:
  `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '30 seconds';`
- **Leaking connections.** Check `app/db.py` — `SupabaseClient._http` must
  be reused (singleton pattern). If we ever see per-request client
  instantiation, that's the bug.
- **Genuine overload.** Bump pool size in Supabase → Project → Settings
  → Database → Pool size. Ask @oliver first if the bump is >20%.

**Mitigation while investigating:** enable Supabase's connection pooler
(Transaction mode, port 6543) if not already on.

---

## 4. Stripe webhook backlog

**Symptoms:** customers report "I upgraded but my plan didn't change"; Stripe
dashboard → Webhooks shows failed deliveries or high retry counts.

```bash
# 1. Check webhook health
#    Stripe dashboard → Developers → Webhooks → api.gradata.ai/api/v1/billing/webhook
#    Look at the "Failed" tab for last 24h.

# 2. Replay failed events
#    Click into each failed event → "Resend".
#    Bulk replay is not yet scripted (TODO).
```

**Common causes & fixes:**

- **Webhook signature mismatch.** `STRIPE_WEBHOOK_SECRET` in Railway
  doesn't match the endpoint secret in Stripe. Fix by copying from
  Stripe dashboard → Webhooks → endpoint → "Signing secret".
- **Our endpoint 500s.** Follow section 1. Stripe retries with exponential
  backoff for 3 days, so short outages self-heal.
- **Webhook handler timeout.** `billing.py` should ack the webhook in
  <5s and defer heavy work. If we ever add sync work here that crosses
  the threshold, it's a regression.

**Verify recovery:** trigger a test event from Stripe CLI or dashboard and
watch `railway logs --service gradata | grep webhook`.

---

## 5. GDPR export / delete endpoint misbehaving

**Symptoms:** customer reports `/me/export` returning 429 they believe is
wrong, or `/me/delete` appearing to succeed but data still showing up.

```sql
-- 1. Check the rate-limit ledger
SELECT user_id, created_at
  FROM gdpr_export_requests
 WHERE user_id = '<uuid>'
 ORDER BY created_at DESC
 LIMIT 5;

-- 2. Check tombstone state after a delete
SELECT id, deleted_at, purge_after FROM users WHERE id = '<uuid>';
SELECT id, deleted_at FROM workspaces WHERE owner_id = '<uuid>';
SELECT id, deleted_at FROM brains WHERE user_id = '<uuid>';
```

- **False 429.** Clear one ledger row: `DELETE FROM gdpr_export_requests
  WHERE id = '<id>';`. Leave a note in the incident doc explaining why.
- **Data still visible after delete.** Verify the filter was applied in
  `auth.py` and `routes/users.py`. If a route is missing the filter,
  patch it immediately and write a test.
- **30-day purge overdue.** The nightly cron is out of scope for this
  PR; manual cleanup via SQL is acceptable meanwhile.

---

## 6. Communication templates

**Status page (investigating):**
> We're investigating reports of <symptom>. Updates every 30 min.

**Status page (identified):**
> We've identified the cause: <one-sentence root cause>. Working on a fix.

**Status page (resolved):**
> Resolved at <time UTC>. Post-mortem to follow within 5 business days
> (per our SLA).

**Customer email (P1 post-mortem):**
- What happened (1 paragraph, non-technical)
- When it happened + duration
- Customer impact (how many, what feature)
- Root cause (2-3 sentences)
- What we're changing so it doesn't happen again (bulleted)

---

## 7. Escalation

| Situation | Who | How |
|-----------|-----|-----|
| Can't reach primary on-call | Secondary on-call | PagerDuty |
| Data loss suspected | @oliver + legal@ | phone |
| Security incident | security@gradata.ai + legal@ | phone |
| Sub-processor breach | security@gradata.ai | see /legal/subprocessors |

---

Last updated: April 2026. When you run an incident, update the relevant
section with what you learned. Stale runbooks cause longer incidents.
