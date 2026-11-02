"""Trim editor: frame preview, filmstrip timeline with start/end handles, and playback.

Frames come from the bundled FFmpeg (raw RGB over a pipe), so there's no dependency on
Qt Multimedia or system codecs. Playback is video only.
"""

from __future__ import annotations

import subprocess
from typing import List, Optional

from PySide6.QtCore import QObject, QPointF, QProcess, QRectF, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from clipshrinker.encode import Trim
from clipshrinker.ffmpeg import NO_WINDOW, MediaInfo, parse_timecode
from clipshrinker.ui import theme

PREVIEW_BOX = (640, 360)
THUMB_HEIGHT = 56
THUMB_COUNT = 12
PLAY_FPS = 30
MIN_KEEP = 0.1  # shortest selection, seconds


def fit_size(w: int, h: int, box_w: int, box_h: int):
    """Largest even width/height with the clip's aspect ratio that fits the box."""
    if not w or not h:
        return box_w, box_h
    scale = min(box_w / w, box_h / h)
    return max(2, int(w * scale) // 2 * 2), max(2, int(h * scale) // 2 * 2)


def format_time(seconds: float, precise: bool = True) -> str:
    seconds = max(0.0, seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    s = f"{secs:06.3f}" if precise else f"{int(secs):02d}"
    if precise:
        s = s.rstrip("0").rstrip(".") if "." in s else s
        if len(s.split(".")[0]) < 2:
            s = "0" + s
    return f"{hours}:{minutes:02d}:{s}" if hours else f"{minutes}:{s}"


def frame_args(src: str, t: float, w: int, h: int) -> List[str]:
    return ["-hide_banner", "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", src,
            "-frames:v", "1", "-an", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]


def to_image(data: bytes, w: int, h: int) -> Optional[QImage]:
    if len(data) < w * h * 3:
        return None
    return QImage(data[: w * h * 3], w, h, w * 3, QImage.Format_RGB888).copy()


class FrameGrabber(QObject):
    """Fetches single frames; while one is being decoded only the latest request is kept."""

    frame_ready = Signal(float, QImage)

    def __init__(self, ffmpeg: str, src: str, w: int, h: int, duration: float, parent=None):
        super().__init__(parent)
        self.ffmpeg, self.src, self.w, self.h, self.duration = ffmpeg, src, w, h, duration
        self._proc: Optional[QProcess] = None
        self._time = 0.0
        self._pending: Optional[float] = None

    def request(self, t: float) -> None:
        # The very last timestamp often has no frame to decode, so stay just before it.
        t = max(0.0, min(t, self.duration - 0.05))
        if self._proc is not None:
            self._pending = t
            return
        self._time = t
        self._proc = QProcess(self)
        self._proc.finished.connect(self._on_finished)
        self._proc.start(self.ffmpeg, frame_args(self.src, t, self.w, self.h))

    def _on_finished(self, *_):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        img = to_image(bytes(proc.readAllStandardOutput()), self.w, self.h)
        proc.deleteLater()
        if img is not None and self._pending is None:
            self.frame_ready.emit(self._time, img)
        if self._pending is not None:
            t, self._pending = self._pending, None
            self.request(t)

    def stop(self) -> None:
        self._pending = None
        if self._proc is not None:
            self._proc.kill()
            self._proc.waitForFinished(1000)
            self._proc = None


class Player(QObject):
    """Streams frames in real time (ffmpeg -re) from a start time to an end time."""

    frame = Signal(float, QImage)
    stopped = Signal()

    def __init__(self, ffmpeg: str, src: str, w: int, h: int, parent=None):
        super().__init__(parent)
        self.ffmpeg, self.src, self.w, self.h = ffmpeg, src, w, h
        self._proc: Optional[QProcess] = None
        self._buf = bytearray()
        self._start = 0.0
        self._index = 0

    @property
    def playing(self) -> bool:
        return self._proc is not None

    def play(self, start: float, end: float) -> None:
        self.stop()
        self._start, self._index, self._buf = start, 0, bytearray()
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._on_data)
        self._proc.finished.connect(self._on_finished)
        self._proc.start(self.ffmpeg, [
            "-hide_banner", "-v", "error", "-nostdin", "-re", "-ss", f"{start:.3f}", "-i", self.src,
            "-t", f"{max(0.05, end - start):.3f}", "-an",
            "-vf", f"fps={PLAY_FPS},scale={self.w}:{self.h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ])

    def _on_data(self) -> None:
        if self._proc is None:
            return
        self._buf += bytes(self._proc.readAllStandardOutput())
        size = self.w * self.h * 3
        latest = None
        while len(self._buf) >= size:
            latest = bytes(self._buf[:size])
            del self._buf[:size]
            self._index += 1
        if latest is not None:
            img = to_image(latest, self.w, self.h)
            if img is not None:
                self.frame.emit(self._start + (self._index - 1) / PLAY_FPS, img)

    def _on_finished(self, *_):
        if self._proc is not None:
            self._proc.deleteLater()
            self._proc = None
            self.stopped.emit()

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            proc.kill()
            proc.waitForFinished(1000)
            proc.deleteLater()
            self.stopped.emit()


class _ThumbSignals(QObject):
    thumb = Signal(int, QImage)


class _ThumbTask(QRunnable):
    def __init__(self, ffmpeg: str, src: str, duration: float, w: int, h: int, signals: _ThumbSignals):
        super().__init__()
        self.ffmpeg, self.src, self.duration, self.w, self.h = ffmpeg, src, duration, w, h
        self.signals = signals
        self.cancelled = False

    def run(self) -> None:
        for i in range(THUMB_COUNT):
            if self.cancelled:
                return
            t = (i + 0.5) / THUMB_COUNT * self.duration
            try:
                out = subprocess.run([self.ffmpeg] + frame_args(self.src, t, self.w, self.h),
                                     capture_output=True, timeout=20, creationflags=NO_WINDOW).stdout
            except (OSError, subprocess.TimeoutExpired):
                continue
            img = to_image(out, self.w, self.h)
            if img is not None and not self.cancelled:
                self.signals.thumb.emit(i, img)


class Timeline(QWidget):
    """Filmstrip with a draggable kept range and a playhead."""

    seek = Signal(float)
    range_changed = Signal(float, float)

    HANDLE_W = 12
    LABEL_H = 20

    def __init__(self, duration: float, parent=None):
        super().__init__(parent)
        self.duration = max(duration, 0.01)
        self.start, self.end, self.position = 0.0, self.duration, 0.0
        self.thumbs: List[Optional[QImage]] = [None] * THUMB_COUNT
        self._drag: Optional[str] = None
        self.setMouseTracking(True)
        self.setMinimumHeight(THUMB_HEIGHT + self.LABEL_H + 12)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setToolTip("Drag the purple handles to set the start and end. Click anywhere to preview that moment.")

    def sizeHint(self) -> QSize:
        return QSize(640, THUMB_HEIGHT + self.LABEL_H + 12)

    # ---- geometry ----------------------------------------------------------
    def _track(self) -> QRectF:
        return QRectF(self.HANDLE_W, 6, self.width() - 2 * self.HANDLE_W, THUMB_HEIGHT)

    def x_for(self, t: float) -> float:
        tr = self._track()
        return tr.left() + max(0.0, min(1.0, t / self.duration)) * tr.width()

    def t_for(self, x: float) -> float:
        tr = self._track()
        return max(0.0, min(self.duration, (x - tr.left()) / max(1.0, tr.width()) * self.duration))

    # ---- state -------------------------------------------------------------
    def set_range(self, start: float, end: float) -> None:
        self.start, self.end = start, end
        self.update()

    def set_position(self, t: float) -> None:
        self.position = t
        self.update()

    def set_thumbnail(self, i: int, img: QImage) -> None:
        if 0 <= i < len(self.thumbs):
            self.thumbs[i] = img
            self.update()

    # ---- painting ----------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        tr = self._track()
        clip = QPainterPath()
        clip.addRoundedRect(tr, 6, 6)
        p.save()
        p.setClipPath(clip)
        p.fillRect(tr, QColor("#0b0c10"))
        cell = tr.width() / THUMB_COUNT
        for i, img in enumerate(self.thumbs):
            if img is None:
                continue
            target = QRectF(tr.left() + i * cell, tr.top(), cell + 1, tr.height())
            # Crop the frame to the cell's aspect ratio (center crop), like a filmstrip.
            src_w = min(img.width(), img.height() * target.width() / target.height())
            src = QRectF((img.width() - src_w) / 2, 0, src_w, img.height())
            p.drawImage(target, img, src)
        shade = QColor(0, 0, 0, 175)
        xs, xe = self.x_for(self.start), self.x_for(self.end)
        p.fillRect(QRectF(tr.left(), tr.top(), xs - tr.left(), tr.height()), shade)
        p.fillRect(QRectF(xe, tr.top(), tr.right() - xe, tr.height()), shade)
        p.restore()

        accent = QColor(theme.ACCENT)
        p.setPen(QPen(accent, 3))
        p.drawLine(QPointF(xs, tr.top() + 1.5), QPointF(xe, tr.top() + 1.5))
        p.drawLine(QPointF(xs, tr.bottom() - 1.5), QPointF(xe, tr.bottom() - 1.5))
        for x, left in ((xs, True), (xe, False)):
            r = QRectF(x - self.HANDLE_W if left else x, tr.top(), self.HANDLE_W, tr.height())
            path = QPainterPath()
            path.addRoundedRect(r, 4, 4)
            p.fillPath(path, accent)
            p.setPen(QPen(QColor(255, 255, 255, 210), 1.5))
            cx = r.center().x()
            p.drawLine(QPointF(cx, r.center().y() - 7), QPointF(cx, r.center().y() + 7))

        xp = self.x_for(self.position)
        p.setPen(QPen(QColor("white"), 2))
        p.drawLine(QPointF(xp, tr.top() - 4), QPointF(xp, tr.bottom() + 4))
        p.setBrush(QColor("white"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(xp, tr.top() - 3), 4, 4)

        font = QFont(self.font())
        if font.pixelSize() > 0:
            font.setPixelSize(max(9, font.pixelSize() - 1))
        p.setFont(font)
        label_rect = QRectF(tr.left(), tr.bottom() + 4, tr.width(), self.LABEL_H)
        p.setPen(QColor(theme.MUTED))
        p.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, "0:00")
        p.drawText(label_rect, Qt.AlignRight | Qt.AlignVCenter, format_time(self.duration, precise=False))
        p.setPen(QColor(theme.TEXT))
        p.drawText(label_rect, Qt.AlignHCenter | Qt.AlignVCenter,
                   f"Keeping {format_time(self.end - self.start)} of {format_time(self.duration)}")
        p.end()

    # ---- mouse -------------------------------------------------------------
    def _handle_at(self, x: float) -> Optional[str]:
        ds, de = abs(x - (self.x_for(self.start) - self.HANDLE_W / 2)), abs(x - (self.x_for(self.end) + self.HANDLE_W / 2))
        best = min(ds, de)
        if best > self.HANDLE_W:
            return None
        return "start" if ds <= de else "end"

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        x = event.position().x()
        self._drag = self._handle_at(x) or "position"
        self._apply_drag(x)

    def mouseMoveEvent(self, event) -> None:
        x = event.position().x()
        if self._drag:
            self._apply_drag(x)
        else:
            self.setCursor(Qt.SizeHorCursor if self._handle_at(x) else Qt.PointingHandCursor)

    def mouseReleaseEvent(self, _event) -> None:
        self._drag = None

    def _apply_drag(self, x: float) -> None:
        if self._drag == "start":
            # The handle sits left of its edge, so offset by half its width.
            t = self.t_for(x + self.HANDLE_W / 2)
            self.start = min(t, self.end - MIN_KEEP)
            self.range_changed.emit(self.start, self.end)
            self.position = self.start
            self.seek.emit(self.start)
        elif self._drag == "end":
            t = self.t_for(x - self.HANDLE_W / 2)
            self.end = max(t, self.start + MIN_KEEP)
            self.range_changed.emit(self.start, self.end)
            self.position = self.end
            self.seek.emit(self.end)
        else:
            self.position = self.t_for(x)
            self.seek.emit(self.position)
        self.update()


class TrimEditor(QWidget):
    """Preview, timeline and time fields for choosing the part of a clip to keep."""

    def __init__(self, ffmpeg: str, src: str, info: MediaInfo, trim: Trim, parent=None):
        super().__init__(parent)
        self.ffmpeg, self.src, self.info = ffmpeg, src, info
        self.duration = max(info.duration, 0.01)
        self.fps = info.fps or 30
        w, h = fit_size(info.width, info.height, *PREVIEW_BOX)
        self._pixmap: Optional[QPixmap] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.preview = QLabel("Loading preview…")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(320, 180)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setStyleSheet(f"background:#000; border-radius:8px; color:{theme.MUTED};")
        lay.addWidget(self.preview, 1)

        self.timeline = Timeline(self.duration)
        lay.addWidget(self.timeline)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("▶  Play")
        self.play_btn.setToolTip("Play from the playhead (Space). Video only, no sound.")
        self.play_btn.setMinimumWidth(96)
        self.time_label = QLabel()
        self.time_label.setMinimumWidth(150)
        self.set_start_btn = QPushButton("⟦  Set start")
        self.set_start_btn.setToolTip("Start the clip at the playhead (I)")
        self.set_end_btn = QPushButton("Set end  ⟧")
        self.set_end_btn.setToolTip("End the clip at the playhead (O)")
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("Flat")
        self.reset_btn.setToolTip("Keep the whole clip")
        controls.addWidget(self.play_btn)
        controls.addWidget(self.time_label)
        controls.addStretch()
        controls.addWidget(self.set_start_btn)
        controls.addWidget(self.set_end_btn)
        controls.addWidget(self.reset_btn)
        lay.addLayout(controls)

        fields = QHBoxLayout()
        self.start_edit = QLineEdit()
        self.end_edit = QLineEdit()
        self.start_edit.setPlaceholderText("0:00")
        self.end_edit.setPlaceholderText(format_time(self.duration))
        for edit in (self.start_edit, self.end_edit):
            edit.setMaximumWidth(130)
        fields.addWidget(QLabel("Start"))
        fields.addWidget(self.start_edit)
        fields.addWidget(QLabel("→  End"))
        fields.addWidget(self.end_edit)
        fields.addSpacing(12)
        self.field_error = QLabel()
        self.field_error.setObjectName("Warning")
        fields.addWidget(self.field_error, 1)
        lay.addLayout(fields)
        hint = QLabel("Drag the handles or type times like 0:12 or 1:05.5. Shortcuts: Space play/pause, "
                      "I / O set start / end, ← → step a frame (Shift: 1 s).")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.grabber = FrameGrabber(ffmpeg, src, w, h, self.duration, self)
        self.player = Player(ffmpeg, src, w, h, self)
        self._thumb_signals = _ThumbSignals()
        tw, th = fit_size(info.width, info.height, THUMB_HEIGHT * 4, THUMB_HEIGHT)
        self._thumb_task = _ThumbTask(ffmpeg, src, self.duration, tw, th, self._thumb_signals)
        self._thumb_task.setAutoDelete(False)

        self.grabber.frame_ready.connect(self._show_frame)
        self.player.frame.connect(self._on_play_frame)
        self.player.stopped.connect(self._on_play_stopped)
        self._thumb_signals.thumb.connect(self.timeline.set_thumbnail)
        self.timeline.seek.connect(self._on_seek)
        self.timeline.range_changed.connect(self._on_range_from_timeline)
        self.play_btn.clicked.connect(self.toggle_play)
        self.set_start_btn.clicked.connect(self.set_start_here)
        self.set_end_btn.clicked.connect(self.set_end_here)
        self.reset_btn.clicked.connect(lambda: self._set_range(0.0, self.duration))
        self.start_edit.editingFinished.connect(self._on_fields_edited)
        self.end_edit.editingFinished.connect(self._on_fields_edited)

        for key, slot in (
            (Qt.Key_Space, self.toggle_play),
            (Qt.Key_I, self.set_start_here),
            (Qt.Key_O, self.set_end_here),
            (Qt.Key_Left, lambda: self._step(-1 / self.fps)),
            (Qt.Key_Right, lambda: self._step(1 / self.fps)),
            (Qt.SHIFT | Qt.Key_Left, lambda: self._step(-1.0)),
            (Qt.SHIFT | Qt.Key_Right, lambda: self._step(1.0)),
        ):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)

        start = trim.start or 0.0
        end = trim.end if trim.end is not None else self.duration
        self._set_range(max(0.0, min(start, self.duration)), max(0.0, min(end, self.duration)))
        self._on_seek(start)
        QThreadPool.globalInstance().start(self._thumb_task)

    # ---- result ------------------------------------------------------------
    def trim(self) -> Trim:
        start = self.timeline.start
        end = self.timeline.end
        return Trim(start if start > 0.005 else None, end if end < self.duration - 0.005 else None)

    def validate(self) -> str:
        """Re-read the text fields; returns an error message or ''."""
        self._on_fields_edited()
        return self.field_error.text()

    # ---- range -------------------------------------------------------------
    def _set_range(self, start: float, end: float) -> None:
        self.timeline.set_range(start, end)
        self.start_edit.setText(format_time(start))
        self.end_edit.setText(format_time(end))
        self.field_error.clear()

    def _on_range_from_timeline(self, start: float, end: float) -> None:
        self.start_edit.setText(format_time(start))
        self.end_edit.setText(format_time(end))
        self.field_error.clear()

    def _on_fields_edited(self) -> None:
        try:
            start = parse_timecode(self.start_edit.text()) or 0.0
            end = parse_timecode(self.end_edit.text())
        except ValueError:
            self.field_error.setText("Use times like 0:12 or 1:05.5")
            return
        end = self.duration if end is None else end
        if start >= self.duration:
            self.field_error.setText("The start is past the end of the clip.")
            return
        end = min(end, self.duration)
        if end - start < MIN_KEEP:
            self.field_error.setText("The end must be after the start.")
            return
        self.field_error.clear()
        if (start, end) != (self.timeline.start, self.timeline.end):
            self.timeline.set_range(start, end)
            self._on_seek(start)

    def set_start_here(self) -> None:
        t = self.timeline.position
        end = self.timeline.end if self.timeline.end - t >= MIN_KEEP else self.duration
        if end - t < MIN_KEEP:
            return
        self._set_range(t, end)

    def set_end_here(self) -> None:
        t = self.timeline.position
        start = self.timeline.start if t - self.timeline.start >= MIN_KEEP else 0.0
        if t - start < MIN_KEEP:
            return
        self._set_range(start, t)

    # ---- preview / playback --------------------------------------------------
    def _on_seek(self, t: float) -> None:
        if self.player.playing:
            self.player.stop()
        self.timeline.set_position(t)
        self._update_time_label(t)
        self.grabber.request(t)

    def _step(self, delta: float) -> None:
        self._on_seek(max(0.0, min(self.duration, self.timeline.position + delta)))

    def toggle_play(self) -> None:
        if self.player.playing:
            self.player.stop()
            return
        # Play shows the part being kept: from the playhead (or the start, when the playhead is
        # outside the kept range) to the end handle.
        pos, start, end = self.timeline.position, self.timeline.start, self.timeline.end
        if pos < start or pos >= end - 0.05:
            pos = start
        self.grabber.stop()
        self.player.play(pos, end)
        self.play_btn.setText("❚❚  Pause")

    def _on_play_frame(self, t: float, img: QImage) -> None:
        self.timeline.set_position(t)
        self._update_time_label(t)
        self._show_frame(t, img)

    def _on_play_stopped(self) -> None:
        self.play_btn.setText("▶  Play")

    def _update_time_label(self, t: float) -> None:
        self.time_label.setText(f"{format_time(t)}  /  {format_time(self.duration)}")

    def _show_frame(self, _t: float, img: QImage) -> None:
        self._pixmap = QPixmap.fromImage(img)
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        self.preview.setPixmap(self._pixmap.scaled(self.preview.size(), Qt.KeepAspectRatio,
                                                   Qt.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def shutdown(self) -> None:
        self._thumb_task.cancelled = True
        self.player.stop()
        self.grabber.stop()
