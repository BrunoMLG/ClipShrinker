"""Encoding settings and translation of those settings into FFmpeg commands."""

from __future__ import annotations

import os
import shlex
from dataclasses import asdict, dataclass, field, fields
from typing import List, Optional

from clipshrinker.ffmpeg import MediaInfo

# Rate-control modes
MODE_SIZE = "size"        # hit a target file size
MODE_QUALITY = "quality"  # constant quality (CRF / CQ)
MODE_BITRATE = "bitrate"  # fixed average bitrate

CODECS = {
    "h264": "H.264 (most compatible)",
    "h265": "H.265 / HEVC (smaller)",
    "av1": "AV1 (smallest, slow)",
    "vp9": "VP9 (WebM)",
}

HARDWARE = {
    "cpu": "CPU (software)",
    "nvenc": "NVIDIA NVENC",
    "qsv": "Intel Quick Sync",
    "amf": "AMD AMF",
    "videotoolbox": "Apple VideoToolbox",
}

ENCODERS = {
    ("h264", "cpu"): "libx264",
    ("h265", "cpu"): "libx265",
    ("av1", "cpu"): "libsvtav1",
    ("vp9", "cpu"): "libvpx-vp9",
    ("h264", "nvenc"): "h264_nvenc",
    ("h265", "nvenc"): "hevc_nvenc",
    ("av1", "nvenc"): "av1_nvenc",
    ("h264", "qsv"): "h264_qsv",
    ("h265", "qsv"): "hevc_qsv",
    ("av1", "qsv"): "av1_qsv",
    ("vp9", "qsv"): "vp9_qsv",
    ("h264", "amf"): "h264_amf",
    ("h265", "amf"): "hevc_amf",
    ("av1", "amf"): "av1_amf",
    ("h264", "videotoolbox"): "h264_videotoolbox",
    ("h265", "videotoolbox"): "hevc_videotoolbox",
}

SPEEDS = ["Fastest", "Fast", "Balanced", "Slow", "Slowest"]

# Per-encoder speed arguments, indexed by SPEEDS position.
_SPEED_ARGS = {
    "libx264": [["-preset", p] for p in ("veryfast", "faster", "medium", "slow", "veryslow")],
    "libx265": [["-preset", p] for p in ("veryfast", "faster", "medium", "slow", "veryslow")],
    "libsvtav1": [["-preset", p] for p in ("12", "10", "8", "6", "4")],
    "libvpx-vp9": [["-deadline", "good", "-cpu-used", p] for p in ("5", "4", "3", "2", "1")],
    "nvenc": [["-preset", p] for p in ("p1", "p3", "p4", "p6", "p7")],
    "qsv": [["-preset", p] for p in ("veryfast", "faster", "medium", "slow", "veryslow")],
    "amf": [["-quality", p] for p in ("speed", "speed", "balanced", "quality", "quality")],
    "videotoolbox": [[] for _ in range(5)],
}

CONTAINERS = {"mp4": "MP4", "mkv": "MKV", "webm": "WebM", "mov": "MOV"}
AUDIO_CODECS = {"aac": "AAC", "opus": "Opus", "copy": "Copy original", "none": "Remove audio"}
AUDIO_TRACKS = {"first": "First track only", "mix": "Mix all tracks"}

# Suggested constant-quality value per codec (lower = better quality, bigger file).
DEFAULT_CRF = {"h264": 23, "h265": 26, "av1": 32, "vp9": 33}
CRF_RANGE = {"h264": (0, 51), "h265": (0, 51), "av1": (0, 63), "vp9": (0, 63)}

# Rough bits-per-pixel each codec needs to look acceptable; used by auto resolution.
_MIN_BPP = {"h264": 0.04, "h265": 0.03, "av1": 0.022, "vp9": 0.03}
AUTO_HEIGHTS = [2160, 1440, 1080, 720, 540, 480, 360, 240]

# Fraction of the target size we actually aim for, leaving room for container overhead
# and rate-control overshoot.
SIZE_SAFETY = 0.96
MIN_VIDEO_KBPS = 40

