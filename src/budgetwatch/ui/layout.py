from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

PAGE_MARGIN = 24
SECTION_GAP = 16
CONTROL_PAD = 8
CONTENT_MAX = 1280
FORM_MAX = 440
NAV_WIDTH = 196
DRAWER_WIDTH = 380
CARD_MIN_H = 88
CARD_MAX_H = 118
CHART_H = 280
ROW_H = 28


def form_policy(widget: QWidget, max_width: int = FORM_MAX) -> QWidget:
    widget.setMaximumWidth(max_width)
    widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    return widget


def expanding_policy(widget: QWidget) -> QWidget:
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return widget


def helper_label(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("helperText")
    label.setWordWrap(True)
    return label


def field_with_help(widget: QWidget, help_text: str) -> QWidget:
    wrap = QWidget()
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(widget)
    layout.addWidget(helper_label(help_text))
    return wrap


def style_table(table: QTableWidget) -> QTableWidget:
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(ROW_H)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return table


def money_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    item.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    font = item.font()
    font.setStyleHint(QFont.StyleHint.Monospace)
    item.setFont(font)
    return item


def text_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return item


class ConstrainedColumn(QWidget):
    """Left-aligned column that will not grow past CONTENT_MAX."""

    def __init__(self, max_width: int = CONTENT_MAX, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMaximumWidth(max_width)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(SECTION_GAP)


class CardStrip(QWidget):
    """One row when wide; wraps when the window is narrow."""

    def __init__(self, cards: list[QWidget], parent: QWidget | None = None):
        super().__init__(parent)
        self._cards = cards
        self._columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        self.setMaximumWidth(CONTENT_MAX)
        for card in cards:
            card.setMinimumHeight(CARD_MIN_H)
            card.setMaximumHeight(CARD_MAX_H)
            card.setMinimumWidth(150)
            card.setMaximumWidth(220)
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._reflow(5)

    def resizeEvent(self, event) -> None:  # noqa: N802
        width = max(1, self.width())
        if width >= 980:
            cols = 5
        elif width >= 700:
            cols = 3
        else:
            cols = 2
        if cols != self._columns:
            self._reflow(cols)
        super().resizeEvent(event)

    def _reflow(self, cols: int) -> None:
        self._columns = cols
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(self)
        for index, card in enumerate(self._cards):
            self._grid.addWidget(card, index // cols, index % cols)


class HLine(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setObjectName("hairline")
        self.setFixedHeight(1)


def page_margins(layout: QVBoxLayout | QHBoxLayout) -> None:
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(SECTION_GAP)
