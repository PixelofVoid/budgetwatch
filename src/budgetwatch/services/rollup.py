from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from budgetwatch.models.entities import (
    Bill,
    BillItem,
    BillOccurrence,
    MonthRollup,
    PayItem,
    PaySource,
    Paycheck,
    Settings,
    TypicalBillsResult,
    UpcomingEvent,
)
from budgetwatch.services.bills import (
    generate_bill_dates,
    merge_occurrences,
    monthly_equivalent,
    occurrence_amount,
    working_amount,
)
from budgetwatch.services.calendar_math import (
    last_day_of_month,
    month_start,
    q2,
    six_month_starts,
)
from budgetwatch.services.income import expected_payday_amount, source_average
from budgetwatch.services.payday import (
    generate_paydays,
    match_paycheck_to_payday,
    paycheck_for_occurrence,
)


def typical_bills(
    bills: list[Bill], occurrences_by_bill: dict[int, list[BillOccurrence]]
) -> TypicalBillsResult:
    items: list[tuple[Bill, Decimal, Decimal]] = []
    total = Decimal("0.00")
    for bill in bills:
        if not bill.active or bill.id is None:
            continue
        working = working_amount(bill, occurrences_by_bill.get(bill.id, []))
        monthly = monthly_equivalent(bill.frequency, working)
        items.append((bill, working, monthly))
        total += monthly
    return TypicalBillsResult(total=q2(total), items=items)


def calendar_month(
    month: date,
    sources: list[PaySource],
    paychecks: list[Paycheck],
    bills: list[Bill],
    occurrences_by_bill: dict[int, list[BillOccurrence]],
    settings: Settings,
    as_of: date,
) -> MonthRollup:
    m_start = month_start(month)
    m_end = last_day_of_month(m_start)
    window_start = as_of - timedelta(days=settings.average_window_days)
    window_end = as_of

    income = Decimal("0.00")
    unknown_sources: list[str] = []
    pay_items: list[PayItem] = []
    counted_paycheck_ids: set[int] = set()

    for source in sources:
        if not source.active or source.id is None:
            continue
        average = source_average(source, paychecks, window_start, window_end)
        expected = expected_payday_amount(source, average)
        paydays = generate_paydays(source, m_start, m_end)
        for payday in paydays:
            linked = match_paycheck_to_payday(
                source.id, payday, paychecks, counted_paycheck_ids
            )
            if linked is not None:
                income += linked.amount
                if linked.id is not None:
                    counted_paycheck_ids.add(linked.id)
                pay_items.append(
                    PayItem(
                        source_id=source.id,
                        source_name=source.name,
                        date=payday,
                        amount=linked.amount,
                        expected=expected,
                        actual=linked.amount,
                        projected=False,
                        unknown=False,
                        paycheck_id=linked.id,
                        linked=True,
                        notes=linked.notes,
                    )
                )
            elif expected is None:
                if source.name not in unknown_sources:
                    unknown_sources.append(source.name)
                pay_items.append(
                    PayItem(
                        source_id=source.id,
                        source_name=source.name,
                        date=payday,
                        amount=None,
                        expected=None,
                        actual=None,
                        projected=True,
                        unknown=True,
                    )
                )
            else:
                income += expected
                pay_items.append(
                    PayItem(
                        source_id=source.id,
                        source_name=source.name,
                        date=payday,
                        amount=expected,
                        expected=expected,
                        actual=None,
                        projected=True,
                        unknown=False,
                    )
                )
        for paycheck in paychecks:
            if paycheck.source_id != source.id:
                continue
            if paycheck.id is not None and paycheck.id in counted_paycheck_ids:
                continue
            if paycheck.occurrence_date is not None:
                # Counted in the payday's month, not the deposit month.
                continue
            if not (m_start <= paycheck.date <= m_end):
                continue
            income += paycheck.amount
            if paycheck.id is not None:
                counted_paycheck_ids.add(paycheck.id)
            pay_items.append(
                PayItem(
                    source_id=source.id,
                    source_name=source.name,
                    date=paycheck.date,
                    amount=paycheck.amount,
                    expected=expected,
                    actual=paycheck.amount,
                    projected=False,
                    unknown=False,
                    paycheck_id=paycheck.id,
                    linked=False,
                    notes=paycheck.notes,
                )
            )

    bills_total = Decimal("0.00")
    bill_items: list[BillItem] = []
    for bill in bills:
        if not bill.active or bill.id is None:
            continue
        persisted = occurrences_by_bill.get(bill.id, [])
        working = working_amount(bill, persisted)
        merged = merge_occurrences(bill, m_start, m_end, persisted)
        for occ in merged:
            amount = occurrence_amount(bill, occ, working)
            bills_total += amount
            bill_items.append(
                BillItem(
                    bill_id=bill.id,
                    bill_name=bill.name,
                    due_date=occ.due_date,
                    amount=amount,
                    actual=occ.amount_actual,
                    projected=occ.amount_actual is None,
                    paid=occ.paid,
                    variable=bill.variable,
                    occurrence_id=occ.id,
                    notes=occ.notes,
                    category=bill.category,
                )
            )

    pay_items.sort(key=lambda item: (item.date, item.source_name))
    bill_items.sort(key=lambda item: (item.due_date, item.bill_name))
    leftover = q2(income - bills_total)
    leftover_after = q2(leftover - settings.savings_target_monthly)
    return MonthRollup(
        month_start=m_start,
        income=q2(income),
        bills=q2(bills_total),
        leftover=leftover,
        leftover_after_savings=leftover_after,
        income_is_partial=bool(unknown_sources),
        unknown_sources=unknown_sources,
        pay_items=pay_items,
        bill_items=bill_items,
    )


