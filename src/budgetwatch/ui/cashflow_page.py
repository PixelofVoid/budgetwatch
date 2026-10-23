from __future__ import annotations

from datetime import date

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.services.budget import BudgetService
from budgetwatch.services.planning import FIXED_CATEGORIES, FLEXIBLE_CATEGORIES, category_actual, occurrences_index
from budgetwatch.ui.formatters import format_money
from budgetwatch.ui.layout import money_item, page_margins, style_table, text_item
from budgetwatch.ui.theme import ACCENT, BG, BORDER, GREEN, MUTED, RED, SURFACE, TEXT
from budgetwatch.ui.widgets import PageHeader


class CashFlowPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self._six = True
        layout = QVBoxLayout(self)
        page_margins(layout)
        layout.addWidget(
            PageHeader("Cash flow", "Income vs expenses from local paychecks, bills, and spend.")
        )
        nav = QHBoxLayout()
        month_btn = QPushButton("This month")
        six_btn = QPushButton("6 months")
        month_btn.setObjectName("rangeButton")
        six_btn.setObjectName("rangeButton")
        month_btn.setCheckable(True)
        six_btn.setCheckable(True)
        six_btn.setChecked(True)
        month_btn.clicked.connect(lambda: self._set_range(False))
        six_btn.clicked.connect(lambda: self._set_range(True))
        nav.addWidget(month_btn)
        nav.addWidget(six_btn)
        nav.addStretch(1)
        layout.addLayout(nav)

        self.chart = QChart()
        self.income_set = QBarSet("Income")
        self.expense_set = QBarSet("Expenses")
        self.income_set.setColor(QColor(GREEN))
        self.expense_set.setColor(QColor(RED))
        for _ in range(6):
            self.income_set.append(0.0)
            self.expense_set.append(0.0)
        self.series = QBarSeries()
        self.series.append(self.income_set)
        self.series.append(self.expense_set)
        self.chart.addSeries(self.series)
        self.axis_x = QBarCategoryAxis()
        self.axis_x.append(["", "", "", "", "", ""])
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.series.attachAxis(self.axis_x)
        self.axis_y = QValueAxis()
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.axis_y)
        self.view = QChartView(self.chart)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setMinimumHeight(240)
        layout.addWidget(self.view)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Category", "This month"])
        style_table(self.table)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def _set_range(self, six: bool) -> None:
        self._six = six
        self.refresh()

    def refresh(self) -> None:
        from budgetwatch.ui import theme as t

        self.chart.setBackgroundBrush(QBrush(QColor(t.SURFACE)))
        self.chart.setTitleBrush(QBrush(QColor(t.TEXT)))
        self.income_set.setColor(QColor(t.GREEN))
        self.expense_set.setColor(QColor(t.RED))
        self.axis_x.setLabelsColor(QColor(t.MUTED))
        self.axis_y.setLabelsColor(QColor(t.MUTED))
        self.axis_y.setGridLineColor(QColor(t.BORDER))

        as_of = date.today()
        symbol = self.service.get_settings().currency_symbol
        months = self.service.six_months(as_of=as_of)
        if not self._six:
            months = months[:1]
        cats = []
        peak = 1.0
        for i in range(6):
            if i < len(months):
                m = months[i]
                expenses = self.service.month_expenses(
                    m.month_start.year, m.month_start.month, as_of=as_of
                )
                self.income_set.replace(i, float(m.income))
                self.expense_set.replace(i, float(expenses))
                cats.append(m.label)
                peak = max(peak, float(m.income), float(expenses))
            else:
                self.income_set.replace(i, 0.0)
                self.expense_set.replace(i, 0.0)
                cats.append("")
        self.axis_x.clear()
        self.axis_x.append(cats)
        self.axis_y.setRange(0, peak * 1.15)

        occ = self.service.db.occurrences.list_all()
        bills = self.service.list_bills()
        txs = self.service.db.transactions.list_in_month(as_of.year, as_of.month)
        idx = occurrences_index(occ)
        rows = []
        for category in list(FIXED_CATEGORIES) + list(FLEXIBLE_CATEGORIES):
            amt = category_actual(category, as_of.year, as_of.month, bills, idx, txs)
            if amt:
                rows.append((category.value, amt))
        rows.sort(key=lambda r: r[1], reverse=True)
        self.table.setRowCount(len(rows))
        for i, (name, amt) in enumerate(rows):
            self.table.setItem(i, 0, text_item(name))
            self.table.setItem(i, 1, money_item(format_money(amt, symbol)))

    def new_item(self) -> None:
        return

    def save_focused(self) -> None:
        return

    def focus_default(self) -> None:
        self.setFocus()
