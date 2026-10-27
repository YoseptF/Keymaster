# Keymaster core

The engine behind every Keymaster host. It runs the CorridorKey 2.0 green-screen keyer
(an unmodified copy lives in `upstream/`) and gives the hosts one command line,
`python -m keymaster`, that speaks JSON. You only use it directly to install the models or to
key from a terminal.

## Requirements

- Linux or Windows with an NVIDIA GPU (RTX 30-series or newer, 4 GB of VRAM up to 1440p,
  6 GB for 4K) and a current NVIDIA driver
- `ffmpeg` on your PATH (needed for video outputs)
- `git`, plus Python 3.12 or 3.13, or [uv](https://docs.astral.sh/uv/), which fetches Python
  for you
- About 12 GB of disk: 7 GB for PyTorch and friends, 5 GB for the models

## Install

From this folder:

    ./install.sh                                        # Linux
    powershell -ExecutionPolicy Bypass -File install.ps1  # Windows

The installer creates `.venv`, installs PyTorch 2.9.1 (CUDA 12.8) and the CorridorKey
requirements, downloads the models into `upstream/weights` and `upstream/vfms`, saves where it
lives in the shared Keymaster settings so the hosts can find it, and finishes with a health check.
Running it again only fills in what is missing.

## Use

Run these from this folder with the environment's Python (`.venv/bin/python` on Linux,
`.venv\Scripts\python.exe` on Windows):

    python -m keymaster doctor
    python -m keymaster key --input /shots/plate.mov --output-dir /shots/keyed
    python -m keymaster key --input /shots/plate_frames --output-dir /shots/keyed \
        --format video --outputs alpha cutout checker --despill 0.7
    python -m keymaster key --input /shots/plate.mov --output-dir /shots/keyed \
        --start-frame 100 --frames 48 --low-vram
    python -m keymaster setup
    python -m keymaster settings get
    python -m keymaster settings set language es-419

`key` options:

| Option | Meaning |
|---|---|
| `--input` | a video file, or a folder of `.exr`/`.png`/`.jpg` frames |
| `--output-dir` | where the results go |
| `--format exr` | scene-linear half-float EXR sequences (default) |
| `--format video` | preview videos: MP4 for alpha, fg and checker, ProRes 4444 MOV for cutout |
| `--outputs` | any of `alpha fg cutout checker` (default `alpha fg cutout`) |
| `--despill` | green spill removal for cutout and checker, 0 to 1 (default 0.5) |
| `--start-frame`, `--frames` | key only part of the clip: from frame S (counting from 0), N frames |
| `--hint-first-frame` | a rough matte for the first keyed frame |
| `--hint-video` | a rough matte for every frame, as a video or a frame folder |
| `--hint-quality` | how much to trust the hints, 0 to 1 (default 0.95) |
| `--low-vram` | slower mode for small GPUs |

Add `--json` to get one JSON event per line on stdout, which is what the hosts read; the format
is described in `docs/ARCHITECTURE.md` at the root of the repository. Without it, progress and
results are printed as text in your language. Messages follow your system language unless you set
one with `settings set language en|es-419` (or `auto` to follow the system again).

To use an ffmpeg that is not on your PATH, run `settings set ffmpeg /path/to/ffmpeg`; the core
puts its folder first on the PATH it uses.

Press Ctrl-C to cancel: the core stops cleanly and removes its temporary files.
