from __future__ import annotations

from datetime import date
from decimal import Decimal

from budgetwatch.models.entities import (
    PayFrequency,
    PaySource,
    Paycheck,
    RecipePart,
    Settings,
    TypicalIncomeResult,
)
from budgetwatch.services.calendar_math import (
    BIWEEKLY_MONTHLY_FACTOR,
    DAYS_PER_MONTH,
    WEEKLY_MONTHLY_FACTOR,
    average_window,
    q2,
)


def next_income_name(existing_names: list[str]) -> str:
    used: set[int] = set()
    for name in existing_names:
        text = (name or "").strip()
        if text.lower().startswith("income "):
            suffix = text[7:].strip()
            if suffix.isdigit():
                used.add(int(suffix))
    n = 1
    while n in used:
        n += 1
    return f"Income {n}"


def income_labels(sources: list[PaySource]) -> dict[int, str]:
    """Stable Income 1, Income 2, … labels in id order."""
    labels: dict[int, str] = {}
    index = 0
    for source in sources:
        if source.id is None:
            continue
        index += 1
        label = f"Income {index}"
        if not source.active:
            label += " (inactive)"
        labels[source.id] = label
    return labels


def included_in_window(
    paychecks: list[Paycheck],
    source_id: int | None,
    window_start: date,
    window_end: date,
) -> list[Paycheck]:
    result = []
    for paycheck in paychecks:
        if not paycheck.include_in_average:
            continue
        if source_id is not None and paycheck.source_id != source_id:
            continue
        if window_start <= paycheck.date <= window_end:
            result.append(paycheck)
    return result


def source_average(
    source: PaySource,
    paychecks: list[Paycheck],
    window_start: date,
    window_end: date,
) -> Decimal | None:
    if source.id is None:
        return None
    checks = included_in_window(paychecks, source.id, window_start, window_end)
    if len(checks) < 2:
        return None
    total = sum((c.amount for c in checks), Decimal("0"))
    return q2(total / Decimal(len(checks)))


def expected_payday_amount(
    source: PaySource, average: Decimal | None
) -> Decimal | None:
    if source.amount_override is not None:
        return q2(source.amount_override)
    return average


def typical_monthly_from_average(
    frequency: PayFrequency,
    average: Decimal,
    *,
    window_sum: Decimal | None = None,
    window_days: int | None = None,
) -> Decimal:
    if frequency == PayFrequency.WEEKLY:
        return q2(average * WEEKLY_MONTHLY_FACTOR)
    if frequency == PayFrequency.BIWEEKLY:
        return q2(average * BIWEEKLY_MONTHLY_FACTOR)
    if frequency == PayFrequency.SEMIMONTHLY:
        return q2(average * Decimal("2"))
    if frequency == PayFrequency.MONTHLY:
        return q2(average)
    if frequency == PayFrequency.IRREGULAR:
        if window_sum is None or not window_days:
            raise ValueError("irregular typical income needs window_sum and window_days")
        return q2((window_sum / Decimal(window_days)) * DAYS_PER_MONTH)
    return q2(average)


def typical_income(
    sources: list[PaySource],
    paychecks: list[Paycheck],
    settings: Settings,
    as_of: date,
) -> TypicalIncomeResult:
    window_start, window_end = average_window(as_of, settings.average_window_days)
    household_checks = included_in_window(paychecks, None, window_start, window_end)
    household_insufficient = len(household_checks) < 2

    parts: list[RecipePart] = []
    unknown_sources: list[str] = []
    total = Decimal("0.00")

    contributing = [
        source
        for source in sources
        if source.active and source.include_in_typical
    ]
    for source in contributing:
        if source.id is None:
            continue
        checks = included_in_window(paychecks, source.id, window_start, window_end)
        average = source_average(source, paychecks, window_start, window_end)
        typical: Decimal | None
        used_average = (
            q2(source.amount_override)
            if source.amount_override is not None
            else average
        )
        unknown = used_average is None
        if source.frequency == PayFrequency.IRREGULAR:
            if source.amount_override is not None:
                typical = q2(source.amount_override)
                unknown = False
            elif len(checks) < 2:
                typical = None
                unknown = True
            else:
                window_sum = sum((c.amount for c in checks), Decimal("0"))
                typical = typical_monthly_from_average(
                    source.frequency,
                    average or Decimal("0"),
                    window_sum=window_sum,
                    window_days=settings.average_window_days,
                )
                unknown = False
        elif unknown:
            typical = None
        else:
            typical = typical_monthly_from_average(source.frequency, used_average)

        if unknown:
            unknown_sources.append(source.name)
        elif typical is not None:
            total += typical

        parts.append(
            RecipePart(
                source_name=source.name,
                frequency=source.frequency,
                average=used_average if source.amount_override is not None else average,
                typical_monthly=typical,
                unknown=unknown,
                check_count=len(checks),
            )
        )

    if unknown_sources:
        return TypicalIncomeResult(
            total=None,
            is_complete=False,
            household_insufficient=household_insufficient,
            unknown_sources=unknown_sources,
            parts=parts,
            included_check_count=len(household_checks),
        )
    return TypicalIncomeResult(
        total=q2(total),
        is_complete=True,
        household_insufficient=household_insufficient,
        unknown_sources=[],
        parts=parts,
        included_check_count=len(household_checks),
    )


def income_recipe(parts: list[RecipePart], symbol: str) -> str:
    if not parts:
        return "No active pay sources included in typical income."
    chunks = []
    for part in parts:
        if part.unknown:
            chunks.append(f"Not enough data for {part.source_name}")
        else:
            avg = part.average if part.average is not None else Decimal("0.00")
            chunks.append(
                f"{part.source_name} {symbol}{avg:,.2f} {part.frequency.value} avg"
            )
    return " + ".join(chunks)
