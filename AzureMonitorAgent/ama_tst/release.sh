#!/usr/bin/env bash
# Release the AMA Troubleshooting Tool to GitHub.
# Run from the root of an Azure/azure-linux-extensions clone.
set -euo pipefail

REPO="Azure/azure-linux-extensions"
TST_DIR="AzureMonitorAgent/ama_tst"
RELEASE_NOTES="${1:-}"  # optional: one-line summary for the release body

# 0. Check prerequisites.
if [[ "$(git rev-parse --show-toplevel 2>/dev/null)" != "$(pwd -P)" ]]; then
    echo "ERROR: You must run this script from the root of the repository." >&2
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI ('gh') is not installed. Please install it first." >&2
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI is not authenticated. Please run 'gh auth login' first." >&2
    exit 1
fi

ORIGIN_URL=$(git remote get-url origin 2>/dev/null || true)
if [[ "$ORIGIN_URL" != *"$REPO"* ]]; then
    echo "ERROR: You must be in a clone of ${REPO} whose 'origin' points to that repo." >&2
    exit 1
fi

# 1. Sync to the latest master.
git checkout master
git pull --ff-only origin master

# 2. Read the version from the source of truth.
VERSION=$(sed -n 's/^TST_VERSION="\([^"]*\)".*/\1/p' "${TST_DIR}/ama_troubleshooter.sh")
if [[ -z "${VERSION}" ]]; then
    echo "ERROR: could not parse TST_VERSION from ${TST_DIR}/ama_troubleshooter.sh" >&2
    exit 1
fi
TAG="ama_tst-${VERSION}"
ASSET="ama_tst-${VERSION}.tgz"
echo "Preparing release ${TAG} (asset: ${ASSET})"

# 3. Refuse to clobber an existing release.
if gh release view "${TAG}" --repo "${REPO}" >/dev/null 2>&1; then
    echo "ERROR: release ${TAG} already exists on ${REPO}." >&2
    exit 1
fi

# 4. Build the archive cleanly from HEAD (no untracked files leak in).
WORKDIR=$(mktemp -d)
trap 'rm -rf "${WORKDIR}"' EXIT
git archive --format=tar HEAD "${TST_DIR}" | tar -x -C "${WORKDIR}"

# Remove the release script itself so it doesn't get packaged into the archive
rm -f "${WORKDIR}/${TST_DIR}/release.sh"

tar -czvf "${ASSET}" -C "${WORKDIR}/AzureMonitorAgent" ama_tst
echo "Built $(pwd)/${ASSET} ($(wc -c <"${ASSET}") bytes)"

exit 0

# 5. Create the GitHub release and upload the asset.
gh release create "${TAG}" "${ASSET}" \
    --repo "${REPO}" \
    --target master \
    --title "AMA Troubleshooter v${VERSION}" \
    --notes "${RELEASE_NOTES:-Release ${TAG}}"

# 6. Verify and print the public download URL.
gh release view "${TAG}" --repo "${REPO}"
echo "Download URL: https://github.com/${REPO}/releases/download/${TAG}/${ASSET}"
