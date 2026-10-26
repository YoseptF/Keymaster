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

One JSON file, read by every package, written by the core installer and by the standalone app's
language control:

- Linux: `$XDG_CONFIG_HOME/keymaster/settings.json` (default `~/.config/keymaster/settings.json`)
- Windows: `%APPDATA%\Keymaster\settings.json`

    {
      "python": "/abs/path/to/core/.venv/bin/python",
      "core": "/abs/path/to/packages/core",
      "language": "auto"
    }

`python` and `core` are written by `setup`. `language` is optional (see Language). Writers keep
keys they do not know. Environment overrides, in priority order over the file: `KEYMASTER_PYTHON`,
`KEYMASTER_CORE`, `KEYMASTER_LANGUAGE` (see Language), and `KEYMASTER_SETTINGS` (path of the
file itself).

## Language

Every package shows text in `en` or `es-419` and resolves which one the same way, first match wins:

1. `KEYMASTER_LANGUAGE` in the environment, unless empty or `auto`
2. `language` in settings.json, when it is `en` or `es-419` (`auto`, missing or anything else
   falls through)
3. the host's UI language: Blender `bpy.app.translations.locale`; After Effects and Premiere the
   CSInterface host environment `appUILocale`; OpenFX hosts (Resolve, Nuke), the standalone app and
   the core CLI use the OS UI language: `LC_ALL`, then `LC_MESSAGES`, then `LANG` on Linux
   (`C`/`POSIX` count as unset), `GetUserDefaultUILanguage` on Windows

The value found is mapped: anything starting with `es` becomes `es-419`, everything else `en`.
Only the standalone app shows a language control; it writes `language` (`auto`, `en` or `es-419`).
Host plugins show none and follow their host. A host applies a change at its next natural refresh
point (panel redraw, next launch).

## Calling the core

    <python> -m keymaster <command> [args] --json

run with the working directory set to `<core>`. Hosts always pass absolute paths (relative ones
are resolved against the working directory). With `--json`, stdout carries one JSON object per
line and nothing else; everything else, including the upstream runtime's own prints and ffmpeg,
goes to stderr. Without `--json` stdout stays empty (except for `settings`, which always prints
its JSON there) and the events are printed to stderr as translated text, for people running the
CLI by hand.

Exit code 0 on success, 1 on failure (the last stdout line is then an `error` event; `doctor` is
the one exception, see below), 130 when cancelled (the last line is then an `error` event with
`core.error.cancelled` if the pipe is still open). Hosts cancel by terminating the process; on
SIGTERM, SIGINT (and SIGBREAK on Windows) the core stops, closes its writers and deletes its temp
files. Temp files live in `<system temp>/keymaster-core/run-<pid>/`; a later run deletes leftover
`run-*` folders whose process is gone, so a Windows `TerminateProcess` leaves nothing behind for
long. Outputs written before a failure or cancel are left in the output folder, incomplete.

### `key`

    key --input PATH --output-dir DIR
        [--hint-first-frame PATH] [--hint-video PATH] [--hint-quality 0.95]
        [--despill 0.5] [--format exr|video] [--outputs alpha fg cutout checker]
        [--start-frame S] [--frames N] [--low-vram] --json

`--input` is a video file or a directory of image frames. In a directory, the frames are every
`*.exr`, `*.png`, `*.jpg` and `*.jpeg` file directly inside it, ordered by plain lexicographic sort
of their full paths (extensions mixed; zero-pad your numbers). Defaults: `--format exr`,
`--outputs alpha fg cutout`, `--start-frame 0`, `--frames 0`.

Frame ranges: frames are counted 0-based in source order (decode order of the video, sorted order
of the directory), the number in a file name does not matter. `--start-frame S` keys from source
frame S; `--frames N` keys the N frames S..S+N-1, clamped to the end of the source; `0` means
"through the last frame". S past the last frame is `core.error.invalid_arguments`.

Hints are indexed like the source: `--hint-video` (a video or a frame directory) must have at
least as many frames as the source, and its frame S is used for source frame S.
`--hint-first-frame` is a single matte image (or a directory, whose first file is used) applied to
the first keyed frame, frame S. `--hint-quality` (0..1) is how much the model trusts the hints.
`--despill` (0..1) is the despill strength for `cutout` and `checker`. `--low-vram` runs the staged
low-memory path; without it the window size and low-memory mode are chosen from free GPU memory.

