"""Preferences and clip-details dialogs."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from clipshrinker.config import AppConfig
from clipshrinker.encode import CODECS, HARDWARE, MODE_BITRATE, MODE_QUALITY, Trim
from clipshrinker.ffmpeg import find_ffmpeg, format_duration, format_size, parse_timecode
from clipshrinker.jobs import DONE, RUNNING, Job


class PreferencesDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(480)
        self.config = config
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 8)
        self.concurrency.setValue(config.concurrent_jobs)
        self.concurrency.setToolTip("How many clips to encode at the same time. FFmpeg already uses "
                                    "every CPU core, so 1–2 is usually fastest.")
        form.addRow("Clips at once", self.concurrency)

        ff_row = QHBoxLayout()
        self.ffmpeg_edit = QLineEdit(config.ffmpeg_path)
        try:
            self.ffmpeg_edit.setPlaceholderText(f"Built-in: {find_ffmpeg('')}")
        except FileNotFoundError:
            self.ffmpeg_edit.setPlaceholderText("Not found - select ffmpeg executable")
        browse = QPushButton("…")
        browse.setFixedWidth(36)
        browse.clicked.connect(self._browse)
        ff_row.addWidget(self.ffmpeg_edit, 1)
        ff_row.addWidget(browse)
        form.addRow("FFmpeg", ff_row)
        lay.addLayout(form)

        self.skip_small = QCheckBox("Skip clips that are already under the target size")
        self.skip_small.setChecked(config.skip_if_smaller)
        self.retry = QCheckBox("Automatically retry when a clip comes out over the size limit")
        self.retry.setChecked(config.retry_oversize)
        self.notify = QCheckBox("Show a notification when the queue finishes")
        self.notify.setChecked(config.notify_when_done)
        self.open_folder = QCheckBox("Open the output folder when the queue finishes")
        self.open_folder.setChecked(config.open_folder_when_done)
        for w in (self.skip_small, self.retry, self.notify, self.open_folder):
            lay.addWidget(w)

        note = QLabel("A custom FFmpeg path takes effect after restarting ClipShrinker.")
        note.setObjectName("Hint")
        lay.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg executable")
        if path:
            self.ffmpeg_edit.setText(path)

    def accept(self) -> None:
        path = self.ffmpeg_edit.text().strip()
        if path and not os.path.isfile(path):
            QMessageBox.warning(self, "Preferences", "The FFmpeg path does not point to a file.")
            return
        c = self.config
        c.concurrent_jobs = self.concurrency.value()
        c.ffmpeg_path = path
        c.skip_if_smaller = self.skip_small.isChecked()
        c.retry_oversize = self.retry.isChecked()
        c.notify_when_done = self.notify.isChecked()
        c.open_folder_when_done = self.open_folder.isChecked()
        super().accept()


def describe_settings(job: Job) -> str:
    s = job.settings
    if s.mode == MODE_QUALITY:
        rate = f"Quality {s.crf}"
    elif s.mode == MODE_BITRATE:
        rate = f"{s.video_bitrate_kbps} kbps"
    else:
        rate = f"Max {s.target_size_mb:g} MB"
    res = {-1: "auto resolution", 0: "original resolution"}.get(s.max_height, f"{s.max_height}p")
    fps = f"{s.max_fps:g} fps max" if s.max_fps else "original fps"
    audio = "no audio" if s.audio_codec == "none" else (
        "original audio" if s.audio_codec == "copy" else f"{s.audio_codec.upper()} {s.audio_bitrate_kbps} kbps")
    return (f"{rate} · {CODECS[s.codec].split(' (')[0]} via {HARDWARE[s.hardware]} · {res} · {fps} · "
            f"{audio} · .{s.container}")


def _format_time(seconds) -> str:
    if seconds is None:
        return ""
    minutes, secs = divmod(seconds, 60)
    if secs == int(secs):
        return f"{int(minutes)}:{int(secs):02d}"
    return f"{int(minutes)}:{secs:06.3f}".rstrip("0")


class JobDialog(QDialog):
    """Details for one clip: info, trimming, output and the FFmpeg log."""

    def __init__(self, job: Job, parent=None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(job.name)
        self.resize(680, 560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(12)

        title = QLabel(job.name)
        title.setObjectName("Title")
        title.setWordWrap(True)
        lay.addWidget(title)

        info = job.info
        form = QFormLayout()
        form.setVerticalSpacing(6)

        def add(label: str, value: str) -> None:
            v = QLabel(value)
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label, v)

        add("Source", job.src)
        if info:
            audio = f"{info.audio_streams} track(s), {info.audio_codec}" if info.has_audio else "none"
            add("Video", f"{info.resolution} · {info.fps:g} fps · {info.video_codec} · "
                         f"{format_duration(info.duration)} · {format_size(info.size_bytes)}")
            add("Audio", audio)
        add("Preset", f"{job.preset}\n{describe_settings(job)}")
        if job.dst:
            add("Output", job.dst + (f"  ({format_size(job.out_size)})" if job.out_size else ""))
        if job.message:
            add("Status", job.message)
        lay.addLayout(form)

        trim_row = QHBoxLayout()
        self.start_edit = QLineEdit(_format_time(job.trim.start))
        self.end_edit = QLineEdit(_format_time(job.trim.end))
        self.start_edit.setPlaceholderText("start (e.g. 0:12)")
        self.end_edit.setPlaceholderText("end (e.g. 1:05)")
        trim_label = QLabel("Trim")
        trim_row.addWidget(trim_label)
        trim_row.addWidget(self.start_edit)
        trim_row.addWidget(QLabel("→"))
        trim_row.addWidget(self.end_edit)
        editable = job.status != RUNNING
        self.start_edit.setEnabled(editable)
        self.end_edit.setEnabled(editable)
        lay.addLayout(trim_row)
        hint = QLabel("Only encode part of the clip. Leave empty to keep the whole thing. "
                      "Size targets apply to the trimmed length.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        log_label = QLabel("FFMPEG LOG")
        log_label.setObjectName("SectionTitle")
        lay.addWidget(log_label)
        self.log = QPlainTextEdit("\n".join(job.log) or "Nothing yet - the log appears once encoding starts.")
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        copy_btn = buttons.addButton("Copy log", QDialogButtonBox.ActionRole)
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText("\n".join(job.log)))
        if job.status == DONE and job.dst:
            open_btn = buttons.addButton("Open output", QDialogButtonBox.ActionRole)
            open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(job.dst)))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def accept(self) -> None:
        try:
            start = parse_timecode(self.start_edit.text())
            end = parse_timecode(self.end_edit.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Trim", str(exc))
            return
        duration = self.job.info.duration if self.job.info else 0
        if start is not None and end is not None and end <= start:
            QMessageBox.warning(self, "Trim", "The end time must be after the start time.")
            return
        if duration and start is not None and start >= duration:
            QMessageBox.warning(self, "Trim", "The start time is past the end of the clip.")
            return
        self.job.trim = Trim(start or None, end)
        super().accept()
