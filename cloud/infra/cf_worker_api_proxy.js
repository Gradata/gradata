// Cloudflare Worker deployed as `gradata-api-proxy` on account
// d568e4421afe0100d09df9e4d29bef81.
//
// Route binding (on zone gradata.ai): api.gradata.ai/*
//
// Purpose: bypass Railway's Let's Encrypt provisioning (which stalls for
// custom domains because their edge 301-redirects the ACME challenge path
// before serving it). CF Universal SSL covers the gradata.ai zone; this
// Worker just forwards the request to Railway's own public URL.
//
// To redeploy from the terminal (requires a CF API token with
// `Workers Scripts Write` on the account):
//
//   curl -sS -X PUT \
//     "https://api.cloudflare.com/client/v4/accounts/$ACCT/workers/scripts/gradata-api-proxy" \
//     -H "Authorization: Bearer $TOKEN" \
//     -F 'metadata={"main_module":"worker.js","compatibility_date":"2025-01-01"};type=application/json' \
//     -F 'worker.js=@cf_worker_api_proxy.js;type=application/javascript+module'

const ORIGIN = "https://gradata-production.up.railway.app";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const target = new URL(url.pathname + url.search, ORIGIN);
    const upstream = new Request(target.toString(), request);
    // Let Railway's edge treat this as native traffic.
    upstream.headers.set("host", new URL(ORIGIN).host);
    return fetch(upstream);
  },
};