Events:

    {"event": "start", "input": "...", "first_frame": 0, "frames": 120, "width": 1920, "height": 1080, "fps": 24.0}
    {"event": "progress", "phase": "load|prepass|stage1|stage2|write", "fraction": 0.42, "message_key": "core.progress.stage1"}
    {"event": "output", "kind": "alpha|fg|cutout|checker", "type": "image_sequence|video", "path": "<dir or file>", "pattern": "<printf pattern, image_sequence only>", "first_frame": 0, "frames": 120}
    {"event": "done", "outputs": [<the output events' objects>], "seconds": 81.2}
    {"event": "error", "message_key": "core.error.<code>", "params": {...}, "detail": "<raw text for logs>"}

`start.frames` and `output.frames` are the number of keyed frames; `first_frame` (in both) is the
source frame index of the first keyed frame, that is S. For image sequences it is also the number
of the first file: files are numbered by source frame index, so `pattern % (first_frame + i)` is
the result for source frame `first_frame + i`. For video outputs, the video's frame 0 is source
frame `first_frame`. `width`/`height` are the output size (the source size). Frame-directory
inputs report `fps` 24.

`fraction` is overall progress in [0, 1] and never decreases; phases arrive in the order listed,
but in the normal (not low-VRAM) path stage 1 and stage 2 interleave, so `stage1` and `stage2`
events can alternate. Hosts show `t(message_key)` for progress and errors; `message_key`s live in
`packages/core/i18n`, and every host bundles that table next to its own so it can translate them.
All `output` events come after the last `progress` event (fraction 1.0) and before `done`.

Output names (`<clip>` is the input file or folder name without its extension, or the parent
folder's name when that name is `input`, `frames` or `rgb`):

| kind | `--format exr` (path / pattern) | `--format video` |
|---|---|---|
| alpha | `<clip>_alpha_exr/` / `alpha_%06d.exr`, 1 channel | `<clip>_alpha.mp4` (grey) |
| fg | `<clip>_fg_exr/` / `fg_%06d.exr`, RGB | `<clip>_fg.mp4` |
| cutout | `<clip>_cutout_exr/` / `cutout_%06d.exr`, RGBA | `<clip>_cutout.mov` (ProRes 4444 with alpha) |
| checker | `<clip>_checker_comp_despillNNN_exr/` / `checker_comp_despillNNN_%06d.exr`, RGB | `<clip>_checker_comp_despillNNN.mp4` |

`NNN` is `--despill` × 100, zero-padded. Hosts must use the `path`/`pattern` from the events
rather than rebuild them. The folder also gets `<clip>_settings.txt`, the runtime's log of the
settings used. EXR outputs are half-float, scene-linear and unclamped (alpha clamped to 0..1);
`cutout` is straight (unpremultiplied) RGBA, `alpha` single channel, `fg` RGB. Video outputs are
display-referred sRGB previews: x264 4:4:4 10-bit, cutout ProRes 4444.

Error codes (`core.error.<code>`, with `params`):

| code | when | params |
|---|---|---|
| `no_gpu` | no CUDA GPU | |
| `ffmpeg_missing` | `--format video` and no ffmpeg on PATH | |
| `weights_missing` | models not downloaded | `missing` (comma list of `corridorkey`, `cradio`, `moge`, `rvm`) |
| `input_unreadable` | input or hint missing or undecodable | `path` |
| `output_unwritable` | output folder cannot be created or written | `path` |
| `out_of_memory` | GPU out of memory | |
| `disk_full` | no space left | |
| `encode_failed` | ffmpeg failed writing a video | |
| `dependency_missing` | a Python package is missing (`setup`, `key`) | `name` |
| `download_failed` | `setup` could not fetch a model | `asset` |
| `invalid_arguments` | bad or missing flags, values out of range | `problem` |
| `invalid_setting` | `settings set` with an unknown key or value | `key`, `value` |
| `cancelled` | SIGTERM / Ctrl-C | |
| `unknown` | anything else; `detail` has the exception | |

### `doctor`

    {"event": "doctor", "ok": false, "checks": [{"id": "gpu|ffmpeg|weights|torch", "ok": true, "message_key": "core.doctor.<id>_ok|<id>_missing", "params": {...}}]}

Checks always come in the order gpu, ffmpeg, weights, torch. Params: `gpu_ok` `name`, `memory`
(GiB); `ffmpeg_ok` `path`; `weights_ok` `path`; `weights_missing` `missing`; `torch_ok` `version`,
`cuda`. When the checks could run, the doctor event is the only line. Exit code 0 when `ok` is true, 1 when it is
false (no `error` event follows).

### `setup`

Downloads the models into `<core>/upstream/weights` and `<core>/upstream/vfms` with upstream's
`scripts/download_weights.py`, skipping each model already present (nothing is fetched when all
are), then writes `python` (the running interpreter) and `core` into the settings file and ends
with `done` (`outputs` empty). Progress events have `phase` `download` and `message_key`
`core.progress.download_<corridorkey|cradio|moge|rvm>`, ending with `core.progress.download_done`
at fraction 1.0; the fraction follows the bytes downloaded. Needs network the first time.

### `settings`

`settings get [key]` prints the effective settings object, or one value, as one JSON line: the
file merged with `KEYMASTER_PYTHON`/`KEYMASTER_CORE`, and `language` resolved per Language (always
`en` or `es-419`). `settings set <key> <value>` accepts `language` (`auto`, `en`, `es-419`),
`python` and `core`, writes the file and prints the stored file contents; anything else is
`core.error.invalid_setting`.

## Installing the core

`packages/core/install.sh` (Linux) and `install.ps1` (Windows) create `<core>/.venv` with Python
3.12 or 3.13 (through `uv` when present), install `torch==2.9.1`, `torchvision==0.24.1` from the
CUDA 12.8 wheel index and `upstream/requirements.txt`, then run `setup` and `doctor`. Both are
safe to run again.

## The fake core

`packages/core/testing/fake_core/keymaster/` is a stand-in with the same CLI and events that runs
instantly with only the Python standard library. It writes tiny PNG sequences named
`<stem>_<kind>/<kind>_%06d.png` (numbered from `--start-frame`), or for `--format video` a
placeholder file, and supports `KEYMASTER_FAKE_FAIL=<code>` to end with that error (`cancelled`
exits 130) and `KEYMASTER_FAKE_DELAY=<seconds per event>`. For `doctor`, `KEYMASTER_FAKE_FAIL`
fails the matching check (`no_gpu`, `ffmpeg_missing`, `weights_missing`, `dependency_missing`
for torch, anything else gpu) and exits 1. Host tests point `KEYMASTER_CORE` at
`packages/core/testing/fake_core` and `KEYMASTER_PYTHON` at any Python 3. The core's own tests
check that the fake's flags and event fields match the real core.

## Real-model runs

Only on a machine with an NVIDIA GPU, never in CI. Anything that runs the real model takes the
lock first so two runs never share the GPU: `flock /tmp/keymaster-gpu.lock <command>`.
