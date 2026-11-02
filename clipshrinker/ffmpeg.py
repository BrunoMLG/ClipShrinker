"""Locating FFmpeg, probing media files and detecting available encoders."""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

# Keep FFmpeg from flashing a console window when we run it from the GUI on Windows.
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def find_ffmpeg(override: str = "") -> str:
    """Return the FFmpeg executable to use.

    Order: user override -> bundled imageio-ffmpeg binary -> ffmpeg on PATH.
    """
    if override and os.path.isfile(override):
        return override
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError(
        "FFmpeg was not found. Install it or set its path in Preferences."
    )


@dataclass
class MediaInfo:
    duration: float = 0.0  # seconds
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_streams: int = 0
    audio_codec: str = ""
    bitrate_kbps: int = 0
    size_bytes: int = 0

    @property
    def has_audio(self) -> bool:
        return self.audio_streams > 0

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}" if self.width else "—"


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_BITRATE_RE = re.compile(r"Duration:.*?bitrate:\s*(\d+)\s*kb/s")
_VIDEO_RE = re.compile(r"Stream #\S+.*?: Video: (\w+).*?, (\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")
_AUDIO_RE = re.compile(r"Stream #\S+.*?: Audio: (\w+)")


def parse_probe_output(text: str) -> MediaInfo:
    """Parse the stderr of ``ffmpeg -i <file>`` into a MediaInfo."""
    info = MediaInfo()
    m = _DURATION_RE.search(text)
    if m:
        h, mi, s = m.groups()
        info.duration = int(h) * 3600 + int(mi) * 60 + float(s)
    m = _BITRATE_RE.search(text)
    if m:
        info.bitrate_kbps = int(m.group(1))
    for line in text.splitlines():
        if not info.width:
            vm = _VIDEO_RE.search(line)
            # Skip cover-art streams (attached pictures) and keep the real video track.
            if vm and "attached pic" not in line:
                info.video_codec = vm.group(1)
                info.width, info.height = int(vm.group(2)), int(vm.group(3))
                fm = _FPS_RE.search(line)
                if fm:
                    info.fps = float(fm.group(1))
                continue
        am = _AUDIO_RE.search(line)
        if am:
            if not info.audio_streams:
                info.audio_codec = am.group(1)
            info.audio_streams += 1
    return info


def probe(ffmpeg: str, path: str) -> MediaInfo:
    """Read basic stream information. Raises ValueError if the file has no video."""
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", path],
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=NO_WINDOW,
    )
    info = parse_probe_output(proc.stderr)
    if not info.width:
        last = proc.stderr.strip().splitlines()[-1:] or ["Unknown error"]
        raise ValueError(f"No video stream found ({last[0]})")
    info.size_bytes = os.path.getsize(path)
    return info


@lru_cache(maxsize=4)
def available_encoders(ffmpeg: str) -> frozenset:
    """Names of encoders compiled into this FFmpeg build."""
    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=NO_WINDOW,
        ).stdout
    except OSError:
        return frozenset()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS":
            names.add(parts[1])
    return frozenset(names)


@lru_cache(maxsize=32)
def encoder_works(ffmpeg: str, encoder: str, vaapi_device: str = "") -> bool:
    """Hardware encoders can be compiled in yet unusable (no GPU / driver).

    Encode a handful of blank frames to find out for sure.
    """
    pre, vf = [], []
    if vaapi_device:
        pre = ["-vaapi_device", vaapi_device]
        vf = ["-vf", "format=nv12,hwupload"]
    try:
        proc = subprocess.run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", *pre,
                "-f", "lavfi", "-i", "color=black:s=256x256:r=30",
                "-frames:v", "5", *vf, "-c:v", encoder, "-f", "null", "-",
            ],
            capture_output=True,
            timeout=20,
            creationflags=NO_WINDOW,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_vaapi_device(ffmpeg: str) -> str:
    """First GPU render node that can encode H.264 or HEVC through VA-API ("" if none).

    Machines with an integrated and a dedicated GPU have several nodes, and not every
    one of them can encode.
    """
    if not sys.platform.startswith("linux"):
        return ""
    for node in sorted(glob.glob("/dev/dri/renderD*")):
        if os.access(node, os.R_OK | os.W_OK) and any(
            encoder_works(ffmpeg, enc, node) for enc in ("h264_vaapi", "hevc_vaapi")
        ):
            return node
    return ""


HW_KINDS = ("nvenc", "qsv", "amf", "videotoolbox")


def detect_hardware(ffmpeg: str):
    """({hardware: works}, vaapi render node or "") for every GPU encoder family."""
    compiled = available_encoders(ffmpeg)
    result = {"cpu": True}
    for hw in HW_KINDS:
        enc = f"h264_{hw}"
        result[hw] = enc in compiled and encoder_works(ffmpeg, enc)
    device = find_vaapi_device(ffmpeg) if {"h264_vaapi", "hevc_vaapi"} & compiled else ""
    result["vaapi"] = bool(device)
    return result, device


def restore_child_environment() -> None:
    """Give programs we launch the system's library path, not the bundle's.

    In a frozen Linux build the PyInstaller bootloader points LD_LIBRARY_PATH at the
    bundled libraries. FFmpeg inherits that, and the GPU driver it loads for VA-API
    (Mesa) then picks up the bundle's older libraries and fails to initialize. The app
    itself is unaffected: the loader reads LD_LIBRARY_PATH only when a process starts.
    """
    if not getattr(sys, "frozen", False) or not sys.platform.startswith("linux"):
        return
    original = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
    if original:
        os.environ["LD_LIBRARY_PATH"] = original
    else:
        os.environ.pop("LD_LIBRARY_PATH", None)


def format_size(num_bytes: Optional[float]) -> str:
    if num_bytes is None or num_bytes < 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return "—"


def format_duration(seconds: float) -> str:
    if not seconds:
        return "—"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_timecode(text: str) -> Optional[float]:
    """Accept '90', '1:30', '01:01:30.5'. Returns None for empty input."""
    text = text.strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid time: {text}")
    total = 0.0
    for part in parts:
        total = total * 60 + float(part)
    if total < 0:
        raise ValueError(f"Invalid time: {text}")
    return total
