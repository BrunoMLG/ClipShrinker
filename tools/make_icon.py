"""Render the app icon to assets/icon.png and assets/icon.ico.

Usage: python tools/make_icon.py   (needs PySide6 and Pillow)
"""

import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")


def render(size: int = 512) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 512

    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor("#8b7bff"))
    grad.setColorAt(1, QColor("#4f3bd9"))
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(24 * s, 24 * s, 464 * s, 464 * s), 110 * s, 110 * s)
    p.fillPath(bg, QBrush(grad))

    # Film frame
    p.setPen(QPen(QColor("white"), 26 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(150 * s, 150 * s, 212 * s, 212 * s), 34 * s, 34 * s)

    # Play triangle
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    tri = QPolygonF([QPointF(222 * s, 205 * s), QPointF(222 * s, 307 * s), QPointF(306 * s, 256 * s)])
    p.drawPolygon(tri)

    # Inward corner arrows ("shrink")
    pen = QPen(QColor("white"), 24 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx = 256 + sx * -184
        cy = 256 + sy * -184
        tip_x, tip_y = cx + sx * 52, cy + sy * 52
        p.drawLine(QPointF(cx * s, cy * s), QPointF(tip_x * s, tip_y * s))
        p.drawLine(QPointF(tip_x * s, tip_y * s), QPointF((tip_x - sx * 36) * s, tip_y * s))
        p.drawLine(QPointF(tip_x * s, tip_y * s), QPointF(tip_x * s, (tip_y - sy * 36) * s))
    p.end()
    return img


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841 - needed for font/paint backends
    os.makedirs(ASSETS, exist_ok=True)
    png = os.path.join(ROOT, "clipshrinker", "resources", "icon.png")
    render(512).save(png)

    from PIL import Image

    Image.open(png).save(
        os.path.join(ASSETS, "icon.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("wrote", png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
