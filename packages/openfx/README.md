# Keymaster for OpenFX

[Español](README.es-419.md)

An OpenFX plugin that brings Keymaster's AI green-screen keyer into DaVinci Resolve (free and
Studio), Nuke and other OpenFX hosts on Linux and Windows.

The plugin does not run the model itself. It sends the clip to Keymaster's core, so install
[keymaster-core](../core) first. The core installer records where it lives in the shared settings
file, and the plugin finds it there. You can also point at it with the `KEYMASTER_PYTHON` and
`KEYMASTER_CORE` environment variables.

## Install

Download `keymaster-openfx-<version>-linux.zip` or `keymaster-openfx-<version>-windows.zip` from
the releases page and unzip it.

- **Linux:** run `./install.sh`. It copies `Keymaster.ofx.bundle` into `/usr/OFX/Plugins` and asks
  for your password if it needs to. The Linux build needs glibc 2.38 or newer (Ubuntu 24.04,
  Fedora 39, Rocky Linux 10 or newer).
- **Windows:** right-click `install.ps1` and choose **Run with PowerShell**. It asks for
  administrator rights and copies `Keymaster.ofx.bundle` into
  `C:\Program Files\Common Files\OFX\Plugins`.

Set `OFX_PLUGIN_DIR` before running either script to install somewhere else. Then restart your
host.

### DaVinci Resolve

After restarting, Keymaster appears in the **Effects** library under **OpenFX > Filters >
Keymaster**. Drag it onto a node on the Color page or onto a clip on the Edit page. If it does not
show up, check **Preferences > System > Video Plugins** and make sure Keymaster is enabled.

### Nuke

Nuke reads the same folder. After restarting, press Tab in the Node Graph and type `Keymaster`, or
find it in the **Keymaster** toolbar menu. If you installed elsewhere, add that folder to
`OFX_PLUGIN_PATH`.

## Use it

1. Apply Keymaster to a green-screen clip. Until the clip is keyed it passes the source through and
   shows a note saying so.
2. Press **Key clip**. Keymaster reads every frame of the clip, sends them to the core and shows its
   progress. Keying runs on the GPU and can take several minutes; cancel it from the progress
   window if you need to.
3. Pick an **Output**: **Cutout** (premultiplied, ready to composite), **Alpha**, **Foreground** or
   **Source**.

**Hint quality** and **Despill** are used when keying. After changing them, or after trimming or
replacing the source clip, Keymaster passes the source through again until you press **Key clip**
once more.

**Clip encoding** tells Keymaster how the pixel values it receives are encoded. Leave it on
**Gamma-encoded** for Resolve timelines and use **Scene linear** in Nuke, which is the default
there.

**Clear key** deletes the cached result. Results are cached on disk, in
`~/.cache/keymaster/openfx` on Linux and `%LOCALAPPDATA%\Keymaster\openfx` on Windows, and survive
saving and reopening the project.

## Language

The plugin speaks English and Latin American Spanish and follows your system language. To pick one
yourself, set `"language": "es-419"` or `"en"` in Keymaster's settings file, or set the
`KEYMASTER_LANGUAGE` environment variable. The host picks up the change the next time it starts.
