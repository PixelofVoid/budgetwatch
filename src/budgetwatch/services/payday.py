from __future__ import annotations

from datetime import date

from budgetwatch.models.entities import PayFrequency, PaySource, Paycheck
from budgetwatch.services.calendar_math import (
    AUTO_LINK_TOLERANCE_DAYS,
    interval_dates,
    monthly_dates,
    semimonthly_dates,
)


def needs_anchor(source: PaySource) -> bool:
    return source.active and source.frequency != PayFrequency.IRREGULAR and source.anchor_date is None


def generate_paydays(source: PaySource, start: date, end: date) -> list[date]:
    if not source.active:
        return []
    if source.frequency == PayFrequency.IRREGULAR:
        return []
    if source.anchor_date is None:
        return []
    anchor = source.anchor_date
    if source.frequency == PayFrequency.WEEKLY:
        return interval_dates(anchor, 7, start, end)
    if source.frequency == PayFrequency.BIWEEKLY:
        return interval_dates(anchor, 14, start, end)
    if source.frequency == PayFrequency.SEMIMONTHLY:
        return semimonthly_dates(anchor, start, end)
    if source.frequency == PayFrequency.MONTHLY:
        return monthly_dates(anchor.day, start, end)
    return []


def linked_occurrence_dates(
    source_id: int,
    paychecks: list[Paycheck],
    exclude_paycheck_id: int | None = None,
) -> set[date]:
    linked: set[date] = set()
    for paycheck in paychecks:
        if paycheck.source_id != source_id:
            continue
        if exclude_paycheck_id is not None and paycheck.id == exclude_paycheck_id:
            continue
        if paycheck.occurrence_date is not None:
            linked.add(paycheck.occurrence_date)
    return linked


def unmatched_paydays(
    source: PaySource,
    paychecks: list[Paycheck],
    start: date,
    end: date,
    exclude_paycheck_id: int | None = None,
) -> list[date]:
    if source.id is None:
        return generate_paydays(source, start, end)
    taken = linked_occurrence_dates(source.id, paychecks, exclude_paycheck_id)
    return [d for d in generate_paydays(source, start, end) if d not in taken]


def paycheck_for_occurrence(
    source_id: int, occurrence_date: date, paychecks: list[Paycheck]
) -> Paycheck | None:
    for paycheck in paychecks:
        if paycheck.source_id == source_id and paycheck.occurrence_date == occurrence_date:
            return paycheck
    return None


def match_paycheck_to_payday(
    source_id: int,
    payday: date,
    paychecks: list[Paycheck],
    used_ids: set[int],
) -> Paycheck | None:
    """Link a scheduled payday to at most one paycheck.

    Prefer an explicit occurrence_date. Otherwise take the closest unlinked
    deposit within AUTO_LINK_TOLERANCE_DAYS so expected + actual are never
    both counted for the same payday.
    """
    for paycheck in paychecks:
        if paycheck.source_id != source_id:
            continue
        if paycheck.id is not None and paycheck.id in used_ids:
            continue
        if paycheck.occurrence_date == payday:
            return paycheck
    candidates: list[Paycheck] = []
    for paycheck in paychecks:
        if paycheck.source_id != source_id:
            continue
        if paycheck.id is not None and paycheck.id in used_ids:
            continue
        if paycheck.occurrence_date is not None:
            continue
        if abs((paycheck.date - payday).days) <= AUTO_LINK_TOLERANCE_DAYS:
            candidates.append(paycheck)
    if not candidates:
        return None
    return min(
        candidates, key=lambda paycheck: (abs((paycheck.date - payday).days), paycheck.date)
    )


def suggest_link(
    source: PaySource,
    paycheck_date: date,
    paychecks: list[Paycheck],
    start: date,
    end: date,
    exclude_paycheck_id: int | None = None,
) -> date | None:
    candidates = [
        payday
        for payday in unmatched_paydays(
            source, paychecks, start, end, exclude_paycheck_id
        )
        if abs((payday - paycheck_date).days) <= AUTO_LINK_TOLERANCE_DAYS
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda payday: (abs((payday - paycheck_date).days), payday))
