from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    EstimateMode,
    Paycheck,
    PayFrequency,
    PaySource,
)
from budgetwatch.services.budget import BudgetService, ValidationError
from budgetwatch.services.income import income_labels, next_income_name
from budgetwatch.ui.formatters import format_date
from budgetwatch.ui.layout import field_with_help
from budgetwatch.ui.widgets import (
    MoneyEdit,
    date_from_edit,
    make_date_edit,
    show_error,
)


PAY_FREQS = [f.value for f in PayFrequency]
BILL_FREQS = [f.value for f in BillFrequency]
CATEGORIES = [c.value for c in BillCategory]


class PaySourceDialog(QDialog):
    def __init__(
        self,
        service: BudgetService,
        parent: QWidget | None = None,
        source: PaySource | None = None,
    ):
        super().__init__(parent)
        self.service = service
        self.source = source
        self.setWindowTitle("Pay source" if source else "New pay source")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        existing = service.list_sources()
        labels = income_labels(existing)
        if source and source.id is not None:
            default_name = labels.get(source.id, source.name).replace(" (inactive)", "")
        else:
            default_name = next_income_name([item.name for item in existing])
        self.name = QLineEdit(default_name)
        self.name.setPlaceholderText("Income 1")
        self.frequency = QComboBox()
        self.frequency.addItems(PAY_FREQS)
        if source:
            self.frequency.setCurrentText(source.frequency.value)
        else:
            self.frequency.setCurrentText(PayFrequency.BIWEEKLY.value)
        self.anchor = make_date_edit(source.anchor_date if source else date.today())
        self.has_anchor = QCheckBox("Payday known")
        self.has_anchor.setChecked(source.anchor_date is not None if source else True)
        self.override = MoneyEdit()
        if source and source.amount_override is not None:
            self.override.set_amount(source.amount_override)
        self.include_typical = QCheckBox("Include in typical monthly income")
        self.include_typical.setChecked(source.include_in_typical if source else True)
        self.active = QCheckBox("Active")
        self.active.setChecked(source.active if source else True)
        form.addRow("Pay source name", self.name)
        form.addRow("How often are you paid?", self.frequency)
        form.addRow(self.has_anchor)
        form.addRow(
            "A recent payday",
            field_with_help(
                self.anchor,
                "Used to predict future paydays. Example: 2026-09-11",
            ),
        )
        form.addRow(
            "Typical amount override (optional)",
            field_with_help(
                self.override,
                "Leave blank to use the average of logged paychecks",
            ),
        )
        form.addRow(self.include_typical)
        form.addRow(self.active)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.has_anchor.toggled.connect(self.anchor.setEnabled)
        self.anchor.setEnabled(self.has_anchor.isChecked())
        self.frequency.currentTextChanged.connect(self._on_freq)
        self._on_freq(self.frequency.currentText())
        self.resize(420, 360)

    def _on_freq(self, text: str) -> None:
        irregular = text == PayFrequency.IRREGULAR.value
        self.has_anchor.setEnabled(not irregular)
        if irregular:
            self.has_anchor.setChecked(False)

    def _save(self) -> None:
        try:
            source = self.source or PaySource(name="", frequency=PayFrequency.WEEKLY)
            source.name = self.name.text()
            source.frequency = PayFrequency(self.frequency.currentText())
            source.anchor_date = (
                date_from_edit(self.anchor) if self.has_anchor.isChecked() else None
            )
            source.amount_override = self.override.amount()
            source.include_in_typical = self.include_typical.isChecked()
            source.active = self.active.isChecked()
            if self.source is None:
                self.service.create_source(source)
            else:
                self.service.update_source(source)
        except ValidationError as exc:
            show_error(self, str(exc))
            return
        self.accept()


