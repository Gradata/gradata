// spike.js — k6 spike test against /health.
//
// 0 -> 100 VUs over 30s, hold 1m, ramp down 30s. Pounds /health to verify
// SlowAPI rate limiting kicks in (429s expected and fine) and that the
// backend never returns 5xx under load.
//
// Run:
//   k6 run k6/spike.js
//   k6 run k6/spike.js -e BASE_URL=https://gradata-production.up.railway.app

import http from 'k6/http';
import { check } from 'k6';
import { Rate, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://gradata-production.up.railway.app';

const fiveXX = new Rate('five_xx_rate');
const rateLimited = new Counter('rate_limited_429');
const successes = new Counter('success_200');

export const options = {
  stages: [
    { duration: '30s', target: 100 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    // The ONLY hard SLO: zero 5xx. SlowAPI should return 429, never 500.
    five_xx_rate: ['rate==0'],
    // Keep an eye on p99 but don't fail on it — spike tests expect slow tails.
    http_req_duration: ['p(99)<3000'],
  },
  tags: {
    scenario: 'spike',
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/health`, {
    tags: { endpoint: 'health_spike' },
  });

  // Classify — 200 is good, 429 is expected (rate limited), 5xx is BAD.
  const is5xx = res.status >= 500;
  fiveXX.add(is5xx);
  if (res.status === 429) rateLimited.add(1);
  if (res.status === 200) successes.add(1);

  check(res, {
    'no 5xx response': (r) => r.status < 500,
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });
}

export function handleSummary(data) {
  const m = data.metrics;
  const p95 = m.http_req_duration ? m.http_req_duration.values['p(95)'] : 'n/a';
  const p99 = m.http_req_duration ? m.http_req_duration.values['p(99)'] : 'n/a';
  const total = m.http_reqs ? m.http_reqs.values.count : 0;
  const ok = m.success_200 ? m.success_200.values.count : 0;
  const rl = m.rate_limited_429 ? m.rate_limited_429.values.count : 0;
  const bad = m.five_xx_rate ? m.five_xx_rate.values.rate : 'n/a';
  return {
    stdout: `
spike.js summary
----------------
total_requests  ${total}
200 OK          ${ok}
429 rate_limit  ${rl}
5xx rate        ${bad}  (SLO: must be 0)
http_req_dur    p95=${p95}ms  p99=${p99}ms
SLO: zero 5xx (429s are expected — SlowAPI rate limiting working).
`,
  };
}
