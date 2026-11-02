"""Dark theme: palette plus a Qt style sheet."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG = "#14151a"
SURFACE = "#1c1d24"
SURFACE_2 = "#24262f"
BORDER = "#2f313c"
TEXT = "#e8e9ee"
MUTED = "#8b8fa3"
ACCENT = "#7c6cff"
ACCENT_HOVER = "#8f81ff"
SUCCESS = "#3ecf8e"
WARNING = "#f5b544"
DANGER = "#f2555a"
DISCORD = "#5865f2"

STYLE = f"""
* {{
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#Panel {{ background: {SURFACE}; border-left: 1px solid {BORDER}; }}
QWidget#TopBar, QWidget#BottomBar {{ background: {SURFACE}; }}
QWidget#TopBar {{ border-bottom: 1px solid {BORDER}; }}
QWidget#BottomBar {{ border-top: 1px solid {BORDER}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

QLabel#Title {{ font-size: 17px; font-weight: 700; }}
QLabel#Subtitle, QLabel.muted, QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel#SectionTitle {{
    color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px;
    padding-top: 6px;
}}
QLabel#Hint {{ color: {MUTED}; font-size: 12px; }}
QLabel#Warning {{ color: {WARNING}; font-size: 12px; }}
QLabel#EmptyTitle {{ font-size: 18px; font-weight: 600; color: {TEXT}; }}
QLabel#EmptyText {{ color: {MUTED}; }}

QFrame#Card {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
}}

QPushButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: #2c2e39; border-color: #3b3e4c; }}
QPushButton:pressed {{ background: #22242c; }}
QPushButton:disabled {{ color: #5c5f70; background: {SURFACE}; }}
QPushButton#Primary {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: white; font-weight: 600;
    padding: 8px 22px;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:disabled {{ background: #3d3870; border-color: #3d3870; color: #a9a3d6; }}
QPushButton#Danger {{
    background: {DANGER}; border: 1px solid {DANGER}; color: white; font-weight: 600;
    padding: 8px 22px;
}}
QPushButton#DiscordOff {{
    background: transparent; border: 1px dashed #4a4d5e; color: {MUTED}; padding: 7px 14px;
}}
QPushButton#DiscordOff:hover {{ color: {TEXT}; border-color: {DISCORD}; }}
QPushButton#DiscordOn {{
    background: rgba(88, 101, 242, 0.18); border: 1px solid {DISCORD}; color: #dfe2ff;
    font-weight: 600; padding: 7px 14px;
}}
QPushButton#DiscordOn:hover {{ background: rgba(88, 101, 242, 0.28); }}
QPushButton#Flat {{ background: transparent; border: none; color: {MUTED}; padding: 6px 8px; }}
QPushButton#Flat:hover {{ color: {TEXT}; background: {SURFACE_2}; }}
QPushButton#Chip {{
    padding: 4px 10px; border-radius: 12px; font-size: 12px;
}}
QPushButton#Segment {{
    border-radius: 0; padding: 6px 4px; background: {SURFACE};
}}
QPushButton#Segment:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600; }}
QPushButton#SegmentFirst {{
    border-radius: 0; border-top-left-radius: 7px; border-bottom-left-radius: 7px;
    padding: 6px 4px; background: {SURFACE};
}}
QPushButton#SegmentLast {{
    border-radius: 0; border-top-right-radius: 7px; border-bottom-right-radius: 7px;
    padding: 6px 4px; background: {SURFACE};
}}
QPushButton#SegmentFirst:checked, QPushButton#SegmentLast:checked {{
    background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600;
}}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 5px 8px; min-height: 20px; selection-background-color: {ACCENT};
}}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: #3f4252; }}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url(@RES@/chevron.svg); width: 12px; height: 12px; margin-right: 8px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 6px;
    selection-background-color: {ACCENT}; padding: 4px;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #4a4d5e; background: {BG};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url(@RES@/check.svg); }}
QCheckBox:disabled {{ color: #5c5f70; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: white; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}}

QTreeWidget {{
    background: {BG}; border: none; alternate-background-color: #17181e;
    selection-background-color: #2a2950;
}}
QTreeWidget::item {{ height: 40px; border: none; padding-left: 8px; }}
QTreeWidget::item:selected {{ background: #2a2950; color: {TEXT}; }}
QTreeWidget::item:hover:!selected {{ background: #1d1e26; }}
QHeaderView::section {{
    background: {BG}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 8px 10px; font-size: 11px; font-weight: 700;
}}

QProgressBar {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 5px; height: 10px;
    text-align: center; font-size: 11px;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3a3c48; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #4a4d5c; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #3a3c48; border-radius: 3px; min-width: 30px; }}

QPlainTextEdit {{
    background: #0e0f13; border: 1px solid {BORDER}; border-radius: 7px;
    font-family: "Consolas", "DejaVu Sans Mono", "Menlo", monospace; font-size: 12px;
}}
QMenu {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 22px 6px 14px; border-radius: 5px; }}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenu::item:disabled {{ color: #5c5f70; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
QToolTip {{
    background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px;
    border-radius: 6px;
}}
QSplitter::handle {{ background: {BORDER}; }}
QTabWidget::pane {{ border: none; border-top: 1px solid {BORDER}; }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 8px 16px; border: none;
    border-bottom: 2px solid transparent; margin-right: 4px;
}}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom-color: {ACCENT}; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}
QMessageBox QLabel {{ color: {TEXT}; }}
"""


def apply_theme(app: QApplication, resource_dir: str) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in (
        (QPalette.Window, BG),
        (QPalette.WindowText, TEXT),
        (QPalette.Base, BG),
        (QPalette.AlternateBase, SURFACE),
        (QPalette.Text, TEXT),
        (QPalette.Button, SURFACE_2),
        (QPalette.ButtonText, TEXT),
        (QPalette.Highlight, ACCENT),
        (QPalette.HighlightedText, "#ffffff"),
        (QPalette.ToolTipBase, SURFACE_2),
        (QPalette.ToolTipText, TEXT),
        (QPalette.PlaceholderText, MUTED),
        (QPalette.Link, ACCENT_HOVER),
    ):
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor("#5c5f70"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#5c5f70"))
    app.setPalette(pal)
    # Qt style sheets want forward slashes even on Windows.
    app.setStyleSheet(STYLE.replace("@RES@", resource_dir.replace("\\", "/")))
