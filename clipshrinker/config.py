"""Persistent user configuration (JSON in the platform's config directory)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from typing import List

from clipshrinker.encode import EncodeSettings
from clipshrinker.presets import DEFAULT_PRESET, BUILTIN_PRESETS


def config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "ClipShrinker")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/ClipShrinker")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "clipshrinker")


OVERWRITE_MODES = {
    "rename": "Add a number (clip_1.mp4)",
    "overwrite": "Overwrite existing file",
    "skip": "Skip the clip",
}


@dataclass
class AppConfig:
    preset: str = DEFAULT_PRESET
    settings: dict = field(default_factory=lambda: BUILTIN_PRESETS[0].settings.to_dict())
    custom_presets: List[dict] = field(default_factory=list)

    output_dir: str = ""  # empty = next to the source file
    name_template: str = "{name}_shrunk"
    overwrite: str = "rename"

    concurrent_jobs: int = 1
    skip_if_smaller: bool = True
    retry_oversize: bool = True
    open_folder_when_done: bool = False
    notify_when_done: bool = True
    ffmpeg_path: str = ""

    # Discord webhook auto-upload
    discord_enabled: bool = False
    discord_webhook: str = ""
    discord_message: str = "{name}"
    discord_webhook_name: str = ""
    discord_guild_id: str = ""

    last_open_dir: str = ""
    window_geometry: str = ""
    splitter_state: str = ""

    @property
    def encode_settings(self) -> EncodeSettings:
        return EncodeSettings.from_dict(self.settings)

    @classmethod
    def path(cls) -> str:
        return os.path.join(config_dir(), "config.json")

    @classmethod
    def load(cls) -> "AppConfig":
        try:
            with open(cls.path(), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        try:
            return cls(**{k: v for k, v in data.items() if k in known})
        except TypeError:
            return cls()

    def save(self) -> None:
        os.makedirs(config_dir(), exist_ok=True)
        tmp = self.path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
        os.replace(tmp, self.path())
