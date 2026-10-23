from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    EstimateMode,
)
from budgetwatch.services.budget import BudgetService, ValidationError
from budgetwatch.ui.dialogs import BILL_FREQS, CATEGORIES, BillDialog
from budgetwatch.ui.formatters import format_money, parse_money
from budgetwatch.ui.layout import (
    FORM_MAX,
    field_with_help,
    form_policy,
    money_item,
    page_margins,
    style_table,
    text_item,
)
from budgetwatch.ui.theme import MUTED
from budgetwatch.ui.widgets import (
    MoneyEdit,
    WarningBanner,
    confirm_delete,
    date_from_edit,
    make_date_edit,
    show_error,
)


class BillsPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self._selected_id: int | None = None
        self._loading = False
        self._occ_actual_cache: dict[int, str] = {}

        layout = QVBoxLayout(self)
        page_margins(layout)
        self.banner = WarningBanner()
        layout.addWidget(self.banner)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Bill name", "Category", "How often?", "Working amount", "Monthly eq.", "Active"]
        )
        style_table(self.table)
        self.table.itemSelectionChanged.connect(self._on_selected)
        top.addWidget(self.table, 1)
        top.addWidget(self._build_form(), 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top, 3)

        layout.addWidget(self._build_occurrences(), 2)

        buttons = QHBoxLayout()
        new_btn = QPushButton("New bill")
        new_btn.clicked.connect(self._blank_form)
        electric = QPushButton("Add electric bill")
        electric.clicked.connect(self._add_electric)
        save = QPushButton("Save bill")
        save.setObjectName("primary")
        save.clicked.connect(self.save_bill)
        delete = QPushButton("Delete bill")
        delete.setObjectName("danger")
        delete.clicked.connect(self._delete_bill)
        buttons.addWidget(new_btn)
        buttons.addWidget(electric)
        buttons.addWidget(save)
        buttons.addStretch(1)
        buttons.addWidget(delete)
        layout.addLayout(buttons)

    def _build_form(self) -> QWidget:
        box = QGroupBox("Bill")
        form_policy(box, FORM_MAX)
        form = QFormLayout(box)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Electric")
        self.estimate = MoneyEdit()
        self.frequency = QComboBox()
        self.frequency.addItems(BILL_FREQS)
        self.frequency.setCurrentText(BillFrequency.MONTHLY.value)
        self.due_day = QLineEdit()
        self.due_day.setPlaceholderText("1–28")
        self.has_next = QCheckBox("Next due date")
        self.next_due = make_date_edit(date.today())
        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        self.category.currentTextChanged.connect(self._on_category_changed)
        self.variable = QCheckBox("Amount changes each time")
        self.estimate_mode = QComboBox()
        self.estimate_mode.addItem("Manual estimate", EstimateMode.MANUAL.value)
        self.estimate_mode.addItem(
            "Estimate using recent actuals", EstimateMode.AVERAGE_ACTUALS.value
        )
        self.avg_n = QLineEdit("6")
        self.active = QCheckBox("Active")
        self.active.setChecked(True)
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(54)
        self.variable_info = QLabel("")
        self.variable_info.setWordWrap(True)
        self.variable_info.setStyleSheet(f"color: {MUTED};")
        self.use_avg = QPushButton("Set estimate = recent average")
        self.use_avg.clicked.connect(self._set_estimate_from_average)
        form.addRow("Bill name", self.name)
        form.addRow("Expected amount", self.estimate)
        form.addRow("How often?", self.frequency)
        form.addRow("Due on day of month", self.due_day)
        form.addRow(self.has_next)
        form.addRow("Next due date", self.next_due)
        form.addRow("Category", self.category)
        form.addRow(self.variable)
        form.addRow("Estimate using recent actuals", self.estimate_mode)
        form.addRow("Average last N actuals", self.avg_n)
        form.addRow(self.active)
        form.addRow("Notes (optional)", self.notes)
        form.addRow(
            field_with_help(
                self.variable_info,
                "Use an estimate until the real bill arrives, then enter the actual on that month",
            )
        )
        form.addRow(self.use_avg)
        self.variable.toggled.connect(self._toggle_variable)
        self.has_next.toggled.connect(self.next_due.setEnabled)
        self._toggle_variable(False)
        self.next_due.setEnabled(False)
        self._form = box
        return box

    def _build_occurrences(self) -> QWidget:
        box = QGroupBox("Upcoming due dates — enter actuals, then leave the field to save")
        layout = QVBoxLayout(box)
        self.occ_table = QTableWidget(0, 5)
        self.occ_table.setHorizontalHeaderLabels(
            ["Due", "Working / expected", "Actual", "Paid", "Notes"]
        )
        style_table(self.occ_table)
        self.occ_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.occ_table.itemChanged.connect(self._occurrence_changed)
        layout.addWidget(self.occ_table)
        self._occ_box = box
        return box

    def _toggle_variable(self, on: bool) -> None:
        self.estimate_mode.setEnabled(on)
        self.avg_n.setEnabled(on)
        self.use_avg.setEnabled(on)

    def _on_category_changed(self, value: str) -> None:
        if self._loading or self._selected_id is not None:
            return
        if value == BillCategory.GROCERIES.value:
            self.name.setPlaceholderText("Groceries")
            self.frequency.setCurrentText(BillFrequency.WEEKLY.value)
            self.variable.setChecked(True)
            self.estimate_mode.setCurrentIndex(1)
            self.has_next.setChecked(True)
            self.next_due.setEnabled(True)
            self._toggle_variable(True)
            return
        self.name.setPlaceholderText("Electric")
        self.frequency.setCurrentText(BillFrequency.MONTHLY.value)
        self.variable.setChecked(False)
        self.estimate_mode.setCurrentIndex(0)
        self._toggle_variable(False)

    def refresh(self) -> None:
        self._loading = True
        symbol = self.service.get_settings().currency_symbol
        bills = self.service.list_bills()
        keep = 0
        self.table.setRowCount(len(bills))
        for row, bill in enumerate(bills):
            working = self.service.bill_working_amount(bill)
            monthly = self.service.bill_monthly_equivalent(bill)
            self.table.setItem(row, 0, text_item(bill.name))
            self.table.setItem(row, 1, text_item(bill.category.value))
            self.table.setItem(row, 2, text_item(bill.frequency.value))
            self.table.setItem(row, 3, money_item(format_money(working, symbol)))
            self.table.setItem(row, 4, money_item(format_money(monthly, symbol)))
            self.table.setItem(row, 5, text_item("Yes" if bill.active else "No"))
            for col in range(6):
                self.table.item(row, col).setData(Qt.ItemDataRole.UserRole, bill.id)
            if bill.id == self._selected_id:
                keep = row
        if bills:
            self.table.selectRow(keep)
        else:
            self._blank_form()
            self.occ_table.setRowCount(0)
        overview = self.service.overview()
        self.banner.set_messages(
            [w for w in overview.warnings if "bills" in w.lower() or "electric" in w.lower()]
            or (["Add recurring bills to see monthly costs"] if not bills else [])
        )
        self._loading = False
        if bills:
            self._on_selected()

    def _current_bill(self) -> Bill | None:
        if self._selected_id is None:
            return None
        return self.service.get_bill(self._selected_id)

    def _on_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        bill_id = items[0].data(Qt.ItemDataRole.UserRole)
        if bill_id is None:
            return
        bill = self.service.get_bill(int(bill_id))
        if bill is None:
            return
        self._selected_id = bill.id
        self._loading = True
        self.name.setText(bill.name)
        self.estimate.set_amount(bill.amount_estimate)
        self.frequency.setCurrentText(bill.frequency.value)
        self.due_day.setText(str(bill.due_day) if bill.due_day else "")
        self.has_next.setChecked(bill.next_due_date is not None)
        if bill.next_due_date:
            self.next_due.setDate(bill.next_due_date)
        self.next_due.setEnabled(bill.next_due_date is not None)
        self.category.setCurrentText(bill.category.value)
        self.variable.setChecked(bill.variable)
        self.estimate_mode.setCurrentIndex(
            1 if bill.estimate_mode == EstimateMode.AVERAGE_ACTUALS else 0
        )
        self.avg_n.setText(str(bill.average_actuals_n))
        self.active.setChecked(bill.active)
        self.notes.setPlainText(bill.notes)
        self._toggle_variable(bill.variable)
        self._refresh_variable_info(bill)
        self._fill_occurrences(bill)
        self._loading = False

    def _refresh_variable_info(self, bill: Bill) -> None:
        symbol = self.service.get_settings().currency_symbol
        if not bill.variable:
            self.variable_info.setText("")
            return
        average = self.service.bill_recent_average(bill)
        working = self.service.bill_working_amount(bill)
        avg_text = format_money(average, symbol) if average is not None else "—"
        self.variable_info.setText(
            f"Recent actual average: {avg_text}  ·  "
            f"Current estimate: {format_money(bill.amount_estimate, symbol)}  ·  "
            f"Working amount: {format_money(working, symbol)}"
        )

    def _fill_occurrences(self, bill: Bill) -> None:
        if bill.id is None:
            return
        symbol = self.service.get_settings().currency_symbol
        working = self.service.bill_working_amount(bill)
        rows = self.service.merged_occurrences(bill.id)
        self.occ_table.blockSignals(True)
        self.occ_table.setRowCount(len(rows))
        self._occ_actual_cache.clear()
        for i, occ in enumerate(rows):
            due = text_item(occ.due_date.isoformat())
            due.setFlags(due.flags() & ~Qt.ItemFlag.ItemIsEditable)
            due.setData(Qt.ItemDataRole.UserRole, occ.due_date.isoformat())
            expected = money_item(format_money(working, symbol))
            expected.setFlags(expected.flags() & ~Qt.ItemFlag.ItemIsEditable)
            actual = money_item(
                f"{occ.amount_actual:.2f}" if occ.amount_actual is not None else ""
            )
            paid = QTableWidgetItem()
            paid.setFlags(paid.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            paid.setCheckState(
                Qt.CheckState.Checked if occ.paid else Qt.CheckState.Unchecked
            )
            notes = text_item(occ.notes)
            self.occ_table.setItem(i, 0, due)
            self.occ_table.setItem(i, 1, expected)
            self.occ_table.setItem(i, 2, actual)
            self.occ_table.setItem(i, 3, paid)
            self.occ_table.setItem(i, 4, notes)
            self._occ_actual_cache[i] = actual.text()
        self.occ_table.blockSignals(False)

    def _occurrence_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or self._selected_id is None:
            return
        row = item.row()
        due_item = self.occ_table.item(row, 0)
        if due_item is None:
            return
        due = date.fromisoformat(due_item.data(Qt.ItemDataRole.UserRole))
        actual_item = self.occ_table.item(row, 2)
        paid_item = self.occ_table.item(row, 3)
        notes_item = self.occ_table.item(row, 4)
        actual_text = actual_item.text().strip() if actual_item else ""
        paid = paid_item.checkState() == Qt.CheckState.Checked if paid_item else False
        notes = notes_item.text() if notes_item else ""
        if actual_text == "":
            amount: Decimal | None = None
        else:
            amount = parse_money(actual_text)
            if amount is None or amount <= 0:
                show_error(self, "Enter an amount greater than 0")
                self.occ_table.blockSignals(True)
                actual_item.setText(self._occ_actual_cache.get(row, ""))
                self.occ_table.blockSignals(False)
                return
        try:
            self.service.set_bill_actual(
                self._selected_id,
                due,
                amount_actual=amount,
                paid=paid,
                notes=notes,
            )
        except ValidationError as exc:
            show_error(self, str(exc))

    def _blank_form(self) -> None:
        self._selected_id = None
        self.table.clearSelection()
        self.name.clear()
        self.estimate.clear()
        self.frequency.setCurrentText(BillFrequency.MONTHLY.value)
        self.due_day.setText("1")
        self.has_next.setChecked(False)
        self.next_due.setEnabled(False)
        self.category.setCurrentText(BillCategory.OTHER.value)
        self.variable.setChecked(False)
        self.estimate_mode.setCurrentIndex(0)
        self.avg_n.setText("6")
        self.active.setChecked(True)
        self.notes.clear()
        self.variable_info.setText("")
        self.occ_table.setRowCount(0)
        self.name.setFocus()

    def save_bill(self) -> None:
        estimate = self.estimate.amount()
        if estimate is None:
            show_error(self, "Enter an amount greater than 0")
            return
        due_text = self.due_day.text().strip()
        try:
            due_day = int(due_text) if due_text else None
        except ValueError:
            show_error(self, "Due day must be a number from 1 to 28.")
            return
        try:
            avg_n = int(self.avg_n.text().strip() or "6")
        except ValueError:
            show_error(self, "Average last N must be an integer.")
            return
        existing = self._current_bill()
        bill = existing or Bill(
            name=self.name.text(),
            amount_estimate=estimate,
            frequency=BillFrequency.MONTHLY,
        )
        bill.name = self.name.text()
        bill.amount_estimate = estimate
        bill.frequency = BillFrequency(self.frequency.currentText())
        bill.due_day = due_day
        bill.next_due_date = (
            date_from_edit(self.next_due) if self.has_next.isChecked() else None
        )
        bill.category = BillCategory(self.category.currentText())
        bill.variable = self.variable.isChecked()
        bill.estimate_mode = EstimateMode(self.estimate_mode.currentData())
        bill.average_actuals_n = avg_n
        bill.active = self.active.isChecked()
        bill.notes = self.notes.toPlainText().strip()
        try:
            if existing is None:
                created = self.service.create_bill(bill)
                self._selected_id = created.id
            else:
                self.service.update_bill(bill)
                self._selected_id = bill.id
        except ValidationError as exc:
            show_error(self, str(exc))

    def _add_electric(self) -> None:
        dialog = BillDialog(self.service, self, electric=True)
        if dialog.exec() and dialog.created_id is not None:
            self._selected_id = dialog.created_id

    def _set_estimate_from_average(self) -> None:
        if self._selected_id is None:
            show_error(self, "Save the bill first, then log actuals.")
            return
        try:
            self.service.set_estimate_from_average(self._selected_id)
        except ValidationError as exc:
            show_error(self, str(exc))

    def _delete_bill(self) -> None:
        bill = self._current_bill()
        if bill is None or bill.id is None:
            return
        if not confirm_delete(
            self, "Delete bill", f"Delete “{bill.name}” and its actuals?"
        ):
            return
        self.service.delete_bill(bill.id)
        self._selected_id = None

    def new_item(self) -> None:
        self._blank_form()

    def focus_default(self) -> None:
        if self._selected_id is None:
            self.name.setFocus()
        else:
            self.table.setFocus()

    def save_focused(self) -> None:
        self.save_bill()
