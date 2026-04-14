# PyPI Trusted Publisher Setup

This repository publishes the `gradata` package to PyPI using **Trusted
Publishing** (OIDC) rather than long-lived API tokens. The GitHub Actions
workflow proves its identity to PyPI via GitHub's OIDC provider, so PyPI
mints a short-lived token at publish time. There are no secrets to rotate.

## One-time setup on PyPI (production)

1. Sign in at https://pypi.org with an account that owns (or will own) the
   `gradata` project. If the project does not yet exist, you will add it as a
   **pending publisher** — PyPI promotes it to a real publisher on the first
   successful upload.
2. Go to **Your account → Publishing** (or the project's *Manage → Publishing*
   tab if the project already exists).
3. Click **Add a new pending publisher** and fill in:

   | Field                 | Value                    |
   |-----------------------|--------------------------|
   | PyPI Project Name     | `gradata`                |
   | Owner                 | `Gradata`                |
   | Repository name       | `gradata`                |
   | Workflow name         | `sdk-publish.yml`        |
   | Environment name      | *(leave blank)*          |

4. Save. PyPI now trusts the
   `Gradata/gradata` repository's `sdk-publish.yml` workflow to publish the
   `gradata` distribution.

5. Push a `sdk-vX.Y.Z` tag (see [`RELEASE.md`](./RELEASE.md)). The first
   successful run promotes the pending publisher to active.

## One-time setup on TestPyPI (release candidates)

Release candidates (tags like `sdk-v0.5.1rc1`) publish to TestPyPI. Mirror the
same configuration there:

1. Sign in at https://test.pypi.org.
2. **Your account → Publishing → Add a new pending publisher** with the same
   values as above — `gradata`, `Gradata/gradata`, `sdk-publish.yml`, no
   environment.
3. Push a pre-release tag (`sdk-v0.5.1rc1`) to validate.

## Why Trusted Publishing

- **No API tokens** in GitHub Secrets — nothing to leak, rotate, or revoke.
- **Workflow-scoped** — only `sdk-publish.yml` on this repo can publish. A
  compromised PR cannot exfiltrate a token because there is no token.
- **Auditable** — every upload is linked to the specific workflow run on GitHub.

See the PyPI docs:
https://docs.pypi.org/trusted-publishers/

## Required workflow permissions

The workflow job that publishes **must** declare:

```yaml
permissions:
  id-token: write  # OIDC — required for Trusted Publishing
  contents: read
```

`sdk-publish.yml` in this repo already does this on the `publish-pypi` and
`publish-testpypi` jobs. Do not remove these blocks.

## Verifying setup

After pushing your first real tag:

1. Workflow page: https://github.com/Gradata/gradata/actions/workflows/sdk-publish.yml
2. Expand the `publish-pypi` (or `publish-testpypi`) job and confirm the
   `Publish to PyPI` step succeeded.
3. PyPI project page: https://pypi.org/project/gradata/ — the new version
   should appear within seconds of the step finishing.

## Troubleshooting

- **`invalid-publisher`** — the repo name, workflow filename, or environment
  does not match the pending publisher. Double-check spelling and case.
- **`403 Forbidden`** — the job is missing `id-token: write`. Add it under
  `permissions:`.
- **`File already exists`** — PyPI will not accept a re-upload of the same
  version. Bump `pyproject.toml` and retag.
