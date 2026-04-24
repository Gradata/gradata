# Gradata Cloud — Sync Architecture + Pricing Tiers

**Status:** DRAFT v1 (2026-04-21)
**Scope:** Full sync protocol + paid-tier feature matrix + pricing structure for Free / Personal / Teams / Enterprise.
**Supersedes:** Current `cloud/sync.py` telemetry-only payload (11-scalar MetricsWindow).

---

## 1. Guiding principles

1. **Local-first, always.** The SDK works forever without cloud. Every "premium" feature remains free when self-hosted.
2. **Cloud is read-only semantically.** Cloud never authors rules, never mutates brain state, never decides scope. It stores what the device sends and returns what the device asks for.
3. **Events are the source of truth.** `events.jsonl` is append-only, monotonically timestamped, device-scoped. `system.db` is a materialized view. Syncing events gives multi-device for free with no merge conflicts.
4. **Privacy gradient.** Raw correction text stays on-device unless user explicitly opts in (corpus contribution). Telemetry-only is the default.
5. **API keys, not CLI login flows.** User generates keys in the dashboard, pastes once. No OAuth device-code dance.

---

## 2. Identity & authentication

### 2.1 API key model

- User signs up on dashboard → authenticates via email magic-link or Google OAuth (browser-only).
- User clicks **Settings → API Keys → Generate new key**.
- Dashboard displays key ONCE: `gk_live_<32-char-base62>`.
- User copies key and pastes into one of:
  - `~/.gradata/api-key` (plain file, mode 0600)
  - `GRADATA_API_KEY` env var
  - `cloud-config.json` per-brain (existing path)
- No terminal login. No device code. No redirect flow. One copy/paste, permanent.

### 2.2 Key scoping

Each key is scoped at creation time:
| Scope | Can read | Can write | Notes |
|---|---|---|---|
| `brain:sync` | own events | own events | default for device sync |
| `brain:read` | own events | — | dashboard read-only, e.g. mobile viewer |
| `team:admin` | team events | team events + ACLs | Teams tier only |
| `marketplace:publish` | — | publish brain snapshot | future marketplace |

### 2.3 Device identity

- First sync on a new device generates `device_id` (UUIDv7, 128-bit).
- `device_id` stored in `cloud-config.json` per brain, per machine.
- Cloud tracks `(user_id, brain_id, device_id)` — enables "sign out of this device" and per-device audit.

### 2.4 Revocation

- Dashboard → API Keys → Revoke → key invalidated within 60s.
- Devices receive 401 on next sync → local `events.jsonl` continues to work; cloud features disabled gracefully.

---

## 3. Sync protocol

### 3.1 Data model

**Event** (wire format, append-only on both sides):
```json
{
  "event_id": "evt_01H7P4...",
  "brain_id": "brn_01G3...",
  "device_id": "dev_018E...",
  "event_ts": "2026-04-21T13:09:19.123Z",
  "kind": "correction | rule_graduated | session_start | ...",
  "payload": { /* kind-specific */ },
  "schema_ver": 1,
  "content_hash": "sha256:ab12..."
}
```

**Constraints:**
- `event_id` is client-generated ULID → sortable, dedupable.
- `content_hash` is sha256 of payload → enables idempotent retries.
- `device_id` scopes authorship — no two devices write events with the same device_id.
- `event_ts` is logical monotonic per-device (HLC-style); global ordering uses `(event_ts, device_id, event_id)`.

### 3.2 Endpoints

```
POST   /api/v1/events/push          # upload N events, chunked
GET    /api/v1/events/pull          # since watermark, exclude own device_id
POST   /api/v1/events/backfill/init # start chunked backfill session
POST   /api/v1/events/backfill/chunk
POST   /api/v1/events/backfill/finalize
GET    /api/v1/brain/snapshot       # materialized system.db view (Personal+)
GET    /api/v1/brain/materialize    # server-side re-materialize trigger
```

All require `Authorization: Bearer gk_live_<key>`. All enforce HTTPS via existing `require_https`.

### 3.3 Push (incremental)

```
POST /api/v1/events/push
Body: { "events": [ event, ... ], "device_id": "dev_...", "brain_id": "brn_..." }
Returns: { "accepted": 42, "deduped": 3, "rejected": [] }
```

