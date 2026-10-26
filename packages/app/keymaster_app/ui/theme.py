from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from keymaster_app import PACKAGE_DIR

CHECK_ICON = (PACKAGE_DIR / "assets" / "check.svg").as_posix()

ACCENT = "#36c46f"
ACCENT_DARK = "#24944f"
BASE = "#16181c"
SURFACE = "#1e2127"
RAISED = "#262a31"
BORDER = "#323741"
TEXT = "#e6e8eb"
MUTED = "#9aa1ab"
DANGER = "#e5584f"

STYLE = f"""
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {BASE}; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#title {{ font-size: 16pt; font-weight: 600; }}
QLabel#subtitle {{ color: {MUTED}; }}
QLabel#section {{ color: {MUTED}; font-size: 9pt; font-weight: 600; letter-spacing: 1px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#dropHint {{ color: {MUTED}; font-size: 12pt; border: 2px dashed {BORDER}; border-radius: 12px; padding: 24px; }}
QLabel#checkOk {{ color: {ACCENT}; font-weight: 600; }}
QLabel#checkBad {{ color: {DANGER}; font-weight: 600; }}
QPushButton {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {MUTED}; background: transparent; border-color: {BORDER}; }}
QPushButton#primary {{ background: {ACCENT}; color: #0b1a10; border: none; font-weight: 600; padding: 8px 22px; }}
QPushButton#primary:hover {{ background: {ACCENT_DARK}; color: white; }}
QPushButton#primary:disabled {{ background: {RAISED}; color: {MUTED}; }}
QPushButton#danger {{ border-color: {DANGER}; }}
QPushButton#danger:hover {{ background: {DANGER}; color: white; }}
QPushButton#danger:disabled {{ border-color: {BORDER}; background: transparent; }}
QTreeWidget, QLineEdit, QComboBox {{
    background: {BASE}; border: 1px solid {BORDER}; border-radius: 7px; padding: 4px;
    selection-background-color: {ACCENT_DARK};
}}
QTreeWidget::item {{ padding: 6px 2px; }}
QHeaderView::section {{ background: {SURFACE}; color: {MUTED}; border: none; padding: 6px; font-weight: 600; }}
QProgressBar {{ background: {BASE}; border: 1px solid {BORDER}; border-radius: 6px; text-align: center; min-height: 14px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}
QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; margin: -6px 0; border-radius: 7px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {MUTED}; border-radius: 4px; background: {BASE}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url("{CHECK_ICON}"); }}
QCheckBox::indicator:disabled {{ border-color: {BORDER}; }}
QCheckBox::indicator:checked:disabled {{ background: {ACCENT_DARK}; border-color: {ACCENT_DARK}; }}
QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER}; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.Window: BASE, QPalette.WindowText: TEXT, QPalette.Base: BASE,
        QPalette.AlternateBase: SURFACE, QPalette.Text: TEXT, QPalette.Button: RAISED,
        QPalette.ButtonText: TEXT, QPalette.Highlight: ACCENT_DARK, QPalette.HighlightedText: "#ffffff",
        QPalette.ToolTipBase: RAISED, QPalette.ToolTipText: TEXT, QPalette.PlaceholderText: MUTED,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(MUTED))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(MUTED))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
