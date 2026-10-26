#!/usr/bin/env bash
set -euo pipefail
BASE=${BASE_SHA:-$(git merge-base HEAD origin/release)}
HEAD=${HEAD_SHA:-HEAD}
changed=$(git diff --name-only "$BASE" "$HEAD")
if ! grep -Eq '^packages/[^/]+/' <<<"$changed"; then echo "no package changed, no changeset needed"; exit 0; fi
added=$(git diff --name-only --diff-filter=A "$BASE" "$HEAD" | grep -E '^\.changeset/[^/]+\.md$' | grep -v README.md || true)
if [ -z "$added" ]; then
  echo "::error::this change touches packages/ but adds no .changeset/*.md file. Run 'bun run changeset' (or 'bun run changeset --empty' if there is nothing to tell users)."
  exit 1
fi
status=0
for file in $added; do
  body=$(awk 'BEGIN{n=0} /^---$/{n++; next} n>=2' "$file")
  [ -z "$(tr -d '[:space:]' <<<"$body")" ] && continue
  if ! grep -Eq '^es-419: .+' <<<"$body"; then
    echo "::error file=$file::changelog text needs a Spanish line too: add 'es-419: <la misma frase en español>' under the English sentence"
    status=1
  fi
done
[ $status -eq 0 ] && { echo "changesets added:"; echo "$added"; }
exit $status
