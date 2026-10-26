# Changesets

One file here per user-visible change, added in the same PR as the change. It names the package
(`keymaster`), the bump (patch, minor, major) and one sentence written for the person reading the
changelog. Many commits can share one file.

    bun run changeset            # interactive
    bun run changeset --empty    # "this PR changes code but has nothing to tell users"

CI refuses a PR into `release` that touches `core/` or `hosts/` without a file here. The bump
rules and the release flow are in CONTRIBUTING.md.
