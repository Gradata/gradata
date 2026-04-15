#!/usr/bin/env bash
# publish-npm.sh — release @gradata/cli from packages/npm.
#
# Usage:
#   NPM_TOKEN=xxx ./scripts/publish-npm.sh            # publish current version
#   NPM_TOKEN=xxx ./scripts/publish-npm.sh --dry-run  # build + pack, no publish
#
# Requires:
#   - Node 18+
#   - NPM_TOKEN env var (an npm automation token with publish scope)
#
# This script is the manual fallback for the tag-triggered
# .github/workflows/npm-publish.yml. CI is the preferred path.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_DIR="${ROOT_DIR}/packages/npm"

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
fi

if [ ! -d "${PKG_DIR}" ]; then
  echo "error: ${PKG_DIR} not found" >&2
  exit 1
fi

cd "${PKG_DIR}"

if [ "${DRY_RUN}" -eq 0 ] && [ -z "${NPM_TOKEN:-}" ]; then
  echo "error: NPM_TOKEN env var is required (unset it and pass --dry-run to skip publish)" >&2
  exit 1
fi

VERSION=$(node -p "require('./package.json').version")
echo "==> Releasing @gradata/cli@${VERSION} from ${PKG_DIR}"

echo "==> Installing dependencies"
npm ci 2>/dev/null || npm install --no-audit --no-fund

echo "==> Typechecking"
npm run typecheck

echo "==> Testing"
npm test

echo "==> Building"
npm run build

echo "==> Packing (dry-run preview)"
npm pack --dry-run

if [ "${DRY_RUN}" -eq 1 ]; then
  echo "==> --dry-run: skipping npm publish"
  exit 0
fi

# Detect pre-release suffix.
DIST_TAG="latest"
case "${VERSION}" in
  *rc*|*alpha*|*beta*|*dev*|*-a.*|*-b.*)
    DIST_TAG="next"
    ;;
esac
echo "==> Publishing with dist-tag=${DIST_TAG}"

# Use a scoped auth config instead of writing ~/.npmrc.
npm config set "//registry.npmjs.org/:_authToken" "${NPM_TOKEN}"
trap 'npm config delete "//registry.npmjs.org/:_authToken" || true' EXIT

npm publish --access public --tag "${DIST_TAG}"
echo "==> Done: @gradata/cli@${VERSION} published to npm with dist-tag=${DIST_TAG}"