# "MB" means MiB everywhere, matching Windows Explorer and Discord's upload limit.
MB = 1024 * 1024

RES_KEEP = 0
RES_AUTO = -1


@dataclass
class EncodeSettings:
    mode: str = MODE_SIZE
    target_size_mb: float = 9.5
    crf: int = 23
    video_bitrate_kbps: int = 4000

    codec: str = "h264"
    hardware: str = "cpu"
    speed: int = 2  # index into SPEEDS
    two_pass: bool = True

    max_height: int = RES_AUTO  # RES_KEEP, RES_AUTO, or the short side in pixels
    max_fps: float = 0  # 0 = keep

    audio_codec: str = "aac"
    audio_bitrate_kbps: int = 96
    audio_channels: int = 0  # 0 = keep, 1 = mono, 2 = stereo
    audio_tracks: str = "first"

    container: str = "mp4"
    strip_metadata: bool = False
    extra_args: str = ""

    def copy(self, **changes) -> "EncodeSettings":
        data = asdict(self)
        data.update(changes)
        return EncodeSettings(**data)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EncodeSettings":
        """Build from a dict, ignoring unknown keys so old config files keep loading."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})

    @property
    def encoder(self) -> str:
        return ENCODERS.get((self.codec, self.hardware), "")

    @property
    def is_software(self) -> bool:
        return self.hardware == "cpu"

    def uses_two_pass(self) -> bool:
        return (
            self.two_pass
            and self.mode in (MODE_SIZE, MODE_BITRATE)
            and self.encoder in ("libx264", "libx265", "libvpx-vp9")
        )


@dataclass
class Trim:
    start: Optional[float] = None
    end: Optional[float] = None

    def clip_duration(self, total: float) -> float:
        start = self.start or 0.0
        end = self.end if self.end is not None else total
        end = min(end, total) if total else end
        return max(0.0, end - start)

    def __bool__(self) -> bool:
        return self.start is not None or self.end is not None


@dataclass
class EncodePlan:
    passes: List[List[str]] = field(default_factory=list)
    video_kbps: Optional[int] = None
    out_height: Optional[int] = None
    duration: float = 0.0
    estimated_bytes: Optional[int] = None
    warnings: List[str] = field(default_factory=list)


def validate(settings: EncodeSettings) -> List[str]:
    """Problems that make the settings unusable."""
    errors = []
    if not settings.encoder:
        errors.append(
            f"{CODECS[settings.codec].split(' ')[0]} is not supported by "
            f"{HARDWARE[settings.hardware]}."
        )
    if settings.container == "webm" and settings.codec not in ("vp9", "av1"):
        errors.append("WebM only supports VP9 or AV1 video.")
    if settings.container == "webm" and settings.audio_codec == "aac":
        errors.append("WebM does not support AAC audio, pick Opus.")
    if settings.mode == MODE_SIZE and settings.target_size_mb <= 0:
        errors.append("Target size must be greater than zero.")
    return errors


def size_to_video_kbps(target_mb: float, duration: float, audio_kbps: float) -> float:
    """Video bitrate (kbit/s) that lands the whole file under target_mb."""
    total_kbits = target_mb * MB * 8 / 1000 * SIZE_SAFETY
    return total_kbits / max(duration, 0.1) - audio_kbps


def pick_auto_height(video_kbps: float, fps: float, src_short: int, codec: str) -> int:
    """Largest common resolution the bitrate can sustain without looking awful."""
    fps = fps or 30
    aspect = 16 / 9
    for h in AUTO_HEIGHTS:
        if h > src_short:
            continue
        bpp = video_kbps * 1000 / (h * h * aspect * fps)
        if bpp >= _MIN_BPP.get(codec, 0.05):
            return h
    return min(AUTO_HEIGHTS[-1], src_short)


def _effective_audio_kbps(settings: EncodeSettings, info: MediaInfo) -> float:
    if not info.has_audio or settings.audio_codec == "none":
        return 0
    if settings.audio_codec == "copy":
        # Unknown exactly; assume a typical stereo track.
        return 160
    return settings.audio_bitrate_kbps


def _quality_args(settings: EncodeSettings) -> List[str]:
    enc, q = settings.encoder, int(settings.crf)
    if enc in ("libx264", "libx265", "libsvtav1"):
        return ["-crf", str(q)]
    if enc == "libvpx-vp9":
        return ["-crf", str(q), "-b:v", "0"]
    if enc.endswith("_nvenc"):
        return ["-rc", "vbr", "-cq", str(q), "-b:v", "0"]
    if enc.endswith("_qsv"):
        return ["-global_quality", str(q)]
    if enc.endswith("_amf"):
        return ["-rc", "cqp", "-qp_i", str(q), "-qp_p", str(q), "-qp_b", str(q)]
    if enc.endswith("_videotoolbox"):
        # VideoToolbox quality is 1-100 where higher is better.
        return ["-q:v", str(max(1, min(100, 100 - q * 2)))]
    return []


def _bitrate_args(settings: EncodeSettings, kbps: int) -> List[str]:
    enc = settings.encoder
    args = ["-b:v", f"{kbps}k"]
    if enc in ("libx264", "libx265"):
        # A loose VBV cap keeps peaks sane without hurting quality much.
        args += ["-maxrate", f"{int(kbps * 1.5)}k", "-bufsize", f"{kbps * 2}k"]
    elif enc.endswith("_nvenc"):
        args = ["-rc", "vbr"] + args + ["-maxrate", f"{int(kbps * 1.2)}k", "-bufsize", f"{kbps * 2}k"]
    elif not settings.is_software:
        args += ["-maxrate", f"{int(kbps * 1.1)}k", "-bufsize", f"{kbps * 2}k"]
    return args


def _speed_args(settings: EncodeSettings) -> List[str]:
    key = settings.encoder if settings.is_software else settings.hardware
    table = _SPEED_ARGS.get(key)
    if not table:
        return []
    return list(table[max(0, min(len(table) - 1, settings.speed))])


def _video_filters(settings: EncodeSettings, info: MediaInfo, height: Optional[int]) -> List[str]:
    filters = []
    if height and info.width and info.height:
        portrait = info.height > info.width
        short = min(info.width, info.height)
        if height < short:
            # Constrain the short side so "720p" means the same thing for portrait clips.
            filters.append(f"scale={height}:-2" if portrait else f"scale=-2:{height}")
    if settings.max_fps and info.fps and info.fps > settings.max_fps + 0.01:
        filters.append(f"fps={settings.max_fps:g}")
    return filters


def build_plan(
    ffmpeg: str,
    info: MediaInfo,
    settings: EncodeSettings,
    src: str,
    dst: str,
    trim: Optional[Trim] = None,
    passlog: str = "",
    size_scale: float = 1.0,
) -> EncodePlan:
    """Translate settings into the FFmpeg command(s) for one file.

    size_scale shrinks the bitrate budget; it is used to retry when a size-targeted
    encode overshoots.
    """
    trim = trim or Trim()
    plan = EncodePlan()
    duration = trim.clip_duration(info.duration) if trim else info.duration
    plan.duration = duration

    audio_kbps = _effective_audio_kbps(settings, info)
    src_short = min(info.width, info.height) if info.width else 0

    video_kbps: Optional[float] = None
    if settings.mode == MODE_SIZE:
        video_kbps = size_to_video_kbps(settings.target_size_mb * size_scale, duration, audio_kbps)
        if video_kbps < MIN_VIDEO_KBPS:
            plan.warnings.append(
                f"Clip is too long for {settings.target_size_mb:g} MB - quality will be very poor."
            )
            video_kbps = MIN_VIDEO_KBPS
    elif settings.mode == MODE_BITRATE:
        video_kbps = settings.video_bitrate_kbps * size_scale

    height: Optional[int] = None
    if settings.max_height == RES_AUTO:
        if video_kbps is not None and src_short:
            height = pick_auto_height(video_kbps, settings.max_fps or info.fps, src_short, settings.codec)
    elif settings.max_height > 0:
        height = settings.max_height
    if height and src_short and height >= src_short:
        height = None
    plan.out_height = height or src_short or None

    if video_kbps is not None:
        plan.video_kbps = int(video_kbps)
        plan.estimated_bytes = int((video_kbps + audio_kbps) * 1000 / 8 * duration)

    head = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-v", "warning", "-progress", "pipe:1", "-nostats"]
    if trim.start:
        head += ["-ss", f"{trim.start:.3f}"]
    head += ["-i", src]
    if trim:
        head += ["-t", f"{duration:.3f}"]

    video = ["-c:v", settings.encoder] + _speed_args(settings)
    video += _quality_args(settings) if video_kbps is None else _bitrate_args(settings, int(video_kbps))
    if settings.encoder in ("libx264", "libx265", "libsvtav1", "libvpx-vp9") or settings.encoder.endswith(
        ("_videotoolbox", "_nvenc", "_amf")
    ):
        # 8-bit 4:2:0 plays everywhere (Discord, browsers, phones).
        video += ["-pix_fmt", "yuv420p"]
    elif settings.encoder.endswith("_qsv"):
        video += ["-pix_fmt", "nv12"]
    if settings.encoder == "libx265" or (settings.codec == "h265" and settings.container in ("mp4", "mov")):
        video += ["-tag:v", "hvc1"]  # lets Apple devices play HEVC in MP4

    vf = _video_filters(settings, info, height)

    mix_audio = (
        settings.audio_tracks == "mix" and info.audio_streams > 1 and settings.audio_codec not in ("none", "copy")
    )
    maps: List[str] = []
    filter_args: List[str] = []
    if mix_audio:
        inputs = "".join(f"[0:a:{i}]" for i in range(info.audio_streams))
        graph = f"{inputs}amix=inputs={info.audio_streams}:normalize=0[aout]"
        if vf:
            graph = f"[0:v:0]{','.join(vf)}[vout];" + graph
            maps += ["-map", "[vout]"]
        else:
            maps += ["-map", "0:v:0"]
        maps += ["-map", "[aout]"]
        filter_args = ["-filter_complex", graph]
    else:
        maps += ["-map", "0:v:0"]
        if settings.audio_codec != "none":
            maps += ["-map", "0:a:0?"]
        if vf:
            filter_args = ["-vf", ",".join(vf)]

    audio: List[str]
    if settings.audio_codec == "none" or not info.has_audio:
        audio = ["-an"]
    elif settings.audio_codec == "copy":
        audio = ["-c:a", "copy"]
    else:
        audio = ["-c:a", "libopus" if settings.audio_codec == "opus" else "aac",
                 "-b:a", f"{settings.audio_bitrate_kbps}k"]
        if settings.audio_channels:
            audio += ["-ac", str(settings.audio_channels)]

    tail: List[str] = []
    if settings.strip_metadata:
        tail += ["-map_metadata", "-1"]
    if settings.container in ("mp4", "mov"):
        tail += ["-movflags", "+faststart"]
    if settings.extra_args.strip():
        tail += shlex.split(settings.extra_args, posix=os.name != "nt")

    if settings.uses_two_pass():
        if settings.encoder == "libx265":
            p1 = ["-x265-params", f"pass=1:stats={passlog}.log"]
            p2 = ["-x265-params", f"pass=2:stats={passlog}.log"]
        else:
            p1 = ["-pass", "1", "-passlogfile", passlog]
            p2 = ["-pass", "2", "-passlogfile", passlog]
        # The analysis pass only looks at video, so skip audio mapping and mixing.
        first_vf = ["-vf", ",".join(vf)] if vf else []
        first = head + first_vf + ["-map", "0:v:0"] + video + p1 + ["-an", "-f", "null", os.devnull]
        second = head + filter_args + maps + video + p2 + audio + tail + [dst]
        plan.passes = [first, second]
    else:
        plan.passes = [head + filter_args + maps + video + audio + tail + [dst]]
    return plan
