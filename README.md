# Keymaster

[Español](README.es-419.md)

AI green and blue screen keying inside DaVinci Resolve, Nuke, After Effects, Premiere Pro and
Blender, plus a standalone app.

## Install

Download the installer from the [latest release](https://github.com/YoseptF/Keymaster/releases/latest)
and run it. It installs everything Keymaster needs (Python, PyTorch, the models and ffmpeg) and
adds Keymaster to the programs you have.

- Windows: `keymaster-installer-<version>-windows.exe`, a normal setup wizard.
- Linux: `keymaster-installer-<version>-linux.sh`, run `bash keymaster-installer-<version>-linux.sh`.

It downloads about 12 GB, so give it some time. Details and options are in
[packages/installer](packages/installer).

## Requirements

- NVIDIA RTX 30-series or newer: 4 GB VRAM for up to 1440p, 6 GB for 4K, and a current driver
- Windows or Linux (64-bit)
- About 15 GB of free disk

## Packages

For advanced users: every package also ships on its own, with its own install steps.

| Package | What it is |
|---|---|
| [installer](packages/installer) | The one-click installer for Windows and Linux. Start here. |
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
