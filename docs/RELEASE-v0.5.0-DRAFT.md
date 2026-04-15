# Release v0.5.0 Draft

This doc holds the notes to paste into the GitHub Release form when cutting
`v0.5.0`, plus the commands Oliver should run **after this PR and PR #60
(publish workflows) are merged**.

Do not tag before merge — the tag must point at the merge commit on `main`,
not at this branch's HEAD.

---

## Prerequisites

1. This PR (`chore/align-versions-v0.5.0`) merged to `main`.
2. PR #60 (PyPI + npm publish workflows) merged to `main`.
   - Heads-up: PR #60's body flags a conflict with the existing `sdk-release.yml`.
     Resolve that before tagging, or the release job will double-publish /
     fight itself. Either delete `sdk-release.yml` or make it a no-op on tags
     that the new workflow already handles.
3. `main` is green in CI.

## Cut the release

```bash
git checkout main
git pull origin main
git tag -s v0.5.0 -m "gradata v0.5.0"
git push origin v0.5.0
```

If you don't sign tags, drop `-s`:

```bash
git tag v0.5.0 && git push --tags
```

Pushing the tag triggers the publish workflows introduced in PR #60:

- **PyPI**: builds `gradata==0.5.0` and publishes via OIDC / trusted publisher.
- **npm**: publishes `gradata-install@0.5.0` (now aligned to the Python SDK).

Watch the Actions tab — if either job fails, the tag is still valid; re-run
the failed job after fixing.

## GitHub Release notes (paste this into the form)

Title: `v0.5.0 — First public release`

Tag: `v0.5.0`

Body:

```markdown
First public release of Gradata — the learning layer for AI agents.

## What's in 0.5.0

- **Graduation pipeline**: corrections → instincts → patterns → rules, with
  meta-rule synthesis on top.
- **Self-healing**: rule failure detection + auto-patching.
- **Cloud backend**: Supabase schema, FastAPI `/sync`, Railway-ready deploy,
  Stripe webhooks, rate limiting, Sentry.
- **Middleware adapters**: OpenAI, Anthropic, LangChain, CrewAI — drop-in.
- **Claude Code plugin**: `/plugin install gradata`.
- **npm wrapper**: `npx gradata-install` for one-command setup.
- **Docs site**: full mkdocs Material at gradata.ai/docs.
- **A/B proof**: `/public/proof` endpoint with ablation export showing
  +13.2% quality lift over baseline.
- **GDPR + security**: data endpoints, DPA/SLA, security.txt, incident runbook.

See [CHANGELOG.md](https://github.com/Gradata/gradata/blob/main/CHANGELOG.md#050---2026-04-15)
for the full list.

## Install

```bash
pipx install gradata
# or
npx gradata-install
```

## License

AGPL-3.0-or-later. Full text in `LICENSE`. See `docs/LICENSING.md` for the
dual-license story (AGPL for community, commercial for closed-source use).
```

## After the release

- [ ] Verify `pip install gradata==0.5.0` works from a clean env.
- [ ] Verify `npx gradata-install@0.5.0` prints the expected banner.
- [ ] Announce in Discord + on the marketing site changelog page.
- [ ] Update `docs/changelog.md` if it drifted from `CHANGELOG.md`.
