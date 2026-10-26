#!/usr/bin/env bash
set -euo pipefail
for pkg in packages/*/package.json; do
  tag="$(jq -r .name "$pkg")@$(jq -r .version "$pkg")"
  [ "${tag##*@}" = "0.0.0" ] && continue
  git rev-parse -q --verify "refs/tags/$tag" >/dev/null && continue
  git tag "$tag"
  echo "tagged $tag"
done
