<p align="center">
  <img src="clipshrinker/resources/icon.png" width="96" alt="ClipShrinker icon">
</p>

<h1 align="center">ClipShrinker</h1>

<p align="center">
  Batch video compressor for Windows and Linux. Drop your clips in, pick a preset, and they come out small enough for Discord, WhatsApp or email.
</p>

---

ClipShrinker is a desktop app built on [FFmpeg](https://ffmpeg.org/). FFmpeg is bundled
with it, so there is nothing else to install. You can queue up any number of clips, and
for size-limited presets each clip's bitrate is worked out from its own length, so every
file ends up just under the limit without being cut short.

## Contents

- [Features](#features)
- [Download and install](#download-and-install)
- [How to use](#how-to-use)
- [Trimming clips](#trimming-clips)
- [Uploading to Discord](#uploading-to-discord)
- [Presets](#presets)
- [Settings reference](#settings-reference)
- [Preferences](#preferences)
- [Running from source](#running-from-source)
- [Building the executables](#building-the-executables)
- [Releasing a new version](#releasing-a-new-version)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Features

- **Queue for many clips**
  - Add files or whole folders by drag & drop or the file picker.
  - Live progress, time remaining and final size for every clip.
  - Cancel, retry, reorder and remove clips, and encode several at once.
- **Auto-upload to Discord**: finished clips are posted to a channel through a webhook, with a clearly visible on/off switch.
- **17 built-in presets, plus your own**
  - Discord (20 / 10 / 50 / 500 MB), WhatsApp, email, quality-based presets, AV1, VP9 WebM, GPU encoding.
- **Detailed settings**
  - **Mode:** target size, constant quality or fixed bitrate.
  - **Video:** H.264 / H.265 / AV1 / VP9, CPU or GPU encoding (NVIDIA, AMD and Intel on Windows and Linux, Apple), speed slider, two-pass.
  - **Resolution:** a cap, or *Auto*, which picks the best resolution for the size limit.
  - **Frame rate:** a cap.
  - **Audio:** codec, bitrate, mono, removing it, or **mixing every audio track into one** (handy for OBS recordings).
- **Trim with a preview**: scrub through the clip, watch it play, and drag the start and end handles on a filmstrip timeline.
- **Size-limit safety net**: a clip that still comes out over the limit is re-encoded automatically with a lower bitrate. Clips already under the limit are skipped.
- **Live size estimate** for the selected clip as you change settings.
- **Notification** when the queue finishes. Settings are remembered between runs.

## Download and install

Download the latest version from the
[Releases page](https://github.com/BrunoMLG/ClipShrinker/releases). Each release lists
what's new in that version.

### Windows

1. Download `ClipShrinker-windows-x64.exe`.
2. Double-click it. It's a single portable file, so there's nothing to install.

> Windows SmartScreen may warn you because the app isn't code-signed. Click
> **More info → Run anyway**.

### Linux

ClipShrinker for Linux is an **AppImage**: one file that runs on most distributions
without installing anything.

1. Download `ClipShrinker-linux-x86_64.AppImage`.
2. Make it executable, either by right-clicking it → *Properties* → *Permissions* →
   **Allow executing file as program**, or in a terminal:
   ```bash
   chmod +x ClipShrinker-linux-x86_64.AppImage
   ```
3. Double-click it, or run:
   ```bash
   ./ClipShrinker-linux-x86_64.AppImage
   ```

*(Optional)* To add it to your application menu, use
[Gear Lever](https://flathub.org/apps/it.mijorus.gearlever) or
[AppImageLauncher](https://github.com/TheAssassin/AppImageLauncher). They also keep
your AppImages in one place.

The AppImage runs on most distros from Ubuntu 22.04 / Debian 12 / Fedora 36 onward
(glibc 2.35+). If it doesn't start, see [Troubleshooting](#troubleshooting).

## How to use

1. **Add clips**: drag videos or folders onto the window, or click **＋ Add clips** /
   **Add folder**.
2. **Pick a preset** in the panel on the right, e.g. *Discord (20 MB)*. Adjust any
   setting if you like; the preset shows **● Modified** and *Reset* brings it back.
3. **Click Start.** Clips are processed from top to bottom. If
   [Discord upload](#uploading-to-discord) is on, the button reads **Start + upload**.
4. Results are saved **next to the original file** as `name_shrunk.mp4` by default. You
   can change the folder and file name under *Output*.

Other tips:

| Action | How |
| --- | --- |
| Change settings for clips already in the queue | Select them and click **Apply to selected clips** (with nothing selected, it applies to all waiting clips) |
| Trim a clip | Double-click it, or right-click → **Trim…** (see [Trimming clips](#trimming-clips)) |
| See why a clip failed | Right-click → **Details & log…** to see the error and the full FFmpeg log |
| Post a finished clip to Discord | Right-click → **Upload to Discord** (works even when automatic upload is off) |
| Reorder | Right-click → Move up/down, or `Ctrl+↑` / `Ctrl+↓` |
| Remove clips | `Delete` key, or right-click → Remove |
| Re-encode a finished clip | Right-click → **Encode again** |
| Clean the list | **Clear finished** in the top bar |
| Open files from the command line | `ClipShrinker clip1.mp4 clip2.mkv some-folder/` |
| See which FFmpeg and GPU encoders it uses | `ClipShrinker --diagnose` (prints to the terminal; see [Troubleshooting](#troubleshooting)) |

Supported inputs: `.mp4 .mkv .mov .avi .webm .m4v .flv .wmv .ts .mts .m2ts .3gp .mpg .mpeg`.
Anything FFmpeg can read also works through *All files* in the file picker.

## Trimming clips

Double-click a clip (or right-click → **Trim…**) to open the trim editor.

- **Preview:** the large frame shows the clip at the playhead. Click anywhere on the
  timeline to jump there, or drag to scrub.
- **Play** (or `Space`) plays the part you're keeping, from the playhead to the end
  handle. The preview has no sound.
- **Start and end:** drag the purple handles on either side of the filmstrip. The area
  outside them is dimmed, and the label shows how much you're keeping.
- **Set start / Set end** (or `I` / `O`) put the start or end at the playhead.
- **Typing times** still works: enter `0:12`, `1:05.5` or `90` in the *Start* and *End*
  fields.
- `←` / `→` step one frame, and `Shift+←` / `Shift+→` jump one second. **Reset** keeps
  the whole clip.

Click **Save**. Trimmed clips show ✂ next to their name. Size targets apply to the
trimmed length, so a shorter clip gets more quality for the same size. Saving a new trim
on a clip that's already done encodes it again.

## Uploading to Discord

ClipShrinker can post every clip that finishes to a Discord channel through a
**webhook**, so your clips land in the channel without you dragging files around.

### Set it up

1. In Discord, open **Server Settings → Integrations → Webhooks → New Webhook**, choose
   the channel, then click **Copy Webhook URL**. You need *Manage Webhooks* permission on
   that server.
2. In ClipShrinker, click **⚙** next to the Discord switch (bottom right), paste the URL
   and click **Test**. It should say *Connected* and show the webhook's name.
3. Optionally change the **Message** posted with each clip: `{name}` = the clip's name,
   `{size}` = its file size. Leave it empty to post only the video.
4. Tick **Upload finished clips automatically** and click **Save**.

### Avoiding accidental uploads

- The **Discord upload** switch sits right next to **Start**, so you always see the
  state before a run. When it's on it's highlighted and shows the webhook's name, and
  **Start** changes to **Start + upload**.
- Turning it on asks for confirmation. Turning it off is a single click and takes effect
  immediately: clips that finish afterwards are not posted, even mid-queue.
- Only clips that ClipShrinker compressed are uploaded. Skipped, failed and cancelled
  clips never are.
- Mentions such as `@everyone` are never triggered by the message or file name.

Each clip's status shows the upload (*uploading 40%*, *sent to Discord*, or *Discord upload
failed*, with the reason in the tooltip). Right-click a clip for **Open in Discord** or to
**Upload to Discord** again. Uploads go out one at a time, in queue order.

> **File size:** Discord rejects files larger than the server's upload limit. Use the
> **Discord (20 MB)** preset, or **Discord (10 MB)** for servers that still have the
> older limit. Boosted servers allow more.
>
> **Keep the webhook URL private.** Anyone with it can post to that channel. It is
> stored in ClipShrinker's settings file on your computer and only sent to Discord.

## Presets

| Preset | Mode | Details |
| --- | --- | --- |
| **Discord (20 MB)** | Target size 19 MB | H.264, auto resolution, max 60 fps, AAC 128 kbps. The default. |
| **Discord (10 MB)** | Target size 9.5 MB | H.264, auto resolution, max 60 fps, AAC 96 kbps. For the older limit. |
| **Discord Nitro Basic (50 MB)** | Target size 48 MB | H.264, auto resolution, max 60 fps, AAC 128 kbps |
| **Discord Nitro (500 MB)** | Target size 480 MB | H.264, up to 1440p, max 60 fps, AAC 160 kbps |
| **WhatsApp / Messaging (16 MB)** | Target size 15 MB | H.264, auto resolution, max 30 fps |
| **Email attachment (25 MB)** | Target size 23.5 MB | H.264, auto resolution, max 30 fps |
| **High quality** | Quality 19 | H.264, original resolution, AAC 192 kbps |
| **Balanced** | Quality 23 | H.264, up to 1080p, AAC 128 kbps |
| **Small (HEVC)** | Quality 28 | H.265, up to 720p, AAC 96 kbps |
| **Tiny** | Quality 32 | H.265, 480p, 30 fps, mono 48 kbps |
| **Archive (AV1)** | Quality 30 | AV1 (SVT-AV1), original resolution, Opus, `.mkv` |
| **Web (VP9 WebM)** | Quality 33 | VP9, up to 1080p, Opus, `.webm` |
| **Fast GPU (NVIDIA / AMD / Intel)** | Quality 25 | Hardware H.264, up to 1080p. The AMD (AMF) one is for Windows. |
| **Fast GPU (Linux VA-API)** | Quality 25 | Hardware H.264 on AMD or Intel GPUs on Linux, up to 1080p |
| **Classic ClipShrinker** | Bitrate 4000 kbps | The original 1.x settings: 720p, 60 fps, AAC 96 kbps |

Size-limit presets aim a little below the real limit to leave a safety margin.
"MB" in ClipShrinker means the same as in Windows Explorer and Discord
(1 MB = 1,048,576 bytes).

**Your own presets:** change any settings, click **Save as…** and give it a name. Saved
presets appear under *My presets* and can be deleted with **Delete**.

## Settings reference

### Compression

| Mode | What it does | Best for |
| --- | --- | --- |
| **Target size** | Works out the bitrate from each clip's length so the file lands just under the size you set. | Upload limits (Discord etc.) |
| **Quality** | Constant quality (CRF/CQ). File size depends on the content. Lower number = better quality and bigger file. Recommended: H.264 23, H.265 26, AV1 32, VP9 33. | Archiving, general use |
| **Bitrate** | A fixed average video bitrate. 1000 kbps ≈ 7.5 MB per minute. | When you need predictable bitrate |

### Video

| Setting | Notes |
| --- | --- |
| **Codec** | **H.264** plays everywhere. **H.265** is ~30–40% smaller at the same quality but some older devices and browsers can't play it. **AV1** is the smallest but encodes slowly. **VP9** is for WebM/web use. |
| **Encoder** | *CPU* gives the best quality per MB. The GPU encoders are much faster (often 5× or more) but slightly less efficient: *NVIDIA NVENC*, *Intel Quick Sync*, *AMD AMF* (Windows), *VA-API* (AMD and Intel GPUs on **Linux**), and *Apple VideoToolbox*. ClipShrinker tests each one at startup and marks missing ones *(not detected)*. |
| **Speed** | Fastest → Slowest. Slower = smaller file / better quality for the same size. |
| **Resolution** | *Auto* (only in Target size mode) picks the highest resolution the size budget can support, e.g. a 30 s clip stays 1080p and a 5 min clip drops to 480p. *Original* keeps the source size. Other values are a maximum; clips are never upscaled. For portrait videos the limit applies to the short side. |
| **Frame rate** | A maximum; lower-fps sources are left alone. Dropping 60 → 30 fps frees a lot of bitrate for long clips. |
| **Two-pass** | Analyses the clip first for more accurate sizes and better quality. Roughly 1.4× slower. CPU H.264/H.265/VP9 only, in Target size and Bitrate modes. |

### Audio

| Setting | Notes |
| --- | --- |
| **Codec** | AAC (MP4/MOV/MKV), Opus (any format; required for WebM), *Copy original*, or *Remove audio*. |
| **Bitrate** | 96 kbps is plenty for clips; 128–192 kbps for music. |
| **Channels** | Original, Stereo or Mono. Mono halves the audio size. |
| **Tracks** | *First track only*, or *Mix all tracks* to merge e.g. OBS game + mic tracks into one. |

### Output

| Setting | Notes |
| --- | --- |
| **Format** | MP4 (most compatible), MKV, WebM (VP9/AV1 only), MOV. |
| **Folder** | Empty = same folder as the original clip. |
| **File name** | Template; `{name}` = original name, `{codec}` = video codec. Default `{name}_shrunk`. |
| **If exists** | Add a number (`clip_shrunk_1.mp4`), overwrite, or skip the clip. The original file is never overwritten. |
| **Strip metadata** | Removes title, creation date, GPS, etc. |
| **Extra FFmpeg arguments** | Advanced: added to the command right before the output file. |

## Preferences

Open with **⚙ Preferences** in the top bar.

| Option | Default | Notes |
| --- | --- | --- |
| Clips at once | 1 | FFmpeg already uses every CPU core, so 1–2 is usually fastest. Higher values help with GPU encoding. |
| FFmpeg | built-in | Point to your own `ffmpeg` executable if you need one (applies after restart). |
| Skip clips already under the target size | on | Only in Target size mode and when the clip isn't trimmed. |
| Retry when a clip is over the size limit | on | Up to 2 retries with a proportionally lower bitrate. |
| Notification when the queue finishes | on | |
| Open the output folder when finished | off | |

Settings are saved to:

- **Windows:** `%APPDATA%\ClipShrinker\config.json`
- **Linux:** `~/.config/clipshrinker/config.json` (or `$XDG_CONFIG_HOME/clipshrinker/`)
- **macOS:** `~/Library/Application Support/ClipShrinker/config.json`

Delete that file to reset everything to defaults.

## Running from source

**Requirements:** Python **3.9 or newer** and Git. FFmpeg is installed automatically
through the `imageio-ffmpeg` package.

1. Clone the repository:
   ```bash
   git clone https://github.com/BrunoMLG/ClipShrinker.git
   ```
   ```bash
   cd ClipShrinker
   ```
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate it:
   - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
   - Windows (cmd): `.venv\Scripts\activate.bat`
   - Linux / macOS: `source .venv/bin/activate`
4. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run it:
   ```bash
   python ClipShrinker.py
   ```
   (`python -m clipshrinker` works too.)

On **Linux**, Qt needs a few system libraries. On Debian/Ubuntu:

```bash
sudo apt install libegl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0 libxcb-randr0 libxcb-render-util0 libxcb-image0
```

On Fedora: `sudo dnf install xcb-util-cursor xcb-util-wm xcb-util-keysyms libxkbcommon-x11`.

## Building the executables

The executables are built with [PyInstaller](https://pyinstaller.org/) using
`ClipShrinker.spec`. It produces **one self-contained file** that includes Python, Qt
and FFmpeg.

> **PyInstaller cannot cross-compile.** Build the Windows `.exe` on Windows and the
> Linux AppImage on Linux. The easiest way to get both is to let GitHub Actions do it
> (see [Automatic builds](#automatic-builds-github-actions)).

### Build on Windows

1. Install [Python 3.12](https://www.python.org/downloads/windows/) and tick
   **"Add python.exe to PATH"** in the installer.
2. In PowerShell, from the project folder:
   ```powershell
   python -m venv .venv
   ```
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
   ```powershell
   pip install -r requirements-dev.txt
   ```
   ```powershell
   pyinstaller --noconfirm ClipShrinker.spec
   ```
3. The result is `dist\ClipShrinker.exe` (about 50–70 MB) with the app icon.

> If PowerShell refuses to run `Activate.ps1`, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `cmd` with
> `.venv\Scripts\activate.bat`.

### Build on Linux

1. Install Python and the Qt libraries listed in [Running from source](#running-from-source).
   On Ubuntu also install `python3-venv`:
   ```bash
   sudo apt install python3 python3-venv
   ```
2. From the project folder:
   ```bash
   python3 -m venv .venv
   ```
   ```bash
   source .venv/bin/activate
   ```
   ```bash
   pip install -r requirements-dev.txt
   ```
   ```bash
   pyinstaller --noconfirm ClipShrinker.spec
   ```
   On Linux this produces a folder, `dist/ClipShrinker/`, rather than a single file.
   You can run it directly with `dist/ClipShrinker/ClipShrinker`.
3. Pack the folder into an AppImage:
   ```bash
   tools/build_appimage.sh
   ```
   The result is `dist/ClipShrinker-linux-x86_64.AppImage`. The script downloads
   [appimagetool](https://github.com/AppImage/appimagetool) on first use (set
   `APPIMAGETOOL=/path/to/appimagetool` to use your own copy). It doesn't need FUSE, so it
   also works in containers. To choose the output path, pass it as an argument:
   `tools/build_appimage.sh my.AppImage`.

> An AppImage only runs on distros with the same or a **newer glibc** than the one it was
> built on. Build on an older distro (CI uses Ubuntu 22.04) so it works on more systems.

### Build on macOS (optional)

The Windows steps also work on macOS and produce a single `dist/ClipShrinker` file. macOS isn't part of the
official builds yet.

### Automatic builds (GitHub Actions)

`.github/workflows/build.yml` runs on every push to `main`, on pull requests, and when
started manually (**Actions → Build → Run workflow**). For both Windows and Linux it:

1. installs Python 3.12 and the dependencies,
2. runs the unit tests,
3. builds with PyInstaller (and on Linux, packs the AppImage),
4. on Linux, checks that the AppImage starts, that its bundled FFmpeg runs, and (with
   `--diagnose`) that FFmpeg doesn't inherit the bundle's library path, which breaks GPU
   drivers,
5. uploads `ClipShrinker-windows-x64.exe` and `ClipShrinker-linux-x86_64.AppImage` as
   workflow artifacts (open the run in the **Actions** tab and look under *Artifacts*).

### Changing the icon

The icon is drawn in code by `tools/make_icon.py`, which writes
`clipshrinker/resources/icon.png` (window/Linux icon) and `assets/icon.ico` (Windows exe
icon). After editing it, run:

```bash
python tools/make_icon.py
```

(needs `requirements-dev.txt`, which includes Pillow). To use your own artwork instead,
replace those two files directly.

## Releasing a new version

1. Update `__version__` in `clipshrinker/__init__.py`.
2. Commit and push to `main`.
3. Create and push a tag that starts with `v`:
   ```bash
   git tag v2.0.0
   ```
   ```bash
   git push origin v2.0.0
   ```
4. GitHub Actions builds both platforms and publishes a **GitHub Release** for the tag
   with the `.exe` and `.AppImage` attached and release notes generated automatically.

## Development

Install the dev dependencies (`pip install -r requirements-dev.txt`) and run the tests:

```bash
pytest
```

The tests cover the FFmpeg command builder, the size and resolution maths, time parsing,
output naming and every built-in preset. On a machine without a display, set
`QT_QPA_PLATFORM=offscreen`.

### Adding a preset

Add a `Preset(...)` entry to `BUILTIN_PRESETS` in `clipshrinker/presets.py`. The helpers
`_size(mb, ...)` and `_quality(crf, ...)` accept any field of `EncodeSettings`
(see `clipshrinker/encode.py`). The test suite automatically checks that every preset is
valid.

## Project structure

```
ClipShrinker.py              launcher (python ClipShrinker.py) and PyInstaller entry point
ClipShrinker.spec            PyInstaller build configuration
clipshrinker/
  app.py                     application start-up
  encode.py                  EncodeSettings model + FFmpeg command builder (pure Python)
  presets.py                 built-in presets
  ffmpeg.py                  finding FFmpeg, probing files, detecting GPU encoders
  jobs.py                    the queue: runs FFmpeg via QProcess, progress, retries
  config.py                  user settings stored as JSON
  discord.py                 Discord webhook client (stdlib HTTP, streamed uploads)
  uploader.py                background upload queue for finished clips
  resources/                 icon and UI images
  ui/
    main_window.py           main window, top/bottom bars, actions
    queue_view.py            clip list with progress bars and drag & drop
    settings_panel.py        presets and all encoding settings
    dialogs.py               Preferences and clip dialog (trim + details tabs)
    trim_editor.py           frame preview, filmstrip timeline, playback
    discord_dialog.py        Discord webhook settings
    theme.py                 dark theme
assets/                      Windows .ico and the Linux .desktop file
tools/build_appimage.sh      packs the Linux build into an AppImage
tests/                       unit tests
tools/make_icon.py           regenerates the icon
.github/workflows/build.yml  Windows + Linux builds and releases
```

## Troubleshooting

**Discord upload failed.** Hover the clip's status to see why, then right-click →
**Upload to Discord** to try again.
- *Bigger than this server's upload limit*: use a smaller Discord preset and encode again.
- *Webhook not found*: the webhook was deleted. Create a new one and paste it in the
  Discord settings.
- *Could not reach Discord*: check your internet connection or firewall.

**A clip failed.** Double-click it to see the error and the FFmpeg log. Use *Copy log*
to share it when reporting an issue.

**Checking what ClipShrinker detects.** Run it from a terminal with `--diagnose`
(for example `./ClipShrinker-linux-x86_64.AppImage --diagnose`). It prints the FFmpeg it
uses and which GPU encoders work, and is handy to include in bug reports.

**A GPU encoder shows "(not detected)".** That GPU or its driver isn't available.
Update the graphics driver, or use *CPU (software)*.
- **AMD or Intel on Linux:** use **VA-API**, not *AMD AMF* or *Intel Quick Sync*. Those
  need vendor-specific driver stacks, while VA-API works with the standard Mesa (AMD) and
  `intel-media-driver` (Intel) drivers most distros ship. If VA-API is also *not detected*,
  install your distro's VA-API driver package (for example `mesa` /
  `libva-mesa-driver`, or `intel-media-driver`). Check that `/dev/dri/renderD128` exists.
- **NVIDIA on Linux:** NVENC needs the proprietary NVIDIA driver.

**The output is slightly over the limit / quality is poor in Target size mode.** Very long
clips leave very little bitrate per second. Lower the frame rate to 30 fps, keep
Resolution on *Auto*, use H.265, or trim the clip. ClipShrinker warns when a clip is too
long for its target.

**H.265 files won't play.** Some older devices and browsers don't support HEVC. Use H.264
for maximum compatibility.

**Linux: the AppImage does nothing when double-clicked.** Make sure it is executable
(see [Download and install](#linux)). Run it from a terminal to see any error message.

**Linux: the AppImage complains about FUSE.** AppImages normally mount themselves using
FUSE. Install it (`sudo apt install fuse3` or `sudo dnf install fuse3`), or skip FUSE
entirely:

```bash
./ClipShrinker-linux-x86_64.AppImage --appimage-extract-and-run
```

**Linux: `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`.** Install the Qt
libraries listed in [Running from source](#running-from-source).

**Windows: SmartScreen blocks the app.** Click **More info → Run anyway**. The executable
isn't code-signed.

**Reset all settings.** Delete `config.json` from the folder listed under
[Preferences](#preferences).

## Credits

- [FFmpeg](https://ffmpeg.org/), the encoder behind everything, bundled through
  [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)
- [Qt for Python (PySide6)](https://doc.qt.io/qtforpython/) for the interface
