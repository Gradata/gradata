# Google Ads API Patterns -- Sprites Reference

> Loaded during demo prep (step 9b) and ad platform work. Source: Google Ads API best practices + field experience.

## Mutate Operations

Always use mutate for create/update/delete. Group related operations in a single request. Set partial_failure=True to handle individual operation errors without failing the entire batch.

## GAQL (Google Ads Query Language)

Use for all reporting. Key rules:
- Always include the resource in FROM that owns the fields you SELECT
- segments.date creates one row per date per entity
- metrics fields require a date range (WHERE or DURING clause)
- Cannot mix certain segment types in the same query
- Enum values use uppercase strings, not numeric codes
- Removed resources still appear in queries unless filtered by status

## Common ROAS Killers (Use in Demo Prep)

These are the mistakes prospects are most likely making. Map each to a Sprites thread during demo prep:

1. **Wrong campaign type** -- running Search when Performance Max would outperform for their product type. Or running Display for conversions when it's better suited for awareness. Sprites recommends the right campaign type per goal.
2. **Budget in wrong units** -- amounts are in micros (multiply by 1,000,000). Misconfigured budgets either overspend massively or starve campaigns.
3. **Manual CPC on automated-friendly accounts** -- clinging to manual bidding when Target CPA or Maximize Conversions would outperform with their conversion volume. Sprites auto-selects bidding strategy.
4. **No conversion tracking or broken tracking** -- conversion actions must be created at the MCC level for cross-account tracking. Missing conversions = blind optimization. Sprites verifies tracking before campaign launch.
5. **Broad match without smart bidding** -- using broad match keywords with manual CPC is a money pit. Sprites pairs broad match with smart bidding only.
6. **Ignoring search term reports** -- not adding negative keywords from actual search queries. Sprites monitors search terms and flags irrelevant traffic.
7. **Manager vs client account confusion** -- manager accounts cannot directly manage campaigns. Operating as the wrong account wastes time and causes permission errors.
8. **No audience signals on Performance Max** -- launching PMax without audience signals makes the learning phase longer and more expensive. Sprites seeds audience signals from existing customer data.

## Key Fields to Always Audit

When evaluating a prospect's current setup:
- Campaign type vs business objective alignment
- Bidding strategy vs conversion volume (Target CPA needs 30+ conversions/month)
- Search impression share (< 50% = budget-constrained or poor quality score)
- Quality Score components (relevance, landing page, expected CTR)
- Conversion tracking status and attribution model
- Resource names follow customers/{id}/campaigns/{id} format

## Format Notes

- Customer IDs have no dashes (1234567890 not 123-456-7890) in API calls
- Budget amounts are in micros (multiply by 1,000,000)
- Resource names are paths like "customers/123/campaigns/456", not just IDs
- Removed resources still appear unless filtered

## Campaign Types for ICP Mapping

| Prospect Profile | Recommended Campaign Type | Why |
|-----------------|--------------------------|-----|
| Lead gen (B2B services) | Search + Performance Max | Intent capture + broad reach |
| E-commerce DTC | Performance Max + Shopping | Full-funnel automation |
| Local services | Local Services Ads + Search | Map pack + intent |
| Brand awareness | Display + YouTube | Reach at scale, visual storytelling |
| High-ticket B2B | Search (exact/phrase match) | Precision targeting, high CPC justified by deal size |

## Bidding Strategy Decision Tree

- <15 conversions/month -> Maximize Clicks (not enough data for smart bidding)
- 15-30 conversions/month -> Maximize Conversions (build conversion data)
- 30-50 conversions/month -> Target CPA (enough data for stable optimization)
- 50+ conversions/month -> Target ROAS (sufficient volume for value optimization)
- New account -> Start with Maximize Conversions for 2-4 weeks, then transition
