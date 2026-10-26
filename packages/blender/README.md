# Keymaster for Blender

[Español](README.es-419.md)

A Blender 5 extension that removes green screens in the Video Sequencer with CorridorKey. It sends
the active strip to the Keymaster core and puts the keyed result back on the timeline, frame for
frame on top of the original.

## Install

1. Install the Keymaster core first and run its setup, so the models are downloaded and Keymaster
   knows where its Python lives.
2. Download `keymaster-blender-<version>.zip` from the
   [releases](https://github.com/YoseptF/Keymaster/releases). Don't unzip it.
3. In Blender, open Edit > Preferences > Get Extensions, open the menu at the top right and choose
   Install from Disk. Pick the zip.
4. In the extension's preferences, press Check setup. Every line should have a check mark. The
   same place shows which core and Python Keymaster found, and lets you switch the language
   between English and Español (Latinoamérica). The language is shared with every other Keymaster
   app.

## Use

1. In the Video Sequencer, select a movie strip or an image sequence strip so it is the active
   strip.
2. Open the sidebar (N) and the Keymaster tab.
3. Optionally pick a first-frame hint image, and set the hint quality, despill, which outputs to
   write and the format (EXR image sequence by default).
4. Press Key. Blender stays usable while it works; the bar shows each step and Cancel stops it.
5. When it finishes, the cutout appears on the first free channel above the source with Alpha Over
   blending, lined up with the source's frames, including its trims. With "Also add the other
   outputs as strips" on, the alpha, foreground and checkerboard outputs are added above it, muted.

Keyed files go to the output folder you choose, or to a `keymaster` folder next to the saved
`.blend` file (the system temp folder if the file is not saved). Only the frames up to the end of
the strip's visible range are keyed.

## Develop

- `bash packages/blender/test.sh` runs the unit tests, and when `blender` is on the PATH also
  installs the extension into a throwaway Blender profile and keys strips with the fake core.
- `python3 packages/blender/build.py --out DIR --version V` writes `keymaster-blender-V.zip`.
- To try the source directly, link `packages/blender/keymaster` into a local extensions repository
  folder; it then reads its translations from the repository.
