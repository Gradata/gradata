# Releasing to PyPI

The `gradata` package on PyPI is published by the
[`sdk-publish.yml`](../../.github/workflows/sdk-publish.yml) GitHub Actions
workflow. It uses **Trusted Publishing** (OIDC) rather than long-lived API
tokens, so there are no secrets to rotate.

Any tag matching `sdk-v*` triggers a release. Pre-release tags (containing
`rc`, `a`, `b`, `dev`, `alpha`, or `beta`) publish to TestPyPI instead.

## One-time setup on PyPI

1. Sign in at <https://pypi.org> with an account that owns (or will own) the
   `gradata` project. If the project does not yet exist, add it as a
   **pending publisher** — PyPI promotes it to a real publisher on the first
   successful upload.
2. Go to **Your account → Publishing** (or, for an existing project, the
   *Manage → Publishing* tab).
3. **Add a new pending publisher** with:

   | Field              | Value             |
   |--------------------|-------------------|
   | PyPI Project Name  | `gradata`         |
   | Owner              | `Gradata`         |
   | Repository name    | `gradata`         |
   | Workflow name      | `sdk-publish.yml` |
   | Environment name   | *(leave blank)*   |

4. Save. PyPI now trusts this repo's `sdk-publish.yml` workflow to publish
   the `gradata` distribution.

## One-time setup on TestPyPI

Mirror the same configuration at <https://test.pypi.org> so release
candidates (e.g. `sdk-v0.5.1rc1`) publish to TestPyPI.

## Cutting a release

1. **Bump the version** in `pyproject.toml`:

   ```toml
   [project]
   name = "gradata"
   version = "0.5.1"
   ```

   The publish workflow fails fast if the git tag does not match this value.

2. **Update `CHANGELOG.md`** with the changes under a new heading, e.g.
   `## [0.5.1] - 2026-04-20`.

3. **Commit** to `main` (directly or via PR):

   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "release: gradata 0.5.1"
   git push origin main
   ```

4. **Tag and push**:

   ```bash
   git tag sdk-v0.5.1 -m "gradata v0.5.1"
   git push origin sdk-v0.5.1
   ```

5. **Watch the workflow** at
   <https://github.com/Gradata/gradata/actions/workflows/sdk-publish.yml> —
   the `build` job validates + builds, then `publish-pypi` uploads via OIDC.

6. **Verify**:

   ```bash
   pip install --upgrade gradata
   python -c "import gradata; print(gradata.__version__)"
   gradata --version
   ```

## Release candidates (TestPyPI)

```bash
# Bump pyproject.toml to 0.5.1rc1, commit, then:
git tag sdk-v0.5.1rc1 -m "gradata v0.5.1rc1"
git push origin sdk-v0.5.1rc1

# Install from TestPyPI:
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            --upgrade gradata==0.5.1rc1
```

## Idempotency & rollback

Re-pushing a tag whose version already exists on the target index is a
no-op — the `build` job detects the existing version and skips the publish
job. Bump `pyproject.toml` and retag to actually ship.

PyPI does not permit re-uploading a version number. If a broken release
ships: yank it on PyPI (*Manage project → Releases → Yank*), bump to the
next patch, fix, retag, publish.

## Local dry run

```bash
uv build
ls dist/
# Expect: gradata-<version>-py3-none-any.whl  gradata-<version>.tar.gz

# Optional: install and smoke-test the wheel in a clean venv
uv venv .venv-release
source .venv-release/bin/activate   # Windows: .venv-release\Scripts\activate
uv pip install dist/gradata-*.whl
python -c "import gradata; print(gradata.__version__)"
```

## Why Trusted Publishing

- **No API tokens** in GitHub Secrets — nothing to leak, rotate, or revoke.
- **Workflow-scoped** — only `sdk-publish.yml` on this repo can publish. A
  compromised PR cannot exfiltrate a token because there is no token.
- **Auditable** — every upload is linked to the specific workflow run.

See the PyPI docs: <https://docs.pypi.org/trusted-publishers/>.

The publishing job **must** declare:

```yaml
permissions:
  id-token: write  # OIDC — required for Trusted Publishing
  contents: read
```

`sdk-publish.yml` already does this on both `publish-pypi` and
`publish-testpypi`. Do not remove these blocks.

## Troubleshooting

- **`invalid-publisher`** — the repo name, workflow filename, or environment
  does not match the pending publisher. Double-check spelling and case.
- **`403 Forbidden`** — the job is missing `id-token: write`. Add it under
  `permissions:`.
- **`File already exists`** — PyPI refuses re-uploads of the same version.
  Bump `pyproject.toml` and retag.

## Test matrix

Every push or PR touching `src/gradata/**`, `tests/**`, or `pyproject.toml`
triggers [`sdk-test.yml`](../../.github/workflows/sdk-test.yml) on
Python 3.11, 3.12, and 3.13. The publish workflow does not gate on this —
it runs its own test suite before building.
