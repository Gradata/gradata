# Gradata SDK Release Process

The Gradata SDK (`gradata` on PyPI) publishes automatically when a tag matching
`sdk-v*` is pushed to GitHub. The workflow lives at
[`.github/workflows/sdk-publish.yml`](../.github/workflows/sdk-publish.yml) and
uses PyPI Trusted Publishing (OIDC) — no API tokens are stored in GitHub
secrets.

## Package layout

- Package name on PyPI: **`gradata`**
- Source of truth: `pyproject.toml` at the repository root
- Source tree: `src/gradata/`
- Build backend: `hatchling`
- Build driver (CI + local): `uv build`

## Prerequisites (one time)

1. Configure the PyPI Trusted Publisher — see [`PYPI-SETUP.md`](./PYPI-SETUP.md).
2. Configure the TestPyPI Trusted Publisher (same file) if you plan to publish
   release candidates.

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

3. **Commit** to the default branch (or merge via PR):

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
   https://github.com/Gradata/gradata/actions/workflows/sdk-publish.yml —
   the `build` job validates + builds, then `publish-pypi` uploads via OIDC.

6. **Verify**:

   ```bash
   pip install --upgrade gradata
   python -c "import gradata; print(gradata.__version__)"
   gradata --version
   ```

## Release candidates (TestPyPI)

Any tag containing `rc`, `a`, `b`, `dev`, `alpha`, or `beta` is treated as a
pre-release and publishes to **TestPyPI** instead of PyPI. The `pyproject.toml`
version must still match.

```bash
# Bump pyproject.toml to 0.5.1rc1, commit, then:
git tag sdk-v0.5.1rc1 -m "gradata v0.5.1rc1"
git push origin sdk-v0.5.1rc1

# Install from TestPyPI:
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            --upgrade gradata==0.5.1rc1
```

## Idempotency

Re-pushing the same tag (or pushing a tag whose version is already on the
target index) does **not** error. The `build` job queries
`pypi.org/pypi/gradata/json` (or the TestPyPI equivalent) and, if the version
already exists, skips the publish job with a warning. Bump `pyproject.toml` and
retag to actually ship.

## Rolling back

PyPI does not permit re-uploading a version number. If a broken release ships:

1. Yank it on PyPI (Manage project → Releases → Yank).
2. Bump to the next patch (e.g. `0.5.2`), fix, retag, publish.

## Local dry run

Before tagging, verify the build locally:

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

## Test matrix (separate workflow)

Every push or PR touching `src/gradata/**`, `tests/**`, or `pyproject.toml`
triggers [`sdk-test.yml`](../.github/workflows/sdk-test.yml) on Python 3.11,
3.12, and 3.13. The publish workflow does not gate on this — it runs its own
test suite before building.
