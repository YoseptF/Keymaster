# Architecture

Keymaster is a monorepo. `packages/core` runs the model; every other package is a thin host
integration that calls the core as a separate process and brings the results back into its host.
No host package imports torch or touches the model directly.

    packages/
      core/       Python runtime + CLI (`python -m keymaster`), installers, upstream CorridorKey copy
      app/        standalone desktop app (PySide6), runs on the core's Python
      openfx/     C++ OpenFX plugin for DaVinci Resolve and Nuke (and any OFX host)
      blender/    Blender 5.x extension
      adobe/      one CEP panel for After Effects and Premiere Pro

Platforms: Linux and Windows. CorridorKey needs an NVIDIA CUDA GPU, so there is no macOS build.

## Every package has

- `package.json` with `name` (`keymaster-<dir>`), `version`, `"private": true`, and, for packages
  whose output differs per OS, `"keymaster": {"platforms": ["linux", "windows"]}`
- `build.py --out DIR --version V [--platform linux|windows]` writing its distributable(s) into
  DIR, every file named `keymaster-<dir>-<V>[-<platform>].<ext>`. Platform-independent packages
  get no `--platform` and are built once, on Linux.
- `test.sh`, run by `bun run test` from the repo root on a Linux CI runner without a GPU. Tests
  there use the fake core (below), never the real model.
- `i18n/en.json` and `i18n/es-419.json`, flat `{"<dir>.some.key": "text"}` tables, every key
  prefixed with the package directory name. All user-visible text goes through the package's
  `t("key")` (C++: `tr("key")`, HTML: `data-i18n="key"` / `data-i18n-title`, `-placeholder`).
  `scripts/check-i18n.py` enforces this; read it before writing UI code.
- `README.md` and `README.es-419.md`: what it is, how to install it, how to use it.
- No code comments anywhere.

## Shared settings

One JSON file, read by every package, written by the core installer and by any package's
language switch:

- Linux: `$XDG_CONFIG_HOME/keymaster/settings.json` (default `~/.config/keymaster/settings.json`)
- Windows: `%APPDATA%\Keymaster\settings.json`

    {
      "language": "en",
      "python": "/abs/path/to/core/.venv/bin/python",
      "core": "/abs/path/to/packages/core"
    }

`language` is `"en"` (default when missing or unknown) or `"es-419"`. Changing it in one host
changes it for all of them; a host applies it at its next natural refresh point (panel redraw,
next launch). Environment overrides, in priority order over the file: `KEYMASTER_PYTHON`,
`KEYMASTER_CORE`, `KEYMASTER_LANGUAGE`, `KEYMASTER_SETTINGS` (path of the file itself).

## Calling the core

    <python> -m keymaster <command> [args] --json

run with the working directory set to `<core>`. Hosts always pass absolute paths. With `--json`,
stdout carries one JSON object per line and nothing else; anything human-readable goes to stderr.
Exit code 0 on success, 1 on failure (the last stdout line is then an `error` event), 130 when
cancelled. Hosts cancel by terminating the process; the core cleans its temp files on SIGTERM and
on Windows `TerminateProcess` leaves nothing that the next run does not overwrite.

### `key`

    key --input PATH --output-dir DIR
        [--hint-first-frame PATH] [--hint-video PATH] [--hint-quality 0.95]
        [--despill 0.5] [--format exr|video] [--outputs alpha fg cutout checker]
        [--frames N] [--low-vram] --json

`--input` is a video file or a directory of image frames. Defaults: `--format exr`,
`--outputs alpha fg cutout`. Events:

    {"event": "start", "input": "...", "frames": 120, "width": 1920, "height": 1080, "fps": 24.0}
    {"event": "progress", "phase": "load|prepass|stage1|stage2|write", "fraction": 0.42, "message_key": "core.progress.stage1"}
    {"event": "output", "kind": "alpha|fg|cutout|checker", "type": "image_sequence|video", "path": "<dir or file>", "pattern": "<printf pattern, image_sequence only>", "first_frame": 0, "frames": 120}
    {"event": "done", "outputs": [<the output events' objects>], "seconds": 81.2}
    {"event": "error", "message_key": "core.error.<code>", "params": {...}, "detail": "<raw text for logs>"}

`fraction` is overall progress in [0, 1] and only grows. Hosts show `t(message_key)` for
progress and errors; `message_key`s live in `packages/core/i18n`, and every host bundles that
table next to its own so it can translate them. EXR outputs are scene-linear, `cutout` is
straight (unpremultiplied) RGBA, `alpha` single channel, `fg` RGB.

### `doctor`

    {"event": "doctor", "ok": false, "checks": [{"id": "gpu|ffmpeg|weights|torch", "ok": true, "message_key": "core.doctor.<id>_ok|<id>_missing", "params": {...}}]}

### `setup`

Downloads the models into `<core>/upstream/weights` and `<core>/upstream/vfms` (skipping what is
present), emitting `progress` events, then writes `python` and `core` into the settings file.

### `settings`

`settings get [key]` prints the settings object or one value; `settings set language es-419`.

## The fake core

`packages/core/testing/fake_core/keymaster/` is a stand-in with the same CLI and events that runs
instantly with only the Python standard library. It writes tiny PNG sequences (or, for
`--format video`, a placeholder file) and supports `KEYMASTER_FAKE_FAIL=<code>` to end with that
error, and `KEYMASTER_FAKE_DELAY=<seconds per event>`. Host tests point `KEYMASTER_CORE` at
`packages/core/testing/fake_core` and `KEYMASTER_PYTHON` at any Python 3.

## Real-model runs

Only on a machine with an NVIDIA GPU, never in CI. Anything that runs the real model takes the
lock first so two runs never share the GPU: `flock /tmp/keymaster-gpu.lock <command>`.
