# FAQ

## 1. Is Gradata open source?

Yes, and with no strings attached. The SDK is released under **Apache-2.0** on [GitHub](https://github.com/Gradata/gradata). You can self-host it, fork it, extend it, ship it in commercial products, bundle it in your own SaaS, or keep your modifications private. No copyleft. No dual-license paperwork.

Gradata Cloud is a paid hosted service layered on top of the SDK. It is optional. Nothing in the SDK depends on Cloud being reachable — with BYOK you have the full product locally.

## 2. Who owns the data in my brain?

You do. A brain is a directory on your disk. You can inspect it, back it up, move it, delete it, or share it. Gradata has no copy unless you explicitly sync to Cloud.

When you sync, Cloud stores a mirror plus derived metrics. You can delete that mirror from the dashboard at any time, and deletion removes the data from Cloud's hot storage within minutes and from backups within the standard 30-day rolling retention window.

## 3. What data leaves my machine?

**With the SDK only:** nothing. Corrections, lessons, events, manifest — all local.

**With `pip install "gradata[embeddings]"`:** still nothing — embeddings run locally via sentence-transformers.

**With `pip install "gradata[gemini]"`:** text to be embedded is sent to Google's Gemini API. You control the API key. No Gradata server is involved.

**With Gradata Cloud sync enabled:** event metadata (types, timestamps, severity, classifications) is always sent. Raw correction text is sent by default but can be redacted via the brain's PII taxonomy before sync.

## 4. Can I self-host the Cloud back-end?

Cloud is a hosted SaaS product — team workspaces, corrections corpus aggregation, brain marketplace, and a managed LLM option. It is not something you install from the repo; it is a service you subscribe to.

For teams that need the dashboard experience inside their own infrastructure, we offer a single-tenant deployment option — see the **Enterprise** plan or email `sales@gradata.ai`.

## 5. What's the rate limit?

| Endpoint class | Limit |
|----------------|-------|
| Read endpoints | 60 / min / key |
| Write endpoints | 10 / min / key |
| Sync endpoints | 100 / hour / key (events are batched) |
| Admin endpoints | 30 / min / key |

Limits are per API key. A `429` response always includes a `Retry-After` header.

## 6. How is the brain different from a CLAUDE.md file?

`CLAUDE.md` is a static list of rules you maintain by hand. You curate it, you argue with it, you never prune it.

A Gradata brain is dynamic: rules enter via corrections, earn confidence via survival, die when contradicted, and cluster into meta-rules automatically. It's the same idea your Markdown file gestures at, but with evidence, graduation, and provenance instead of vibes.

You can export a brain **to** `CLAUDE.md`, `.cursorrules`, `BRAIN-RULES.md`, or any other format your agent host expects. The brain is the source of truth; the Markdown file is the build artifact.

## 7. Does this work with LLM providers other than OpenAI and Anthropic?

Yes. The SDK is provider-agnostic:

- The `Brain` class has no LLM dependency.
- The [middleware](sdk/middleware.md) includes adapters for OpenAI, Anthropic, LangChain, and CrewAI out of the box.
- For any other provider, wrap your calls in three steps: inject rules, call the LLM, capture outputs.

## 8. What's the pricing?

SDK is free forever (Apache-2.0) — 100% capable standalone with BYOK. Cloud adds team features, corrections corpus, and brain marketplace:

| Plan | Price | Includes |
|------|-------|----------|
| Free | $0 | 1 brain, 500 sync events / month, community support |
| Pro | Small monthly fee | Unlimited brains, 50k sync events / month, priority support |
| Team | Per-seat | Pro + workspaces + shared brains + team analytics |
| Enterprise | Custom | Team + SSO + SLA + single-tenant option |

Exact pricing and seat counts live at [gradata.ai/pricing](https://gradata.ai/pricing). We keep numbers out of docs so prices can evolve without stale pages everywhere.

## 9. How do I export my brain from Cloud?

Two ways:

1. **Local SDK export.** Run `gradata export --mode full` on any machine that has the brain synced locally. You get a portable zip with the database, manifest, and knowledge files.

2. **Cloud export API.** `POST /brains/{brain_id}/export` kicks off a server-side export and returns a signed download URL. Use this when the machine you're exporting *to* has never had the brain locally.

Both produce the same format.

## 10. Can I contribute?

Yes — see [Contributing](contributing.md). Good first issues are tagged on GitHub. We accept PRs for bugfixes, new adapters, new hook templates, and docs improvements.

For larger changes (new graduation algorithms, new storage backends, new LLM providers), please open a discussion first so we can make sure the approach fits the architecture.
