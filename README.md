# ClipShrinker

ClipShrinker is a simple Python-based GUI application designed to compress MP4 video files to meet Discord's upload requirements. The application uses **FFmpeg** (bundled with the app) to optimize videos, reducing file size, adjusting frame rate, resolution, and bitrates, making them ready for upload to Discord.

## Features

- **Video Input Selection**: Choose an MP4 video to compress.
- **Output Path Selection**: The program suggests an output file name, but you can customize it.
- **Video Compression**: The app uses FFmpeg to compress the input video, optimizing it for upload to Discord with the following settings:
  - **Resolution**: 1280x720 (HD)
  - **Frame rate**: 60 FPS
  - **Audio bitrate**: 96 Kbps
  - **Video bitrate**: 4 Mbps
  - **File size limit**: ~7.95 MB (to fit Discord’s file size limitations)

## Requirements

- **Python 3.x** (Python 3.6+ recommended) if you want to run the source code.
- **FFmpeg** (bundled with the application through `imageio-ffmpeg`).
- Required Python packages:
  - `tkinter` (for the GUI)
  - `subprocess` (to run FFmpeg commands)
  - `imageio-ffmpeg` (bundled for FFmpeg functionality)

## Installation

### 1. Install Python dependencies (if running the source code):
Make sure you have Python installed on your system. Then, install the necessary libraries using `pip`:
```bash
pip install tk imageio-ffmpeg
```

### 2. Running the Program
To run the program from source, execute the following command in your terminal:
```bash
python ClipShrinker.py
```
### 3. Build Standalone Executable

To create a standalone .exe file for Windows (with no need for Python installation), use PyInstaller.
Steps to create the .exe:

    Install PyInstaller:

pip install pyinstaller

Run the following command to create the executable:

    pyinstaller --onefile --noconsole --icon=ClipShrinker.ico --name "ClipShrinker" ClipShrinker.py

    This will generate a ClipShrinker.exe file in the dist/ directory, which can be distributed and run without Python.

This will launch the GUI where you can select the input video, choose an output location, and render the compressed video.

## Usage

1. **Select Input File**: Click on "Select Input File" to choose the MP4 video you want to compress.
2. **Select Output File**: Click on "Select Output File" to choose where to save the compressed video.
3. **Render**: Click "Render" to compress the video for Discord. The app will apply the optimized settings and save the file at the selected location.

Once the process is complete, a success message will appear, and the input/output paths will be reset, ready for the next task.

## Executable Version

If you don’t want to install Python or set up dependencies, an **executable version** of the application is available in the [Releases](https://github.com/BrunoMLG/ClipShrinker/releases) section. You can download and run the `.exe` directly on your Windows machine, which makes it easier for users to compress videos without any additional setup.

### Best Way to Use the Software

For users who just want to quickly compress videos for Discord:

1. **Download the latest `.exe`** from the [Releases](https://github.com/BrunoMLG/ClipShrinker/releases) section.
2. **Run the executable** and follow the simple GUI prompts:
   - Select your input video.
   - Choose the output location and file name.
   - Click "Render" to compress the video.

The application will automatically handle everything, ensuring that the video file is optimized to fit within Discord's 8 MB file size limit.

## Purpose

The primary goal of **ClipShrinker** is to help users compress video files to meet Discord’s upload restrictions. Videos on Discord are limited to a file size of **8 MB** for non-Nitro users. This tool automatically adjusts the video’s quality, size, and resolution, ensuring it fits within Discord’s constraints while maintaining acceptable video quality.

---
