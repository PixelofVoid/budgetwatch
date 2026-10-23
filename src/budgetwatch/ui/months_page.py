from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.models.entities import MonthRollup
from budgetwatch.services.budget import BudgetService
from budgetwatch.ui.dialogs import BillActualDialog, PaycheckDialog
from budgetwatch.ui.formatters import format_money
from budgetwatch.ui.layout import money_item, page_margins, style_table, text_item
from budgetwatch.ui.theme import GREEN, MUTED, RED
from budgetwatch.ui.widgets import leftover_stylesheet


class MonthsPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self._months: list[MonthRollup] = []
        layout = QVBoxLayout(self)
        page_margins(layout)

        hint = QLabel(
            "Calendar-month math only: paydays that fall in the month "
            "(actual if logged, else projected) minus bill due dates in that month. "
            "This is not the typical-month leftover."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [
                "Month",
                "Income",
                "Bills",
                "Leftover",
                "After savings",
                "Notes",
            ]
        )
        style_table(self.table)
        self.table.itemSelectionChanged.connect(self._show_detail)
        splitter.addWidget(self.table)

        detail = QGroupBox("Month detail")
        d_layout = QVBoxLayout(detail)
        self.detail_label = QLabel("Select a month.")
        self.detail_label.setWordWrap(True)
        d_layout.addWidget(self.detail_label)
        inner = QSplitter(Qt.Orientation.Horizontal)
        self.pay_table = QTableWidget(0, 5)
        self.pay_table.setHorizontalHeaderLabels(
            ["Date", "Source", "Amount", "Status", "Linked"]
        )
        self.bill_table = QTableWidget(0, 5)
        self.bill_table.setHorizontalHeaderLabels(
            ["Due", "Bill", "Amount", "Actual", "Paid"]
        )
        for table in (self.pay_table, self.bill_table):
            style_table(table)
        inner.addWidget(self.pay_table)
        inner.addWidget(self.bill_table)
        d_layout.addWidget(inner)
        buttons = QHBoxLayout()
        log_pay = QPushButton("Log paycheck for selected payday")
        log_pay.clicked.connect(self._log_paycheck)
        log_bill = QPushButton("Enter bill actual")
        log_bill.clicked.connect(self._log_bill)
        buttons.addWidget(log_pay)
        buttons.addWidget(log_bill)
        buttons.addStretch(1)
        d_layout.addLayout(buttons)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self.pay_table.doubleClicked.connect(self._log_paycheck)
        self.bill_table.doubleClicked.connect(self._log_bill)

    def refresh(self) -> None:
        symbol = self.service.get_settings().currency_symbol
        self._months = self.service.six_months()
        self.table.setRowCount(len(self._months))
        for row, month in enumerate(self._months):
            note = ""
            if month.income_is_partial:
                note = "Estimated — " + ", ".join(
                    f"Not enough data for {name}" for name in month.unknown_sources
                )
            self.table.setItem(row, 0, text_item(month.label))
            self.table.setItem(row, 1, money_item(format_money(month.income, symbol)))
            self.table.setItem(row, 2, money_item(format_money(month.bills, symbol)))
            leftover_item = money_item(format_money(month.leftover, symbol))
            leftover_item.setForeground(QColor(GREEN if month.leftover >= 0 else RED))
            self.table.setItem(row, 3, leftover_item)
            after_item = money_item(format_money(month.leftover_after_savings, symbol))
            after_item.setForeground(
                QColor(GREEN if month.leftover_after_savings >= 0 else RED)
            )
            self.table.setItem(row, 4, after_item)
            self.table.setItem(row, 5, text_item(note))
        if self._months:
            self.table.selectRow(0)

    def _current_month(self) -> MonthRollup | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._months):
            return None
        return self._months[row]

    def _show_detail(self) -> None:
        month = self._current_month()
        if month is None:
            return
        symbol = self.service.get_settings().currency_symbol
        extra = ""
        if month.income_is_partial:
            extra = (
                " Projected income is incomplete: "
                + ", ".join(f"Not enough data for {n}" for n in month.unknown_sources)
                + "."
            )
        self.detail_label.setText(
            f"{month.label} calendar leftover {format_money(month.leftover, symbol)} "
            f"(after savings {format_money(month.leftover_after_savings, symbol)})."
            f"{extra}"
        )
        self.detail_label.setStyleSheet(leftover_stylesheet(month.leftover))
        self.pay_table.setRowCount(len(month.pay_items))
        for i, item in enumerate(month.pay_items):
            status = "Unknown" if item.unknown else ("Projected" if item.projected else "Logged")
            amount = "—" if item.unknown else format_money(item.amount, symbol)
            values = [
                item.date.isoformat(),
                item.source_name,
                amount,
                status,
                "Yes" if item.linked else "No",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, i)
                self.pay_table.setItem(i, col, cell)
        self.bill_table.setRowCount(len(month.bill_items))
        for i, item in enumerate(month.bill_items):
            values = [
                item.due_date.isoformat(),
                item.bill_name,
                format_money(item.amount, symbol),
                format_money(item.actual, symbol) if item.actual is not None else "—",
                "Yes" if item.paid else "No",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, i)
                self.bill_table.setItem(i, col, cell)

    def _log_paycheck(self) -> None:
        month = self._current_month()
        if month is None:
            return
        row = self.pay_table.currentRow()
        if row < 0 or row >= len(month.pay_items):
            PaycheckDialog(self.service, self).exec()
            return
        item = month.pay_items[row]
        paycheck = (
            self.service.get_paycheck(item.paycheck_id) if item.paycheck_id else None
        )
        PaycheckDialog(
            self.service,
            self,
            paycheck=paycheck,
            source_id=item.source_id,
            preset_date=item.date,
            occurrence_date=item.date,
        ).exec()

    def _log_bill(self) -> None:
        month = self._current_month()
        if month is None:
            return
        row = self.bill_table.currentRow()
        if row < 0 or row >= len(month.bill_items):
            return
        item = month.bill_items[row]
        BillActualDialog(
            self.service,
            item.bill_id,
            item.due_date,
            self,
            amount=item.actual,
            paid=item.paid,
            notes=item.notes,
        ).exec()

    def new_item(self) -> None:
        self._log_paycheck()

    def save_focused(self) -> None:
        return

    def focus_default(self) -> None:
        self.table.setFocus()
