from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Module-level palette used by charts/widgets after apply_theme.
BG = "#1B1B1F"
SURFACE = "#2A2A30"
SURFACE_2 = "#333338"
TEXT = "#F4F4F5"
MUTED = "#A1A1AA"
DIM = "#A1A1AA"
BORDER = "#3F3F46"
ACCENT = "#F97316"
ACCENT_HOVER = "#EA580C"
GREEN = "#34D399"
RED = "#FB7185"
AMBER = "#F97316"
INPUT = "#333338"
HOVER = "#3F3F46"
NAV_BG = "#141416"
NAV_TEXT = "#A1A1AA"
NAV_ACTIVE = "#F97316"
BTN_TEXT = "#FFFFFF"

LIGHT = {
    "BG": "#F4F4F5",
    "SURFACE": "#FFFFFF",
    "SURFACE_2": "#F4F4F5",
    "TEXT": "#18181B",
    "MUTED": "#71717A",
    "DIM": "#A1A1AA",
    "BORDER": "#E4E4E7",
    "ACCENT": "#F97316",
    "ACCENT_HOVER": "#EA580C",
    "GREEN": "#059669",
    "RED": "#E11D48",
    "AMBER": "#EA580C",
    "INPUT": "#FFFFFF",
    "HOVER": "#FFF7ED",
    "NAV_BG": "#18181B",
    "NAV_TEXT": "#A1A1AA",
    "NAV_ACTIVE": "#F97316",
    "BTN_TEXT": "#FFFFFF",
}

DARK = {
    "BG": "#1B1B1F",
    "SURFACE": "#2A2A30",
    "SURFACE_2": "#333338",
    "TEXT": "#F4F4F5",
    "MUTED": "#A1A1AA",
    "DIM": "#A1A1AA",
    "BORDER": "#3F3F46",
    "ACCENT": "#F97316",
    "ACCENT_HOVER": "#EA580C",
    "GREEN": "#34D399",
    "RED": "#FB7185",
    "AMBER": "#F97316",
    "INPUT": "#333338",
    "HOVER": "#3F3F46",
    "NAV_BG": "#141416",
    "NAV_TEXT": "#A1A1AA",
    "NAV_ACTIVE": "#F97316",
    "BTN_TEXT": "#FFFFFF",
}

CURRENT = "dark"


def _apply_globals(palette: dict[str, str]) -> None:
    g = globals()
    for key, value in palette.items():
        g[key] = value


