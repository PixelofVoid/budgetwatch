from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from budgetwatch.models.entities import (
    Bill,
    BillFrequency,
    BillOccurrence,
    EstimateMode,
    UpcomingBillItem,
)
from budgetwatch.services.calendar_math import (
    BIWEEKLY_MONTHLY_FACTOR,
    WEEKLY_MONTHLY_FACTOR,
    every_n_months_dates,
    interval_dates,
    last_day_of_month,
    month_start,
    monthly_dates,
    q2,
)


def generate_bill_dates(bill: Bill, start: date, end: date) -> list[date]:
    if not bill.active:
        return []
    freq = bill.frequency
    if freq == BillFrequency.ONE_TIME:
        if bill.next_due_date and start <= bill.next_due_date <= end:
            return [bill.next_due_date]
        return []
    if freq == BillFrequency.MONTHLY:
        day = bill.due_day
        if day is None and bill.next_due_date is not None:
            day = bill.next_due_date.day
        if day is None:
            return []
        return monthly_dates(day, start, end)
    if freq == BillFrequency.WEEKLY:
        if bill.next_due_date is None:
            return []
        return interval_dates(bill.next_due_date, 7, start, end)
    if freq == BillFrequency.BIWEEKLY:
        if bill.next_due_date is None:
            return []
        return interval_dates(bill.next_due_date, 14, start, end)
    if freq == BillFrequency.QUARTERLY:
        if bill.next_due_date is None:
            return []
        return every_n_months_dates(bill.next_due_date, 3, start, end)
    if freq == BillFrequency.YEARLY:
        if bill.next_due_date is None:
            return []
        return every_n_months_dates(bill.next_due_date, 12, start, end)
    return []


def recent_actuals(occurrences: list[BillOccurrence], n: int) -> list[Decimal]:
    rows = [occ for occ in occurrences if occ.amount_actual is not None]
    rows.sort(key=lambda occ: occ.due_date, reverse=True)
    return [occ.amount_actual for occ in rows[:n] if occ.amount_actual is not None]


def recent_actual_average(
    occurrences: list[BillOccurrence], n: int
) -> Decimal | None:
    actuals = recent_actuals(occurrences, n)
    if not actuals:
        return None
    return q2(sum(actuals) / Decimal(len(actuals)))


def working_amount(bill: Bill, occurrences: list[BillOccurrence]) -> Decimal:
    if bill.variable and bill.estimate_mode == EstimateMode.AVERAGE_ACTUALS:
        actuals = recent_actuals(occurrences, bill.average_actuals_n)
        if len(actuals) >= 2:
            return q2(sum(actuals) / Decimal(len(actuals)))
    return q2(bill.amount_estimate)


def occurrence_amount(
    bill: Bill, occurrence: BillOccurrence | None, working: Decimal
) -> Decimal:
    if occurrence is not None and occurrence.amount_actual is not None:
        return q2(occurrence.amount_actual)
    return q2(working)


def monthly_equivalent(frequency: BillFrequency, amount: Decimal) -> Decimal:
    if frequency == BillFrequency.WEEKLY:
        return q2(amount * WEEKLY_MONTHLY_FACTOR)
    if frequency == BillFrequency.BIWEEKLY:
        return q2(amount * BIWEEKLY_MONTHLY_FACTOR)
    if frequency == BillFrequency.MONTHLY:
        return q2(amount)
    if frequency == BillFrequency.QUARTERLY:
        return q2(amount / Decimal("3"))
    if frequency == BillFrequency.YEARLY:
        return q2(amount / Decimal("12"))
    if frequency == BillFrequency.ONE_TIME:
        return Decimal("0.00")
    return q2(amount)


def merge_occurrences(
    bill: Bill,
    start: date,
    end: date,
    persisted: list[BillOccurrence],
) -> list[BillOccurrence]:
    by_date = {occ.due_date: occ for occ in persisted}
    merged: list[BillOccurrence] = []
    seen: set[date] = set()
    if bill.id is None:
        return []
    for due in generate_bill_dates(bill, start, end):
        seen.add(due)
        if due in by_date:
            merged.append(by_date[due])
        else:
            merged.append(BillOccurrence(bill_id=bill.id, due_date=due))
    for occ in persisted:
        if occ.due_date not in seen and start <= occ.due_date <= end:
            merged.append(occ)
    merged.sort(key=lambda occ: occ.due_date)
    return merged


BILL_RANGE_14D = "14d"
BILL_RANGE_MONTH = "month"
BILL_RANGE_6W = "6w"


def bill_range_bounds(key: str, as_of: date) -> tuple[date, date]:
    if key == BILL_RANGE_MONTH:
        return month_start(as_of), last_day_of_month(as_of)
    if key == BILL_RANGE_6W:
        return as_of, as_of + timedelta(days=42)
    return as_of, as_of + timedelta(days=14)


def upcoming_bill_items(
    bills: list[Bill],
    occurrences_by_bill: dict[int, list[BillOccurrence]],
    as_of: date,
    range_key: str = BILL_RANGE_14D,
) -> list[UpcomingBillItem]:
    range_start, range_end = bill_range_bounds(range_key, as_of)
    lookback = as_of - timedelta(days=90)
    gen_start = min(lookback, range_start)
    week_end = as_of + timedelta(days=6)
    items: list[UpcomingBillItem] = []
    for bill in bills:
        if not bill.active or bill.id is None:
            continue
        persisted = occurrences_by_bill.get(bill.id, [])
        working = working_amount(bill, persisted)
        merged = merge_occurrences(bill, gen_start, range_end, persisted)
        for occ in merged:
            overdue = occ.due_date < as_of and not occ.paid
            in_range = range_start <= occ.due_date <= range_end
            if not overdue and not in_range:
                continue
            if overdue:
                group = "overdue"
            elif as_of <= occ.due_date <= week_end:
                group = "this_week"
            else:
                group = "later"
            items.append(
                UpcomingBillItem(
                    bill_id=bill.id,
                    name=bill.name,
                    due_date=occ.due_date,
                    amount=occurrence_amount(bill, occ, working),
                    actual=occ.amount_actual,
                    paid=occ.paid,
                    variable=bill.variable,
                    group=group,
                )
            )
    # One overdue row per bill (latest unpaid due date before as_of),
    # plus every in-range occurrence.
    latest_overdue: dict[int, UpcomingBillItem] = {}
    in_range_items: list[UpcomingBillItem] = []
    for item in items:
        if item.group == "overdue":
            previous = latest_overdue.get(item.bill_id)
            if previous is None or item.due_date > previous.due_date:
                latest_overdue[item.bill_id] = item
        else:
            in_range_items.append(item)
    combined = list(latest_overdue.values()) + in_range_items
    combined.sort(key=lambda item: (item.due_date, item.name))
    return combined
