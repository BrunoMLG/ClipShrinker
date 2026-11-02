import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from clipshrinker.discord import (
    DiscordError,
    format_message,
    message_link,
    normalize_webhook_url,
    parse_webhook_url,
    upload_file,
)


class FakeDiscord(BaseHTTPRequestHandler):
    """Records uploads; the path decides the behavior (ok / ratelimit / toolarge)."""

    requests = []
    ratelimited_once = False

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        FakeDiscord.requests.append((self.path, self.headers, body))
        if "ratelimit" in self.path and not FakeDiscord.ratelimited_once:
            FakeDiscord.ratelimited_once = True
            return self._reply(429, {"retry_after": 0.1})
        if "toolarge" in self.path:
            return self._reply(413, {"message": "Request entity too large"})
        self._reply(200, {"id": "999", "channel_id": "555"})

    def _reply(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def server():
    FakeDiscord.requests = []
    FakeDiscord.ratelimited_once = False
    httpd = HTTPServer(("127.0.0.1", 0), FakeDiscord)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/api/webhooks/1/tok"
    httpd.shutdown()


@pytest.fixture()
def clip(tmp_path):
    path = tmp_path / "my clip.mp4"
    path.write_bytes(b"\x00\x01video-bytes" * 5000)
    return path


def test_parse_webhook_url():
    good = "https://discord.com/api/webhooks/123456/AbC-d_e"
    assert parse_webhook_url(good) == ("123456", "AbC-d_e")
    assert parse_webhook_url("https://canary.discordapp.com/api/v10/webhooks/1/x/") == ("1", "x")
    assert parse_webhook_url("https://evil.example.com/api/webhooks/1/x") is None
    assert parse_webhook_url("http://discord.com/api/webhooks/1/x") is None
    assert normalize_webhook_url(good + "?wait=true") == good
    with pytest.raises(DiscordError):
        normalize_webhook_url("nope")


def test_upload_sends_file_and_blocks_mentions(server, clip):
    seen = []
    msg = upload_file(server, str(clip), "@everyone look", progress=lambda s, t: seen.append((s, t)))
    assert msg["id"] == "999"
    path, headers, body = FakeDiscord.requests[0]
    assert "wait=true" in path
    assert headers["User-Agent"].startswith("DiscordBot")
    assert clip.read_bytes() in body
    assert b'filename="my clip.mp4"' in body
    payload = json.loads(body.split(b"\r\n\r\n", 1)[1].split(b"\r\n--", 1)[0])
    assert payload == {"content": "@everyone look", "allowed_mentions": {"parse": []}}
    assert seen[-1][0] == seen[-1][1] == clip.stat().st_size


def test_upload_retries_after_rate_limit(server, clip):
    upload_file(server.replace("/tok", "/ratelimit"), str(clip))
    assert len(FakeDiscord.requests) == 2


def test_upload_reports_too_large(server, clip):
    with pytest.raises(DiscordError, match="upload limit"):
        upload_file(server.replace("/tok", "/toolarge"), str(clip))


def test_upload_unreachable(clip):
    with pytest.raises(DiscordError):
        upload_file("http://127.0.0.1:9/api/webhooks/1/x", str(clip), timeout=3)


def test_message_helpers():
    assert format_message("{name} ({size})", "PEAK clip.mp4", 3 * 1024 * 1024) == "PEAK clip (3.0 MB)"
    assert format_message("{oops}", "a.mp4", 0) == "{oops}"
    assert message_link({"id": "3", "channel_id": "2"}, "1") == "https://discord.com/channels/1/2/3"
    assert message_link({}) == ""
