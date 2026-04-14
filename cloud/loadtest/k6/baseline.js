// baseline.js — k6 smoke test for the Gradata cloud backend.
//
// 5 VUs for 2 minutes hitting public, unauthenticated endpoints.
// Used as a canary: if this fails, something is fundamentally wrong.
//
// Run:
//   k6 run k6/baseline.js
//   k6 run k6/baseline.js -e BASE_URL=https://gradata-production.up.railway.app

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://gradata-production.up.railway.app';

const errorRate = new Rate('errors');

export const options = {
  vus: 5,
  duration: '2m',
  thresholds: {
    // SLO: p95 latency under 500ms, error rate under 1%
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
    errors: ['rate<0.01'],
  },
  tags: {
    scenario: 'baseline',
  },
};

export default function () {
  // Primary: root /health (always present, no auth, cheap)
  const healthRes = http.get(`${BASE_URL}/health`, {
    tags: { endpoint: 'health' },
  });

  const healthOk = check(healthRes, {
    '/health status is 200': (r) => r.status === 200,
    '/health body has status field': (r) => {
      try {
        return r.json('status') === 'healthy';
      } catch (_e) {
        return false;
      }
    },
  });
  errorRate.add(!healthOk);

  // Secondary: try /api/v1/health (may 404 — that's fine, we just want to
  // confirm the router is reachable). We don't assert 200 here since the
  // backend doesn't currently expose this path.
  const apiHealthRes = http.get(`${BASE_URL}/api/v1/health`, {
    tags: { endpoint: 'api_health' },
  });
  check(apiHealthRes, {
    '/api/v1/health responds (any status)': (r) => r.status > 0,
    '/api/v1/health not 5xx': (r) => r.status < 500,
  });

  sleep(1);
}

export function handleSummary(data) {
  return {
    stdout: textSummary(data),
  };
}

// Minimal text summary — avoids k6/x/jslib dep for portability.
function textSummary(data) {
  const m = data.metrics;
  const p95 = m.http_req_duration ? m.http_req_duration.values['p(95)'] : 'n/a';
  const p99 = m.http_req_duration ? m.http_req_duration.values['p(99)'] : 'n/a';
  const failed = m.http_req_failed ? m.http_req_failed.values.rate : 'n/a';
  return `
baseline.js summary
-------------------
http_req_duration  p95=${p95}ms  p99=${p99}ms
http_req_failed    rate=${failed}
SLO: p95<500ms, error_rate<1%
`;
}
