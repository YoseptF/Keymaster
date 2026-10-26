#!/usr/bin/env bash
set -euo pipefail
for pkg in packages/*/package.json; do
  dir=$(dirname "$pkg"); name=$(jq -r .name "$pkg"); version=$(jq -r .version "$pkg"); tag="$name@$version"
  git rev-parse -q --verify "refs/tags/$tag" >/dev/null || continue
  gh release view "$tag" >/dev/null 2>&1 && continue
  notes=$(awk -v v="## $version" 'BEGIN{p=0} $0==v{p=1;next} /^## /{if(p)exit} p' "$dir/CHANGELOG.md" 2>/dev/null || true)
  shopt -s nullglob
  files=(dist/"$name-$version"*)
  shopt -u nullglob
  gh release create "$tag" --title "$tag" --notes "${notes:-No changelog entry.}" "${files[@]}"
  echo "released $tag"
done
