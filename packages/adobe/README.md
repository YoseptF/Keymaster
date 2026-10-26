# Keymaster for After Effects and Premiere Pro

[Español](README.es-419.md)

One panel that keys green and blue screen footage with CorridorKey, inside After Effects and
Premiere Pro (2022 or newer, Windows). It sends the selected clip to the Keymaster core, shows
the progress, then imports the result and places the cutout right above your source.

## Install

1. Install the Keymaster core first and let it finish downloading the models. The panel uses
   the core's Python and finds it through the shared Keymaster settings.
2. Unzip `keymaster-adobe-<version>.zip` anywhere.
3. Double-click `install.cmd` (or run `install.ps1` in PowerShell). It copies the panel to
   `%APPDATA%\Adobe\CEP\extensions\com.keymaster.adobe` and turns on `PlayerDebugMode` for
   CEP 11 and 12, which Adobe apps need to load a panel that is not signed.
4. Restart After Effects or Premiere Pro and open **Window > Extensions > Keymaster**.
5. Click **Check setup**. Every line should have a check mark.

The panel is not signed yet. That is fine for testing, but it is why `PlayerDebugMode` is
needed. To remove the panel, run `uninstall.cmd`. It leaves `PlayerDebugMode` on because other
unsigned panels may need it.

## Use it in After Effects

1. In a composition, select one layer whose source is a video file or an image sequence.
2. Pick your options and click **Key**.
3. When it finishes, the results are in a **Keymaster** folder in the Project panel and the
   cutout sits directly above the source layer, with the same timing, transforms and masks
   (effects are not copied). **Turn off the source** hides the original layer.

After Effects defaults to an EXR sequence. EXR results are scene-linear, so use a linear
working space or the color management settings you normally use for EXR.

## Use it in Premiere Pro

1. In the active sequence, select one clip.
2. Pick your options and click **Key**.
3. The results go into a **Keymaster** bin. The cutout is placed on the first free video track
   above the clip, at the same position and with the same in and out points. Nothing else on
   the timeline moves; if every track above is busy in that range, a new track is added.

Premiere Pro defaults to video, which gives a ProRes 4444 cutout with alpha.

## Options

- **First-frame hint**: an optional rough matte of the first frame (white keeps, black removes).
- **Hint quality** and **Despill**: from 0 to 1.
- **Outputs**: cutout, alpha matte, foreground and a checkerboard preview. Only the cutout is
  placed on the timeline; the others are imported next to it.
- **Format**: EXR sequence or video.
- **Output folder**: by default a `Keymaster` folder next to the source, one subfolder per run.
- **Low VRAM mode**: slower, for graphics cards with little memory.

**Cancel** stops the core and deletes the unfinished run folder.

## Language

The panel follows the language of your Adobe app: Spanish when the app runs in any Spanish
locale, English otherwise. To pin a language for every Keymaster host, set `language` in the
shared settings file (`%APPDATA%\Keymaster\settings.json`) to `en` or `es-419`; `auto` or no
value follows the app. The `KEYMASTER_LANGUAGE` environment variable overrides both.

## For developers

`bash test.sh` runs the tests on Linux with Node 24 and Python 3, using the fake core. To try
the panel from the repository on Windows, link `packages\adobe\extension` into
`%APPDATA%\Adobe\CEP\extensions\com.keymaster.adobe` (`mklink /J`) and set `PlayerDebugMode`;
in that layout the panel reads its translations straight from the repository.

`vendor/adobe/CSInterface.js` is Adobe's library, distributed under Adobe's CEP SDK license
(`vendor/adobe/LICENSE.pdf`), not under the Keymaster licence.