Client behavior:
- Triggered on Stop hook or every 5min when events accumulated.
- Pushes since `last_push_event_id` watermark.
- Chunks of 500 events max per request.
- On 429: exponential backoff; on 5xx: retry with same `event_id`s (server dedups by `event_id`).

### 3.4 Pull (incremental)

```
GET /api/v1/events/pull?since=<event_ts>&exclude_device=<self>&limit=500
Returns: { "events": [ ... ], "has_more": true, "next_cursor": "..." }
```

Client behavior:
- Pulls events authored by OTHER devices of the same brain.
- Appends to local `events.jsonl`.
- Triggers local re-materialization (`brain/materialize.py`).

### 3.5 Backfill (first device, first sync)

New account, existing local brain with thousands of events:

1. `POST /backfill/init` → returns `backfill_session_id`.
2. Client reads `events.jsonl`, chunks into 10k events / batch.
3. `POST /backfill/chunk` × N with `session_id`.
4. `POST /backfill/finalize` → server materializes snapshot.
5. Dashboard becomes available.

Backfill runs in background thread, shows progress in CLI (`gradata cloud status`) and dashboard.

### 3.6 Second-device onboarding

1. User pastes API key on device B → `device_id` generated.
2. `GET /events/pull?since=0&exclude_device=dev_B` → streams entire event log.
3. Local materializer rebuilds `events.jsonl` + `system.db`.
4. Device B starts its own append stream. Stable forever.

### 3.7 Conflict resolution

There are no conflicts.

- Each event has one author (`device_id`).
- Events are append-only → no updates, no deletes (tombstones if needed for deletion are themselves events).
- Global order = lex-sort on `(event_ts, device_id, event_id)` → deterministic across devices.
- Materialization is a pure function of event log → same events → same `system.db`.

### 3.8 Rule graduation across devices

- Graduation is a LOCAL decision on the device where the threshold crossed.
- The graduation *event* gets pushed.
- Other devices pull the graduation event; their materializer sees `rule_graduated` and updates local `system.db` accordingly.
- No device "re-decides" — first-to-graduate wins (monotonic, deterministic).

---

## 4. Feature matrix (locked to pricing tier)

| Feature | Free | Personal | Teams | Enterprise |
|---|---|---|---|---|
| SDK (all features, local) | ✓ | ✓ | ✓ | ✓ |
| Cloud account | ✓ | ✓ | ✓ | ✓ |
| Dashboard: basic metrics | ✓ | ✓ | ✓ | ✓ |
| Dashboard: full visualization | — | ✓ | ✓ | ✓ |
| Multi-device sync | 1 device | unlimited | unlimited | unlimited |
| Historical retention (cloud) | 7 days | 90 days | 2 years | unlimited |
| Local DB pruning helper | — | ✓ | ✓ | ✓ |
| Backup / point-in-time restore | — | 7 days | 30 days | 90 days |
| Team / shared brain | — | — | up to 10 seats | unlimited |
| Multi-agent permissions (RBAC) | — | — | ✓ | ✓ + SSO |
| Audit logs | — | — | 90 days | unlimited + export |
| Cross-brain rule discovery | — | — | ✓ | ✓ |
| Marketplace: install brains | view | install | install | install |
| Marketplace: publish brains | — | ✓ | ✓ | ✓ |
| Self-host cloud backend | — | — | — | ✓ |
| SLA | — | — | 99.5% | 99.9% + custom |
| Support | community | email | priority email | dedicated + Slack |

**Indicative pricing** (subject to market validation — treat as placeholder until 10 paid users):
- **Free:** $0
- **Personal:** $12/mo or $108/yr (one user, sync, dashboard, 90d history)
- **Teams:** $20/seat/mo, min 3 seats (shared brains, RBAC, audit, 2yr)
- **Enterprise:** custom (self-host option, SSO, unlimited retention, SLA)

---

## 5. Tier-by-tier detail

### 5.1 Free

**What they get:**
- Unlimited local SDK (every feature — quality gates, truth protocol, rule graduation, meta-rules, Thompson sampling, all of it).
- Cloud account + dashboard showing **basic metrics only**:
  - Session count, rule count, rewrite rate trend (single chart, last 7 days).
  - No correction content, no rule details, no graduation timeline.
