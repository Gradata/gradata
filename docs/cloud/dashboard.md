# Dashboard

The Gradata Cloud dashboard is a Next.js app at [app.gradata.ai](https://app.gradata.ai). It wraps the same data the local `brain.manifest.json` exposes, plus Cloud-only views for meta-rule synthesis, team management, and the operator console.

<!-- Screenshot placeholders will land after the dashboard design pass. -->

## Widgets

The home view shows, per brain:

- **Sessions trained** — cumulative session count.
- **Correction rate** — corrections per output, rolling over the last N sessions.
- **Rules active** — current count in each tier (INSTINCT / PATTERN / RULE).
- **Compound score** — 0-100 composite quality score.
- **Convergence curve** — corrections-per-session trend (the "is this brain learning?" chart).
- **Category extinction** — correction categories that have stopped recurring.
- **Recent graduations** — lessons promoted in the last 7 days.

Each widget is backed by the same metrics function in the SDK, so the dashboard and your local `brain.health()` agree.

## Brain detail view

Clicking a brain opens:

- **Lessons** — the full lesson table with state, confidence, fire count, and last-fired session.
- **Meta-rules** — cloud-synthesized principles with their source rules.
- **Corrections** — paginated event log with severity, classification, and diff.
- **Rule patches** — history of manual rule edits with rollback buttons.
- **Analytics** — cohort analysis, rule effectiveness, misfire trends.

!!! tip "Dashboard screenshots are placeholders"
    The images in this section reference `docs/assets/*.png`. Real screenshots will be added after the dashboard design pass lands. You can follow progress in `cloud/dashboard/`.

## Operator view

For internal Gradata ops (and self-hosted deployments with `operator` role), the `/admin` section exposes:

- **Global KPIs** — total brains, total events, revenue, active accounts.
- **Customer table** — per-workspace usage and health.
- **Alerts** — anomalies: sudden correction spikes, rule kill storms, sync failures.

See the API endpoints under `/api/v1/admin/*` in the [API Reference](api.md).

## Team management

A **workspace** is the unit of collaboration in Cloud. Each workspace has:

- Members (with roles: `owner`, `admin`, `member`, `viewer`).
- Brains (shared across the workspace or owned by a single member).
- Shared meta-rules — principles everyone on the team inherits.
- Per-member overrides — a member can mute or patch a shared rule without affecting the team brain.

Team endpoints live under `/api/v1/workspaces/{id}/team`.

## Notifications

From the dashboard **Settings → Notifications** you can opt into:

- **Graduation** — notified when a new RULE graduates.
- **Meta-rule created** — notified when a meta-rule emerges.
- **Rule killed** — notified when a rule drops below kill threshold.
- **Sync failure** — notified if a scheduled sync fails.

Delivery channels: email, webhook, Slack (via Incoming Webhook).

## Billing

Dashboard **Settings → Billing** uses Stripe. Plans:

- **Free** — one brain, 500 sync events / month, community support.
- **Pro** — unlimited brains, 50k sync events / month, priority support.
- **Team** — everything in Pro, plus workspaces and shared brains.
- **Enterprise** — custom, SLA-backed, single-tenant option.

See [FAQ → pricing](../faq.md).

## Local access

You don't need the dashboard to use Gradata. Everything exposed in the UI is available locally:

```bash
gradata manifest --json
gradata report --type rules
gradata report --type meta-rules
gradata convergence
```

The dashboard is optional and additive.
