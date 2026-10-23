from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.models.entities import BillCategory, LedgerEntry
from budgetwatch.services.budget import BudgetService, ValidationError
from budgetwatch.services.income import income_labels
from budgetwatch.services.bills import occurrence_amount, working_amount
from budgetwatch.services.rollup import occurrences_index
from budgetwatch.ui.dialogs import CATEGORIES
from budgetwatch.ui.formatters import format_money
from budgetwatch.ui.layout import money_item, page_margins, style_table, text_item
from budgetwatch.ui.widgets import (
    MoneyEdit,
    PageHeader,
    confirm_delete,
    date_from_edit,
    make_date_edit,
    show_error,
)


class SpendDialog(QDialog):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Add spend")
        self.setModal(True)
        form = QFormLayout(self)
        self.payee = QLineEdit()
        self.payee.setPlaceholderText("Store or payee")
        self.amount = MoneyEdit()
        self.when = make_date_edit(date.today())
        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        self.notes = QLineEdit()
        form.addRow("Payee", self.payee)
        form.addRow("Amount", self.amount)
        form.addRow("Date", self.when)
        form.addRow("Category", self.category)
        form.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self) -> None:
        amount = self.amount.amount()
        if amount is None:
            show_error(self, "Enter an amount greater than 0")
            return
        try:
            self.service.create_transaction(
                LedgerEntry(
                    date=date_from_edit(self.when),
                    payee=self.payee.text(),
                    amount=amount,
                    category=BillCategory(self.category.currentText()),
                    kind="expense",
                    notes=self.notes.text().strip(),
                )
            )
        except ValidationError as exc:
            show_error(self, str(exc))
            return
        self.accept()


class TransactionsPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self._manual_ids: list[int | None] = []
        layout = QVBoxLayout(self)
        page_margins(layout)
        layout.addWidget(
            PageHeader(
                "Transactions",
                "Paychecks, paid bills, and one-off spend. Linked rows count once in Plan.",
            )
        )
        buttons = QHBoxLayout()
        add = QPushButton("Add spend")
        add.setObjectName("primary")
        add.clicked.connect(self._add)
        delete = QPushButton("Delete spend")
        delete.setObjectName("danger")
        delete.clicked.connect(self._delete)
        buttons.addWidget(add)
        buttons.addWidget(delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Payee", "Amount", "Category", "Type", "Notes"]
        )
        style_table(self.table)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        symbol = self.service.get_settings().currency_symbol
        rows: list[tuple] = []
        source_list = self.service.list_sources()
        sources = income_labels(source_list)
        for paycheck in self.service.list_paychecks():
            rows.append(
                (
                    paycheck.date,
                    sources.get(paycheck.source_id, "Income"),
                    paycheck.amount,
                    "income",
                    "Income",
                    paycheck.notes,
                    None,
                )
            )
        bills = {b.id: b for b in self.service.list_bills()}
        occ_index = occurrences_index(self.service.db.occurrences.list_all())
        counted_occ: set[int] = set()
        for bill in bills.values():
            if bill.id is None:
                continue
            working = working_amount(bill, occ_index.get(bill.id, []))
            for occ in occ_index.get(bill.id, []):
                if not occ.paid:
                    continue
                amt = occurrence_amount(bill, occ, working)
                rows.append(
                    (
                        occ.due_date,
                        bill.name,
                        amt,
                        bill.category.value,
                        "Bill",
                        occ.notes,
                        None,
                    )
                )
                if occ.id is not None:
                    counted_occ.add(occ.id)
        for entry in self.service.list_transactions():
            if entry.occurrence_id is not None and entry.occurrence_id in counted_occ:
                continue
            rows.append(
                (
                    entry.date,
                    entry.payee,
                    entry.amount,
                    entry.category.value,
                    "Spend" if entry.kind == "expense" else "Income",
                    entry.notes,
                    entry.id,
                )
            )
        rows.sort(key=lambda row: row[0], reverse=True)
        self._manual_ids = []
        self.table.setRowCount(len(rows))
        for i, (when, payee, amount, category, kind, notes, manual_id) in enumerate(rows):
            self._manual_ids.append(manual_id)
            self.table.setItem(i, 0, text_item(when.isoformat()))
            self.table.setItem(i, 1, text_item(payee))
            self.table.setItem(i, 2, money_item(format_money(amount, symbol)))
            self.table.setItem(i, 3, text_item(category))
            self.table.setItem(i, 4, text_item(kind))
            self.table.setItem(i, 5, text_item(notes or ""))

    def _add(self) -> None:
        SpendDialog(self.service, self).exec()

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._manual_ids):
            return
        entry_id = self._manual_ids[row]
        if entry_id is None:
            show_error(self, "Only one-off spend can be deleted here.")
            return
        if not confirm_delete(self, "Delete spend", "Delete this one-off spend?"):
            return
        self.service.delete_transaction(entry_id)

    def new_item(self) -> None:
        self._add()

    def save_focused(self) -> None:
        return

    def focus_default(self) -> None:
        self.table.setFocus()
