# Keymaster app

**Español:** [README.es-419.md](README.es-419.md)

A desktop app for Linux and Windows that keys green-screen clips with CorridorKey 2.0. Drop your
clips in, press Start, and get the alpha matte, the despilled foreground and a ready-to-composite
cutout next to each clip. No editing software needed.

You need an NVIDIA graphics card and the Keymaster core (`keymaster-core`) installed first. The app
runs on the core's own Python, so it adds only a small interface library on top.

## Install

1. Install `keymaster-core` and run its installer. It downloads the models and saves its location
   in the Keymaster settings file.
2. Unzip `keymaster-app-<version>.zip` somewhere permanent (the app runs from that folder).
3. Run the installer from the unzipped `keymaster-app` folder:
   - Linux: `bash install.sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy Bypass -File install.ps1`

The installer adds PySide6 (the interface library) to the core's Python and creates a launcher:

- Linux: `~/.local/bin/keymaster-app` and a **Keymaster** entry in your applications menu.
- Windows: `keymaster-app.bat` in the app folder and a **Keymaster** shortcut in the Start Menu.

If the core is not installed yet, the installer stops and tells you so.

## Use

1. Drag videos or folders of frames into the queue, or use **Add files…** / **Add folder…**.
   Dropping a single frame adds its whole folder.
2. Optional: select a clip and press **Set hint…** to give it a matte for its first frame (white
   where the subject is, black where it is not, same size as the clip). Without one, the model keys
   the clip on its own.
3. Pick the options:
   - **Hint quality** and **Despill** (0 to 1).
   - **Outputs**: alpha matte, foreground, cutout (RGBA) and a checkerboard preview.
   - **Format**: EXR image sequences or video files.
   - **Low VRAM mode** for graphics cards with less memory (slower).
   - **Output folder**: leave it empty to write a `<clip>_keyed` folder next to each clip.
4. Press **Start**. Clips run one at a time; **Cancel** stops the current clip and keeps the rest
   waiting. Pressing **Start** again retries failed or cancelled clips.
5. Select a finished clip to see its first frame over a checkerboard, and **Open output folder** to
   get to the files. EXR results open in your compositor; the app previews PNG results only.

**Setup check** runs the core's own diagnostics (graphics card, FFmpeg, model files, PyTorch) and
tells you what is missing. The language menu switches between English and Spanish right away and
remembers your choice for every Keymaster host.

You can also start the app with clips already queued: `keymaster-app clip1.mp4 frames_folder/`.

## Troubleshooting

- Linux, "could not load the Qt platform plugin xcb": install your distribution's `libxcb-cursor`
  package (for example `libxcb-cursor0` on Ubuntu).
- The app says the interface library is missing: run the installer again.
