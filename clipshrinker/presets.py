"""Built-in compression presets."""

from __future__ import annotations

from dataclasses import dataclass

from clipshrinker.encode import (
    MODE_BITRATE,
    MODE_QUALITY,
    MODE_SIZE,
    RES_AUTO,
    RES_KEEP,
    EncodeSettings,
)


@dataclass
class Preset:
    name: str
    description: str
    settings: EncodeSettings
    builtin: bool = True
    category: str = "Size limit"


def _size(mb: float, **kw) -> EncodeSettings:
    return EncodeSettings(mode=MODE_SIZE, target_size_mb=mb, **kw)


def _quality(crf: int, **kw) -> EncodeSettings:
    return EncodeSettings(mode=MODE_QUALITY, crf=crf, two_pass=False, **kw)


BUILTIN_PRESETS = [
    # --- Upload limits -------------------------------------------------------
    Preset(
        "Discord (10 MB)",
        "Fits Discord's free upload limit. Resolution adapts to the clip length.",
        _size(9.5, max_height=RES_AUTO, max_fps=60, audio_bitrate_kbps=96),
    ),
    Preset(
        "Discord Nitro Basic (50 MB)",
        "Fits the Nitro Basic upload limit.",
        _size(48, max_height=RES_AUTO, max_fps=60, audio_bitrate_kbps=128),
    ),
    Preset(
        "Discord Nitro (500 MB)",
        "Fits the full Nitro upload limit, up to 1440p.",
        _size(480, max_height=1440, max_fps=60, audio_bitrate_kbps=160),
    ),
    Preset(
        "WhatsApp / Messaging (16 MB)",
        "Small enough to send as a regular video message.",
        _size(15, max_height=RES_AUTO, max_fps=30, audio_bitrate_kbps=96),
    ),
    Preset(
        "Email attachment (25 MB)",
        "Fits most email providers' attachment limit.",
        _size(23.5, max_height=RES_AUTO, max_fps=30, audio_bitrate_kbps=96),
    ),
    # --- Quality-based ------------------------------------------------------
    Preset(
        "High quality",
        "Visually close to the original at roughly half the size.",
        _quality(19, codec="h264", speed=3, max_height=RES_KEEP, audio_bitrate_kbps=192),
        category="Quality",
    ),
    Preset(
        "Balanced",
        "Good quality and a solid size reduction. Plays everywhere.",
        _quality(23, codec="h264", max_height=1080, audio_bitrate_kbps=128),
        category="Quality",
    ),
    Preset(
        "Small (HEVC)",
        "H.265 at 720p - much smaller, still looks good.",
        _quality(28, codec="h265", max_height=720, audio_bitrate_kbps=96),
        category="Quality",
    ),
    Preset(
        "Tiny",
        "480p, 30 fps, mono audio. For when size is all that matters.",
        _quality(32, codec="h265", max_height=480, max_fps=30, audio_bitrate_kbps=48, audio_channels=1),
        category="Quality",
    ),
    Preset(
        "Archive (AV1)",
        "Best compression for long-term storage. Slower to encode.",
        _quality(30, codec="av1", speed=2, max_height=RES_KEEP, audio_codec="opus",
                 audio_bitrate_kbps=128, container="mkv"),
        category="Quality",
    ),
    Preset(
        "Web (VP9 WebM)",
        "WebM for embedding on websites.",
        _quality(33, codec="vp9", max_height=1080, audio_codec="opus", audio_bitrate_kbps=96,
                 container="webm"),
        category="Quality",
    ),
    # --- Fast / hardware ----------------------------------------------------
    Preset(
        "Fast GPU (NVIDIA)",
        "Uses an NVIDIA GPU for very fast H.264 encoding.",
        _quality(25, codec="h264", hardware="nvenc", speed=2, max_height=1080),
        category="Hardware",
    ),
    Preset(
        "Fast GPU (AMD)",
        "Uses an AMD GPU for very fast H.264 encoding.",
        _quality(25, codec="h264", hardware="amf", speed=2, max_height=1080),
        category="Hardware",
    ),
    Preset(
        "Fast GPU (Intel)",
        "Uses Intel Quick Sync for very fast H.264 encoding.",
        _quality(25, codec="h264", hardware="qsv", speed=2, max_height=1080),
        category="Hardware",
    ),
    Preset(
        "Classic ClipShrinker",
        "The original 1.x settings: 720p60, 4 Mbps video, 96 kbps audio.",
        EncodeSettings(mode=MODE_BITRATE, video_bitrate_kbps=4000, two_pass=False,
                       max_height=720, max_fps=60, audio_bitrate_kbps=96),
        category="Other",
    ),
]

DEFAULT_PRESET = BUILTIN_PRESETS[0].name
