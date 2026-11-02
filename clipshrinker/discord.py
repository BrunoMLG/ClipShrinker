"""Posting finished clips to a Discord channel through a webhook (no Qt, plain stdlib)."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import ssl
import time
import uuid
from typing import Callable, Optional, Tuple
from urllib import error, request

from clipshrinker import __version__

# Discord's API sits behind Cloudflare, which rejects Python's default user agent.
USER_AGENT = f"DiscordBot (https://github.com/BrunoMLG/ClipShrinker, {__version__})"

_WEBHOOK_RE = re.compile(
    r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api(?:/v\d+)?/webhooks/(\d+)/([\w-]+)/?(?:\?.*)?$"
)

MAX_RATE_LIMIT_RETRIES = 3
CHUNK = 256 * 1024


class DiscordError(Exception):
    pass


def parse_webhook_url(url: str) -> Optional[Tuple[str, str]]:
    """(id, token) for a valid Discord webhook URL, otherwise None."""
    m = _WEBHOOK_RE.match(url.strip())
    return (m.group(1), m.group(2)) if m else None


def normalize_webhook_url(url: str) -> str:
    parsed = parse_webhook_url(url)
    if not parsed:
        raise DiscordError("That isn't a Discord webhook URL.")
    return f"https://discord.com/api/webhooks/{parsed[0]}/{parsed[1]}"


def _ssl_context() -> ssl.SSLContext:
    # Bundled Python builds can't always find the OS certificate store (notably inside the
    # Linux AppImage), so prefer certifi's CA bundle when it's available.
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _open(req: request.Request, timeout: float):
    ctx = _ssl_context() if req.full_url.startswith("https:") else None
    return request.urlopen(req, timeout=timeout, context=ctx)


def _error_message(exc: error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
    except ValueError:
        body = {}
    if exc.code == 413:
        return "The file is bigger than this server's upload limit."
    if exc.code == 404:
        return "Webhook not found. It may have been deleted."
    if exc.code in (401, 403):
        return "Discord refused the webhook (invalid token or no permission)."
    detail = body.get("message") if isinstance(body, dict) else None
    return f"Discord error {exc.code}" + (f": {detail}" if detail else "")


def get_webhook_info(url: str, timeout: float = 15) -> dict:
    """Fetch the webhook's name, channel and server ids. Raises DiscordError."""
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _open(req, timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise DiscordError(_error_message(exc)) from None
    except (error.URLError, OSError, ValueError) as exc:
        raise DiscordError(f"Could not reach Discord: {getattr(exc, 'reason', exc)}") from None


class _MultipartBody:
    """Streams a multipart/form-data body so big files aren't loaded into memory."""

    def __init__(self, payload: dict, path: str, progress: Optional[Callable[[int, int], None]]):
        self.boundary = uuid.uuid4().hex
        self.path = path
        self.progress = progress
        name = os.path.basename(path)
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        b = self.boundary
        self.head = (
            f"--{b}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
            f"Content-Type: application/json\r\n\r\n{json.dumps(payload)}\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"files[0]\"; "
            f"filename=\"{name.replace(chr(34), '')}\"\r\nContent-Type: {ctype}\r\n\r\n"
        ).encode("utf-8")
        self.tail = f"\r\n--{b}--\r\n".encode()
        self.file_size = os.path.getsize(path)
        self.length = len(self.head) + self.file_size + len(self.tail)

    @property
    def content_type(self) -> str:
        return f"multipart/form-data; boundary={self.boundary}"

    def __iter__(self):
        yield self.head
        sent = 0
        with open(self.path, "rb") as fh:
            while True:
                chunk = fh.read(CHUNK)
                if not chunk:
                    break
                sent += len(chunk)
                if self.progress:
                    self.progress(sent, self.file_size)
                yield chunk
        yield self.tail


def upload_file(
    url: str,
    path: str,
    content: str = "",
    progress: Optional[Callable[[int, int], None]] = None,
    timeout: float = 120,
) -> dict:
    """Post a file to the webhook's channel and return the created message.

    Mentions are always disabled, so a file name can never ping @everyone.
    """
    payload = {"content": content[:2000], "allowed_mentions": {"parse": []}}
    target = url + ("&" if "?" in url else "?") + "wait=true"
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        body = _MultipartBody(payload, path, progress)
        req = request.Request(
            target,
            data=iter(body),
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": body.content_type,
                "Content-Length": str(body.length),
            },
        )
        try:
            with _open(req, timeout) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except error.HTTPError as exc:
            if exc.code == 429 and attempt < MAX_RATE_LIMIT_RETRIES:
                try:
                    wait = float(json.loads(exc.read().decode()).get("retry_after", 2))
                except ValueError:
                    wait = 2.0
                time.sleep(min(max(wait, 0.5), 30))
                continue
            raise DiscordError(_error_message(exc)) from None
        except (error.URLError, OSError) as exc:
            raise DiscordError(f"Upload failed: {getattr(exc, 'reason', exc)}") from None
    raise DiscordError("Discord kept rate-limiting the upload.")


def message_link(message: dict, guild_id: str = "") -> str:
    channel, msg = message.get("channel_id"), message.get("id")
    if not channel or not msg:
        return ""
    guild = message.get("guild_id") or guild_id or "@me"
    return f"https://discord.com/channels/{guild}/{channel}/{msg}"


def format_message(template: str, clip_name: str, size_bytes: int) -> str:
    stem = os.path.splitext(clip_name)[0]
    try:
        return template.format(name=stem, size=f"{size_bytes / 1024 / 1024:.1f} MB")
    except (KeyError, IndexError, ValueError):
        return template
