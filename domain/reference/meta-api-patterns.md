# Meta Marketing API Patterns -- Sprites Reference

> Loaded during demo prep (step 9b) and ad platform work. Source: Meta API best practices + field experience.

## Rate Limiting

Meta uses Business Use Case rate limiting. Check headers on every response:
- X-Business-Use-Case-Usage contains usage percentages per ad account
- Throttle at 75% usage, pause at 90%
- Different endpoints have different rate limit pools

## Batch Requests

Always batch when operating on 2+ objects. Max 50 operations per batch. For larger sets, chunk into multiple batches with delays.

## Campaign Structure

```
Campaign (objective + budget)
  -> Ad Set (targeting + schedule + bid)
    -> Ad (creative + tracking)
```

## Common ROAS Killers (Use in Demo Prep)

These are the mistakes prospects are most likely making. Map each to a Sprites thread during demo prep:

1. **Wrong campaign objective** -- objective is set at creation and CANNOT be changed. Prospects running Traffic when they should run Conversions leave 30-50% ROAS on the table. Sprites auto-selects the right objective.
2. **No batch optimization** -- managing ads one at a time instead of batching. Sprites batches operations, reducing API overhead and enabling cross-ad optimization.
3. **Ignoring rate limits** -- hitting throttles kills campaign launch speed. Sprites handles rate limit headers automatically.
4. **Manual bid management on small budgets** -- prospects with <$5k/month spending hours on manual bids. Sprites automates bid strategy selection based on budget + goal.
5. **Not using Advantage+ audiences** -- sticking with legacy detailed targeting when broad + creative testing outperforms. Sprites tests both.
6. **Creative fatigue blindness** -- running the same creatives past frequency 3+ without rotation. Sprites monitors frequency and flags stale creative.
7. **No attribution window alignment** -- default 7-day click attribution misses longer B2B cycles. Sprites configures attribution windows per campaign type.
8. **Special ad category violations** -- housing/credit/employment campaigns with restricted targeting get rejected. Sprites pre-checks category compliance.

## Key Fields to Always Audit

When evaluating a prospect's current setup:
- effective_status vs configured_status (campaigns can be "active" but not delivering)
- optimization_goal alignment with business goal
- billing_event matches optimization (e.g., IMPRESSIONS billing with CONVERSIONS optimization is a red flag)
- daily_budget vs lifetime_budget strategy
- tracking_specs for proper conversion attribution

## Currency and Format Notes

- Currency amounts are in cents (multiply by 100)
- Deleted objects return 404, not a "deleted" status
- Audience size estimates are async, can take minutes
- Image hash is per-ad-account, not global
- Date ranges in insights use the ad account timezone, not UTC

## Campaign Types for ICP Mapping

| Prospect Profile | Recommended Campaign Type | Why |
|-----------------|--------------------------|-----|
| Lead gen (B2B services) | Conversions + Lead Forms | Lower friction than landing page |
| E-commerce DTC | Advantage+ Shopping | Auto-optimizes across placements |
| Local services | Store Traffic + Conversions | Geo-targeted with radius bidding |
| Brand awareness | Reach + Frequency | Controlled exposure, not wasted impressions |
| App install | App Campaigns | Integrated with app store events |

## Bidding Strategy Decision Tree

- Budget <$3k/month -> Advantage Campaign Budget (let Meta optimize)
- Budget $3-10k/month -> Target CPA with Advantage+ placements
- Budget >$10k/month -> Target ROAS with manual placement control
- New account (<30 conversions) -> Maximize Conversions first, then switch to target CPA after learning phase
