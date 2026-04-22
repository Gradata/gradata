# Cloud Retention Clock Semantics

**Status:** SPEC v1 (2026-04-21)
**Blocks:** Billing, `/events/pull?rebuild_from=...` rewind window, storage-tier pricing.

---

## 1. The question

"2-year cloud retention" means the clock starts when?

Three candidates:

| Candidate | Meaning | Problem |
|---|---|---|
| `emit_ts` | Original event timestamp on the device. | User replays a 3-year-old correction from a backup → immediately expired on arrival. |
| `push_ts` | Time the event was accepted by the cloud. | User on Free tier for 18 months, upgrades, starts syncing → all historical events get a fresh 2-year clock, which is a backdoor to unbounded retention. |
| `first_cloud_store_ts` | Time cloud first persisted the row (monotonically assigned server-side). | Stable. Deterministic. Clean rewind window. |

---

## 2. Decision

**Use `first_cloud_store_ts` as the retention clock.**

- Assigned server-side at row insertion, never overwritten.
- Exposed on every event as `server_stored_at` in pull responses.
- Retention window is `now - first_cloud_store_ts > retention_days` → eligible for archival/deletion.

Rationale:
- `emit_ts` fails the backup-restore case.
- `push_ts` lets users game it — re-pushing an expiring event would reset the clock. `first_cloud_store_ts` is write-once, so dedup on `(brain_id, event_id)` prevents clock reset.
- Server-assigned means no clock skew between devices.

---

## 3. Retention windows by tier

(Cross-reference with `docs/specs/cloud-sync-and-pricing.md` when pricing lands.)

| Tier | Raw events | Graduated rules | Derived analytics |
|---|---|---|---|
| Free | 30 days | 90 days | aggregate only, 30 days |
| Personal | 2 years | indefinite | 1 year |
| Teams | 2 years | indefinite | 2 years |
| Enterprise | contract | contract | contract |

"Indefinite" means "until the user deletes them." It does not mean "forever on Gradata's dime" — the marketing contract is "we don't auto-expire your graduated rules," not "we store your data in perpetuity for free."

---

## 4. Archival vs deletion

Past the retention window, eligible rows are **archived**, not deleted:

1. Move row to cold storage (S3/Glacier equivalent), compressed.
2. `/events/pull?include_archived=true` is permitted only for Personal+ tiers.
3. Archival is reversible until a hard-delete is explicitly requested (GDPR right-to-erasure).

The `RULE_GRADUATED` side of the stream is **never** archived under Free tier rules — graduated rules are the product, not the exhaust. Retention only applies to raw events.

---

## 5. Rewind window

`/events/pull?rebuild_from=<watermark>` may only rewind as far as the oldest row still in hot storage for that `(brain_id, device_id)`. If the watermark is older than the hot boundary:

- Response: `HTTP 410 Gone` with body `{"error": "rewind_beyond_retention", "earliest_available": "<ts>"}`.
- Client must either pick a later `rebuild_from` or accept archived-tier retrieval (Personal+).

This is the **only** case where rewind fails. Everything else is "here's the window, replay from here."

---

## 6. Clock edge cases

- **Device restored from backup:** `emit_ts` is preserved (part of the event); `first_cloud_store_ts` is fresh. User sees their 3-year-old note with a 2-year-fresh retention clock. Correct.
- **Event pushed twice:** dedup on `(brain_id, event_id)` — second push is a no-op. `first_cloud_store_ts` unchanged.
- **Cloud-only event (e.g. admin override):** `emit_ts = first_cloud_store_ts`. Trivial case.
- **Migration 002 backfill assigns `event_id` retroactively:** ULID `event_id` encodes the original `emit_ts`; `first_cloud_store_ts` is the push time. No collision.

---

## 7. Implementation checklist (Phase 2, before `/events/push` GA)

- [ ] Server-side column `events.first_cloud_store_ts` (default `now()`).
- [ ] `/events/pull` response includes `server_stored_at` field.
- [ ] Retention job scans `first_cloud_store_ts < now() - retention_days`.
- [ ] Tier lookup from `brain_id → user_id → plan_tier`.
- [ ] Test: re-push of an event does not reset the clock.
- [ ] Test: `410 Gone` returned when `rebuild_from` is older than retention.
- [ ] Billing dashboard: show "days remaining" per brain, computed from oldest `first_cloud_store_ts`.

---

## 8. Non-goals

- Per-event retention override (would complicate tier pricing).
- User-chosen retention window below tier minimum (privacy-oriented users who want 7-day retention can use local-only).
- GDPR specifics — tracked separately in `docs/privacy-compliance.md` (TBD).
