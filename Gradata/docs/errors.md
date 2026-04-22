# Gradata — User-Facing Errors

**Status:** SPEC v1 (2026-04-21)
**Scope:** Every error string a non-developer user can see, with code, message, and remediation.

Every user-visible error maps to one of the codes below. Internal `log.debug(...)` and raw exceptions are not part of this contract — they may change freely.

---

## 1. Cloud credential errors (`CRED_*`)

| Code | Surface | Message | Remediation |
|---|---|---|---|
| `CRED_MISSING` | `gradata cloud status`, push summary | `credential: (none)` / `status: no_credential` | Run `gradata cloud enable --key gk_live_...` or set `GRADATA_API_KEY`. |
| `CRED_WRONG_PREFIX` | `gradata cloud enable\|rotate-key` | `Warning: credential does not begin with 'gk_live_'. Proceeding anyway — verify this is a live cloud key.` | Double-check the key copied from the dashboard. Live keys always start with `gk_live_`. |
| `CRED_KEYFILE_UNREADABLE` | internal (`log.debug`) + `status: no_credential` | silent — falls through to env var | Check `~/.gradata/key` permissions. On Windows, mode 0600 is advisory — see [Windows caveat](#windows-key-file-caveat). |

---

## 2. Cloud sync errors (`SYNC_*`)

Returned by `push_pending_events()` in the `status` field of the summary dict.

| Code | `status` value | Cause | Remediation |
|---|---|---|---|
| `SYNC_OK` | `ok` | All batches pushed. | — |
| `SYNC_DISABLED` | `disabled` | `cloud-config.json` has `sync_enabled: false`. | `gradata cloud enable --key ...` or flip the flag. |
| `SYNC_KILLED` | `kill_switch` | `GRADATA_CLOUD_SYNC_DISABLE` is truthy. | Unset the env var when you want sync back. |
| `SYNC_NO_DB` | `error / reason=no_db` | No `system.db` in brain dir. | Run any brain command once to initialise. |
| `SYNC_CONFIG_LOAD` | `error / reason=config_load_failed` | `cloud-config.json` is corrupt. | Delete the file and re-run `gradata cloud enable`. |
| `SYNC_NO_HTTPS` | `error / reason=https_required` | `api_base` is not HTTPS. | Set `GRADATA_CLOUD_API_BASE` to an `https://` URL. |
| `SYNC_NO_CREDENTIAL` | `no_credential` | See `CRED_MISSING`. | See `CRED_MISSING`. |
| `SYNC_HTTP_4XX` | `error / reason=rejected` + per-batch HTTP code in logs | Server rejected batch (auth, payload shape, quota). | Check `gradata cloud status` credential; check account quota in dashboard. |
| `SYNC_HTTP_5XX_MAX_RETRY` | `error / reason=transport` | Server errored through all retry attempts. | Retry later; if persistent, status page check. |

---

## 3. Migration errors (`MIG_*`)

| Code | Surface | Cause | Remediation |
|---|---|---|---|
| `MIG_002_FAIL` | `raise SystemExit` in `_migrations/002_add_event_identity.py` | SQLite error during chunked backfill. | Restore DB from automatic backup at `system.db.bak.YYYYMMDD`; re-run migration with `GRADATA_MIGRATION_CHUNK_SIZE=1000` for slower progress. |
| `MIG_003_FAIL` | `raise SystemExit` in `_migrations/003_add_sync_state.py` | SQLite error creating `sync_state` table. | Same as MIG_002_FAIL. |
| `MIG_PARTIAL_BACKFILL` | `status["rows_backfilled"]` less than expected | Process killed mid-backfill. | Re-run — migration is idempotent; only NULL rows are touched. |

---

## 4. PII redaction errors (`REDACT_*`)

Redaction is fail-closed — if the redactor raises, **neither** the raw side-log **nor** the canonical event is persisted.

| Code | Surface | Cause | Remediation |
|---|---|---|---|
| `REDACT_FAIL_CLOSED` | `log.error` + nothing written to events.jsonl | Bug in `_redact_payload` or its dependencies. | File a bug with the log excerpt. Do not bypass — raw text would leak to cloud. |

---

## 5. Event validation errors (`EVT_*`)

| Code | Surface | Cause | Remediation |
|---|---|---|---|
| `EVT_TAG_INVALID` | `log.debug("tag validation: %s", issue)` | Tag violates taxonomy. | Non-blocking — event still persists. Review taxonomy in `_tag_taxonomy.py`. |
| `EVT_DUAL_WRITE_FAIL` | raises from `emit()` | Both JSONL and SQLite writes failed. | Disk space / permissions issue. Cannot proceed; learning data integrity requires at least one path to succeed. |

---

## 6. Conflict resolution (`CONFLICT_*`) — Phase 2

| Code | Surface | Cause | Remediation |
|---|---|---|---|
| `CONFLICT_TIER2_HOLD` | Dashboard banner + `RULE_CONFLICT` event | Two devices graduated the same rule with `|Δconfidence| >= 0.15` or opposite directions. | Resolve in dashboard: "Device A says X, Device B says Y." |
| `CONFLICT_META_BLOCKED` | `META_RULE_BLOCKED` event | A source lesson is in conflict hold. | Resolve the underlying rule conflict first. |

---

## Windows key-file caveat

`~/.gradata/key` is created with `chmod 0600` on POSIX. On Windows, `os.chmod` accepts the call but cannot enforce POSIX permissions — file ACLs are governed by Windows security descriptors, not Unix modes. Treat the key file as user-scoped but assume any process running under your Windows account can read it.

**Phase 2 hardening:** wrap the keyfile in DPAPI (Windows `CryptProtectData`) so the on-disk blob is machine+user-scoped. Tracked in `docs/specs/cloud-sync-and-pricing.md` §2.5.

---

## Adding new errors

Every new user-facing error must:

1. Get a code here before the PR merges.
2. Use a concrete remediation — "contact support" is not a remediation.
3. Show up identically in whatever surface it appears (CLI, dashboard, API error body).

If the error is internal-only, log at `debug` and do not document here. The rule is: **if a user will ever read it, it goes in this file.**
