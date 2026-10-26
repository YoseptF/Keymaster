#!/usr/bin/env bash
set -euo pipefail
gh release delete staging --yes --cleanup-tag >/dev/null 2>&1 || true
gh release create staging --prerelease --target "$GITHUB_SHA" --title "Staging build ${GITHUB_SHA:0:7}" \
  --notes "The current state of the release branch, built from ${GITHUB_SHA:0:7}. Replaced on every merge into release." dist/*
