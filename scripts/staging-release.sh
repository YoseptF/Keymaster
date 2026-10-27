#!/usr/bin/env bash
set -euo pipefail
if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
  echo "error: $(basename "$0") publishes release files and only runs inside GitHub Actions. Release files are built by CI only, see 'Releases are built by CI only' in CONTRIBUTING.md." >&2
  exit 1
fi
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shopt -s nullglob
files=(dist/keymaster-installer-*)
for file in dist/*; do
  case "$file" in dist/keymaster-installer-*) ;; *) files+=("$file") ;; esac
done
shopt -u nullglob
notes="$(bash "$here/installer-notes.sh" dist)

The current state of the release branch, built from ${GITHUB_SHA:0:7}. Replaced on every merge into release."
gh release delete staging --yes --cleanup-tag >/dev/null 2>&1 || true
gh release create staging --prerelease --target "$GITHUB_SHA" --title "Staging build ${GITHUB_SHA:0:7}" \
  --notes "$notes" "${files[@]}"
