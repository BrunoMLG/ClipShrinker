"""Uploads finished clips to Discord in the background, one at a time."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from clipshrinker.discord import DiscordError, format_message, message_link, upload_file
from clipshrinker.jobs import Job

QUEUED, UPLOADING, UPLOADED, UPLOAD_FAILED = "queued", "uploading", "uploaded", "failed"


class _Signals(QObject):
    progress = Signal(int, float)  # job id, 0..1
    finished = Signal(int, str, str)  # job id, link, error ("" on success)


class _UploadTask(QRunnable):
    def __init__(self, job_id: int, path: str, webhook: str, content: str, guild_id: str, signals: _Signals):
        super().__init__()
        self.job_id, self.path, self.webhook = job_id, path, webhook
        self.content, self.guild_id, self.signals = content, guild_id, signals
        self._last_emit = 0.0

    def _progress(self, sent: int, total: int) -> None:
        now = time.monotonic()
        if now - self._last_emit > 0.15 or sent >= total:
            self._last_emit = now
            self.signals.progress.emit(self.job_id, sent / max(1, total))

    def run(self) -> None:
        try:
            message = upload_file(self.webhook, self.path, self.content, progress=self._progress)
            self.signals.finished.emit(self.job_id, message_link(message, self.guild_id), "")
        except DiscordError as exc:
            self.signals.finished.emit(self.job_id, "", str(exc))
        except Exception as exc:  # noqa: BLE001 - never let an upload crash the app
            self.signals.finished.emit(self.job_id, "", f"Upload failed: {exc}")


class DiscordUploader(QObject):
    job_changed = Signal(object)

    def __init__(self, find_job, parent=None):
        super().__init__(parent)
        self._find_job = find_job
        self._pool = QThreadPool(self)
        # One at a time keeps clips in queue order in the channel and avoids rate limits.
        self._pool.setMaxThreadCount(1)
        self._signals = _Signals()
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_finished)

    def upload(self, job: Job, path: str, webhook: str, template: str, guild_id: str = "") -> None:
        if job.upload_state in (QUEUED, UPLOADING):
            return
        job.upload_state, job.upload_progress = QUEUED, 0.0
        job.upload_message, job.upload_link = "Waiting to upload", ""
        self.job_changed.emit(job)
        content = format_message(template, job.name, job.out_size or 0)
        self._pool.start(_UploadTask(job.id, path, webhook, content, guild_id, self._signals))

    @property
    def busy(self) -> bool:
        return self._pool.activeThreadCount() > 0

    def _on_progress(self, job_id: int, frac: float) -> None:
        job = self._find_job(job_id)
        if job:
            job.upload_state, job.upload_progress = UPLOADING, frac
            job.upload_message = f"Uploading to Discord {frac * 100:.0f}%"
            self.job_changed.emit(job)

    def _on_finished(self, job_id: int, link: str, err: str) -> None:
        job = self._find_job(job_id)
        if not job:
            return
        if err:
            job.upload_state, job.upload_message = UPLOAD_FAILED, err
        else:
            job.upload_state, job.upload_progress = UPLOADED, 1.0
            job.upload_message, job.upload_link = "Sent to Discord", link
        self.job_changed.emit(job)

    def shutdown(self) -> None:
        self._pool.clear()
        self._pool.waitForDone(1000)