- 1 device syncing → on 2nd device prompt shows upgrade to Personal.
- 7 days of cloud event retention (older events pruned from cloud; local keeps everything).
- Community Discord support.

**Why give this away:** adoption funnel. They're using the full SDK — any friction they hit leaves them wanting sync, history, or team features. Conversion engine, not value dilution.

### 5.2 Personal ($12/mo)

**Adds over Free:**
- **Full dashboard:** every rule, every graduation event, confidence trajectories, correction heatmaps, meta-rule derivations.
- **Unlimited devices** (laptop + desktop + cloud agents + mobile viewer all sync to same brain).
- **90-day cloud retention** — older events pruned but snapshot preserved.
- **Local DB pruning helper:** CLI command `gradata brain prune --older-than 30d --keep-in-cloud` (your local `system.db` stays small; cloud keeps the tail).
- **7-day backup / point-in-time restore** — "restore my brain to yesterday 3pm."
- **Publish to marketplace** (when marketplace ships).

**Who buys:** solo developers / indie agent builders who run Claude Code on multiple machines and want their brain to follow them.

### 5.3 Teams ($20/seat/mo, min 3 seats)

**Adds over Personal:**
- **Shared brains.** A team brain is a separate `brain_id` that multiple users+devices can read/write. Example: a 5-person SDR team shares an "outbound" brain; every correction anyone makes graduates for everyone.
- **Multi-agent permissions (RBAC):**
  - Owner: full control, billing.
  - Admin: manage seats, ACLs, brain settings.
  - Writer: append events (agents + humans both).
  - Reader: dashboard + rule install only.
  - Agent: restricted write — can graduate rules, cannot delete or modify ACLs.
- **Audit logs** (90 days): every event authored, every rule graduated, every ACL change, every API key use. Queryable by user / device / timeframe.
- **2-year cloud retention.**
- **30-day backup** with rollback.
- **Cross-brain rule discovery:** "users in teams similar to yours graduated this rule; install delta." Driven by anonymized meta-rule clustering server-side.
- **Priority email support.**

**Who buys:** agencies, SDR teams, support teams running multi-agent workflows where the brain is shared IP.

### 5.4 Enterprise (custom)

**Adds over Teams:**
- **Self-host option.** Same protocol, run the cloud backend on your own Postgres + object store. API keys issued by your instance. Zero data leaves your VPC.
- **SSO** (SAML, OIDC) + directory sync (SCIM).
- **Unlimited retention + unlimited audit log** (exportable to customer's SIEM).
- **Dedicated subdomain** (`brain.customer.com`).
- **90-day backup + custom RPO/RTO.**
- **Custom SLA (99.9%+).**
- **Dedicated support channel** (Slack Connect or equiv).
- **Custom contract, DPA, security review.**

**Who buys:** regulated industries (finance, healthcare, defense) where data sovereignty is non-negotiable. Also the natural home for large enterprise agent-team deployments (50+ seats).

---

## 6. Feature deep-dives

### 6.1 Multi-device sync

Architecture covered in §3. Key UX:
- **Install & paste key:** `gradata cloud enable --key gk_live_...` writes to config.
- **Status:** `gradata cloud status` shows last push, last pull, backfill state, device_id.
- **Pause:** `gradata cloud pause` flips `sync_enabled=false` — local continues, cloud idles.
- **Disconnect device:** `gradata cloud disconnect` clears device_id, revokes this device's key scope server-side.

### 6.2 Team / shared brain state

- **Team brain** = separate `brain_id` in cloud, owned by a team not a user.
- **Join flow:** admin invites email → user accepts in dashboard → receives a team-scoped API key → local SDK switches `brain_id` to team.
- **Per-user agents:** my Claude on my laptop writes events with `(team_brain, my_device)`. Your Claude on your laptop writes with `(team_brain, your_device)`. Graduations are team-wide.
- **Permissions enforced server-side.** Writer key on a read-only user's machine = 403 on push.
- **Conflict-free** — same event model, just team-scoped.

### 6.3 Audit logs

- Every API request logged: `(user_id, api_key_id, device_id, endpoint, status, bytes, ts)`.
- Every event push logged with `content_hash`.
- Every ACL change emits an `acl_changed` event in the brain itself — visible in dashboard timeline and queryable.
- Teams: 90d retention, dashboard view. Enterprise: unlimited + export API.

### 6.4 Historical retention

- **Local:** user controls. Default keeps everything. `gradata brain prune --older-than 30d` deletes from local `events.jsonl` + rebuilds `system.db`.
- **Cloud:** tier-gated. Server runs nightly pruner on events older than tier's retention. Rule graduations and meta-rules NEVER pruned (they're derived state, summaries of pruned events).
- **Read-through:** dashboard for an event older than cloud retention shows "archived" with the graduation it contributed to (so you never lose the *outcome*, only the raw event).