def six_month_rollups(
    sources: list[PaySource],
    paychecks: list[Paycheck],
    bills: list[Bill],
    occurrences_by_bill: dict[int, list[BillOccurrence]],
    settings: Settings,
    as_of: date,
) -> list[MonthRollup]:
    return [
        calendar_month(
            start,
            sources,
            paychecks,
            bills,
            occurrences_by_bill,
            settings,
            as_of,
        )
        for start in six_month_starts(as_of)
    ]


def upcoming_events(
    sources: list[PaySource],
    paychecks: list[Paycheck],
    bills: list[Bill],
    occurrences_by_bill: dict[int, list[BillOccurrence]],
    settings: Settings,
    as_of: date,
    start: date,
    end: date,
    limit: int = 10,
) -> list[UpcomingEvent]:
    window_start = as_of - timedelta(days=settings.average_window_days)
    events: list[UpcomingEvent] = []
    for source in sources:
        if not source.active or source.id is None:
            continue
        average = source_average(source, paychecks, window_start, as_of)
        expected = expected_payday_amount(source, average)
        for payday in generate_paydays(source, start, end):
            if payday < as_of:
                continue
            linked = paycheck_for_occurrence(source.id, payday, paychecks)
            events.append(
                UpcomingEvent(
                    date=payday,
                    kind="pay",
                    name=source.name,
                    expected=expected,
                    actual=linked.amount if linked else None,
                    unknown=linked is None and expected is None,
                    linked=linked is not None,
                    source_id=source.id,
                )
            )
    for bill in bills:
        if not bill.active or bill.id is None:
            continue
        persisted = occurrences_by_bill.get(bill.id, [])
        working = working_amount(bill, persisted)
        for occ in merge_occurrences(bill, start, end, persisted):
            if occ.due_date < as_of:
                continue
            events.append(
                UpcomingEvent(
                    date=occ.due_date,
                    kind="bill",
                    name=bill.name,
                    expected=working,
                    actual=occ.amount_actual,
                    unknown=False,
                    paid=occ.paid,
                    bill_id=bill.id,
                )
            )
    events.sort(key=lambda event: (event.date, event.kind, event.name))
    return events[:limit]


def occurrences_index(
    occurrences: list[BillOccurrence],
) -> dict[int, list[BillOccurrence]]:
    index: dict[int, list[BillOccurrence]] = {}
    for occ in occurrences:
        index.setdefault(occ.bill_id, []).append(occ)
    return index
