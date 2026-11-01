import os

import pytest

from clipshrinker.encode import (
    MODE_BITRATE,
    MODE_QUALITY,
    MB,
    MODE_SIZE,
    RES_KEEP,
    EncodeSettings,
    Trim,
    build_plan,
    pick_auto_height,
    size_to_video_kbps,
    validate,
)
from clipshrinker.ffmpeg import MediaInfo, parse_probe_output, parse_timecode
from clipshrinker.jobs import resolve_output
from clipshrinker.presets import BUILTIN_PRESETS

PROBE = """
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clip.mp4':
  Duration: 00:01:30.50, start: 0.000000, bitrate: 51994 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 51914 kb/s, 59.94 fps, 60 tbr, 15360 tbn (default)
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 160 kb/s (default)
  Stream #0:2[0x3](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 160 kb/s
"""

INFO = MediaInfo(duration=60, width=1920, height=1080, fps=60, audio_streams=1, size_bytes=200_000_000)


def test_parse_probe():
    info = parse_probe_output(PROBE)
    assert info.duration == pytest.approx(90.5)
    assert (info.width, info.height) == (1920, 1080)
    assert info.fps == pytest.approx(59.94)
    assert info.audio_streams == 2
    assert info.bitrate_kbps == 51994


def test_parse_timecode():
    assert parse_timecode("") is None
    assert parse_timecode("90") == 90
    assert parse_timecode("1:30") == 90
    assert parse_timecode("1:00:00.5") == 3600.5
    with pytest.raises(ValueError):
        parse_timecode("abc")


def test_size_budget_fits_target():
    kbps = size_to_video_kbps(10, 60, 96)
    total_mb = (kbps + 96) * 1000 / 8 * 60 / MB
    assert total_mb < 10


def test_auto_height_drops_resolution_for_long_clips():
    assert pick_auto_height(size_to_video_kbps(9.5, 30, 96), 60, 1080, "h264") >= 720
    assert pick_auto_height(size_to_video_kbps(9.5, 600, 96), 60, 1080, "h264") <= 360
    # Never upscales.
    assert pick_auto_height(50_000, 30, 480, "h264") == 480


def test_size_mode_two_pass():
    s = EncodeSettings(mode=MODE_SIZE, target_size_mb=10, two_pass=True)
    plan = build_plan("ffmpeg", INFO, s, "in.mp4", "out.mp4", passlog="/tmp/log")
    assert len(plan.passes) == 2
    first, second = plan.passes
    assert first[-1] == os.devnull and "-an" in first
    assert second[-1] == "out.mp4"
    assert "-pass" in second and "-b:v" in second
    assert plan.estimated_bytes < 10 * MB


def test_quality_mode_single_pass_and_scaling():
    s = EncodeSettings(mode=MODE_QUALITY, crf=28, codec="h265", max_height=720, max_fps=30)
    plan = build_plan("ffmpeg", INFO, s, "in.mp4", "out.mp4")
    cmd = plan.passes[0]
    assert len(plan.passes) == 1
    assert cmd[cmd.index("-c:v") + 1] == "libx265"
    assert cmd[cmd.index("-crf") + 1] == "28"
    assert cmd[cmd.index("-vf") + 1] == "scale=-2:720,fps=30"


def test_portrait_scales_short_side():
    portrait = MediaInfo(duration=10, width=1080, height=1920, fps=30, audio_streams=1)
    s = EncodeSettings(mode=MODE_QUALITY, max_height=720)
    cmd = build_plan("ffmpeg", portrait, s, "in.mp4", "out.mp4").passes[0]
    assert cmd[cmd.index("-vf") + 1] == "scale=720:-2"


def test_no_upscale_and_keep():
    s = EncodeSettings(mode=MODE_QUALITY, max_height=2160)
    assert "-vf" not in build_plan("ffmpeg", INFO, s, "a", "b").passes[0]
    s = EncodeSettings(mode=MODE_QUALITY, max_height=RES_KEEP)
    assert "-vf" not in build_plan("ffmpeg", INFO, s, "a", "b").passes[0]


def test_trim_and_mix_audio():
    info = MediaInfo(duration=60, width=1280, height=720, fps=30, audio_streams=3)
    s = EncodeSettings(mode=MODE_BITRATE, video_bitrate_kbps=2000, two_pass=False, audio_tracks="mix")
    plan = build_plan("ffmpeg", info, s, "in.mp4", "out.mp4", trim=Trim(10, 25))
    cmd = plan.passes[0]
    assert plan.duration == 15
    assert cmd[cmd.index("-ss") + 1] == "10.000"
    assert cmd[cmd.index("-t") + 1] == "15.000"
    assert "amix=inputs=3" in cmd[cmd.index("-filter_complex") + 1]


def test_remove_audio():
    s = EncodeSettings(mode=MODE_QUALITY, audio_codec="none")
    cmd = build_plan("ffmpeg", INFO, s, "a", "b").passes[0]
    assert "-an" in cmd and "0:a:0?" not in cmd


def test_hardware_has_no_two_pass():
    s = EncodeSettings(mode=MODE_SIZE, hardware="nvenc", two_pass=True)
    plan = build_plan("ffmpeg", INFO, s, "a", "b")
    assert len(plan.passes) == 1
    assert "h264_nvenc" in plan.passes[0]


def test_validate():
    assert validate(EncodeSettings()) == []
    assert validate(EncodeSettings(codec="vp9", hardware="nvenc"))
    assert validate(EncodeSettings(container="webm"))


@pytest.mark.parametrize("preset", BUILTIN_PRESETS, ids=lambda p: p.name)
def test_builtin_presets_are_valid(preset):
    assert validate(preset.settings) == []
    build_plan("ffmpeg", INFO, preset.settings, "a.mp4", "b." + preset.settings.container, passlog="x")


def test_resolve_output(tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"x")
    s = EncodeSettings()
    dst = resolve_output(str(src), s, "", "{name}_shrunk", "rename", set())
    assert dst == str(tmp_path / "clip_shrunk.mp4")
    (tmp_path / "clip_shrunk.mp4").write_bytes(b"x")
    assert resolve_output(str(src), s, "", "{name}_shrunk", "rename", set()).endswith("clip_shrunk_1.mp4")
    assert resolve_output(str(src), s, "", "{name}_shrunk", "skip", set()) is None
    # Never overwrite the source itself.
    assert resolve_output(str(src), s, "", "{name}", "overwrite", set()).endswith("clip_1.mp4")
