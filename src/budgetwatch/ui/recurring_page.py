from __future__ import annotations

from calendar import monthrange
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.models.entities import Bill
from budgetwatch.services.budget import BudgetService
from budgetwatch.services.bills import merge_occurrences, working_amount
from budgetwatch.services.rollup import occurrences_index
from budgetwatch.ui.dialogs import BillDialog
from budgetwatch.ui.formatters import format_money, format_short_date
from budgetwatch.ui.layout import money_item, page_margins, style_table, text_item
from budgetwatch.ui.widgets import PageHeader, confirm_delete, show_error


class RecurringPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self._year = date.today().year
        self._month = date.today().month
        layout = QVBoxLayout(self)
        page_margins(layout)
        layout.addWidget(
            PageHeader("Recurring", "Bills you already entered — edit updates the same row.")
        )
        top = QHBoxLayout()
        self.mode = QButtonGroup(self)
        self.mode.setExclusive(True)
        list_btn = QPushButton("List")
        cal_btn = QPushButton("Calendar")
        for btn in (list_btn, cal_btn):
            btn.setObjectName("rangeButton")
            btn.setCheckable(True)
            self.mode.addButton(btn)
        list_btn.setChecked(True)
        list_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        cal_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        add = QPushButton("Add bill")
        add.setObjectName("primary")
        add.clicked.connect(self._add)
        edit = QPushButton("Edit")
        edit.clicked.connect(self._edit)
        top.addWidget(list_btn)
        top.addWidget(cal_btn)
        top.addStretch(1)
        top.addWidget(add)
        top.addWidget(edit)
        layout.addLayout(top)

        self.stack = QStackedWidget()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Due", "Name", "Amount", "Category", "Frequency", "Paid"]
        )
        style_table(self.table)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._edit)
        self.stack.addWidget(self.table)

        cal_wrap = QWidget()
        cal_l = QVBoxLayout(cal_wrap)
        nav = QHBoxLayout()
        prev = QPushButton("‹")
        nxt = QPushButton("›")
        prev.clicked.connect(self._prev_month)
        nxt.clicked.connect(self._next_month)
        self.cal_label = QLabel()
        nav.addWidget(prev)
        nav.addWidget(self.cal_label)
        nav.addWidget(nxt)
        nav.addStretch(1)
        cal_l.addLayout(nav)
        self.cal_grid = QGridLayout()
        cal_l.addLayout(self.cal_grid, 1)
        self.stack.addWidget(cal_wrap)
        layout.addWidget(self.stack, 1)
        self._rows: list[tuple[int, date]] = []

    def refresh(self) -> None:
        symbol = self.service.get_settings().currency_symbol
        as_of = date.today()
        bills = [b for b in self.service.list_bills() if b.active]
        occ_index = occurrences_index(self.service.db.occurrences.list_all())
        items = []
        start = date(self._year, self._month, 1)
        end = date(self._year, self._month, monthrange(self._year, self._month)[1])
        for bill in bills:
            if bill.id is None:
                continue
            working = working_amount(bill, occ_index.get(bill.id, []))
            for occ in merge_occurrences(bill, start, end, occ_index.get(bill.id, [])):
                items.append((occ.due_date, bill, occ, working))
        items.sort(key=lambda row: (row[0], row[1].name))
        self._rows = [(bill.id, occ.due_date) for _, bill, occ, _ in items if bill.id]
        self.table.setRowCount(len(items))
        for row, (due, bill, occ, working) in enumerate(items):
            amt = occ.amount_actual if occ.amount_actual is not None else working
            self.table.setItem(row, 0, text_item(due.isoformat()))
            self.table.setItem(row, 1, text_item(bill.name))
            self.table.setItem(row, 2, money_item(format_money(amt, symbol)))
            self.table.setItem(row, 3, text_item(bill.category.value))
            self.table.setItem(row, 4, text_item(bill.frequency.value))
            self.table.setItem(row, 5, text_item("Paid" if occ.paid else "Unpaid"))
            for col in range(6):
                self.table.item(row, col).setData(Qt.ItemDataRole.UserRole, bill.id)
        self._fill_calendar(items, symbol)
        _ = as_of

    def _fill_calendar(self, items, symbol: str) -> None:
        while self.cal_grid.count():
            item = self.cal_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cal_label.setText(date(self._year, self._month, 1).strftime("%B %Y"))
        for i, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            lab = QLabel(name)
            lab.setObjectName("cardTitle")
            self.cal_grid.addWidget(lab, 0, i)
        first = date(self._year, self._month, 1)
        offset = first.weekday()
        days = monthrange(self._year, self._month)[1]
        by_day: dict[int, list[str]] = {}
        for due, bill, occ, working in items:
            amt = occ.amount_actual if occ.amount_actual is not None else working
            by_day.setdefault(due.day, []).append(
                f"{bill.name} {format_money(amt, symbol)}"
            )
        for day in range(1, days + 1):
            cell = QLabel()
            cell.setWordWrap(True)
            cell.setAlignment(Qt.AlignmentFlag.AlignTop)
            text = str(day)
            extra = by_day.get(day, [])
            if extra:
                text += "\n" + "\n".join(extra[:3])
            cell.setText(text)
            cell.setObjectName("dashCard")
            r = (offset + day - 1) // 7 + 1
            c = (offset + day - 1) % 7
            self.cal_grid.addWidget(cell, r, c)

    def _prev_month(self) -> None:
        m = self._month - 2
        self._year += m // 12
        self._month = m % 12 + 1
        self.refresh()

    def _next_month(self) -> None:
        m = self._month
        self._year += m // 12
        self._month = m % 12 + 1
        self.refresh()

    def _selected_bill(self) -> Bill | None:
        items = self.table.selectedItems()
        if not items:
            return None
        bill_id = items[0].data(Qt.ItemDataRole.UserRole)
        if bill_id is None:
            return None
        return self.service.get_bill(int(bill_id))

    def _add(self) -> None:
        BillDialog(self.service, self).exec()

    def _edit(self) -> None:
        bill = self._selected_bill()
        if bill is None:
            show_error(self, "Select a bill to edit.")
            return
        BillDialog(self.service, self, bill=bill).exec()

    def new_item(self) -> None:
        self._add()

    def save_focused(self) -> None:
        return

    def focus_default(self) -> None:
        self.table.setFocus()
