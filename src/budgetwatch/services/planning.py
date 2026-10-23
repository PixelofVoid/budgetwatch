from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    BillOccurrence,
    LedgerEntry,
    Paycheck,
)
from budgetwatch.services.bills import monthly_equivalent, occurrence_amount, working_amount
from budgetwatch.services.calendar_math import last_day_of_month, month_start, q2
from budgetwatch.services.rollup import calendar_month, occurrences_index

FIXED_CATEGORIES = (
    BillCategory.HOUSING,
    BillCategory.INSURANCE,
    BillCategory.DEBT,
    BillCategory.SUBSCRIPTIONS,
)
FLEXIBLE_CATEGORIES = (
    BillCategory.GROCERIES,
    BillCategory.UTILITIES,
    BillCategory.TRANSPORT,
    BillCategory.OTHER,
)
NON_MONTHLY_FREQUENCIES = {
    BillFrequency.QUARTERLY,
    BillFrequency.YEARLY,
    BillFrequency.ONE_TIME,
}


def plan_group_for_bill(bill: Bill) -> str:
    if bill.frequency in NON_MONTHLY_FREQUENCIES:
        return "non_monthly"
    if bill.category in FIXED_CATEGORIES:
        return "fixed"
    return "flexible"


@dataclass
class PlanRow:
    key: str
    label: str
    group: str
    planned: Decimal
    actual: Decimal
    remaining: Decimal
    source: str  # "default" | "override"


@dataclass
class PlanMonth:
    year: int
    month: int
    income_planned: Decimal
    income_actual: Decimal
    rows: list[PlanRow]
    flex_planned: Decimal
    flex_actual: Decimal
    flex_remaining: Decimal
    total_planned: Decimal
    total_actual: Decimal


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    return start, last_day_of_month(start)


def default_planned_for_category(
    category: BillCategory,
    bills: list[Bill],
    occurrences_by_bill: dict[int, list[BillOccurrence]],
) -> Decimal:
    total = Decimal("0.00")
    for bill in bills:
        if not bill.active or bill.category != category:
            continue
        if plan_group_for_bill(bill) == "non_monthly":
            continue
        working = working_amount(bill, occurrences_by_bill.get(bill.id or -1, []))
        total += monthly_equivalent(bill.frequency, working)
    return q2(total)


def category_actual(
    category: BillCategory,
    year: int,
    month: int,
    bills: list[Bill],
    occurrences_by_bill: dict[int, list[BillOccurrence]],
    transactions: list[LedgerEntry],
) -> Decimal:
    start, end = _month_bounds(year, month)
    total = Decimal("0.00")
    counted_occ: set[int] = set()
    for bill in bills:
        if not bill.active or bill.category != category or bill.id is None:
            continue
        working = working_amount(bill, occurrences_by_bill.get(bill.id, []))
        for occ in occurrences_by_bill.get(bill.id, []):
            if not (start <= occ.due_date <= end):
                continue
            if not occ.paid:
                continue
            total += occurrence_amount(bill, occ, working)
            if occ.id is not None:
                counted_occ.add(occ.id)
    for entry in transactions:
        if entry.kind != "expense":
            continue
        if entry.category != category:
            continue
        if not (start <= entry.date <= end):
            continue
        if entry.occurrence_id is not None and entry.occurrence_id in counted_occ:
            continue
        total += entry.amount
    return q2(total)


def paycheck_actual(year: int, month: int, paychecks: list[Paycheck]) -> Decimal:
    start, end = _month_bounds(year, month)
    total = Decimal("0.00")
    for paycheck in paychecks:
        if start <= paycheck.date <= end:
            total += paycheck.amount
    return q2(total)


def build_plan(
    year: int,
    month: int,
    bills: list[Bill],
    occurrences: list[BillOccurrence],
    paychecks: list[Paycheck],
    transactions: list[LedgerEntry],
    overrides: dict[str, Decimal],
    income_planned: Decimal,
) -> PlanMonth:
    occ_index = occurrences_index(occurrences)
    rows: list[PlanRow] = []
    income_actual = paycheck_actual(year, month, paychecks)
    for entry in transactions:
        start, end = _month_bounds(year, month)
        if entry.kind == "income" and start <= entry.date <= end:
            income_actual += entry.amount
    income_actual = q2(income_actual)
    rows.append(
        PlanRow(
            key="income",
            label="Paychecks",
            group="income",
            planned=q2(overrides.get("income", income_planned)),
            actual=income_actual,
            remaining=q2(q2(overrides.get("income", income_planned)) - income_actual),
            source="override" if "income" in overrides else "default",
        )
    )

    flex_planned = Decimal("0.00")
    flex_actual = Decimal("0.00")
    for group, categories in (
        ("fixed", FIXED_CATEGORIES),
        ("flexible", FLEXIBLE_CATEGORIES),
    ):
        for category in categories:
            default = default_planned_for_category(category, bills, occ_index)
            planned = overrides.get(category.value, default)
            actual = category_actual(
                category, year, month, bills, occ_index, transactions
            )
            rows.append(
                PlanRow(
                    key=category.value,
                    label=category.value,
                    group=group,
                    planned=q2(planned),
                    actual=actual,
                    remaining=q2(q2(planned) - actual),
                    source="override" if category.value in overrides else "default",
                )
            )
            if group == "flexible":
                flex_planned += q2(planned)
                flex_actual += actual

    start, end = _month_bounds(year, month)
    for bill in bills:
        if not bill.active or bill.id is None:
            continue
        if plan_group_for_bill(bill) != "non_monthly":
            continue
        working = working_amount(bill, occ_index.get(bill.id, []))
        planned_default = Decimal("0.00")
        actual = Decimal("0.00")
        for occ in occ_index.get(bill.id, []):
            if start <= occ.due_date <= end:
                planned_default += occurrence_amount(bill, occ, working)
                if occ.paid:
                    actual += occurrence_amount(bill, occ, working)
        key = f"bill:{bill.id}"
        planned = overrides.get(key, planned_default)
        rows.append(
            PlanRow(
                key=key,
                label=bill.name,
                group="non_monthly",
                planned=q2(planned),
                actual=q2(actual),
                remaining=q2(q2(planned) - q2(actual)),
                source="override" if key in overrides else "default",
            )
        )

    expense_rows = [r for r in rows if r.group != "income"]
    return PlanMonth(
        year=year,
        month=month,
        income_planned=q2(overrides.get("income", income_planned)),
        income_actual=income_actual,
        rows=rows,
        flex_planned=q2(flex_planned),
        flex_actual=q2(flex_actual),
        flex_remaining=q2(flex_planned - flex_actual),
        total_planned=q2(sum((r.planned for r in expense_rows), Decimal("0"))),
        total_actual=q2(sum((r.actual for r in expense_rows), Decimal("0"))),
    )


def month_expense_total(
    year: int,
    month: int,
    bills: list[Bill],
    occurrences: list[BillOccurrence],
    transactions: list[LedgerEntry],
    settings,
    sources,
    paychecks,
    as_of: date,
) -> Decimal:
    rollup = calendar_month(
        date(year, month, 1),
        sources,
        paychecks,
        bills,
        occurrences_index(occurrences),
        settings,
        as_of,
    )
    start, end = _month_bounds(year, month)
    counted = {item.occurrence_id for item in rollup.bill_items if item.occurrence_id}
    extra = Decimal("0.00")
    for entry in transactions:
        if entry.kind != "expense":
            continue
        if not (start <= entry.date <= end):
            continue
        if entry.occurrence_id is not None and entry.occurrence_id in counted:
            continue
        extra += entry.amount
    return q2(rollup.bills + extra)
