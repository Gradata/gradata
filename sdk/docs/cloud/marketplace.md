# Marketplace

The Gradata Marketplace is where trained brains become products. Creators list brains with proven quality. Users rent access to compound expertise.

## How It Works

### For Creators

1. **Train your brain** -- use it daily with Claude Code, Cursor, or any MCP host
2. **Connect to cloud** -- `brain.connect_cloud()` enables server-side adaptation
3. **Reach Grade B+** -- the cloud scores your brain on 5 quality dimensions
4. **List it** -- one-click listing from the dashboard
5. **Earn revenue** -- 80/20 split (creator/platform), monthly recurring

Your brain keeps improving while listed. Renters benefit from your ongoing work.

### For Renters

1. **Browse the marketplace** -- filter by domain, grade, sessions trained
2. **Rent a brain** -- flat monthly pricing, cancel anytime
3. **Connect via MCP** -- point your MCP config at the cloud brain
4. **Get proven rules** -- the brain's behavioral rules apply to your work

You don't download the brain. You stream access to it, like Spotify for expertise.

## Brain Grades

Brains are scored on 5 dimensions:

| Dimension | What It Measures |
|-----------|-----------------|
| **Training Depth** | Sessions trained, events logged, corrections captured |
| **Learning Signal** | Correction rate declining over time (brain is improving) |
| **Metric Integrity** | Event data is consistent, no gaps or anomalies |
| **Data Completeness** | Coverage across task types and audience tiers |
| **Behavioral Coverage** | Rules cover the domain's key scenarios |

### Grade Scale

| Grade | Score | Marketplace Status |
|-------|-------|-------------------|
| A+ | 90-100 | Featured, premium pricing |
| A | 80-89 | Full listing |
| B+ | 75-79 | Listed, standard pricing |
| B | 70-74 | Listed, trial only |
| C | 60-69 | Unlisted (training) |
| D-F | <60 | Unlisted (early stage) |

## Maturity Tiers

| Tier | Sessions | Trust Level | Access |
|------|----------|------------|--------|
| **Seedling** | 0-50 | Provisional | Private only |
| **Trained** | 50-200 | Verified | Listed, trial |
| **Expert** | 200-1K | Trusted | Full rental |
| **Master** | 1K-10K | Certified | Featured |
| **Legendary** | 10K+ | Legendary | Flagship, custom pricing |

## Rent vs. Buy

Brains are rented, never sold. This is by design:

- **Anti-cloning**: raw brain data never leaves the cloud
- **Living product**: the brain keeps improving after listing
- **Creator incentive**: recurring revenue motivates continued training
- **Quality guarantee**: platform monitors brain health, delists degrading brains

## Pricing

- **Standard**: $29-99/month per brain (creator sets price within tier)
- **Premium** (Master+): custom pricing
- **Revenue split**: 80% creator / 20% platform
- **Payouts**: Stripe Connect, monthly

## Domain Examples

| Domain | Example | Value |
|--------|---------|-------|
| Sales | 44-session brain with 66 proven rules for email drafting and objection handling | New AEs ramp faster by inheriting patterns that took months to learn |
| Engineering | Code review brain trained on 200+ PRs with accuracy and completeness rules | Consistent review quality across the team |
| Recruiting | Sourcing brain with outreach patterns proven across 500+ candidate interactions | Higher response rates from day one |
| Customer Support | Ticket response brain with empathy-first rules and resolution patterns | Consistent quality, faster resolution |

## Checking Your Status

```python
brain = Brain("./my-brain").connect_cloud()

status = brain._cloud.marketplace_status()
print(f"Grade: {status.get('grade')}")
print(f"Eligible: {status.get('eligible')}")
```
