# PyInstaller spec - build with:  pyinstaller ClipShrinker.spec
#
# Windows/macOS: a single self-contained executable in dist/.
# Linux: a folder (dist/ClipShrinker/) that tools/build_appimage.sh packs into an AppImage.
# The AppImage is already a single file, and a folder starts faster than a one-file build
# that has to unpack itself on every launch.
import sys

from PyInstaller.utils.hooks import collect_data_files

ONEDIR = sys.platform.startswith("linux")

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

if ONEDIR:
    exe = EXE(
        pyz,
        a.scripts,
        exclude_binaries=True,
        name="ClipShrinker",
        console=False,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="ClipShrinker", upx=False)
else:
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