### 6.5 Cross-brain rule discovery

The real moat. Mechanism:
- Server-side clustering over anonymized rule metadata (rule text, graduation context, trigger scope — NO correction content unless `contribute_corpus=true`).
- For a team brain, nightly job computes: "Similar brains (vector distance on rule corpus) graduated these rules you don't have."
- Dashboard surfaces top-10 with confidence deltas: "This rule saved similar teams ~12 corrections each. Install?"
- One-click install → fetches rule snapshot → applies locally at INSTINCT confidence → user's own graduation pipeline decides if it survives.

**This is what makes the paid tier not-a-Grafana-clone.** You can't Streamlit your way to this — it requires a population.

### 6.6 Backup / DR

- **Snapshot cadence:** hourly for Personal+, every 15min for Teams+, continuous WAL for Enterprise.
- **Point-in-time restore:** dashboard → "Restore brain to 2026-04-20 14:30" → server rebuilds snapshot at that ts → user confirms → pushed to devices on next sync as a special `restore` event (devices re-materialize to that point, then resume).
- **Export:** any tier can export raw events as JSONL. Owning your data is non-negotiable.

---

## 7. What ships in v1 (Week 1-2)

Scope for first cut to get the flywheel spinning:

1. **Dashboard-issued API keys** (replace current `GRADATA_API_TOKEN` env with `gk_live_*` keys in Settings UI).
2. **Event model migration:** extend `cloud/sync.py` to push `Event` objects in addition to `TelemetryPayload`. Maintain backward compat for 2 releases.
3. **`/events/push` + `/events/pull` endpoints** on `api.gradata.ai`.
4. **Backfill flow** (chunked init/chunk/finalize).
5. **Server-side materializer** (port `brain/materialize.py` to a job worker).
6. **Dashboard: basic metrics (Free) + full dashboard (Personal).**
7. **Stripe integration** for Personal tier only. Teams/Enterprise contact-sales link.
8. **Device management UI** (list devices, revoke).

Teams / RBAC / cross-brain / audit can follow in v2 (week 3-6). Marketplace + self-host are v3+.

---

## 8. Open questions

1. **Event encryption at rest.** Do we E2E encrypt events with a user-held key? Protects against cloud compromise but complicates server-side materialization and cross-brain discovery. Likely: opt-in E2E for Enterprise only.
2. **Mobile viewer.** Does Personal tier include a read-only iOS/Android app, or is that a separate line item?
3. **Marketplace pricing split.** If Alex Hormozi uploads a brain, what's the rev share? 70/30? 80/20? Subscription vs one-time?
4. **Free tier abuse.** What stops a single user from spinning 100 brains on Free tier? Likely: 1 brain per free account, upgrade for more.
5. **Rate limits per tier.** Needs pricing math after load-testing.

---

## 9. Why this shape (one-paragraph summary)

The SDK is already a CRDT disguised as a learning pipeline. Events are append-only, monotonically timestamped, and device-authored — exactly what multi-device sync needs with zero additional machinery. The cloud becomes a *durable event log* plus a *materializer* plus a *coordinator* (for teams and cross-brain comparison). Pricing is tiered not by gating "premium SDK features" — those stay free forever — but by gating the things that genuinely *require* a cloud: multi-device, multi-user, retention, comparison. This makes Free protective (it's how Anthropic-native-memory users discover you when they hit the sovereignty wall), Personal obvious ($12 to have my brain on every device), Teams real (shared cognition is a Netflix-scale problem for 5-person teams), and Enterprise boring (compliance + self-host for the regulated).
