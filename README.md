<p align="center">
  <img src="clipshrinker/resources/icon.png" width="96" alt="ClipShrinker icon">
</p>

# ClipShrinker

ClipShrinker is a desktop app for compressing video clips in batches. Drop in a pile of
clips, pick a preset such as **Discord (10 MB)**, and press **Start**. Each clip is sized to
fit the limit based on its own length. FFmpeg is bundled, so there's nothing else to install.

Runs on **Windows** and **Linux** (macOS works from source).

## Features

- **Queue**: add any number of clips (or whole folders) by drag & drop or the file picker.
  Each clip shows live progress, time left, and the final size. You can reorder, cancel,
  retry, or remove clips, and encode several at once.
- **Presets**
  - Upload limits: Discord (10 MB), Discord Nitro Basic (50 MB), Discord Nitro (500 MB),
    WhatsApp / Messaging (16 MB), Email (25 MB)
  - Quality: High quality, Balanced, Small (HEVC), Tiny, Archive (AV1), Web (VP9 WebM)
  - Hardware: fast GPU encoding on NVIDIA, AMD, and Intel
  - Classic ClipShrinker (the original 1.x settings)
  - **Your own presets**: tweak any setting and click *Save as…*
- **Fine-tuning**
  - Three rate-control modes: *Target size*, *Quality* (CRF), or *Bitrate*
  - Codecs: H.264, H.265/HEVC, AV1, VP9
  - Encoders: CPU, NVIDIA NVENC, Intel Quick Sync, AMD AMF, Apple VideoToolbox. The app
    checks which ones actually work on your machine.
  - Speed / efficiency slider, two-pass encoding
  - Resolution cap, including **Auto**, which picks the best resolution the size limit
    allows. Portrait clips are handled correctly.
  - Frame-rate cap, audio codec / bitrate / mono, removing audio
  - **Mixing every audio track into one**, for OBS recordings with separate game and mic tracks
  - **Trim** (start/end) for each clip
  - Output format (MP4, MKV, WebM, MOV), output folder, file-name template, what to do
    when the file already exists, metadata stripping, extra FFmpeg arguments
- **Size-limit safety net**: if a clip still comes out over the limit, it is re-encoded
  automatically with a lower bitrate. Clips that are already small enough are skipped.
- Live size estimate for the selected clip, a notification when the queue finishes, and
  settings that persist between runs.

## Download

Get the latest build from [Releases](https://github.com/BrunoMLG/ClipShrinker/releases):

| Platform | File | How to run |
| --- | --- | --- |
| Windows | `ClipShrinker-windows-x64.exe` | Double-click it. Nothing to install. |
| Linux | `ClipShrinker-linux-x64.tar.gz` | Extract it, then run `./ClipShrinker`, or run `./install-linux.sh` to add it to your app menu. |

## Running from source

Requires Python 3.9+.

```bash
python -m venv .venv
```

Activate it (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` on Linux/macOS), then:

```bash
pip install -r requirements.txt
```

```bash
python ClipShrinker.py
```

You can also pass files on the command line (`python ClipShrinker.py clip1.mp4 folder/`) to
add them to the queue.

## Building the executables

Builds run on **GitHub Actions** (`.github/workflows/build.yml`) for Windows and Linux on every
push. Pushing a version tag publishes a GitHub Release with both files attached:

```bash
git tag v2.0.0 && git push origin v2.0.0
```

To build locally, on the platform you're targeting:

```bash
pip install -r requirements-dev.txt
```

```bash
pyinstaller --noconfirm ClipShrinker.spec
```

The executable ends up in `dist/`. PyInstaller can't cross-compile, so build the Windows `.exe`
on Windows and the Linux binary on Linux (or just let CI do both).

## Development

```bash
pytest
```

Project layout:

```
clipshrinker/
  encode.py        settings model + FFmpeg command builder (pure Python, unit tested)
  presets.py       built-in presets
  ffmpeg.py        locating FFmpeg, probing files, detecting hardware encoders
  jobs.py          the queue: runs FFmpeg via QProcess, progress, retries
  config.py        settings saved to the user config folder
  ui/              PySide6 interface (main window, queue list, settings panel, dialogs)
tools/make_icon.py regenerates the app icon
```

Settings are stored in `%APPDATA%\ClipShrinker\config.json` on Windows and
`~/.config/clipshrinker/config.json` on Linux.
