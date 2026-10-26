# Keymaster

[Español](README.es-419.md)

AI green and blue screen keying inside DaVinci Resolve, Nuke, After Effects, Premiere Pro and
Blender, plus a standalone app.

## Requirements

- NVIDIA RTX 30-series or newer: 4 GB VRAM for up to 1440p, 6 GB for 4K
- Windows or Linux
- `ffmpeg` on your PATH

## Packages

| Package | What it is |
|---|---|
| [core](packages/core) | The keying runtime every other package calls. Install it first. |
| [app](packages/app) | Standalone app: drop clips in, get mattes out. |
| [openfx](packages/openfx) | OpenFX plugin for DaVinci Resolve and Nuke. |
| [blender](packages/blender) | Blender add-on. |
| [adobe](packages/adobe) | Panel for After Effects and Premiere Pro. |

Each package's folder explains how to install it.

## Credits and license

Keymaster runs CorridorKey by Corridor Digital and is distributed under the CorridorKey licence in
[LICENSE](LICENSE). Third-party model notices are in
[packages/core/upstream/THIRD_PARTY_NOTICES.md](packages/core/upstream/THIRD_PARTY_NOTICES.md).
