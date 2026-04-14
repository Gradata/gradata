# Gradata Cloud — k6 Load Tests

k6 load tests against the FastAPI backend deployed on Railway.

Base URL (default): `https://gradata-production.up.railway.app`

> `https://api.gradata.ai` is the intended custom domain, but SSL is
> currently broken (Cloudflare orange-cloud blocks the Railway cert).
> Point k6 at the Railway URL directly until that's fixed.

---

## Install k6

```bash
# macOS
brew install k6

# Windows
scoop install k6

# Docker
docker pull grafana/k6:latest

# Linux — see https://k6.io/docs/get-started/installation/
```

## Scenarios

All scripts accept `BASE_URL` via `-e BASE_URL=...` (default:
`https://gradata-production.up.railway.app`).

| Script | Purpose | VUs | Duration | Auth | Nightly? |
|---|---|---|---|---|---|
| `k6/baseline.js` | Smoke test — public `/health` endpoints | 5 | 2m | No | Yes |
| `k6/authed-read.js` | Dashboard read load (`/brains`, `/users/me`) | 25 (ramp) | 5m | Yes | No |
| `k6/sync-write.js` | SDK write load (`POST /sync`) | 10 | 3m | Yes | No |
| `k6/spike.js` | Burst traffic to verify rate limiting | 0→100 | 2m | No | Yes |

### Run

```bash
cd cloud/loadtest

# 1. Smoke (no auth, safe anywhere)
k6 run k6/baseline.js

# 2. Authed read — requires a real gd_* key for a TEST workspace
K6_API_KEY=gd_xxx k6 run k6/authed-read.js

# 3. Write load — ALSO writes rows, so use a throwaway test workspace
K6_API_KEY=gd_xxx K6_BRAIN_NAME=k6-loadtest k6 run k6/sync-write.js

# 4. Spike — no auth, OK on prod (/health is cheap)
k6 run k6/spike.js

# Override base URL for staging / local
k6 run k6/baseline.js -e BASE_URL=http://localhost:8000

# Docker (no local install)
docker run --rm -v $(pwd)/k6:/scripts grafana/k6:latest run /scripts/baseline.js
```

### CI

`.github/workflows/loadtest-nightly.yml` runs `baseline.js` + `spike.js`
nightly at 03:00 UTC against production. Authed scenarios are opt-in via
`workflow_dispatch` to avoid writing synthetic rows without coordination.

---

## SLOs

| Scenario | p95 | Error rate | Notes |
|---|---|---|---|
| baseline | < 500ms | < 1% | Public, no auth. If this breaks, Railway is sick. |
| authed-read | < 800ms | < 2% | Includes DB round-trip + auth validation. |
| sync-write | < 1500ms | < 5% | Write path — slower by design. |
| spike | p99 < 3s | **0% 5xx** | 429s are expected (SlowAPI). 5xx is a real bug. |

### Reading k6 output

```
http_req_duration...: avg=120ms  min=42ms  med=105ms  max=2.1s  p(90)=190ms  p(95)=240ms
http_req_failed.....: 0.12%   ✓ 2  ✗ 1643
```

- **p95 (95th percentile)**: 95% of requests completed faster than this.
  The "worst case most users see." Main SLO gate.
- **p99**: 1% of requests were slower than this. Watch for tail latency
  regressions — a creeping p99 often means the DB is about to fall over.
- **http_req_failed**: fraction of requests with a non-2xx/3xx status
  *excluding* explicit `expect` overrides. A spike here usually means
  connection errors or 5xx, not 404/429.
- **checks**: logical assertions inside the script. These should be 100%.
  If `checks` drops below `http_req_failed`, you have logic bugs, not
  network ones.

k6 exits 0 if all thresholds pass, non-zero otherwise. CI treats a
non-zero exit as an SLO breach.

---

## Rollback playbook — deploy regressed SLOs

1. **Confirm it's real.** Re-run the failing scenario against production.
   Check the last 3 nightly runs in GitHub Actions to distinguish a
   regression from a flake (one red run on a busy night ≠ broken deploy).
2. **Identify the bad deploy.** Railway dashboard → Deployments → note
   the commit SHA of the last green deploy.
3. **Roll back.** In Railway: Deployments → pick the last green → ⋮ →
   "Redeploy". This replays the known-good image; no git push needed.
4. **Verify.** Re-run `baseline.js` and `spike.js` against prod. Both
   should go green within ~60s of the redeploy finishing.
5. **Fix forward.** Open a revert PR or a fix PR against `main`. The
   nightly workflow will re-check once merged.

### Sentry cross-check

All 5xx responses during load tests land in Sentry (`gradata-cloud`
project). If `spike.js` fails its "zero 5xx" SLO, check Sentry for the
stack trace before assuming it's k6's fault.

---

## Safety notes

- `sync-write.js` writes real rows. Use a dedicated test workspace — the
  `brain_name` defaults to `k6-loadtest` so it's easy to filter/clean up
  in Supabase.
- `authed-read.js` and `sync-write.js` `fail()` cleanly if `K6_API_KEY`
  is unset. Don't stub the key — a "silent pass" hides regressions.
- The spike test is safe to run against production at any time; `/health`
  is cheap and SlowAPI prevents overrun.
- Rate limiting is keyed on client IP. If you're running from a shared
  runner (GitHub Actions), expect 429s earlier than from a residential IP.
