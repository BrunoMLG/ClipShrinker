"""Main application window."""

from __future__ import annotations

import os
import sys
from typing import List

from PySide6.QtCore import QByteArray, QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from clipshrinker import __app_name__, __version__
from clipshrinker.config import AppConfig
from clipshrinker.encode import MODE_QUALITY, EncodeSettings, build_plan
from clipshrinker.ffmpeg import detect_hardware, format_size
from clipshrinker.jobs import (
    DONE,
    FAILED,
    FINISHED_STATES,
    PROBING,
    READY,
    RUNNING,
    VIDEO_EXTENSIONS,
    Job,
    JobQueue,
    collect_videos,
    resolve_output,
)
from clipshrinker.presets import BUILTIN_PRESETS, Preset
from clipshrinker.uploader import QUEUED, UPLOADED, UPLOADING, DiscordUploader
from clipshrinker.ui.dialogs import JobDialog, PreferencesDialog
from clipshrinker.ui.discord_dialog import DiscordDialog
from clipshrinker.ui.queue_view import QueueView
from clipshrinker.ui.settings_panel import SettingsPanel


class _HwSignals(QObject):
    done = Signal(dict)
    vaapi_device = Signal(str)


class _HwDetect(QRunnable):
    """Find out which hardware encoders actually work on this machine."""

    def __init__(self, ffmpeg: str, signals: _HwSignals):
        super().__init__()
        self.ffmpeg, self.signals = ffmpeg, signals

    def run(self) -> None:
        result, device = detect_hardware(self.ffmpeg)
        if device:
            self.signals.vaapi_device.emit(device)
        self.signals.done.emit(result)