def stylesheet() -> str:
    return f"""
QMainWindow, QDialog, QMessageBox, QFileDialog {{
    background-color: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QWidget {{
    color: {TEXT};
    font-size: 13px;
}}
QStackedWidget {{
    background-color: {BG};
}}
QFrame#sideNav {{
    background-color: {NAV_BG};
    border-right: 1px solid {BORDER};
}}
QLabel#brand {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#brandSub {{
    color: {MUTED};
    font-size: 11px;
}}
QPushButton#navButton {{
    background: transparent;
    color: {NAV_TEXT};
    border: none;
    border-radius: 10px;
    text-align: left;
    padding: 10px 12px;
    min-height: 36px;
    font-size: 13px;
}}
QPushButton#navButton:hover {{
    background: {HOVER};
    color: {TEXT};
    border: none;
}}
QPushButton#navButton:checked {{
    background: {ACCENT};
    color: {BTN_TEXT};
    font-weight: 600;
    border: none;
}}
QPushButton#navButton:checked:hover {{
    background: {ACCENT_HOVER};
    color: {BTN_TEXT};
    border: none;
}}
QPushButton#drawerToggle {{
    background: transparent;
    color: {ACCENT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 12px;
}}
QPushButton#drawerToggle:checked {{
    background: rgba(249, 115, 22, 0.22);
    border-color: {ACCENT};
    color: {TEXT};
}}
QWidget#upcomingDrawer, QFrame#upcomingDrawer {{
    background-color: {SURFACE};
    border-left: 1px solid {BORDER};
    color: {TEXT};
}}
QFrame#metricCard, QFrame#dashCard {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#billRow, QFrame#billRowThisWeek, QFrame#billRowOverdue {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#billRowOverdue {{
    border-color: {RED};
    background: #3F2228;
}}
QFrame#billRowThisWeek {{
    border-color: {ACCENT};
}}
QLabel#groupOverdue {{
    color: {RED};
    font-weight: 600;
}}
QLabel#groupWeek {{
    color: {ACCENT};
    font-weight: 600;
}}
QLabel#groupLater {{
    color: {MUTED};
    font-weight: 600;
}}
QLabel#pageTitle {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#pageSubtitle, QLabel#helperText, QLabel#cardHint, QLabel#chartSubtitle {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#cardTitle, QLabel#sectionTitle {{
    color: {MUTED};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QLabel#cardValue {{
    font-size: 28px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#monoPath {{
    color: {TEXT};
    font-family: monospace;
    font-size: 12px;
}}
QLabel#recipe {{
    color: {MUTED};
    font-size: 12px;
}}
QFrame#warningBanner {{
    background: #3F2A1A;
    border: 1px solid {ACCENT};
    border-radius: 10px;
}}
QLabel#warningText {{
    color: {ACCENT};
}}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    min-height: 28px;
    selection-background-color: {ACCENT};
    selection-color: {BTN_TEXT};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {BTN_TEXT};
    border: 1px solid {BORDER};
}}
QPushButton {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 12px;
    min-height: 28px;
}}
QPushButton:hover {{
    background: {HOVER};
    border-color: {ACCENT};
}}
QPushButton#primary {{
    background: {ACCENT};
    color: {BTN_TEXT};
    font-weight: 600;
    border: none;
    border-radius: 9px;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#danger {{
    color: {RED};
    border-color: {RED};
    background: {SURFACE};
}}
QPushButton#rangeButton {{
    background: {SURFACE_2};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-radius: 9px;
}}
QPushButton#rangeButton:checked {{
    background: {ACCENT};
    color: {BTN_TEXT};
    border-color: {ACCENT};
    font-weight: 600;
}}
QTableWidget, QTreeWidget, QTableView, QListWidget {{
    background: {SURFACE};
    alternate-background-color: {SURFACE_2};
    color: {TEXT};
    gridline-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 12px;
    selection-background-color: rgba(249, 115, 22, 0.28);
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {SURFACE_2};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 10px;
    font-weight: 600;
    font-size: 12px;
}}
QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 14px;
    padding: 16px 16px 14px 16px;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {MUTED};
    font-weight: 600;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QSplitter::handle {{
    background: {BORDER};
}}
QSplitter#incomeSplitter::handle {{
    background: {BORDER};
    margin: 12px 0;
    width: 1px;
}}
QSplitter#incomeSplitter::handle:hover {{
    background: {ACCENT};
}}
QStatusBar {{
    color: {MUTED};
    background: {NAV_BG};
    border-top: 1px solid {BORDER};
}}
QProgressBar {{
    border: none;
    background: {SURFACE_2};
    border-radius: 6px;
    height: 10px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 6px;
}}
QCheckBox {{
    spacing: 8px;
    color: {TEXT};
}}
QCheckBox::indicator, QCheckBox#themeToggle::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    background: {INPUT};
    border-radius: 4px;
}}
QCheckBox::indicator:checked, QCheckBox#themeToggle::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:focus {{
    border-color: {ACCENT};
}}
QSlider::groove:horizontal {{
    background: {SURFACE_2};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_HOVER};
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}
QScrollBar:vertical {{
    background: {NAV_BG};
    width: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}
QScrollBar:horizontal {{
    background: {NAV_BG};
    height: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    min-width: 24px;
    border-radius: 5px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QMenu {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: {BTN_TEXT};
}}
QMessageBox QLabel {{
    color: {TEXT};
}}
QDialogButtonBox QPushButton {{
    min-width: 88px;
    border-radius: 9px;
}}
QDialogButtonBox QPushButton:default {{
    background: {ACCENT};
    color: {BTN_TEXT};
    border: none;
    font-weight: 600;
}}
QCalendarWidget QWidget {{
    background: {SURFACE};
    color: {TEXT};
}}
QCalendarWidget QAbstractItemView:enabled {{
    background: {SURFACE};
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {BTN_TEXT};
}}
QCalendarWidget QToolButton {{
    color: {TEXT};
    background: {SURFACE_2};
    border-radius: 8px;
}}
QCalendarWidget QToolButton:hover {{
    background: {ACCENT};
    color: {BTN_TEXT};
}}
QHeaderView {{
    background: {SURFACE_2};
}}
QToolTip {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 8px;
    border-radius: 8px;
}}
"""


def apply_theme(app: QApplication, name: str = "dark") -> None:
    global CURRENT
    CURRENT = "dark" if name != "light" else "light"
    palette_map = DARK if CURRENT == "dark" else LIGHT
    _apply_globals(palette_map)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_2))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE_2))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BTN_TEXT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE_2))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet())
