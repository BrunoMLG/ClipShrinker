"""The clip queue list, with drag & drop and inline progress bars."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem

from clipshrinker.ffmpeg import format_duration, format_size
from clipshrinker.jobs import CANCELLED, DONE, FAILED, PROBING, READY, RUNNING, SKIPPED, Job
from clipshrinker.ui import theme

COL_NAME, COL_LENGTH, COL_RES, COL_SIZE, COL_PRESET, COL_STATUS, COL_RESULT = range(7)
HEADERS = ["CLIP", "LENGTH", "RESOLUTION", "SIZE", "PRESET", "STATUS", "RESULT"]

STATUS_COLORS = {
    RUNNING: theme.ACCENT,
    DONE: theme.SUCCESS,
    FAILED: theme.DANGER,
    SKIPPED: theme.MUTED,
    CANCELLED: theme.MUTED,
}


def status_text(job: Job) -> str:
    if job.status == PROBING:
        return "Reading…"
    if job.status == READY:
        return "Waiting"
    if job.status == RUNNING:
        pct = f"{job.progress * 100:.0f}%"
        parts = [pct]
        if job.eta is not None:
            parts.append(f"{format_duration(job.eta) if job.eta >= 1 else '0:01'} left")
        return " · ".join(parts)
    return {DONE: "Done", FAILED: "Failed", SKIPPED: "Skipped", CANCELLED: "Cancelled"}[job.status]


def scaled_font(font: QFont, factor: float) -> QFont:
    """Copy of font scaled by factor; style sheets set pixel sizes, so handle both units."""
    font = QFont(font)
    if font.pixelSize() > 0:
        font.setPixelSize(max(1, round(font.pixelSize() * factor)))
    else:
        font.setPointSizeF(font.pointSizeF() * factor)
    return font


class ProgressDelegate(QStyledItemDelegate):
    def __init__(self, view: "QueueView"):
        super().__init__(view)
        self.view = view

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)
        job = self.view.job_for_index(index)
        if not job:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect).adjusted(8, 0, -10, 0)
        bar = QRectF(r.left(), r.center().y() + 6, r.width(), 4)
        track = QPainterPath()
        track.addRoundedRect(bar, 2, 2)
        painter.fillPath(track, QColor(theme.BORDER))
        progress = job.progress if job.status in (RUNNING, DONE, SKIPPED) else 0
        if job.status == FAILED:
            progress = 1
        if progress > 0:
            fill = QPainterPath()
            fill.addRoundedRect(QRectF(bar.left(), bar.top(), max(4.0, bar.width() * progress), bar.height()), 2, 2)
            painter.fillPath(fill, QColor(STATUS_COLORS.get(job.status, theme.ACCENT)))
        text_rect = QRectF(r.left(), r.top() + 3, r.width(), r.height() / 2 + 2)
        color = STATUS_COLORS.get(job.status, theme.MUTED) if job.status != RUNNING else theme.TEXT
        painter.setPen(QPen(QColor(color)))
        painter.setFont(scaled_font(option.font, 0.92))
        label = status_text(job)
        if job.status == RUNNING and job.message:
            label = f"{label}  ·  {job.message}"
        elided = painter.fontMetrics().elidedText(label, Qt.ElideRight, int(text_rect.width()))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(170, 40)


class QueueView(QTreeWidget):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: Dict[int, Job] = {}
        self._items: Dict[int, QTreeWidgetItem] = {}
        self.setColumnCount(len(HEADERS))
        self.setHeaderLabels(HEADERS)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setItemDelegateForColumn(COL_STATUS, ProgressDelegate(self))
        self.setMouseTracking(True)
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        for col, width in ((COL_LENGTH, 70), (COL_RES, 95), (COL_SIZE, 80), (COL_PRESET, 150),
                           (COL_STATUS, 230), (COL_RESULT, 130)):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            self.setColumnWidth(col, width)
        header.setMinimumSectionSize(50)

    # ---- jobs ------------------------------------------------------------
    def job_for_index(self, index) -> Optional[Job]:
        item = self.itemFromIndex(index)
        return self._jobs.get(item.data(0, Qt.UserRole)) if item else None

    def add_job(self, job: Job) -> None:
        item = QTreeWidgetItem()
        item.setData(0, Qt.UserRole, job.id)
        self._jobs[job.id] = job
        self._items[job.id] = item
        self.addTopLevelItem(item)
        self.update_job(job)
        self.viewport().update()

    def remove_job(self, job: Job) -> None:
        item = self._items.pop(job.id, None)
        self._jobs.pop(job.id, None)
        if item is not None:
            self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        self.viewport().update()

    def update_job(self, job: Job) -> None:
        item = self._items.get(job.id)
        if item is None:
            return
        info = job.info
        name = job.name + (" ✂" if job.trim else "")
        item.setText(COL_NAME, name)
        item.setToolTip(COL_NAME, job.src + (f"\n→ {job.dst}" if job.dst else ""))
        item.setText(COL_LENGTH, format_duration(info.duration) if info else "")
        item.setText(COL_RES, info.resolution if info else "")
        item.setText(COL_SIZE, format_size(info.size_bytes) if info else "")
        item.setText(COL_PRESET, job.preset)
        item.setToolTip(COL_STATUS, job.message or status_text(job))
        for col in (COL_LENGTH, COL_RES, COL_SIZE, COL_PRESET):
            item.setForeground(col, QColor(theme.MUTED))
        if job.status == DONE and job.out_size is not None and info:
            saved = 1 - job.out_size / max(1, info.size_bytes)
            item.setText(COL_RESULT, f"{format_size(job.out_size)}  ({-saved * 100:+.0f}%)")
            item.setForeground(COL_RESULT, QColor(theme.SUCCESS if saved > 0 else theme.WARNING))
            item.setToolTip(COL_RESULT, job.dst + (f"\n{job.message}" if job.message else ""))
        elif job.status in (FAILED, SKIPPED):
            item.setText(COL_RESULT, job.message)
            item.setForeground(COL_RESULT, QColor(theme.DANGER if job.status == FAILED else theme.MUTED))
            item.setToolTip(COL_RESULT, job.message)
        else:
            item.setText(COL_RESULT, "")
        self.viewport().update(self.visualItemRect(item))

    def selected_jobs(self) -> List[Job]:
        jobs = [self._jobs.get(i.data(0, Qt.UserRole)) for i in self.selectedItems()]
        order = {jid: self.indexOfTopLevelItem(it) for jid, it in self._items.items()}
        return sorted((j for j in jobs if j), key=lambda j: order.get(j.id, 0))

    def reorder(self, jobs: List[Job]) -> None:
        """Re-sync row order with the queue's job order, keeping the selection."""
        selected = {j.id for j in self.selected_jobs()}
        for job in jobs:
            item = self._items.get(job.id)
            if item is not None:
                self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        for job in jobs:
            item = self._items.get(job.id)
            if item is not None:
                self.addTopLevelItem(item)
                item.setSelected(job.id in selected)

    # ---- drag & drop -----------------------------------------------------
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            event.acceptProposedAction()
            if paths:
                self.files_dropped.emit(paths)
        else:
            super().dropEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.topLevelItemCount():
            return
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.viewport().rect()).adjusted(28, 28, -28, -28)
        pen = QPen(QColor(theme.BORDER), 2, Qt.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(rect, 16, 16)
        center = rect.center()
        title_font = scaled_font(self.font(), 1.45)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(rect.left(), center.y() - 34, rect.width(), 30), Qt.AlignCenter, "Drop clips here")
        p.setFont(self.font())
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(rect.left(), center.y() + 2, rect.width(), 40), Qt.AlignCenter | Qt.TextWordWrap,
                   "Drag videos or folders onto this window, or use Add clips.\n"
                   "Every clip gets the settings on the right.")
        p.end()
