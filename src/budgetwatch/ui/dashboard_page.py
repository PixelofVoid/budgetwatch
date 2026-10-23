from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from budgetwatch.services.budget import BudgetService
from budgetwatch.services.income import income_labels
from budgetwatch.services.planning import (
    FIXED_CATEGORIES,
    FLEXIBLE_CATEGORIES,
    category_actual,
    occurrences_index,
)
from budgetwatch.ui.chart import SurplusChart
from budgetwatch.ui.formatters import format_money
from budgetwatch.ui.layout import page_margins
from budgetwatch.ui.widgets import DashCard, PageHeader


class DashboardPage(QWidget):
    def __init__(self, service: BudgetService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        page_margins(layout)
        layout.setSpacing(16)
        layout.addWidget(
            PageHeader(
                "Dashboard",
                "This month at a glance — leftover is after the bills and transactions you have entered.",
            )
        )
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)
        self.grid.setContentsMargins(0, 0, 0, 0)

        self.cash_card = DashCard("This month cash flow")
        self.cash_card.setMinimumHeight(140)
        self.cash_income = QLabel("—")
        self.cash_income.setObjectName("cardValue")
        self.cash_hint = QLabel()
        self.cash_hint.setObjectName("cardHint")
        self.cash_bar = QProgressBar()
        self.cash_bar.setTextVisible(False)
        self.cash_bar.setFixedHeight(10)
        self.cash_card.body.addWidget(self.cash_income)
        self.cash_card.body.addStretch(1)
        self.cash_card.body.addWidget(self.cash_hint)
        self.cash_card.body.addWidget(self.cash_bar)

        self.plan_card = DashCard("Plan progress")
        self.plan_card.setMinimumHeight(140)
        self.plan_value = QLabel("—")
        self.plan_value.setObjectName("cardValue")
        self.plan_hint = QLabel()
        self.plan_hint.setObjectName("cardHint")
        self.plan_bar = QProgressBar()
        self.plan_bar.setTextVisible(False)
        self.plan_bar.setFixedHeight(10)
        self.plan_card.body.addWidget(self.plan_value)
        self.plan_card.body.addStretch(1)
        self.plan_card.body.addWidget(self.plan_hint)
        self.plan_card.body.addWidget(self.plan_bar)

        self.left_card = DashCard("Left after entered bills")
        self.left_card.setMinimumHeight(160)
        self.left_value = QLabel("—")
        self.left_value.setObjectName("cardValue")
        self.left_hint = QLabel()
        self.left_hint.setObjectName("cardHint")
        self.left_hint.setWordWrap(True)
        self.left_card.body.addWidget(self.left_value)
        self.left_card.body.addStretch(1)
        self.left_card.body.addWidget(self.left_hint)

        self.up_card = DashCard("Upcoming recurring")
        self.up_card.setMinimumHeight(160)
        self.up_body = QLabel("—")
        self.up_body.setWordWrap(True)
        self.up_body.setObjectName("helperText")
        self.up_body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.up_card.body.addWidget(self.up_body, 1)

        self.cat_card = DashCard("Category spend this month")
        self.cat_card.setMinimumHeight(360)
        self.cat_body = QVBoxLayout()
        self.cat_card.body.addLayout(self.cat_body, 1)

        self.chart_card = DashCard("6-month leftover")
        self.chart_card.setMinimumHeight(360)
        self.chart = SurplusChart()
        self.chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.chart_card.body.addWidget(self.chart, 1)

        self.grid.addWidget(self.cash_card, 0, 0)
        self.grid.addWidget(self.plan_card, 0, 1)
        self.grid.addWidget(self.left_card, 1, 0)
        self.grid.addWidget(self.up_card, 1, 1)
        self.grid.addWidget(self.cat_card, 2, 0)
        self.grid.addWidget(self.chart_card, 2, 1)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnMinimumWidth(0, 240)
        self.grid.setColumnMinimumWidth(1, 240)
        self.grid.setRowStretch(0, 1)
        self.grid.setRowStretch(1, 1)
        self.grid.setRowStretch(2, 2)
        self.grid.setRowMinimumHeight(0, 140)
        self.grid.setRowMinimumHeight(1, 160)
        self.grid.setRowMinimumHeight(2, 360)
        layout.addLayout(self.grid, 1)

    def refresh(self) -> None:
        from budgetwatch.ui import theme as t

        data = self.service.overview()
        symbol = data.currency_symbol
        as_of = date.today()
        month = data.this_month
        expenses = self.service.month_expenses(as_of.year, as_of.month, as_of=as_of)
        leftover = month.income - expenses
        self.cash_income.setText(format_money(leftover, symbol))
        self.cash_income.setStyleSheet(
            f"color: {t.GREEN if leftover >= 0 else t.RED}; font-weight: 700;"
        )
        self.cash_hint.setText(
            f"Income {format_money(month.income, symbol)} − expenses "
            f"{format_money(expenses, symbol)}"
        )
        total = float(month.income) if month.income else 1.0
        used = min(100, int(float(expenses) / total * 100)) if total else 0
        self.cash_bar.setValue(used)

        plan = self.service.plan_for_month(as_of.year, as_of.month, as_of=as_of)
        self.plan_value.setText(
            f"{format_money(plan.total_actual, symbol)} of {format_money(plan.total_planned, symbol)}"
        )
        pct = 0
        if plan.total_planned > 0:
            pct = min(100, int(float(plan.total_actual / plan.total_planned) * 100))
        self.plan_bar.setValue(pct)
        self.plan_hint.setText(f"{pct}% of planned spend used this month")

        leftover_t = data.leftover_after_bills
        other = self.service.other_monthly_spending()
        if leftover_t is not None and other:
            leftover_t = leftover_t - other
        self.left_value.setText(format_money(leftover_t, symbol))
        if leftover_t is not None:
            self.left_value.setStyleSheet(
                f"color: {t.GREEN if leftover_t >= 0 else t.RED}; font-weight: 700;"
            )
        n = data.active_bill_count
        extra = (
            f"Typical month minus {n} entered bills"
            + (f" and {format_money(other, symbol)} other monthly spending." if other else ".")
        )
        self.left_hint.setText(extra)

        pay_labels = income_labels(self.service.list_sources())
        lines = []
        for event in data.upcoming[:6]:
            kind = "Payday" if event.kind == "pay" else "Bill"
            amt = "—" if event.unknown else format_money(event.expected or event.actual, symbol)
            name = (
                pay_labels.get(event.source_id, event.name)
                if event.kind == "pay"
                else event.name
            )
            lines.append(f"{event.date.isoformat()}  {kind}  {name}  {amt}")
        self.up_body.setText("\n".join(lines) or "Nothing upcoming in range.")

        while self.cat_body.count():
            item = self.cat_body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        occ = self.service.db.occurrences.list_all()
        bills = self.service.list_bills()
        txs = self.service.db.transactions.list_in_month(as_of.year, as_of.month)
        occ_index = occurrences_index(occ)
        spend_rows = []
        for category in list(FIXED_CATEGORIES) + list(FLEXIBLE_CATEGORIES):
            amt = category_actual(
                category,
                as_of.year,
                as_of.month,
                bills,
                occ_index,
                txs,
            )
            if amt > 0:
                spend_rows.append((category.value, amt))
        spend_rows.sort(key=lambda row: row[1], reverse=True)
        peak = max((float(a) for _, a in spend_rows), default=1.0)
        shown = spend_rows[:8]
        for name, amt in shown:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lab = QLabel(name)
            lab.setMinimumWidth(90)
            lab.setObjectName("helperText")
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setFixedHeight(12)
            bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar.setValue(int(float(amt) / peak * 100) if peak else 0)
            val = QLabel(format_money(amt, symbol))
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lab)
            row.addWidget(bar, 1)
            row.addWidget(val)
            wrap = QWidget()
            wrap.setLayout(row)
            wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.cat_body.addWidget(wrap, 1)
        if not shown:
            empty = QLabel("No spend logged this month yet.")
            empty.setObjectName("helperText")
            self.cat_body.addWidget(empty)
            self.cat_body.addStretch(1)

        self.chart.refresh(data.months, symbol)

    def new_item(self) -> None:
        return

    def save_focused(self) -> None:
        return

    def focus_default(self) -> None:
        self.setFocus()
