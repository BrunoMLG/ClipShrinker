"""Job queue: probing clips, running FFmpeg processes and tracking progress."""

from __future__ import annotations

import glob
import itertools
import os
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QProcess, QRunnable, QThreadPool, Signal

from clipshrinker.encode import MB, MODE_SIZE, EncodeSettings, Trim, build_plan, validate
from clipshrinker.ffmpeg import MediaInfo, probe

PROBING = "probing"
READY = "ready"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"
SKIPPED = "skipped"

FINISHED_STATES = (DONE, FAILED, CANCELLED, SKIPPED)

VIDEO_EXTENSIONS = (
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv", ".ts", ".mts", ".m2ts", ".3gp", ".mpg", ".mpeg",
)

MAX_SIZE_RETRIES = 2

_ids = itertools.count(1)


@dataclass
class Job:
    src: str
    settings: EncodeSettings
    preset: str
    id: int = field(default_factory=lambda: next(_ids))
    trim: Trim = field(default_factory=Trim)
    info: Optional[MediaInfo] = None
    status: str = PROBING
    progress: float = 0.0
    message: str = ""
    dst: str = ""
    out_size: Optional[int] = None
    eta: Optional[float] = None
    speed: str = ""
    log: List[str] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def name(self) -> str:
        return os.path.basename(self.src)

    @property
    def is_finished(self) -> bool:
        return self.status in FINISHED_STATES

    def reset(self) -> None:
        self.status = READY if self.info else PROBING
        self.progress = 0.0
        self.message = ""
        self.out_size = None
        self.eta = None
        self.speed = ""
        self.log.clear()


def resolve_output(src: str, settings: EncodeSettings, output_dir: str, template: str,
                   overwrite: str, reserved: set) -> Optional[str]:
    """Where to write a job's result. Returns None when the job should be skipped."""
    folder = output_dir or os.path.dirname(src)
    stem = os.path.splitext(os.path.basename(src))[0]
    try:
        name = (template or "{name}_shrunk").format(name=stem, codec=settings.codec)
    except (KeyError, IndexError, ValueError):
        name = f"{stem}_shrunk"
    name = "".join(c for c in name if c not in '<>:"/\\|?*') or f"{stem}_shrunk"
    base = os.path.join(folder, name)
    ext = "." + settings.container
    dst = base + ext

    def taken(path: str) -> bool:
        return os.path.exists(path) or os.path.normcase(path) in reserved

    if os.path.normcase(os.path.abspath(dst)) == os.path.normcase(os.path.abspath(src)):
        overwrite = "rename"  # never encode a file onto itself
    if taken(dst):
        if overwrite == "skip":
            return None
        if overwrite == "rename" or os.path.normcase(dst) in reserved:
            for n in itertools.count(1):
                candidate = f"{base}_{n}{ext}"
                if not taken(candidate) and os.path.abspath(candidate) != os.path.abspath(src):
                    dst = candidate
                    break
    return dst


def collect_videos(paths: List[str]) -> List[str]:
    """Expand dropped files and folders into a list of video files."""
    found = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for name in sorted(files):
                    if name.lower().endswith(VIDEO_EXTENSIONS):
                        found.append(os.path.join(root, name))
        elif os.path.isfile(path):
            found.append(path)
    return found


class _ProbeSignals(QObject):
    done = Signal(int, object, str)  # job id, MediaInfo or None, error


class _ProbeTask(QRunnable):
    def __init__(self, ffmpeg: str, job: Job, signals: _ProbeSignals):
        super().__init__()
        self.ffmpeg, self.job_id, self.path, self.signals = ffmpeg, job.id, job.src, signals

    def run(self) -> None:
        try:
            info = probe(self.ffmpeg, self.path)
            self.signals.done.emit(self.job_id, info, "")
        except Exception as exc:  # noqa: BLE001 - any failure just marks the job
            self.signals.done.emit(self.job_id, None, str(exc))


class _Run:
    """State of one job while FFmpeg is running for it."""

    def __init__(self, job: Job, process: QProcess):
        self.job = job
        self.process = process
        self.passes: List[List[str]] = []
        self.pass_index = 0
        self.duration = 0.0
        self.tmp_path = ""
        self.passlog = ""
        self.size_scale = 1.0
        self.attempt = 0
        self.cancelled = False
        self.stdout_buf = ""


