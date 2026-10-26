#!/usr/bin/env bash
set -euo pipefail
declare -A before
for pkg in packages/*/package.json; do before[$pkg]=$(jq -r .version "$pkg"); done
bunx changeset version >/dev/null 2>&1 || true
bumped=0
for pkg in packages/*/package.json; do
  dir=$(dirname "$pkg"); name=$(jq -r .name "$pkg"); new=$(jq -r .version "$pkg"); old=${before[$pkg]}
  [ "$new" = "$old" ] && continue
  bumped=1
  if [ "${new%%.*}" != "${old%%.*}" ]; then
    echo "### $name $old → $new (**MAJOR release**)"
  else
    echo "### $name $old → $new"
  fi
  awk -v v="## $new" 'BEGIN{p=0} $0==v{p=1;next} /^## /{if(p)exit} p' "$dir/CHANGELOG.md"
  echo
done
if [ $bumped -eq 0 ]; then
  echo "No pending changesets. Merging bumps no version and creates no release."
fi
