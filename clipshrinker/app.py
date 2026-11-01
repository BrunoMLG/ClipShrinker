"""Application entry point."""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from clipshrinker import __app_name__, __version__
from clipshrinker.config import AppConfig
from clipshrinker.ffmpeg import find_ffmpeg
from clipshrinker.ui.main_window import MainWindow
from clipshrinker.ui.theme import apply_theme


def resource_path(*parts: str) -> str:
    # PyInstaller unpacks data files under sys._MEIPASS.
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if hasattr(sys, "_MEIPASS"):
        base = os.path.join(base, "clipshrinker")
    return os.path.join(base, *parts)


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
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
