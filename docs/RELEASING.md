# Releasing Gradata

Releases are fully automated. Pushing a version tag fires two GitHub Actions
workflows that publish to PyPI and npm:

- `.github/workflows/publish-python.yml` → PyPI (`gradata`)
- `.github/workflows/publish-npm.yml` → npm (`gradata-install` and `@gradata/install`)

Both workflows trigger **only** on tags matching `v*.*.*` (e.g. `v0.5.0`).
They will refuse to publish if the tag does not match the version declared in
`pyproject.toml` / `gradata-install/package.json`.

## Cut a release

1. Bump versions in lock-step:
   - `pyproject.toml` → `[project] version = "X.Y.Z"`
   - `gradata-install/package.json` → `"version": "X.Y.Z"`
2. Commit, open PR, merge to `main`.
3. Tag and push:
   ```bash
   git checkout main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
4. Watch the workflows at **Actions** → *Publish Python to PyPI* and
   *Publish npm packages*.

If a workflow fails because the tag version does not match the manifest,
delete the tag (`git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`),
fix the manifest, and retag.

## Required secrets

Add at **Settings → Secrets and variables → Actions** on the repository:

| Secret | Used by | Where to get it |
|--------|---------|-----------------|
| `PYPI_API_TOKEN` | `publish-python.yml` | https://pypi.org/manage/account/token/ — scope to the `gradata` project |
| `NPM_TOKEN` | `publish-npm.yml` | https://www.npmjs.com/settings/<user>/tokens — *Automation* token, 2FA-compatible |

No secret value ever appears in a workflow file; the jobs only reference
`${{ secrets.PYPI_API_TOKEN }}` and `${{ secrets.NPM_TOKEN }}`.

## Rotate tokens

1. Create the replacement token at PyPI or npm (same scope).
2. In GitHub **Settings → Secrets → Actions**, click the existing secret and
   *Update* the value. The name stays the same, so no workflow edits needed.
3. Revoke the old token at PyPI / npm.
4. Push a throwaway pre-release tag (e.g. `v0.0.0-rc.verify`) on a fork or
   re-run a prior release workflow to confirm the new token works, then
   delete the test tag.