class PaycheckDialog(QDialog):
    def __init__(
        self,
        service: BudgetService,
        parent: QWidget | None = None,
        paycheck: Paycheck | None = None,
        source_id: int | None = None,
        preset_date: date | None = None,
        occurrence_date: date | None = None,
    ):
        super().__init__(parent)
        self.service = service
        self.paycheck = paycheck
        self.unlinked = False
        self.setWindowTitle("Edit paycheck" if paycheck else "Log paycheck")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.source = QComboBox()
        all_sources = service.list_sources()
        labels = income_labels(all_sources)
        sources = [
            s
            for s in all_sources
            if s.active or (paycheck and s.id == paycheck.source_id)
        ]
        self._source_ids: list[int] = []
        selected = paycheck.source_id if paycheck else source_id
        for source in sources:
            if source.id is None:
                continue
            self.source.addItem(labels.get(source.id, source.name), source.id)
            self._source_ids.append(source.id)
            if selected is not None and source.id == selected:
                self.source.setCurrentIndex(self.source.count() - 1)
        self.date = make_date_edit(
            paycheck.date if paycheck else (preset_date or date.today())
        )
        self.amount = MoneyEdit()
        if paycheck:
            self.amount.set_amount(paycheck.amount)
        self.include = QCheckBox("Count this toward typical pay?")
        self.include.setChecked(paycheck.include_in_average if paycheck else True)
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(70)
        self.notes.setPlaceholderText("Overtime, bonus, short week...")
        if paycheck:
            self.notes.setPlainText(paycheck.notes)
        self.link_label = QLabel()
        self.link_label.setWordWrap(True)
        self.unlink_btn = QPushButton("Unlink payday")
        self.unlink_btn.clicked.connect(self._unlink)
        form.addRow("Which job?", self.source)
        form.addRow("Pay date", self.date)
        form.addRow("Net amount deposited", self.amount)
        form.addRow(self.include)
        form.addRow("Notes (optional)", self.notes)
        form.addRow(self.link_label)
        form.addRow(self.unlink_btn)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._occurrence = occurrence_date or (paycheck.occurrence_date if paycheck else None)
        self.source.currentIndexChanged.connect(self._refresh_link)
        self.date.dateChanged.connect(self._refresh_link)
        self._refresh_link()
        self.resize(440, 420)

    def _current_source_id(self) -> int | None:
        data = self.source.currentData()
        return int(data) if data is not None else None

    def _refresh_link(self) -> None:
        if self.unlinked:
            self.link_label.setText("Not linked to a scheduled payday.")
            return
        source_id = self._current_source_id()
        if source_id is None:
            return
        suggested = self.service.suggest_link(
            source_id,
            date_from_edit(self.date),
            exclude_paycheck_id=self.paycheck.id if self.paycheck else None,
        )
        current = self._occurrence or suggested
        self._occurrence = current
        if current:
            self.link_label.setText(f"Linked to scheduled payday {format_date(current)}")
            self.unlink_btn.setEnabled(True)
        else:
            self.link_label.setText("No nearby scheduled payday to auto-link.")
            self.unlink_btn.setEnabled(False)

    def _unlink(self) -> None:
        self.unlinked = True
        self._occurrence = None
        self._refresh_link()

    def _save(self) -> None:
        source_id = self._current_source_id()
        amount = self.amount.amount()
        if source_id is None:
            show_error(self, "Choose a pay source.")
            return
        if amount is None:
            show_error(self, "Enter an amount greater than 0")
            return
        try:
            if self.paycheck is None:
                self.service.create_paycheck(
                    Paycheck(
                        source_id=source_id,
                        date=date_from_edit(self.date),
                        amount=amount,
                        notes=self.notes.toPlainText().strip(),
                        include_in_average=self.include.isChecked(),
                        occurrence_date=None if self.unlinked else self._occurrence,
                    ),
                    auto_link=not self.unlinked,
                )
            else:
                self.paycheck.source_id = source_id
                self.paycheck.date = date_from_edit(self.date)
                self.paycheck.amount = amount
                self.paycheck.notes = self.notes.toPlainText().strip()
                self.paycheck.include_in_average = self.include.isChecked()
                self.paycheck.occurrence_date = None if self.unlinked else self._occurrence
                self.service.update_paycheck(
                    self.paycheck, auto_link=not self.unlinked and self._occurrence is None
                )
        except ValidationError as exc:
            show_error(self, str(exc))
            return
        self.accept()


