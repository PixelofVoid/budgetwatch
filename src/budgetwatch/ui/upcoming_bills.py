from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.models.entities import UpcomingBillItem
from budgetwatch.services.bills import BILL_RANGE_14D, BILL_RANGE_6W, BILL_RANGE_MONTH
from budgetwatch.services.budget import BudgetService, ValidationError
from budgetwatch.ui.formatters import format_money, format_short_date
from budgetwatch.ui.layout import DRAWER_WIDTH, helper_label
from budgetwatch.ui.widgets import MoneyEdit, show_error


class BillRow(QFrame):
    clicked = Signal(object)

    def __init__(self, item: UpcomingBillItem, symbol: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        if item.group == "overdue":
            self.setObjectName("billRowOverdue")
        elif item.group == "this_week":
            self.setObjectName("billRowThisWeek")
        else:
            self.setObjectName("billRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        top = QHBoxLayout()
        from budgetwatch.ui import theme as t

        due = QLabel(format_short_date(item.due_date))
        due.setStyleSheet(f"color: {t.MUTED};")
        name = QLabel(item.name)
        name.setWordWrap(True)
        top.addWidget(due)
        top.addWidget(name, 1)
        layout.addLayout(top)
        bottom = QHBoxLayout()
        amount = QLabel(format_money(item.actual or item.amount, symbol))
        paid = "Paid" if item.paid else "Unpaid"
        kind = "Variable" if item.variable else "Fixed"
        meta = QLabel(f"{paid} · {kind}")
        meta.setStyleSheet(f"color: {t.MUTED}; font-size: 11px;")
        bottom.addWidget(amount)
        bottom.addStretch(1)
        bottom.addWidget(meta)
        layout.addLayout(bottom)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self.item)
        super().mousePressEvent(event)


class UpcomingBillsPanel(QFrame):
    """Right-side Upcoming Bills drawer. Live-updates from dataChanged."""

    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self._range = BILL_RANGE_14D
        self._selected: UpcomingBillItem | None = None
        self.setObjectName("upcomingDrawer")
        self.setMinimumWidth(360)
        self.setMaximumWidth(400)
        self.setFixedWidth(DRAWER_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("Upcoming Bills")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        ranges = QHBoxLayout()
        ranges.setSpacing(6)
        self.range_group = QButtonGroup(self)
        self.range_group.setExclusive(True)
        for key, label in (
            (BILL_RANGE_14D, "Next 14 days"),
            (BILL_RANGE_MONTH, "This month"),
            (BILL_RANGE_6W, "Next 6 weeks"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("rangeButton")
            btn.setCheckable(True)
            btn.setChecked(key == BILL_RANGE_14D)
            btn.clicked.connect(lambda _=False, k=key: self._set_range(k))
            self.range_group.addButton(btn)
            ranges.addWidget(btn)
        layout.addLayout(ranges)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.scroll.setWidget(self.list_host)
        layout.addWidget(self.scroll, 1)

        self.empty = QLabel("No bills due in this range")
        self.empty.setObjectName("helperText")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        layout.addWidget(self.empty)

        editor = QFrame()
        editor.setObjectName("metricCard")
        form = QVBoxLayout(editor)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        self.edit_title = QLabel("Select a bill")
        self.edit_title.setWordWrap(True)
        self.actual = MoneyEdit()
        self.actual.setPlaceholderText("Actual amount")
        self.paid = QCheckBox("Paid")
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self._save_selected)
        form.addWidget(self.edit_title)
        form.addWidget(helper_label("Variable bills: enter the real amount when it arrives."))
        form.addWidget(self.actual)
        form.addWidget(self.paid)
        form.addWidget(save)
        layout.addWidget(editor)
        self._editor = editor
        self._loading = False

    def _set_range(self, key: str) -> None:
        self._range = key
        self.refresh()

    def refresh(self) -> None:
        self._loading = True
        symbol = self.service.get_settings().currency_symbol
        items = self.service.upcoming_bills(self._range)
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        if not items:
            self.empty.show()
        else:
            self.empty.hide()
            groups = [
                ("overdue", "Overdue", "groupOverdue"),
                ("this_week", "Due this week", "groupWeek"),
                ("later", "Later", "groupLater"),
            ]
            for key, title, style in groups:
                bucket = [item for item in items if item.group == key]
                if not bucket:
                    continue
                header = QLabel(title)
                header.setObjectName(style)
                self.list_layout.addWidget(header)
                for item in bucket:
                    row = BillRow(item, symbol)
                    row.clicked.connect(self._select)
                    self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)
        if self._selected is not None:
            match = next(
                (
                    item
                    for item in items
                    if item.bill_id == self._selected.bill_id
                    and item.due_date == self._selected.due_date
                ),
                None,
            )
            if match:
                self._fill_editor(match)
        self._loading = False

    def _select(self, item: UpcomingBillItem) -> None:
        self._fill_editor(item)
        if not item.variable and not item.paid:
            self.paid.setFocus()

    def _fill_editor(self, item: UpcomingBillItem) -> None:
        self._selected = item
        self.edit_title.setText(
            f"{item.name} · due {item.due_date.isoformat()}"
        )
        self.actual.setEnabled(item.variable)
        self.actual.set_amount(item.actual)
        self.paid.setChecked(item.paid)
        if item.variable:
            self.actual.setFocus()
            self.actual.selectAll()

    def _save_selected(self) -> None:
        item = self._selected
        if item is None:
            return
        amount = self.actual.amount() if item.variable else item.actual
        try:
            self.service.set_bill_actual(
                item.bill_id,
                item.due_date,
                amount_actual=amount,
                paid=self.paid.isChecked(),
            )
        except ValidationError as exc:
            show_error(self, str(exc))
