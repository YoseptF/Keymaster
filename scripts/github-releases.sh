#!/usr/bin/env bash
set -euo pipefail
if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
  echo "error: $(basename "$0") publishes release files and only runs inside GitHub Actions. Release files are built by CI only, see 'Releases are built by CI only' in CONTRIBUTING.md." >&2
  exit 1
fi
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
installer_tag="keymaster-installer@$(jq -r .version packages/installer/package.json)"
for pkg in packages/*/package.json; do
  dir=$(dirname "$pkg"); name=$(jq -r .name "$pkg"); version=$(jq -r .version "$pkg"); tag="$name@$version"
  git rev-parse -q --verify "refs/tags/$tag" >/dev/null || continue
  gh release view "$tag" >/dev/null 2>&1 && continue
  notes=$(awk -v v="## $version" 'BEGIN{p=0} $0==v{p=1;next} /^## /{if(p)exit} p' "$dir/CHANGELOG.md" 2>/dev/null || true)
  if [ "$tag" = "$installer_tag" ]; then
    header="$(bash "$here/installer-notes.sh" dist)"
  else
    header="$(INSTALLER_URL="https://github.com/${GITHUB_REPOSITORY:-YoseptF/Keymaster}/releases/tag/${installer_tag/@/%40}" bash "$here/installer-notes.sh" dist)"
  fi
  shopt -s nullglob
  files=(dist/"$name-$version"*)
  shopt -u nullglob
  gh release create "$tag" --title "$tag" --notes "$header

${notes:-No changelog entry.}" "${files[@]}"
  echo "released $tag"
done
