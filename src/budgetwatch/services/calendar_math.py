from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

WEEKLY_MONTHLY_FACTOR = Decimal("4.345")
BIWEEKLY_MONTHLY_FACTOR = Decimal("2.172")
DAYS_PER_MONTH = Decimal("30.44")
AUTO_LINK_TOLERANCE_DAYS = 3
LOOKBACK_DAYS = 14
FORWARD_MONTHS = 5
TWOPLACES = Decimal("0.01")


def q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def last_day_of_month(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def projection_window(as_of: date) -> tuple[date, date]:
    """From 14 days ago through the end of the month 5 months after current."""
    start = as_of - timedelta(days=LOOKBACK_DAYS)
    end_month = add_months(month_start(as_of), FORWARD_MONTHS)
    return start, last_day_of_month(end_month)


def six_month_starts(as_of: date) -> list[date]:
    start = month_start(as_of)
    return [add_months(start, i) for i in range(6)]


def month_label(d: date) -> str:
    return d.strftime("%b %y")


def average_window(as_of: date, window_days: int) -> tuple[date, date]:
    return as_of - timedelta(days=window_days), as_of


def interval_dates(anchor: date, step_days: int, start: date, end: date) -> list[date]:
    if step_days <= 0:
        raise ValueError("step_days must be positive")
    if start > end:
        return []
    if anchor >= start:
        steps_back = (anchor - start).days // step_days
        current = anchor - timedelta(days=steps_back * step_days)
    else:
        delta = (start - anchor).days
        steps_forward = (delta + step_days - 1) // step_days
        current = anchor + timedelta(days=steps_forward * step_days)
    dates: list[date] = []
    while current <= end:
        if current >= start:
            dates.append(current)
        current += timedelta(days=step_days)
    return dates


def monthly_dates(day_of_month: int, start: date, end: date) -> list[date]:
    if day_of_month < 1:
        raise ValueError("day_of_month must be >= 1")
    dates: list[date] = []
    cursor = month_start(start)
    while cursor <= end:
        last = monthrange(cursor.year, cursor.month)[1]
        current = date(cursor.year, cursor.month, min(day_of_month, last))
        if start <= current <= end:
            dates.append(current)
        cursor = add_months(cursor, 1)
    return dates


def semimonthly_dates(anchor: date, start: date, end: date) -> list[date]:
    primary = min(anchor.day, 28)
    secondary = primary + 15 if primary <= 15 else primary - 15
    dates: list[date] = []
    cursor = month_start(start)
    while cursor <= end:
        last = monthrange(cursor.year, cursor.month)[1]
        for day in sorted({primary, secondary}):
            current = date(cursor.year, cursor.month, min(day, last))
            if start <= current <= end:
                dates.append(current)
        cursor = add_months(cursor, 1)
    return dates


def every_n_months_dates(
    anchor: date, n_months: int, start: date, end: date
) -> list[date]:
    if n_months <= 0:
        raise ValueError("n_months must be positive")
    months_diff = (start.year - anchor.year) * 12 + (start.month - anchor.month)
    k = months_diff // n_months - 2
    dates: list[date] = []
    while True:
        current = add_months(anchor, k * n_months)
        if current > end:
            break
        if current >= start:
            dates.append(current)
        k += 1
        if k > 10_000:
            break
    return dates


def days_between_inclusive(a: date, b: date) -> int:
    return abs((b - a).days)
