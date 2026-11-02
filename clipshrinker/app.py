"""Application entry point."""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from clipshrinker import __app_name__, __version__
from clipshrinker.config import AppConfig
from clipshrinker.ffmpeg import find_ffmpeg, restore_child_environment
from clipshrinker.ui.main_window import MainWindow
from clipshrinker.ui.theme import apply_theme


def resource_path(*parts: str) -> str:
    # PyInstaller unpacks data files under sys._MEIPASS.
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if hasattr(sys, "_MEIPASS"):
        base = os.path.join(base, "clipshrinker")
    return os.path.join(base, *parts)


def diagnose(ffmpeg: str) -> int:
    """Print what ClipShrinker detects (ClipShrinker --diagnose), for bug reports."""
    from clipshrinker.ffmpeg import available_encoders, detect_hardware

    print(f"{__app_name__} {__version__} ({sys.platform}, frozen={getattr(sys, 'frozen', False)})")
    print(f"FFmpeg: {ffmpeg}")
    print(f"LD_LIBRARY_PATH for FFmpeg: {os.environ.get('LD_LIBRARY_PATH', '(unset)')}")
    gpu = sorted(e for e in available_encoders(ffmpeg) if e.split("_")[-1] in
                 ("nvenc", "qsv", "amf", "vaapi", "videotoolbox"))
    print(f"GPU encoders compiled in: {', '.join(gpu) or 'none'}")
    result, device = detect_hardware(ffmpeg)
    for hw, ok in result.items():
        print(f"  {hw:13} {'works' if ok else 'not detected'}" + (f" ({device})" if hw == "vaapi" and ok else ""))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    restore_child_environment()
    if "--diagnose" in argv:
        try:
            return diagnose(find_ffmpeg(AppConfig.load().ffmpeg_path))
        except FileNotFoundError as exc:
            print(exc)
            return 1
    if sys.platform == "win32":
        # Give the app its own taskbar entry and icon instead of python.exe's.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"ClipShrinker.{__version__}")
        except Exception:  # noqa: BLE001
            pass

    app = QApplication(argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("clipshrinker")
    icon = QIcon(resource_path("resources", "icon.png"))
    app.setWindowIcon(icon)
    apply_theme(app, resource_path("resources"))

    config = AppConfig.load()
    try:
        ffmpeg = find_ffmpeg(config.ffmpeg_path)
    except FileNotFoundError as exc:
        QMessageBox.critical(None, __app_name__, str(exc))
        return 1

    window = MainWindow(ffmpeg, config, icon)
    window.show()
    # Files passed on the command line (e.g. "Open with" or dropped on the executable).
    files = [a for a in argv[1:] if os.path.exists(a)]
    if files:
        window.add_paths(files)
    return app.exec()
