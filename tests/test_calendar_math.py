from datetime import date

from budgetwatch.services.calendar_math import (
    add_months,
    average_window,
    every_n_months_dates,
    interval_dates,
    last_day_of_month,
    month_label,
    monthly_dates,
    projection_window,
    semimonthly_dates,
    six_month_starts,
)


def test_last_day_of_month_handles_february():
    assert last_day_of_month(date(2026, 2, 1)) == date(2026, 2, 28)
    assert last_day_of_month(date(2028, 2, 10)) == date(2028, 2, 29)
    assert last_day_of_month(date(2026, 9, 15)) == date(2026, 9, 30)


def test_add_months_clamps_day():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 9, 1), 5) == date(2027, 2, 1)


def test_projection_window_covers_lookback_and_six_months():
    start, end = projection_window(date(2026, 9, 15))
    assert start == date(2026, 9, 1)
    assert end == date(2027, 2, 28)


def test_six_month_starts_and_labels():
    months = six_month_starts(date(2026, 9, 15))
    assert [m.isoformat() for m in months] == [
        "2026-09-01",
        "2026-10-01",
        "2026-11-01",
        "2026-12-01",
        "2027-01-01",
        "2027-02-01",
    ]
    assert [month_label(m) for m in months] == [
        "Sep 26",
        "Oct 26",
        "Nov 26",
        "Dec 26",
        "Jan 27",
        "Feb 27",
    ]


def test_average_window():
    start, end = average_window(date(2026, 9, 15), 90)
    assert end == date(2026, 9, 15)
    assert start == date(2026, 6, 17)


def test_interval_dates_weekly_and_biweekly():
    weekly = interval_dates(date(2026, 9, 1), 7, date(2026, 9, 1), date(2026, 9, 30))
    assert weekly == [
        date(2026, 9, 1),
        date(2026, 9, 8),
        date(2026, 9, 15),
        date(2026, 9, 22),
        date(2026, 9, 29),
    ]
    biweekly = interval_dates(date(2026, 9, 1), 14, date(2026, 9, 1), date(2026, 9, 30))
    assert biweekly == [
        date(2026, 9, 1),
        date(2026, 9, 15),
        date(2026, 9, 29),
    ]


def test_interval_dates_walks_backward_from_future_anchor():
    dates = interval_dates(date(2026, 9, 29), 14, date(2026, 9, 1), date(2026, 9, 30))
    assert dates == [
        date(2026, 9, 1),
        date(2026, 9, 15),
        date(2026, 9, 29),
    ]


def test_monthly_dates_clamp_to_month_length():
    dates = monthly_dates(31, date(2026, 1, 1), date(2026, 3, 31))
    assert dates == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]


def test_semimonthly_from_first():
    dates = semimonthly_dates(date(2026, 9, 1), date(2026, 9, 1), date(2026, 9, 30))
    assert dates == [date(2026, 9, 1), date(2026, 9, 16)]


def test_semimonthly_fifteenth_uses_last_day_in_short_month():
    dates = semimonthly_dates(date(2026, 1, 15), date(2026, 2, 1), date(2026, 2, 28))
    assert dates == [date(2026, 2, 15), date(2026, 2, 28)]


def test_every_n_months_quarterly_and_yearly():
    quarterly = every_n_months_dates(
        date(2026, 9, 1), 3, date(2026, 9, 1), date(2027, 2, 28)
    )
    assert quarterly == [date(2026, 9, 1), date(2026, 12, 1)]
    yearly = every_n_months_dates(
        date(2026, 12, 15), 12, date(2026, 9, 1), date(2027, 2, 28)
    )
    assert yearly == [date(2026, 12, 15)]