class JobQueue(QObject):
    """Owns the list of jobs and runs them through FFmpeg."""

    job_added = Signal(object)
    job_changed = Signal(object)
    job_removed = Signal(object)
    running_changed = Signal(bool)
    queue_finished = Signal(int, int, int)  # done, failed, bytes saved

    def __init__(self, ffmpeg: str, parent=None):
        super().__init__(parent)
        self.ffmpeg = ffmpeg
        self.jobs: List[Job] = []
        self.concurrency = 1
        self.skip_if_smaller = True
        self.retry_oversize = True
        self.output_resolver: Callable[[Job, set], Optional[str]] = lambda job, reserved: None
        self._runs: Dict[int, _Run] = {}
        self._running = False
        self._session: List[Job] = []
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(4)
        self._probe_signals = _ProbeSignals()
        self._probe_signals.done.connect(self._on_probed)

    # ---- queue management ------------------------------------------------
    @property
    def is_running(self) -> bool:
        return self._running

    def add(self, path: str, settings: EncodeSettings, preset: str) -> Job:
        job = Job(src=path, settings=settings, preset=preset)
        self.jobs.append(job)
        self.job_added.emit(job)
        self._pool.start(_ProbeTask(self.ffmpeg, job, self._probe_signals))
        return job

    def find(self, job_id: int) -> Optional[Job]:
        return next((j for j in self.jobs if j.id == job_id), None)

    def remove(self, job: Job) -> None:
        if job.id in self._runs:
            self.cancel(job)
        if job in self.jobs:
            self.jobs.remove(job)
            self.job_removed.emit(job)

    def move(self, job: Job, delta: int) -> None:
        i = self.jobs.index(job)
        j = max(0, min(len(self.jobs) - 1, i + delta))
        if i != j:
            self.jobs.insert(j, self.jobs.pop(i))

    def update_job(self, job: Job, settings: EncodeSettings, preset: str) -> None:
        if job.status in (RUNNING,):
            return
        job.settings, job.preset = settings, preset
        if job.is_finished:
            job.reset()
        self.job_changed.emit(job)
        self._schedule()

    def retry(self, job: Job) -> None:
        if job.is_finished:
            job.reset()
            self.job_changed.emit(job)
            self._schedule()

    def clear_finished(self) -> None:
        for job in [j for j in self.jobs if j.status in (DONE, SKIPPED, CANCELLED)]:
            self.remove(job)

    def _on_probed(self, job_id: int, info, error: str) -> None:
        job = self.find(job_id)
        if not job:
            return
        if info is None:
            job.status, job.message = FAILED, error or "Could not read file"
        else:
            job.info, job.status = info, READY
        self.job_changed.emit(job)
        self._schedule()

    # ---- running ---------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._session = []
        self.running_changed.emit(True)
        self._schedule()

    def stop(self) -> None:
        """Stop everything; running jobs go back to the queue."""
        self._running = False
        for run in list(self._runs.values()):
            self._kill(run)
            run.job.reset()
            self.job_changed.emit(run.job)
        self._runs.clear()
        self.running_changed.emit(False)

    def cancel(self, job: Job) -> None:
        run = self._runs.pop(job.id, None)
        if run:
            self._kill(run)
        if not job.is_finished:
            job.status, job.message, job.eta = CANCELLED, "Cancelled", None
            self.job_changed.emit(job)
        self._schedule()

    def _kill(self, run: _Run) -> None:
        run.cancelled = True
        run.process.kill()
        run.process.waitForFinished(3000)
        self._cleanup(run, remove_output=True)

    def _schedule(self) -> None:
        if not self._running:
            return
        for job in self.jobs:
            if len(self._runs) >= max(1, self.concurrency):
                break
            if job.status == READY and job.id not in self._runs:
                self._start_job(job)
        if not self._runs and not any(j.status in (READY, PROBING) for j in self.jobs):
            self._finish_session()

    def _finish_session(self) -> None:
        self._running = False
        done = [j for j in self._session if j.status == DONE]
        failed = sum(1 for j in self._session if j.status == FAILED)
        saved = sum((j.info.size_bytes - (j.out_size or 0)) for j in done if j.info)
        self.running_changed.emit(False)
        if self._session:
            self.queue_finished.emit(len(done), failed, saved)
        self._session = []

    def _fail(self, job: Job, message: str) -> None:
        job.status, job.message, job.eta = FAILED, message, None
        job.finished_at = time.time()
        self.job_changed.emit(job)

    def _start_job(self, job: Job) -> None:
        self._session.append(job)
        errors = validate(job.settings)
        if errors:
            self._fail(job, errors[0])
            return
        settings, info = job.settings, job.info
        assert info is not None

        if (
            self.skip_if_smaller
            and settings.mode == MODE_SIZE
            and not job.trim
            and info.size_bytes <= settings.target_size_mb * MB
        ):
            job.status, job.progress = SKIPPED, 1.0
            job.message = "Already under the target size"
            self.job_changed.emit(job)
            return

        reserved = {os.path.normcase(r.job.dst) for r in self._runs.values()}
        dst = self.output_resolver(job, reserved)
        if dst is None:
            job.status, job.message = SKIPPED, "Output file already exists"
            self.job_changed.emit(job)
            return
        try:
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        except OSError as exc:
            self._fail(job, f"Cannot create output folder: {exc}")
            return

        job.reset()
        job.dst = dst
        job.status, job.message = RUNNING, "Starting…"
        job.started_at = time.time()

        process = QProcess(self)
        run = _Run(job, process)
        stem, ext = os.path.splitext(dst)
        run.tmp_path = f"{stem}.part{ext}"
        run.passlog = os.path.join(tempfile.gettempdir(), f"clipshrinker-{os.getpid()}-{job.id}")
        self._runs[job.id] = run

        process.readyReadStandardOutput.connect(lambda r=run: self._on_stdout(r))
        process.readyReadStandardError.connect(lambda r=run: self._on_stderr(r))
        process.finished.connect(lambda code, _status, r=run: self._on_finished(r, code))
        process.errorOccurred.connect(lambda err, r=run: self._on_error(r, err))
        self._launch(run)

    def _launch(self, run: _Run) -> None:
        job = run.job
        plan = build_plan(self.ffmpeg, job.info, job.settings, job.src, run.tmp_path,
                          trim=job.trim, passlog=run.passlog, size_scale=run.size_scale)
        run.passes, run.pass_index, run.duration = plan.passes, 0, plan.duration
        for w in plan.warnings:
            job.log.append(f"[warning] {w}")
        self._start_pass(run)

    def _start_pass(self, run: _Run) -> None:
        cmd = run.passes[run.pass_index]
        run.job.log.append("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        run.stdout_buf = ""
        run.process.start(cmd[0], cmd[1:])

    def _pass_weights(self, run: _Run) -> List[float]:
        # The analysis pass of a 2-pass encode is usually much quicker.
        return [0.35, 0.65] if len(run.passes) == 2 else [1.0]

    def _on_stdout(self, run: _Run) -> None:
        data = bytes(run.process.readAllStandardOutput()).decode("utf-8", "replace")
        run.stdout_buf += data
        *lines, run.stdout_buf = run.stdout_buf.split("\n")
        job = run.job
        frac = None
        for line in lines:
            key, _, value = line.strip().partition("=")
            if key in ("out_time_us", "out_time_ms") and value.lstrip("-").isdigit():
                frac = int(value) / 1_000_000 / max(run.duration, 0.01)
            elif key == "speed" and value not in ("N/A", ""):
                job.speed = value.strip()
        if frac is None:
            return
        weights = self._pass_weights(run)
        frac = max(0.0, min(1.0, frac))
        total = sum(weights[: run.pass_index]) + weights[run.pass_index] * frac
        job.progress = min(0.999, total)
        elapsed = time.time() - job.started_at
        job.eta = elapsed / job.progress - elapsed if job.progress > 0.02 else None
        pass_note = f"Pass {run.pass_index + 1}/{len(run.passes)} · " if len(run.passes) > 1 else ""
        retry_note = f"Retry {run.attempt} · " if run.attempt else ""
        job.message = f"{retry_note}{pass_note}{job.speed}".rstrip(" ·")
        self.job_changed.emit(job)

    def _on_stderr(self, run: _Run) -> None:
        text = bytes(run.process.readAllStandardError()).decode("utf-8", "replace")
        run.job.log.extend(l for l in text.splitlines() if l.strip())
        del run.job.log[:-500]

    def _on_error(self, run: _Run, error) -> None:
        if error == QProcess.ProcessError.FailedToStart and not run.cancelled:
            self._runs.pop(run.job.id, None)
            self._fail(run.job, "Could not start FFmpeg")
            self._schedule()

    def _on_finished(self, run: _Run, code: int) -> None:
        job = run.job
        if run.cancelled or self._runs.get(job.id) is not run:
            return
        if code != 0:
            self._runs.pop(job.id, None)
            self._cleanup(run, remove_output=True)
            errors = [l for l in job.log if not l.startswith(("$ ", "[warning]"))]
            self._fail(job, errors[-1] if errors else f"FFmpeg exited with code {code}")
            self._schedule()
            return
        if run.pass_index + 1 < len(run.passes):
            run.pass_index += 1
            self._start_pass(run)
            return

        size = os.path.getsize(run.tmp_path) if os.path.exists(run.tmp_path) else 0
        target = job.settings.target_size_mb * MB
        if (
            job.settings.mode == MODE_SIZE
            and self.retry_oversize
            and size > target
            and run.attempt < MAX_SIZE_RETRIES
        ):
            # Overshot the size limit: re-encode with a proportionally smaller budget.
            run.attempt += 1
            run.size_scale *= target / size * 0.97
            job.log.append(f"[retry] {size / MB:.2f} MB is over the limit, retrying with a lower bitrate")
            job.started_at = time.time()
            self._launch(run)
            return

        self._runs.pop(job.id, None)
        try:
            os.replace(run.tmp_path, job.dst)
        except OSError as exc:
            self._cleanup(run, remove_output=True)
            self._fail(job, f"Could not save output: {exc}")
            self._schedule()
            return
        self._cleanup(run, remove_output=False)
        job.out_size = size
        job.status, job.progress, job.eta = DONE, 1.0, None
        job.finished_at = time.time()
        job.message = ""
        if job.settings.mode == MODE_SIZE and size > target:
            job.message = "Still over the target size"
        self.job_changed.emit(job)
        self._schedule()

    def _cleanup(self, run: _Run, remove_output: bool) -> None:
        paths = glob.glob(glob.escape(run.passlog) + "*")
        if remove_output:
            paths.append(run.tmp_path)
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass

    def shutdown(self) -> None:
        self._running = False
        for run in list(self._runs.values()):
            self._kill(run)
        self._runs.clear()
        self._pool.clear()
        self._pool.waitForDone(2000)
