from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.services.budget import BudgetService
from budgetwatch.ui.chart import SurplusChart
from budgetwatch.ui.dialogs import PaycheckDialog
from budgetwatch.ui.formatters import format_money
from budgetwatch.ui.layout import (
    CONTENT_MAX,
    page_margins,
    money_item,
    style_table,
    text_item,
    CardStrip,
)
from budgetwatch.ui.widgets import MetricCard, WarningBanner


class OverviewPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        page_margins(layout)

        self.banner = WarningBanner()
        self.banner.setMaximumWidth(CONTENT_MAX)
        layout.addWidget(self.banner)

        self.income_card = MetricCard(
            "Typical monthly income", "Usual month from paycheck averages"
        )
        self.bills_card = MetricCard(
            "Typical monthly bills", "Usual month from bill equivalents"
        )
        self.leftover_card = MetricCard(
            "Left after the bills you have entered",
            "Typical month · income − those bills",
        )
        self.savings_card = MetricCard(
            "Left after bills and savings", "Typical month minus savings target"
        )
        self.month_card = MetricCard(
            "This month so far", "Calendar math · actuals when logged"
        )
        self.cards = CardStrip(
            [
                self.income_card,
                self.bills_card,
                self.leftover_card,
                self.savings_card,
                self.month_card,
            ]
        )
        layout.addWidget(self.cards, 0, Qt.AlignmentFlag.AlignLeft)

        self.chart = SurplusChart()
        self.chart.setMaximumWidth(CONTENT_MAX)
        layout.addWidget(self.chart)

        self.recipe = QLabel()
        self.recipe.setObjectName("recipe")
        self.recipe.setWordWrap(True)
        self.recipe.setMaximumWidth(CONTENT_MAX)
        layout.addWidget(self.recipe)

        upcoming_title = QLabel("Next up")
        upcoming_title.setObjectName("sectionTitle")
        layout.addWidget(upcoming_title)

        self.upcoming = QTableWidget(0, 5)
        self.upcoming.setHorizontalHeaderLabels(
            ["Date", "Type", "Name", "Expected", "Actual"]
        )
        style_table(self.upcoming)
        header = self.upcoming.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.upcoming.setMaximumHeight(180)
        self.upcoming.setMinimumHeight(140)
        self.upcoming.setMaximumWidth(CONTENT_MAX)
        layout.addWidget(self.upcoming)
        layout.addStretch(1)

        scroll.setWidget(inner)
        root.addWidget(scroll)

    def refresh(self) -> None:
        data = self.service.overview()
        symbol = data.currency_symbol
        self.banner.set_messages(data.warnings)

        typical = data.typical_income
        if typical.is_complete and typical.total is not None:
            self.income_card.set_amount(typical.total, symbol)
            self.income_card.set_hint("Usual month from paycheck averages")
        else:
            names = ", ".join(typical.unknown_sources) or "pay sources"
            self.income_card.set_amount(
                None,
                symbol,
                unknown=True,
                unknown_text=f"Not enough data for {names}",
            )
            self.income_card.set_hint("Add at least two included paychecks per source")

        if data.has_bills:
            self.bills_card.set_amount(data.typical_bills, symbol)
            self.bills_card.set_hint("Usual month from bill equivalents")
        else:
            self.bills_card.set_amount(
                None, symbol, unknown=True, unknown_text="Add recurring bills"
            )
            self.bills_card.set_hint("Rent, utilities, insurance…")

        n_bills = data.active_bill_count
        bill_word = "bill" if n_bills == 1 else "bills"
        self.leftover_card.set_amount(
            data.leftover_after_bills,
            symbol,
            unknown=data.leftover_after_bills is None,
            unknown_text="Need typical income first",
            colorize=True,
        )
        self.leftover_card.set_hint(
            f"Typical month · income − the {n_bills} {bill_word} you have entered"
        )
        self.savings_card.set_amount(
            data.leftover_after_savings,
            symbol,
            unknown=data.leftover_after_savings is None,
            unknown_text="Need typical income first",
            colorize=True,
        )
        self.savings_card.set_hint(
            f"After those {n_bills} {bill_word}, minus savings target "
            f"{format_money(data.savings_target, symbol)} / month"
        )

        this_month = data.this_month
        self.month_card.set_amount(this_month.leftover, symbol, colorize=True)
        extra = ""
        if this_month.income_is_partial:
            extra = (
                f" · estimated (not enough data for "
                f"{', '.join(this_month.unknown_sources)})"
            )
        self.month_card.set_hint(
            f"Calendar {this_month.label} after the {n_bills} {bill_word} entered: "
            f"in {format_money(this_month.income, symbol)} − "
            f"bills {format_money(this_month.bills, symbol)}{extra}"
        )

        self.chart.refresh(data.months, symbol)
        self.recipe.setText(data.recipe or "")

        rows = data.upcoming[:5]
        self.upcoming.setRowCount(len(rows))
        for row, event in enumerate(rows):
            kind = "Payday" if event.kind == "pay" else "Bill"
            expected = (
                "Not enough data"
                if event.unknown
                else format_money(event.expected, symbol)
            )
            self.upcoming.setItem(row, 0, text_item(event.date.isoformat()))
            self.upcoming.setItem(row, 1, text_item(kind))
            self.upcoming.setItem(row, 2, text_item(event.name))
            self.upcoming.setItem(row, 3, money_item(expected))
            self.upcoming.setItem(
                row,
                4,
                money_item(
                    format_money(event.actual, symbol)
                    if event.actual is not None
                    else "—"
                ),
            )

    def new_item(self) -> None:
        PaycheckDialog(self.service, self).exec()

    def save_focused(self) -> None:
        return

    def focus_default(self) -> None:
        self.setFocus()
