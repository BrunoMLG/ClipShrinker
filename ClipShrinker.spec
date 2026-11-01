# PyInstaller spec - build with:  pyinstaller ClipShrinker.spec
import sys

from PyInstaller.utils.hooks import collect_data_files

datas = [("clipshrinker/resources", "clipshrinker/resources")]
# The FFmpeg binary that ships inside the imageio-ffmpeg wheel.
datas += collect_data_files("imageio_ffmpeg", subdir="binaries")

# Qt modules ClipShrinker never uses; leaving them out keeps the download small.
excludes = [
    "tkinter", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia",
    "PySide6.QtPdf", "PySide6.QtCharts", "PySide6.Qt3DCore", "PySide6.QtOpenGL",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtPositioning",
]

a = Analysis(
    ["ClipShrinker.py"],
    datas=datas,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="ClipShrinker",
    console=False,
    upx=False,
    icon="assets/icon.ico" if sys.platform == "win32" else None,
)
