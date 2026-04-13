// sync-write.js — k6 write load test against POST /api/v1/sync.
//
// 10 VUs for 3 minutes sending small synthetic correction + event payloads
// in the shape the SDK uses when GRADATA_API_KEY is set (see
// cloud/app/models.py::SyncRequest).
//
// Requires K6_API_KEY (a gd_* API key for a TEST workspace — writes land
// in the DB!). If unset, exits cleanly — do NOT fake-pass.
//
// Run:
//   K6_API_KEY=gd_xxx k6 run k6/sync-write.js

import http from 'k6/http';
import { check, sleep, fail } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://gradata-production.up.railway.app';
const API_KEY = __ENV.K6_API_KEY;
const BRAIN_NAME = __ENV.K6_BRAIN_NAME || 'k6-loadtest';

const errorRate = new Rate('errors');

export const options = {
  vus: 10,
  duration: '3m',
  thresholds: {
    // SLO: writes are slower, allow p95<1500ms and error_rate<5%.
    http_req_duration: ['p(95)<1500'],
    http_req_failed: ['rate<0.05'],
    errors: ['rate<0.05'],
  },
  tags: {
    scenario: 'sync-write',
  },
};

export function setup() {
  if (!API_KEY) {
    fail(
      'K6_API_KEY is unset. Set K6_API_KEY=gd_... (from a TEST workspace — ' +
        'this test writes rows!) to run sync-write.js. Refusing to run.'
    );
  }
  return { baseUrl: BASE_URL };
}

// Generate a small-but-realistic SyncRequest payload.
// Matches cloud/app/models.py::SyncRequest.
function buildPayload(vu, iter) {
  const now = new Date().toISOString();
  const session = Math.floor(Math.random() * 10000) + 1;
  return {
    brain_name: BRAIN_NAME,
    corrections: [
      {
        session,
        category: 'LOADTEST',
        severity: 'minor',
        description: `k6 synthetic correction vu=${vu} iter=${iter}`,
        draft_preview: 'draft text',
        final_preview: 'final text',
        created_at: now,
      },
    ],
    lessons: [],
    events: [
      {
        type: 'loadtest.ping',
        source: 'k6',
        data: { vu, iter, ts: now },
        tags: ['loadtest', 'k6'],
        session,
        created_at: now,
      },
    ],
    meta_rules: [],
    manifest: { source: 'k6-loadtest', version: '1' },
  };
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${API_KEY}`,
    'Content-Type': 'application/json',
  };

  const payload = JSON.stringify(buildPayload(__VU, __ITER));
  const res = http.post(`${data.baseUrl}/api/v1/sync`, payload, {
    headers,
    tags: { endpoint: 'sync' },
  });

  const ok = check(res, {
    '/sync 200': (r) => r.status === 200,
    '/sync status=ok': (r) => {
      try {
        return r.json('status') === 'ok';
      } catch (_e) {
        return false;
      }
    },
    '/sync counts present': (r) => {
      try {
        return typeof r.json('corrections_synced') === 'number';
      } catch (_e) {
        return false;
      }
    },
  });
  errorRate.add(!ok);

  // Small think time — SDK syncs are not back-to-back in real usage.
  sleep(Math.random() * 1 + 0.2);
}

export function handleSummary(data) {
  const m = data.metrics;
  const p95 = m.http_req_duration ? m.http_req_duration.values['p(95)'] : 'n/a';
  const p99 = m.http_req_duration ? m.http_req_duration.values['p(99)'] : 'n/a';
  const failed = m.http_req_failed ? m.http_req_failed.values.rate : 'n/a';
  return {
    stdout: `
sync-write.js summary
---------------------
http_req_duration  p95=${p95}ms  p99=${p99}ms
http_req_failed    rate=${failed}
SLO: p95<1500ms, error_rate<5%
`,
  };
}