class BillDialog(QDialog):
    def __init__(
        self,
        service: BudgetService,
        parent: QWidget | None = None,
        bill: Bill | None = None,
        electric: bool = False,
    ):
        super().__init__(parent)
        self.service = service
        self.bill = bill
        self.created_id: int | None = bill.id if bill else None
        self.setWindowTitle("Edit bill" if bill else "New bill")
        self.setModal(True)
        if electric and bill is None:
            bill = service.electric_defaults()
            self.setWindowTitle("Add electric bill")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(bill.name if bill else "")
        self.name.setPlaceholderText("Electric")
        self.estimate = MoneyEdit()
        if bill:
            self.estimate.set_amount(bill.amount_estimate)
        self.frequency = QComboBox()
        self.frequency.addItems(BILL_FREQS)
        if bill:
            self.frequency.setCurrentText(bill.frequency.value)
        else:
            self.frequency.setCurrentText(BillFrequency.MONTHLY.value)
        self.due_day = QLineEdit(str(bill.due_day) if bill and bill.due_day else "")
        self.due_day.setPlaceholderText("1–28, blank if unused")
        self.next_due = make_date_edit(bill.next_due_date if bill else date.today())
        self.has_next = QCheckBox("Next due date")
        self.has_next.setChecked(bool(bill and bill.next_due_date) or (bill is None))
        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        if bill:
            self.category.setCurrentText(bill.category.value)
        self.category.currentTextChanged.connect(self._on_category_changed)
        self.variable = QCheckBox("Amount changes each time")
        self.variable.setChecked(bill.variable if bill else False)
        self.estimate_mode = QComboBox()
        self.estimate_mode.addItem("Manual estimate", EstimateMode.MANUAL.value)
        self.estimate_mode.addItem(
            "Estimate using recent actuals", EstimateMode.AVERAGE_ACTUALS.value
        )
        if bill:
            self.estimate_mode.setCurrentIndex(
                1 if bill.estimate_mode == EstimateMode.AVERAGE_ACTUALS else 0
            )
        self.avg_n = QLineEdit(str(bill.average_actuals_n if bill else 6))
        self.active = QCheckBox("Active")
        self.active.setChecked(bill.active if bill else True)
        self.notes = QPlainTextEdit(bill.notes if bill else "")
        self.notes.setFixedHeight(70)
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
        layout.addLayout(form)
        layout.addWidget(
            QLabel(
                "Use an estimate until the real bill arrives, then enter the actual on that month"
            )
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.variable.toggled.connect(self._toggle_variable)
        self.has_next.toggled.connect(self.next_due.setEnabled)
        self.next_due.setEnabled(self.has_next.isChecked())
        self._toggle_variable(self.variable.isChecked())
        self.resize(460, 560)

    def _toggle_variable(self, on: bool) -> None:
        self.estimate_mode.setEnabled(on)
        self.avg_n.setEnabled(on)

    def _on_category_changed(self, value: str) -> None:
        if self.bill is not None:
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

    def _save(self) -> None:
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
            show_error(self, "Average last N actuals must be an integer.")
            return
        bill = self.bill or Bill(
            name="", amount_estimate=estimate, frequency=BillFrequency.MONTHLY
        )
        bill.name = self.name.text()
        bill.amount_estimate = estimate
        bill.frequency = BillFrequency(self.frequency.currentText())
        bill.due_day = due_day
        bill.next_due_date = date_from_edit(self.next_due) if self.has_next.isChecked() else None
        bill.category = BillCategory(self.category.currentText())
        bill.variable = self.variable.isChecked()
        bill.estimate_mode = EstimateMode(self.estimate_mode.currentData())
        bill.average_actuals_n = avg_n
        bill.active = self.active.isChecked()
        bill.notes = self.notes.toPlainText().strip()
        try:
            if self.bill is None:
                created = self.service.create_bill(bill)
                self.created_id = created.id
            else:
                self.service.update_bill(bill)
                self.created_id = bill.id
        except ValidationError as exc:
            show_error(self, str(exc))
            return
        except ValueError as exc:
            show_error(self, str(exc))
            return
        self.accept()


class BillActualDialog(QDialog):
    def __init__(
        self,
        service: BudgetService,
        bill_id: int,
        due_date: date,
        parent: QWidget | None = None,
        amount: Decimal | None = None,
        paid: bool = False,
        notes: str = "",
    ):
        super().__init__(parent)
        self.service = service
        self.bill_id = bill_id
        self.due_date = due_date
        self.setWindowTitle(f"Bill actual — {due_date.isoformat()}")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.amount = MoneyEdit()
        self.amount.set_amount(amount)
        self.paid = QCheckBox("Paid")
        self.paid.setChecked(paid)
        self.notes = QLineEdit(notes)
        form.addRow("Actual amount", self.amount)
        form.addRow(self.paid)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)
        row = QHBoxLayout()
        clear = QPushButton("Clear actual")
        clear.clicked.connect(self._clear)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        row.addWidget(clear)
        row.addWidget(buttons)
        layout.addLayout(row)

    def _save(self) -> None:
        try:
            self.service.set_bill_actual(
                self.bill_id,
                self.due_date,
                amount_actual=self.amount.amount(),
                paid=self.paid.isChecked(),
                notes=self.notes.text().strip(),
            )
        except ValidationError as exc:
            show_error(self, str(exc))
            return
        self.accept()

    def _clear(self) -> None:
        try:
            self.service.set_bill_actual(
                self.bill_id,
                self.due_date,
                amount_actual=None,
                paid=self.paid.isChecked(),
                notes=self.notes.text().strip(),
            )
        except ValidationError as exc:
            show_error(self, str(exc))
            return
        self.accept()
