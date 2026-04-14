// authed-read.js — k6 authenticated read-heavy load test.
//
// 25 VUs for 5 minutes with a ramp, hitting /api/v1/brains and
// /api/v1/users/me. Simulates a busy dashboard session.
//
// Requires K6_API_KEY (a real gd_* API key for a test workspace).
// If unset, exits cleanly with a message — do NOT fake-pass.
//
// Run:
//   K6_API_KEY=gd_xxx k6 run k6/authed-read.js
//   K6_API_KEY=gd_xxx k6 run k6/authed-read.js -e BASE_URL=https://gradata-production.up.railway.app

import http from 'k6/http';
import { check, sleep, fail } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://gradata-production.up.railway.app';
const API_KEY = __ENV.K6_API_KEY;

const errorRate = new Rate('errors');

export const options = {
  // Ramp: 0 -> 25 over 1m, hold 25 for 3m, ramp down 25 -> 0 over 1m.
  stages: [
    { duration: '1m', target: 25 },
    { duration: '3m', target: 25 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    // SLO: p95 < 800ms, error rate < 2%. Auth adds a little latency.
    http_req_duration: ['p(95)<800'],
    http_req_failed: ['rate<0.02'],
    errors: ['rate<0.02'],
  },
  tags: {
    scenario: 'authed-read',
  },
};

export function setup() {
  if (!API_KEY) {
    // Fail LOUD — don't let CI pretend this passed.
    fail(
      'K6_API_KEY is unset. Set K6_API_KEY=gd_... (a real API key from a test ' +
        'workspace) to run authed-read.js. Refusing to run without auth.'
    );
  }
  // Sanity check: make sure the key actually works before burning the full run.
  const probe = http.get(`${BASE_URL}/api/v1/users/me`, {
    headers: { Authorization: `Bearer ${API_KEY}` },
    tags: { endpoint: 'setup_probe' },
  });
  if (probe.status !== 200) {
    fail(
      `Setup probe failed: GET /api/v1/users/me returned ${probe.status}. ` +
        `Check K6_API_KEY is a valid gd_* key. Body: ${probe.body}`
    );
  }
  return { baseUrl: BASE_URL };
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${API_KEY}`,
    'Content-Type': 'application/json',
  };

  // 70/30 split: brains list is the hotter endpoint in real usage.
  const pickBrains = Math.random() < 0.7;

  if (pickBrains) {
    const res = http.get(`${data.baseUrl}/api/v1/brains`, {
      headers,
      tags: { endpoint: 'brains_list' },
    });
    const ok = check(res, {
      '/brains 200': (r) => r.status === 200,
      '/brains returns array': (r) => {
        try {
          return Array.isArray(r.json());
        } catch (_e) {
          return false;
        }
      },
    });
    errorRate.add(!ok);
  } else {
    const res = http.get(`${data.baseUrl}/api/v1/users/me`, {
      headers,
      tags: { endpoint: 'users_me' },
    });
    const ok = check(res, {
      '/users/me 200': (r) => r.status === 200,
      '/users/me has user_id': (r) => {
        try {
          return typeof r.json('user_id') === 'string';
        } catch (_e) {
          return false;
        }
      },
    });
    errorRate.add(!ok);
  }

  // Think time between requests — real dashboards don't hammer 24/7.
  sleep(Math.random() * 2 + 0.5);
}

export function handleSummary(data) {
  const m = data.metrics;
  const p95 = m.http_req_duration ? m.http_req_duration.values['p(95)'] : 'n/a';
  const p99 = m.http_req_duration ? m.http_req_duration.values['p(99)'] : 'n/a';
  const failed = m.http_req_failed ? m.http_req_failed.values.rate : 'n/a';
  return {
    stdout: `
authed-read.js summary
----------------------
http_req_duration  p95=${p95}ms  p99=${p99}ms
http_req_failed    rate=${failed}
SLO: p95<800ms, error_rate<2%
`,
  };
}
