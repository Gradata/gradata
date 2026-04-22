# `/events/pull` Endpoint Contract

**Status:** SPEC v1 (2026-04-21)
**Implementation status:** Ships **disabled** in Phase 1. Interface is the commitment.
**Blocks on:** `docs/specs/merge-semantics.md` (Decision 9), `docs/specs/retention-clock.md`.
**Unblocks:** Materializer (Phase 2), multi-device sync, disaster recovery from cloud.

---

## 1. Why document an interface we haven't built

Council Architect: "The interface is the commitment." If `/events/pull` is going to be the disaster-recovery path for the materializer, the shape must be frozen now — both sides of the network need to agree before the client ships, even if the server returns 501 for now.

Per the council report: "Document the `/events/pull?rebuild_from=<watermark>` contract NOW even if the implementation ships disabled."

---

## 2. Request

```
GET {api_base}/events/pull
Authorization: Bearer <credential>
Query parameters:
  brain_id       required, string     tenant UUID
  device_id      required, string     requester's device
  rebuild_from   optional, string     event_id watermark (ULID) or ISO-8601 ts
  limit          optional, int        max events returned (1..1000, default 500)
  cursor         optional, string     opaque pagination token from previous response
  include_archived  optional, bool    default false; Personal+ tier only
```

### 2.1 `rebuild_from` semantics

- If `rebuild_from` is a **ULID**, the server returns events with `event_id > rebuild_from`, monotonically increasing.
- If `rebuild_from` is an **ISO-8601 timestamp**, the server returns events with `emit_ts >= rebuild_from`.
- If absent, the server uses the requester's last known pull cursor from `sync_state.last_pull_cursor`; first-ever pull starts from the oldest hot-tier event.

### 2.2 Rewind boundary

If `rebuild_from` predates the retention window (see `retention-clock.md`):

```
HTTP 410 Gone
{
  "error": "rewind_beyond_retention",
  "earliest_available": "01JN..." ,
  "hint": "Rewind window for this tier is 2 years. Archived events require include_archived=true on Personal+ tier."
}
```

---

## 3. Response (200)

```json
{
  "events": [
    {
      "event_id": "01JN7KXT...",
      "ts": "2026-04-20T12:34:56Z",
      "type": "RULE_GRADUATED",
      "source": "graduate",
      "data": { ... redacted ... },
      "tags": [ ... ],
      "device_id": "dev_7f3a...",
      "content_hash": "a1b2...",
      "correction_chain_id": null,
      "origin_agent": "session_close",
      "server_stored_at": "2026-04-20T12:34:58Z"
    }
  ],
  "next_cursor": "opaque-string-or-null",
  "watermark": "01JN7KXT...",
  "end_of_stream": false
}
```

- `events` is ordered by `server_stored_at` ASC, ties broken by `event_id` ASC.
- `next_cursor == null` **and** `end_of_stream == true` → caller has caught up.
- `watermark` is the last `event_id` the client should persist to `sync_state.last_pull_cursor`.

---

## 4. Error responses

| Code | Meaning | Client action |
|---|---|---|
| `401 Unauthorized` | Credential missing/invalid/revoked. | Re-run `gradata cloud enable`. Surface `CRED_MISSING` or `CRED_REVOKED`. |
| `403 Forbidden` | Credential scope lacks `brain:read`. | Re-issue key with proper scope. |
| `404 Not Found` | `brain_id` doesn't exist for this user. | Surface "brain not registered; run `gradata cloud enable`." |
| `410 Gone` | `rebuild_from` beyond retention. | Pick a later watermark or opt into archived retrieval. |
| `429 Too Many Requests` | Rate-limited. | Exponential backoff using `Retry-After` header. |
| `501 Not Implemented` | **Phase 1 only.** Endpoint exists but returns 501 with `{"error": "pull_not_enabled_yet"}`. | Client swallows 501 silently; surface as "pull disabled" in `gradata cloud status`. |

---

## 5. Merge semantics on the client side

When pulled events are merged into the local brain:

1. Events are applied in `server_stored_at` order (not `emit_ts`).
2. Dedup via `(event_id)` — already in local `events` table → skip.
3. For `RULE_GRADUATED` / `RULE_DEMOTED` events touching rules local has already graduated, apply the **Tier 1/2/3 logic from `merge-semantics.md`.**
4. Materializer reruns after merge to rebuild `lessons` table.

---

## 6. Property invariants (tests that must exist before GA)

1. **Idempotent replay:** pulling the same window twice yields the same local state.
2. **Order-independence for non-conflicting events:** shuffling the response order produces the same materialized `lessons` table (modulo conflict events, which explicitly order-depend).
3. **Watermark monotonicity:** the `watermark` field never decreases across paginated responses in a single pull session.
4. **Dedup invariant:** `count(events WHERE event_id = X) <= 1` after any sequence of pulls.
5. **Retention boundary:** requesting a `rebuild_from` one tick older than the oldest hot row returns 410, never an empty 200.

---

## 7. Phase 1 client stub

Ships in `gradata.cloud.pull.pull_events()` with this behavior:

- If server returns 501 → return `{"status": "disabled_server_side", "events_pulled": 0}`.
- If server returns 200 → **intentionally raise `NotImplementedError`** so nothing accidentally gets merged before the materializer ships.
- Public API is stable from this point: signature, return dict shape, error codes all frozen.

This gives us a client we can release in Phase 1 that is safely no-op, while every field of the contract is locked in code.

---

## 8. What this contract does NOT cover

- **Push** — see `cloud/push.py` and its tests.
- **Conflict resolution UI** — see `merge-semantics.md` Tier 2.
- **Archival storage format** — server-internal, not a client concern.
- **Team/RBAC** — Phase 3+.
