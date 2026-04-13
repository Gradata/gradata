# Cloud API Reference

The Gradata Cloud API is a REST API rooted at:

```
https://api.gradata.ai/api/v1
```

All endpoints require authentication. All responses are JSON.

## Authentication

Gradata Cloud uses bearer tokens:

```
Authorization: Bearer <your-api-key>
```

Create and rotate keys from the dashboard (**Settings → API keys**) or via the API below.

## Rate limits

- 60 requests / minute / API key for read endpoints.
- 10 requests / minute / API key for write endpoints.
- Sync endpoints use a longer window (100 / hour) because events are batched.

A `429` response includes a `Retry-After` header.

## Errors

All errors are returned as:

```json
{
  "detail": "Human-readable message",
  "code": "machine-readable-code"
}
```

Standard HTTP status codes: `400`, `401`, `403`, `404`, `409`, `422`, `429`, `5xx`.

---

## Users

### `GET /users/me`

Return the current user profile.

### `PATCH /users/me`

Update the current user's profile (`display_name`, `email`, `timezone`).

### `GET /users/me/notifications`

Return notification preferences.

### `PUT /users/me/notifications`

Replace notification preferences.

---

## API keys

### `POST /api-keys`

Create an API key. Returns the secret **once** — store it immediately.

**Request:**

```json
{
  "name": "CI key",
  "scopes": ["brains:read", "brains:write", "sync:write"]
}
```

**Response:**

```json
{
  "id": "key_123",
  "secret": "gdk_live_...",
  "created_at": "2026-04-13T12:00:00Z"
}
```

### `GET /api-keys`

List API keys (secrets redacted).

### `DELETE /api-keys/{key_id}`

Revoke an API key.

---

## Brains

### `POST /brains/connect`

Connect a local brain to Cloud. Pass the `brain.manifest.json` and receive a `brain_id` to use in subsequent sync calls.

### `GET /brains`

List all brains the caller can access.

### `GET /brains/{brain_id}`

Full detail for a brain: metadata, quality metrics, recent activity.

### `PATCH /brains/{brain_id}`

Update brain metadata (`name`, `domain`, `visibility`).

### `DELETE /brains/{brain_id}`

Delete a brain and all associated data. Irreversible.

### `POST /brains/{brain_id}/clear-demo`

Remove demo / seed data from a brain. Used after onboarding.

---

## Sync

### `POST /sync`

Stream events from a local brain to Cloud. Incremental — send only events since your last cursor.

**Request:**

```json
{
  "brain_id": "brn_abc",
  "cursor": "evt_000123",
  "events": [
    {
      "event_type": "CORRECTION",
      "source": "cli",
      "session": 42,
      "timestamp": "2026-04-13T12:00:00Z",
      "data": { "severity": "moderate", "classifications": ["TONE"] }
    }
  ]
}
```

**Response:**

```json
{
  "accepted": 1,
  "rejected": 0,
  "next_cursor": "evt_000124"
}
```

---

## Corrections

### `GET /brains/{brain_id}/corrections`

List corrections for a brain.

Query parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `session` | int | Filter to a single session |
| `category` | string | Filter by category |
| `severity` | string | `trivial`, `minor`, `moderate`, `major`, `rewrite` |
| `limit` | int | Default 50, max 500 |
| `cursor` | string | Pagination cursor |

---

## Lessons

### `GET /brains/{brain_id}/lessons`

List graduated lessons.

Query parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `state` | string | `INSTINCT`, `PATTERN`, `RULE`, `ARCHIVED` |
| `category` | string | Filter by category |
| `min_confidence` | float | Minimum confidence |

---

## Meta-rules

### `GET /brains/{brain_id}/meta-rules`

List synthesized meta-rules with their source lesson IDs and confidence.

---

## Rule patches

### `GET /brains/{brain_id}/rule-patches`

History of manual rule edits, including who, when, old value, new value.

### `POST /brains/{brain_id}/rule-patches/{patch_id}/rollback`

Revert a rule patch. Returns 204 on success.

---

## Analytics

### `GET /brains/{brain_id}/analytics`

Aggregated brain analytics: convergence trend, rule hit rate, misfire rate, compound score series.

### `GET /brains/{brain_id}/activity`

Recent activity feed (corrections, graduations, rule applications).

---

## Workspaces and team

### `GET /workspaces/{workspace_id}/members`

List members of a workspace.

### `POST /workspaces/{workspace_id}/invites`

Invite a teammate. Owner or admin only.

**Request:**

```json
{
  "email": "dev@acme.com",
  "role": "member"
}
```

**Response:** invite token and accept URL.

### `DELETE /workspaces/{workspace_id}/members/{user_id}`

Remove a member. Owner cannot be removed; transfer ownership first.

### `PATCH /workspaces/{workspace_id}/members/{user_id}`

Change a member's role. Valid roles: `admin`, `member`, `viewer`. `owner` is assigned only through the ownership transfer flow.

---

## Billing

### `POST /billing/checkout`

Create a Stripe checkout session for a plan upgrade.

### `POST /billing/portal`

Open a Stripe customer portal session.

### `POST /billing/webhook`

Stripe webhook endpoint (not for direct call — registered on stripe.com).

### `GET /billing/subscription`

Current subscription, seats, and usage.

---

## Admin / operator

All admin endpoints require an operator-scoped API key.

### `GET /admin/global-kpis`

Tenant-wide KPIs: total brains, events, active accounts, revenue.

### `GET /admin/customers`

Per-workspace usage and health.

### `GET /admin/alerts`

Active anomalies: correction spikes, rule kill storms, sync failures.

---

## Health

### `GET /health`

Liveness probe. Always returns `200` if the service is running.

### `GET /ready`

Readiness probe. Returns `200` only once Postgres, Redis, and Stripe are reachable.

---

## OpenAPI

The full OpenAPI 3.1 schema is available at:

```
https://api.gradata.ai/api/v1/openapi.json
```

Generate a client with any OpenAPI generator (oapi-codegen, openapi-typescript, openapi-python-client).
