# How changes ship

Two locked branches. Everything else is a short-lived branch.

| Branch | Is | Gets changes from | Publishes |
|---|---|---|---|
| `release` | staging, the next release in the making | pull requests from feature branches | the `staging` pre-release on GitHub, rebuilt on every merge |
| `main` | production | one pull request from `release` | a GitHub release per package whose version changed |

## Day to day

1. Branch off `release`. Commit as often as you like, one short plain sentence per commit.
2. If a user would notice the change, add a changeset in the same branch: `bun run changeset`.
   Pick the package, the bump, and write the changelog sentence in English, then a second line
   `es-419: ` with the same sentence in Latin American Spanish. Refactors, tests and tooling need
   none; code changed with nothing to tell users? `bun run changeset --empty`.
3. Open a PR into `release`. CI runs the tests, the language check and the builds, and refuses
   the PR if a package changed without a changeset. It also comments download links for this PR's
   builds (see below). Merge when green. Merging means "this ships next".

## Two languages, always

Everything a user sees ships in English (the default) and Latin American Spanish (`es-419`).
`bun run check:i18n` runs the same check CI does. It fails when:

- a package's `i18n/en.json` and `i18n/es-419.json` differ in keys or placeholders, or a value is empty
- code uses a key that does not exist, or a key exists that no code uses
- text is written straight into a UI call (labels, buttons, dialogs, HTML text) instead of going
  through the package's `t("key")`
- a user-facing `README.md` has no `README.es-419.md` next to it

Keys start with the package name: `blender.panel.title`, `core.error.no_gpu`. The language a user
picks is stored once in the shared Keymaster settings, so every host follows it. A literal that
is genuinely not user text (a file extension, a node class name) goes in that package's
`i18n/allow.txt` as `<path>: <the flagged text>`.

## Previews

Every PR into `release` builds every package and attaches the files to the run. A comment on the
PR links them and is updated on every push. They are kept 14 days.

## Bump rules

| Bump | Means for Keymaster | Who decides |
|---|---|---|
| major (`1.0.0`, `2.0.0`) | an event: a deliberate release, usually with breaking changes (removed option, changed output layout or file names, settings format change, new minimum host version) | the maintainer only: CI refuses a major changeset unless the PR has the `major-release` label |
| minor (`1.x.0`) | anything new: options, outputs, hosts, behaviour changes that break nobody | whoever writes the change |
| patch (`1.x.y`) | same behaviour, better: fixes, wording, speed, translations | whoever writes the change |

Between minor and patch, either is fine. A breaking change without a planned major waits, or goes
behind an option, until the maintainer schedules the major.

## Releasing

Every merge into `release` rebuilds the `staging` pre-release on GitHub. Nothing is versioned yet:
the changesets pile up in `.changeset/` until you ship.

1. Open `release` → `main`. CI comments on the PR what the merge will release: each package's new
   version and its changelog text.
2. Merge it. Actions turns the pending changesets into version bumps and changelog entries,
   commits "Version packages" to `main` and fast-forwards `release` to match, builds every package,
   tags `<package>@<version>` and creates a GitHub release with that package's files.

Nobody chooses a version number and nobody publishes from a laptop. If `release` moved in the
meantime, Actions opens a "Sync the version commit into release" PR instead; merge it before the
next release.

## Commit messages

One line, natural language, no type prefixes, no trailers, no tool attribution.

## Code

No code comments. The models are never committed: `packages/core/upstream/weights` and `vfms`
are ignored and filled by the core's download script. `packages/core/upstream` is an unmodified
copy of CorridorKey at the revision in `upstream/REVISION`; Keymaster's own code lives beside it.
