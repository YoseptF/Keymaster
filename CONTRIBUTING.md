# How changes ship

One long-lived branch, `main`. Everything else is a short-lived branch that merges into it. People
never download a branch: they download GitHub releases, and every release is a release candidate
first.

## Day to day

1. Branch off `main`. Commit as often as you like, one short plain sentence per commit.
2. If a user would notice the change, add a changeset in the same branch: `bun run changeset`.
   Pick the package, the bump, and write the changelog sentence in English, then a second line
   `es-419: ` with the same sentence in Latin American Spanish. Refactors, tests and tooling need
   none; code changed with nothing to tell users? `bun run changeset --empty`.
3. Open a PR into `main`. CI runs the tests, the language check and the builds, and refuses
   the PR if a package changed without a changeset. It also comments download links for this PR's
   builds (see below). Merge when green. Merging means "this ships in the next release candidate".

Every merge into `main` runs the tests and builds every package again. The files stay on that
workflow run for 3 days; nothing is published.

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

Every PR into `main` builds every package and attaches the files to the run. A comment on the
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

Changesets pile up in `.changeset/` on `main` until a release. Releasing is always: cut a release
candidate, friends test it, promote it.

1. **Cut a release candidate.** Actions, "Cut release candidate", Run workflow (it builds `main`
   unless you give another `ref`). It fails if there are no pending changesets. Otherwise it works
   out the next versions from them (nothing is committed), builds every package once with those
   versions inside, names the files `…-<version>-rc.<N>…`, tags the commit `v<version>-rc.<N>` and
   publishes the pre-release "Keymaster `<version>` RC `<N>`": installers first, then the
   per-package zips, then `SHA256SUMS`, with the install instructions and the release notes (one
   line per changeset, per package, linked to its PR and author, English and Spanish).
2. **Friends test it.** Send them the pre-release.
3. **Promote it.** Actions, "Promote release candidate", Run workflow (an empty `rc` means the
   newest candidate). It downloads that candidate's files, checks them against its `SHA256SUMS`,
   drops `-rc.<N>` from the names, commits "Version packages" to `main` (new versions and
   changelogs, from only the changesets that were in that candidate), tags the candidate's commit
   `v<version>` and `<package>@<version>` for every package that changed, publishes the release
   "Keymaster `<version>`" as the latest one and deletes that version's pre-releases (their tags
   stay).

`<version>` is the installer's version, because the installer is what users download. When no
pending changeset bumps `keymaster-installer`, the cut gives it a patch ("Bundles the updated
packages.") so every release has a new version. A major bump is announced as MAJOR in the cut's
run. Changesets merged after a candidate was cut stay pending for the next release.

Hotfix: something broke in the candidate? Fix it on `main` with a normal PR and changeset, then cut
again. You get `rc.<N+1>`; promote the candidate that passed.

### Build once, promote

What people get is the candidate friends tested, byte for byte. A release is never rebuilt:
promoting only renames the candidate's files. That is why the files carry the final version inside
(manifests, `package.json` versions, installer metadata) and only their names say `rc`. Both
releases' `SHA256SUMS` list the same hashes, under the two names.

Nobody chooses a version number and nobody publishes from a laptop.

## Releases are built by CI only

Nothing people download is built or uploaded by hand.

- What builds it: the Build workflow (`.github/workflows/build.yml`) runs `scripts/package.py`,
  which runs every package's `build.py`, including the one-click installers in
  `packages/installer`. For a release candidate it first stamps the computed versions into the
  packages (`scripts/release.py stamp`). The workflow installs the tools it needs (CMake, MinGW,
  NSIS) itself.
- Where it runs: on the local-ci self-hosted runner (`vars.CI_RUNNER`), never by hand.
- Where it is published: PR and `main` builds as workflow artifacts, release candidates as
  pre-releases (`scripts/release.py cut-publish`, only the files the build job of the same run
  produced), releases by promoting a candidate (`scripts/release.py promote`, only that candidate's
  own files, checked against its `SHA256SUMS`). Every push and every release change in
  `scripts/release.py` refuses to run outside GitHub Actions.
- Local builds (`bun run build`, a package's `build.py`) are for testing only. Never upload them.
- To add a release file, make a package's `build.py` write it into `--out`. Nothing else is needed:
  CI builds, collects and publishes it.
- The release scripts are tested in `scripts/tests` (`bun run test`), including a dry run of both
  workflows against a throwaway repository and a fake `gh`. They opt in with
  `KEYMASTER_RELEASE_TEST=1`, which only works when `origin` is a local path and `KEYMASTER_GH`
  points at a stand-in for `gh`.

### Leftovers from the old flow

The `release` branch and the `staging` pre-release belong to the flow this one replaced. Once this
flow is on `main`: make `main` the default branch, drop `release` from the "Locked branches"
ruleset, delete the `release` branch, and delete the staging box with
`gh release delete staging --yes --cleanup-tag`.

## Commit messages

One line, natural language, no type prefixes, no trailers, no tool attribution.

## Code

No code comments. The models are never committed: `packages/core/upstream/weights` and `vfms`
are ignored and filled by the core's download script. `packages/core/upstream` is an unmodified
copy of CorridorKey at the revision in `upstream/REVISION`; Keymaster's own code lives beside it.
