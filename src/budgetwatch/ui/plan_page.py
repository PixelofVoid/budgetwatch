from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.services.budget import BudgetService, ValidationError
from budgetwatch.ui.formatters import format_money, parse_money
from budgetwatch.ui.layout import money_item, page_margins, style_table, text_item
from budgetwatch.ui import theme as t
from budgetwatch.ui.widgets import DashCard, PageHeader, show_error


class PlanPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self._year = date.today().year
        self._month = date.today().month
        self._loading = False
        layout = QVBoxLayout(self)
        page_margins(layout)
        layout.addWidget(
            PageHeader(
                "Plan",
                "Planned amounts default from your bills. Editing here does not change stored estimates.",
            )
        )
        nav = QHBoxLayout()
        prev = QPushButton("‹ Prev")
        nxt = QPushButton("Next ›")
        prev.clicked.connect(self._prev)
        nxt.clicked.connect(self._next)
        self.month_label = QLabel()
        self.month_label.setObjectName("sectionTitle")
        nav.addWidget(prev)
        nav.addWidget(self.month_label)
        nav.addWidget(nxt)
        nav.addStretch(1)
        layout.addLayout(nav)

        self.flex_card = DashCard("Flexible spend", expand=False)
        self.flex_value = QLabel("—")
        self.flex_value.setObjectName("cardValue")
        self.flex_hint = QLabel()
        self.flex_hint.setObjectName("cardHint")
        self.flex_card.body.addWidget(self.flex_value)
        self.flex_card.body.addWidget(self.flex_hint)
        layout.addWidget(self.flex_card)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Group", "Category", "Planned", "Actual", "Remaining"]
        )
        style_table(self.table)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._planned_edited)
        layout.addWidget(self.table, 1)
        self._keys: list[str] = []

    def _shift(self, delta: int) -> None:
        month = self._month - 1 + delta
        year = self._year + month // 12
        month = month % 12 + 1
        self._year, self._month = year, month
        self.refresh()

    def _prev(self) -> None:
        self._shift(-1)

    def _next(self) -> None:
        self._shift(1)

    def refresh(self) -> None:
        self._loading = True
        self.month_label.setText(date(self._year, self._month, 1).strftime("%B %Y"))
        plan = self.service.plan_for_month(self._year, self._month)
        symbol = self.service.get_settings().currency_symbol
        self.flex_value.setText(
            f"{format_money(plan.flex_actual, symbol)} of {format_money(plan.flex_planned, symbol)}"
        )
        rem = plan.flex_remaining
        self.flex_hint.setText(f"Remaining {format_money(rem, symbol)}")
        self.flex_hint.setStyleSheet(f"color: {t.GREEN if rem >= 0 else t.RED};")
        self.table.blockSignals(True)
        self.table.setRowCount(len(plan.rows))
        self._keys = []
        group_names = {
            "income": "Income",
            "fixed": "Fixed",
            "flexible": "Flexible",
            "non_monthly": "Non-monthly",
        }
        for row, item in enumerate(plan.rows):
            self._keys.append(item.key)
            self.table.setItem(row, 0, text_item(group_names.get(item.group, item.group)))
            self.table.setItem(row, 1, text_item(item.label))
            planned = money_item(f"{item.planned:.2f}")
            planned.setFlags(planned.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, planned)
            self.table.setItem(row, 3, money_item(format_money(item.actual, symbol)))
            rem_item = money_item(format_money(item.remaining, symbol))
            rem_item.setForeground(QColor(t.GREEN if item.remaining >= 0 else t.RED))
            self.table.setItem(row, 4, rem_item)
        self.table.blockSignals(False)
        self._loading = False

    def _planned_edited(self, item) -> None:
        if self._loading or item.column() != 2:
            return
        row = item.row()
        if row >= len(self._keys):
            return
        amount = parse_money(item.text())
        if amount is None:
            show_error(self, "Enter an amount greater than 0")
            self.refresh()
            return
        try:
            self.service.set_plan_amount(self._year, self._month, self._keys[row], amount)
        except ValidationError as exc:
            show_error(self, str(exc))
            self.refresh()

    def new_item(self) -> None:
        return

    def save_focused(self) -> None:
        return

    def focus_default(self) -> None:
        self.table.setFocus()