def _open_path(path: str) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class MainWindow(QMainWindow):
    def __init__(self, ffmpeg: str, config: AppConfig, icon: QIcon):
        super().__init__()
        self.config = config
        self.ffmpeg = ffmpeg
        self.setWindowTitle(__app_name__)
        self.setWindowIcon(icon)
        self.resize(1280, 780)
        self.setMinimumSize(960, 600)
        self.setAcceptDrops(True)

        self.queue = JobQueue(ffmpeg, self)
        self.queue.output_resolver = self._resolve_output
        self._apply_queue_prefs()
        self.uploader = DiscordUploader(self.queue.find, self)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- top bar ---------------------------------------------------------
        top = QWidget()
        top.setObjectName("TopBar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(18, 12, 18, 12)
        tl.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icon.pixmap(30, 30))
        tl.addWidget(logo)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel(__app_name__)
        title.setObjectName("Title")
        subtitle = QLabel(f"Batch video compressor · v{__version__}")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        tl.addLayout(title_box)
        tl.addSpacing(24)
        self.add_btn = QPushButton("＋  Add clips")
        self.add_btn.setObjectName("Primary")
        self.add_folder_btn = QPushButton("Add folder")
        tl.addWidget(self.add_btn)
        tl.addWidget(self.add_folder_btn)
        tl.addStretch()
        self.clear_btn = QPushButton("Clear finished")
        self.clear_btn.setObjectName("Flat")
        self.prefs_btn = QPushButton("⚙  Preferences")
        self.prefs_btn.setObjectName("Flat")
        tl.addWidget(self.clear_btn)
        tl.addWidget(self.prefs_btn)
        root.addWidget(top)

        # ---- body ------------------------------------------------------------
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        self.view = QueueView()
        self.panel = SettingsPanel()
        self.splitter.addWidget(self.view)
        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([880, 400])
        root.addWidget(self.splitter, 1)

        # ---- bottom bar ------------------------------------------------------
        bottom = QWidget()
        bottom.setObjectName("BottomBar")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(18, 10, 18, 10)
        bl.setSpacing(14)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("Subtitle")
        self.overall = QProgressBar()
        self.overall.setTextVisible(False)
        self.overall.setFixedHeight(8)
        self.overall.setRange(0, 1000)
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("Primary")
        self.start_btn.setMinimumWidth(130)
        # Kept right next to Start, so it's obvious before every run whether clips will be posted.
        self.discord_btn = QPushButton()
        self.discord_btn.setCursor(Qt.PointingHandCursor)
        self.discord_settings_btn = QPushButton("⚙")
        self.discord_settings_btn.setObjectName("Flat")
        self.discord_settings_btn.setToolTip("Discord upload settings")
        bl.addWidget(self.summary_label)
        bl.addWidget(self.overall, 1)
        bl.addWidget(self.discord_btn)
        bl.addWidget(self.discord_settings_btn)
        bl.addWidget(self.start_btn)
        root.addWidget(bottom)

        # ---- presets / settings ---------------------------------------------
        self._reload_presets(config.preset)
        self.panel.set_settings(config.encode_settings)
        self.panel.set_output_options(config.output_dir, config.name_template, config.overwrite)
        self.panel.refresh_preset_meta()

        # ---- wiring ----------------------------------------------------------
        self.add_btn.clicked.connect(self.add_files_dialog)
        self.add_folder_btn.clicked.connect(self.add_folder_dialog)
        self.clear_btn.clicked.connect(self.queue.clear_finished)
        self.prefs_btn.clicked.connect(self.open_preferences)
        self.start_btn.clicked.connect(self.toggle_queue)
        self.discord_btn.clicked.connect(self.toggle_discord)
        self.discord_settings_btn.clicked.connect(self.open_discord_settings)
        self.uploader.job_changed.connect(self._on_job_changed)
        self.queue.job_finished.connect(self._on_job_finished)
        self.view.files_dropped.connect(self.add_paths)
        self.view.itemSelectionChanged.connect(self._update_estimate)
        self.view.itemDoubleClicked.connect(lambda *_: self.show_details())
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.panel.changed.connect(self._on_settings_changed)
        self.panel.apply_to_selected.connect(self.apply_to_selected)
        self.panel.save_preset_requested.connect(self.save_preset)
        self.panel.delete_preset_requested.connect(self.delete_preset)
        self.queue.job_added.connect(self._on_job_added)
        self.queue.job_changed.connect(self._on_job_changed)
        self.queue.job_removed.connect(self._on_job_removed)
        self.queue.running_changed.connect(self._on_running_changed)
        self.queue.queue_finished.connect(self._on_queue_finished)

        delete = QAction(self)
        delete.setShortcuts([QKeySequence.Delete, QKeySequence(Qt.Key_Backspace)])
        delete.triggered.connect(self.remove_selected)
        self.view.addAction(delete)
        open_action = QAction(self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.add_files_dialog)
        self.addAction(open_action)
        for key, delta in ((Qt.CTRL | Qt.Key_Up, -1), (Qt.CTRL | Qt.Key_Down, 1)):
            act = QAction(self)
            act.setShortcut(QKeySequence(key))
            act.triggered.connect(lambda _=False, d=delta: self.move_selected(d))
            self.view.addAction(act)

        self._save_timer = QTimer(self, singleShot=True, interval=800)
        self._save_timer.timeout.connect(self._save_config)
        self._ui_timer = QTimer(self, singleShot=True, interval=100)
        self._ui_timer.timeout.connect(self._refresh_summary)

        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip(__app_name__)

        if config.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(config.window_geometry.encode()))
        if config.splitter_state:
            self.splitter.restoreState(QByteArray.fromBase64(config.splitter_state.encode()))

        self._hw_signals = _HwSignals()
        self._hw_signals.done.connect(self.panel.set_hardware_availability)
        self._hw_signals.vaapi_device.connect(lambda dev: setattr(self.queue, "vaapi_device", dev))
        QThreadPool.globalInstance().start(_HwDetect(ffmpeg, self._hw_signals))

        self._refresh_discord()
        self._refresh_summary()
        self._update_estimate()

    # ---- discord ---------------------------------------------------------------
    @property
    def discord_on(self) -> bool:
        return self.config.discord_enabled and bool(self.config.discord_webhook)

    def _refresh_discord(self) -> None:
        on = self.discord_on
        name = self.config.discord_webhook_name or "webhook"
        if on:
            self.discord_btn.setText(f"●  Discord upload ON · {name}")
            self.discord_btn.setToolTip(f"Finished clips are posted to Discord as “{name}”. Click to turn off.")
        else:
            self.discord_btn.setText("Discord upload OFF")
            self.discord_btn.setToolTip("Click to post finished clips to a Discord channel automatically."
                                        if self.config.discord_webhook else "Set up a Discord webhook")
        self.discord_btn.setObjectName("DiscordOn" if on else "DiscordOff")
        self.discord_btn.style().unpolish(self.discord_btn)
        self.discord_btn.style().polish(self.discord_btn)
        self._on_running_changed(self.queue.is_running)

    def toggle_discord(self) -> None:
        if self.discord_on:
            self.config.discord_enabled = False
        elif not self.config.discord_webhook:
            self.open_discord_settings(enable=True)
            return
        else:
            name = self.config.discord_webhook_name or "the webhook's channel"
            answer = QMessageBox.question(
                self, "Discord upload",
                f"Every clip that finishes from now on will be posted to Discord as “{name}”.\n\n"
                "Turn on automatic upload?",
            )
            if answer != QMessageBox.Yes:
                return
            self.config.discord_enabled = True
        self._refresh_discord()
        self._save_config()

    def open_discord_settings(self, enable: bool = False) -> None:
        dialog = DiscordDialog(self.config, self)
        if enable:
            dialog.enable_check.setChecked(True)
        if dialog.exec():
            self._refresh_discord()
            self._save_config()

    def upload_to_discord(self, jobs: List[Job]) -> None:
        if not self.config.discord_webhook:
            self.open_discord_settings()
            if not self.config.discord_webhook:
                return
        for job in jobs:
            if job.status == DONE and os.path.exists(job.dst):
                self.uploader.upload(job, job.dst, self.config.discord_webhook, self.config.discord_message,
                                     self.config.discord_guild_id)

    def _on_job_finished(self, job: Job) -> None:
        # Decided the moment a clip finishes: turning the switch off stops all later uploads.
        if self.discord_on:
            self.upload_to_discord([job])

    # ---- presets -------------------------------------------------------------
    def _all_presets(self) -> List[Preset]:
        custom = [
            Preset(p["name"], p.get("description", "Your saved preset."), EncodeSettings.from_dict(p["settings"]),
                   builtin=False, category="My presets")
            for p in self.config.custom_presets
            if p.get("name")
        ]
        return BUILTIN_PRESETS + custom

    def _reload_presets(self, selected: str) -> None:
        self.panel.set_presets(self._all_presets(), selected)

    def save_preset(self) -> None:
        current = self.panel.current_preset()
        suggestion = current.name if current and not current.builtin else ""
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=suggestion)
        name = name.strip()
        if not ok or not name:
            return
        if any(p.name == name for p in BUILTIN_PRESETS):
            QMessageBox.warning(self, "Save preset", "A built-in preset already uses that name.")
            return
        settings = self.panel.settings()
        self.config.custom_presets = [p for p in self.config.custom_presets if p.get("name") != name]
        self.config.custom_presets.append({"name": name, "description": "Your saved preset.",
                                           "settings": settings.to_dict()})
        self._reload_presets(name)
        self.panel.set_settings(settings)
        self.panel.refresh_preset_meta()
        self._on_settings_changed()

    def delete_preset(self) -> None:
        preset = self.panel.current_preset()
        if not preset or preset.builtin:
            return
        if QMessageBox.question(self, "Delete preset", f"Delete the preset “{preset.name}”?") != QMessageBox.Yes:
            return
        self.config.custom_presets = [p for p in self.config.custom_presets if p.get("name") != preset.name]
        self._reload_presets(BUILTIN_PRESETS[0].name)
        self.panel.set_settings(BUILTIN_PRESETS[0].settings)
        self.panel.refresh_preset_meta()
        self._on_settings_changed()

    # ---- adding clips ----------------------------------------------------------
    def add_files_dialog(self) -> None:
        patterns = " ".join(f"*{e}" for e in VIDEO_EXTENSIONS)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add clips", self.config.last_open_dir, f"Videos ({patterns});;All files (*)"
        )
        if files:
            self.config.last_open_dir = os.path.dirname(files[0])
            self.add_paths(files)

    def add_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add folder", self.config.last_open_dir)
        if folder:
            self.config.last_open_dir = folder
            self.add_paths([folder])

    def add_paths(self, paths: List[str]) -> None:
        files = collect_videos(paths)
        existing = {os.path.normcase(j.src) for j in self.queue.jobs if not j.is_finished}
        settings, preset = self.panel.settings(), self.panel.preset_name()
        for path in files:
            if os.path.normcase(path) not in existing:
                self.queue.add(path, settings.copy(), preset)
        if not files:
            QMessageBox.information(self, __app_name__, "No video files were found there.")

    # ---- queue actions ---------------------------------------------------------
    def toggle_queue(self) -> None:
        if self.queue.is_running:
            self.queue.stop()
        else:
            if not any(j.status in (READY, PROBING) for j in self.queue.jobs):
                if not self.queue.jobs:
                    self.add_files_dialog()
                    return
                retry = [j for j in self.queue.jobs if j.status == FAILED]
                if retry and QMessageBox.question(self, __app_name__, "Retry the failed clips?") == QMessageBox.Yes:
                    for job in retry:
                        self.queue.retry(job)
                else:
                    return
            self._apply_queue_prefs()
            self.queue.start()

    def remove_selected(self) -> None:
        jobs = self.view.selected_jobs()
        running = [j for j in jobs if j.status == RUNNING]
        if running and QMessageBox.question(
            self, "Remove clips", "Some selected clips are being encoded. Cancel and remove them?"
        ) != QMessageBox.Yes:
            return
        for job in jobs:
            self.queue.remove(job)

    def move_selected(self, delta: int) -> None:
        jobs = self.view.selected_jobs()
        for job in (jobs if delta < 0 else reversed(jobs)):
            self.queue.move(job, delta)
        self.view.reorder(self.queue.jobs)

    def apply_to_selected(self) -> None:
        jobs = self.view.selected_jobs() or [j for j in self.queue.jobs if j.status in (READY, PROBING)]
        settings, preset = self.panel.settings(), self.panel.preset_name()
        for job in jobs:
            if job.status != RUNNING:
                self.queue.update_job(job, settings.copy(), preset)
        self._update_estimate()

    def show_details(self, job: Job = None, tab: str = "") -> None:
        job = job or next(iter(self.view.selected_jobs()), None)
        if not job:
            return
        if not tab:
            tab = "trim" if job.status not in (DONE,) and job.info and job.status != RUNNING else "details"
        dialog = JobDialog(job, self.ffmpeg, self, tab=tab)
        if dialog.exec():
            # A new trim on a finished clip means it should be encoded again.
            if job.is_finished and (job.status != DONE or dialog.trim_changed_on_save):
                self.queue.retry(job)
            self.view.update_job(job)
            self._update_estimate()

    def open_preferences(self) -> None:
        if PreferencesDialog(self.config, self).exec():
            self._apply_queue_prefs()
            self._save_config()

    def _apply_queue_prefs(self) -> None:
        self.queue.concurrency = self.config.concurrent_jobs
        self.queue.skip_if_smaller = self.config.skip_if_smaller
        self.queue.retry_oversize = self.config.retry_oversize

    def _resolve_output(self, job: Job, reserved: set):
        folder, template, overwrite = self.panel.output_options()
        return resolve_output(job.src, job.settings, folder, template, overwrite, reserved)

    def _context_menu(self, pos) -> None:
        jobs = self.view.selected_jobs()
        if not jobs:
            return
        job = jobs[0]
        menu = QMenu(self)
        trim = menu.addAction("Trim…", lambda: self.show_details(job, "trim"))
        trim.setEnabled(job.info is not None and job.status != RUNNING)
        menu.addAction("Details && log…", lambda: self.show_details(job, "details"))
        menu.addAction("Open clip", lambda: _open_path(job.src))
        out = menu.addAction("Open result", lambda: _open_path(job.dst))
        out.setEnabled(job.status == DONE and os.path.exists(job.dst))
        folder = menu.addAction("Show in folder", lambda: _open_path(os.path.dirname(job.dst or job.src)))
        folder.setEnabled(True)
        menu.addSeparator()
        menu.addAction("Apply current settings", self.apply_to_selected)
        retry = menu.addAction("Encode again", lambda: [self.queue.retry(j) for j in jobs])
        retry.setEnabled(any(j.is_finished for j in jobs))
        cancel = menu.addAction("Cancel", lambda: [self.queue.cancel(j) for j in jobs if not j.is_finished])
        cancel.setEnabled(any(j.status == RUNNING for j in jobs))
        menu.addSeparator()
        sendable = [j for j in jobs if j.status == DONE and j.upload_state not in (QUEUED, UPLOADING)]
        send = menu.addAction("Upload to Discord" if not any(j.upload_state == UPLOADED for j in sendable)
                              else "Upload to Discord again", lambda: self.upload_to_discord(sendable))
        send.setEnabled(bool(sendable))
        if job.upload_link:
            menu.addAction("Open in Discord", lambda: QDesktopServices.openUrl(QUrl(job.upload_link)))
        menu.addSeparator()
        menu.addAction("Move up", lambda: self.move_selected(-1))
        menu.addAction("Move down", lambda: self.move_selected(1))
        menu.addAction("Remove", self.remove_selected)
        menu.exec(self.view.viewport().mapToGlobal(pos))

    # ---- queue signals ---------------------------------------------------------
    def _on_job_added(self, job: Job) -> None:
        self.view.add_job(job)
        self._schedule_refresh()

    def _on_job_changed(self, job: Job) -> None:
        self.view.update_job(job)
        self._schedule_refresh()
        if job.status == READY:
            # Probing finished, so this clip may now provide the size estimate.
            self._update_estimate()

    def _on_job_removed(self, job: Job) -> None:
        self.view.remove_job(job)
        self._schedule_refresh()
        self._update_estimate()

    def _on_running_changed(self, running: bool) -> None:
        self.start_btn.setText("Stop" if running else ("Start + upload" if self.discord_on else "Start"))
        self.start_btn.setObjectName("Danger" if running else "Primary")
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self._refresh_summary()

    def _on_queue_finished(self, done: int, failed: int, saved: int) -> None:
        msg = f"{done} clip{'s' if done != 1 else ''} compressed"
        if saved > 0:
            msg += f", {format_size(saved)} saved"
        if failed:
            msg += f" · {failed} failed"
        if self.config.notify_when_done and self.tray is not None:
            self.tray.show()
            self.tray.showMessage(__app_name__, msg, self.windowIcon(), 6000)
        QApplication.alert(self)
        if self.config.open_folder_when_done and done:
            last = next((j for j in reversed(self.queue.jobs) if j.status == DONE), None)
            if last:
                _open_path(os.path.dirname(last.dst))

    def _schedule_refresh(self) -> None:
        if not self._ui_timer.isActive():
            self._ui_timer.start()

    def _refresh_summary(self) -> None:
        jobs = self.queue.jobs
        if not jobs:
            self.summary_label.setText("No clips in the queue")
            self.overall.setValue(0)
            self.start_btn.setEnabled(True)
            return
        done = [j for j in jobs if j.status == DONE]
        finished = sum(1 for j in jobs if j.status in FINISHED_STATES)
        before = sum(j.info.size_bytes for j in done if j.info)
        after = sum(j.out_size or 0 for j in done)
        text = f"{finished} of {len(jobs)} clips finished"
        if done:
            text += f"  ·  {format_size(before)} → {format_size(after)}"
        failed = sum(1 for j in jobs if j.status == FAILED)
        if failed:
            text += f"  ·  {failed} failed"
        sent = sum(1 for j in jobs if j.upload_state == UPLOADED)
        if sent:
            text += f"  ·  {sent} sent to Discord"
        self.summary_label.setText(text)
        progress = sum(1.0 if j.status in FINISHED_STATES else j.progress for j in jobs) / len(jobs)
        self.overall.setValue(int(progress * 1000))

    # ---- settings --------------------------------------------------------------
    def _on_settings_changed(self) -> None:
        self._update_estimate()
        self._save_timer.start()

    def _update_estimate(self) -> None:
        jobs = self.view.selected_jobs()
        job = next((j for j in jobs if j.info), None) or next((j for j in self.queue.jobs if j.info), None)
        settings = self.panel.settings()
        selected = len(jobs)
        self.panel.apply_btn.setText(
            f"Apply to {selected} selected clip{'s' if selected != 1 else ''}" if selected
            else "Apply to all waiting clips"
        )
        if not job:
            self.panel.set_estimate("Add a clip to see a size estimate.")
            return
        try:
            plan = build_plan(self.ffmpeg, job.info, settings, job.src, "out", trim=job.trim, passlog="x")
        except Exception:  # noqa: BLE001 - estimate is best effort
            self.panel.set_estimate("")
            return
        parts = []
        if plan.estimated_bytes is not None:
            parts.append(f"≈ {format_size(plan.estimated_bytes)}")
        elif settings.mode == MODE_QUALITY:
            parts.append("Size depends on the content")
        if plan.out_height:
            parts.append(f"{plan.out_height}p")
        if plan.video_kbps:
            parts.append(f"{plan.video_kbps:,} kbps video")
        name = job.name if len(job.name) < 34 else job.name[:31] + "…"
        text = f"<b>{name}</b><br>" + "  ·  ".join(parts)
        if plan.warnings:
            text += f"<br><span style='color:#f5b544'>{plan.warnings[0]}</span>"
        self.panel.set_estimate(text)

    def _save_config(self) -> None:
        c = self.config
        preset = self.panel.current_preset()
        c.preset = preset.name if preset else c.preset
        c.settings = self.panel.settings().to_dict()
        c.output_dir, c.name_template, c.overwrite = self.panel.output_options()
        c.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
        c.splitter_state = bytes(self.splitter.saveState().toBase64()).decode()
        try:
            c.save()
        except OSError as exc:
            print(f"Could not save settings: {exc}", file=sys.stderr)

    # ---- window ---------------------------------------------------------------
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.add_paths(paths)

    def closeEvent(self, event) -> None:
        if self.queue.is_running and QMessageBox.question(
            self, __app_name__, "Clips are still being compressed. Stop and quit?"
        ) != QMessageBox.Yes:
            event.ignore()
            return
        uploading = any(j.upload_state in (QUEUED, UPLOADING) for j in self.queue.jobs)
        if uploading and QMessageBox.question(
            self, __app_name__, "Clips are still being uploaded to Discord. Quit anyway?"
        ) != QMessageBox.Yes:
            event.ignore()
            return
        self.queue.shutdown()
        self.uploader.shutdown()
        self._save_config()
        if self.tray is not None:
            self.tray.hide()
        event.accept()
