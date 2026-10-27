# Keymaster installer

[Español](README.es-419.md)

One download that installs Keymaster and adds it to the programs you have: the keying core
(Python, PyTorch and the CorridorKey models), the standalone app, and the plugins for Blender,
DaVinci Resolve and Nuke (OpenFX), and After Effects and Premiere Pro. You do not need Python, git
or ffmpeg beforehand.

You need an NVIDIA graphics card with a current driver, a 64-bit Windows or Linux, an internet
connection and about 15 GB of free disk. The installer downloads about 12 GB, so the first install
takes a while.

## Windows

1. Download `keymaster-installer-<version>-windows.exe` from the
   [releases](https://github.com/YoseptF/Keymaster/releases) and double-click it. The installer is
   not signed yet: if Windows SmartScreen stops it, choose **More info**, then **Run anyway**.
2. Pick what to install. Programs found on this computer are already ticked; the rest say
   "not found on this computer".
3. Keep the suggested folder (`%LOCALAPPDATA%\Programs\Keymaster`) or choose another one and press
   **Install**. The log shows each step while Python, PyTorch and the models download.
4. If you picked DaVinci Resolve and Nuke, Windows asks for administrator rights once, only to copy
   the plugin into `C:\Program Files\Common Files\OFX\Plugins`. Everything else stays in your user
   account.
5. The last step checks the installation and tells you whether everything is ready. Restart
   Blender, Resolve, Nuke, After Effects or Premiere Pro to see Keymaster; the app is in the Start
   menu.

To remove Keymaster, use **Settings > Apps > Keymaster > Uninstall** (or Add or Remove Programs). It
removes the core, the models, the plugins, the Start menu entry and the registry entries it added.
Your keyed clips are never touched.

Silent install, for example for a lab: `keymaster-installer-<version>-windows.exe /S`, with
`/COMPONENTS=app,blender,openfx,adobe` to choose the optional parts and `/D=C:\path` (last) for the
folder. Silent uninstall: `"%LOCALAPPDATA%\Programs\Keymaster\uninstall.exe" /S`.

## Linux

1. Download `keymaster-installer-<version>-linux.sh` from the
   [releases](https://github.com/YoseptF/Keymaster/releases).
2. Run it in a terminal: `bash keymaster-installer-<version>-linux.sh`
3. Answer the questions (press Enter for the suggested answer). It installs into
   `~/.local/share/keymaster` and does not need administrator rights, except for the OpenFX plugin:
   copying it to `/usr/OFX/Plugins` asks for your password through `sudo`. If you skip that, it
   prints the command to run later.
4. When it finishes, it prints the result of the setup check and how to open each part.

Options:

| Option | Meaning |
|---|---|
| `--yes` | no questions, install what was found |
| `--components core,app,blender,openfx` | choose the parts (the core is always installed) |
| `--prefix DIR` | install somewhere else |
| `--bundled-ffmpeg` | use Keymaster's own ffmpeg even if one is installed |
| `--uninstall` | remove Keymaster |

To remove Keymaster: `bash ~/.local/share/keymaster/uninstall.sh`. It removes the folder, the app
launcher and menu entry, the Blender extension, the OpenFX plugin and the settings file if the
installer created it. Your keyed clips are never touched.

## What it installs and downloads

| Part | Where |
|---|---|
| Core, Python 3.12, PyTorch 2.9.1 (CUDA 12.8), models | the install folder |
| Standalone app | the install folder, plus a Start menu entry or a `keymaster-app` launcher and menu entry |
| Blender extension | Blender's own extensions folder, for every Blender 5 found |
| OpenFX plugin | `C:\Program Files\Common Files\OFX\Plugins` or `/usr/OFX/Plugins` |
| After Effects and Premiere Pro panel (Windows) | `%APPDATA%\Adobe\CEP\extensions`, and `PlayerDebugMode` for CEP 11 and 12, which unsigned panels need |
| Shared settings | `%APPDATA%\Keymaster\settings.json` or `~/.config/keymaster/settings.json` |

Downloads are pinned to exact versions and checked against their SHA-256 sums:
[uv](https://github.com/astral-sh/uv) (which installs Python and PyTorch; bundled on Windows,
downloaded on Linux when `uv` is missing) and a static ffmpeg build (on Windows always, on Linux
when ffmpeg is missing). ffmpeg is downloaded from its original publishers
([gyan.dev](https://www.gyan.dev/ffmpeg/builds/) for Windows,
[johnvansickle.com](https://johnvansickle.com/ffmpeg/) for Linux) and is licensed under the GPL
version 3; its licence files are kept next to it. The models come from Hugging Face and Google
Cloud Storage, as in the core.

## Troubleshooting

- The details of every step are in `logs/install.log` inside the install folder.
- A failed download or a checksum mismatch stops the installer without using the file. Run it
  again; it continues where it stopped and keeps what was already downloaded.
- Running the installer again repairs or updates an installation without downloading the models
  again.

## Develop

- `python3 packages/installer/build.py --out DIR --version V --platform linux|windows` builds
  `keymaster-installer-V-linux.sh` or `keymaster-installer-V-windows.exe`. It builds the other
  packages it embeds, so it needs what they need, plus `makensis` (`apt install nsis`) for Windows.
  Downloads are cached in `tmp/installer-cache`. Release files are built by CI only.
- `bash packages/installer/test.sh` tests the generators, builds the Linux installer and installs
  it into a throwaway home with a fake core and fake downloads; with `makensis`, `wine` and
  `xvfb-run` it also installs and uninstalls the Windows installer silently under Wine.
- Pinned downloads live in `pins.json`. When `packages/core/upstream/requirements.txt` changes a
  git dependency, update its pin there, or the build stops.
