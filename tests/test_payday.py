from datetime import date

from budgetwatch.models.entities import PayFrequency, PaySource
from budgetwatch.services.calendar_math import projection_window
from budgetwatch.services.payday import (
    generate_paydays,
    needs_anchor,
    suggest_link,
    unmatched_paydays,
)
from helpers import AS_OF, add_check, add_source


def test_weekly_and_biweekly_same_household_in_september(db):
    mine = add_source(
        db,
        name="My paycheck",
        frequency=PayFrequency.BIWEEKLY,
        anchor_date=date(2026, 9, 1),
    )
    spouse = add_source(
        db,
        name="Spouse paycheck",
        frequency=PayFrequency.WEEKLY,
        anchor_date=date(2026, 9, 1),
    )
    start, end = date(2026, 9, 1), date(2026, 9, 30)
    biweekly = generate_paydays(mine, start, end)
    weekly = generate_paydays(spouse, start, end)
    assert biweekly == [date(2026, 9, 1), date(2026, 9, 15), date(2026, 9, 29)]
    assert weekly == [
        date(2026, 9, 1),
        date(2026, 9, 8),
        date(2026, 9, 15),
        date(2026, 9, 22),
        date(2026, 9, 29),
    ]
    assert len(biweekly) == 3
    assert len(weekly) == 5


def test_projection_includes_lookback_and_six_months(db):
    source = add_source(
        db, frequency=PayFrequency.WEEKLY, anchor_date=date(2026, 9, 1)
    )
    start, end = projection_window(AS_OF)
    paydays = generate_paydays(source, start, end)
    assert paydays[0] == date(2026, 9, 1)
    assert paydays[-1] == date(2027, 2, 23)
    assert date(2027, 2, 23) <= end


def test_missing_anchor_yields_no_paydays():
    source = PaySource(name="My paycheck", frequency=PayFrequency.BIWEEKLY)
    assert needs_anchor(source)
    assert generate_paydays(source, date(2026, 9, 1), date(2026, 9, 30)) == []


def test_irregular_has_no_schedule():
    source = PaySource(
        name="Extra / irregular",
        frequency=PayFrequency.IRREGULAR,
        anchor_date=date(2026, 9, 1),
    )
    assert not needs_anchor(source)
    assert generate_paydays(source, date(2026, 9, 1), date(2026, 9, 30)) == []


def test_semimonthly_and_monthly_pay_sources():
    semi = PaySource(
        name="Semi",
        frequency=PayFrequency.SEMIMONTHLY,
        anchor_date=date(2026, 9, 1),
        active=True,
    )
    monthly = PaySource(
        name="Monthly",
        frequency=PayFrequency.MONTHLY,
        anchor_date=date(2026, 9, 15),
        active=True,
    )
    start, end = date(2026, 9, 1), date(2026, 10, 31)
    assert generate_paydays(semi, start, end) == [
        date(2026, 9, 1),
        date(2026, 9, 16),
        date(2026, 10, 1),
        date(2026, 10, 16),
    ]
    assert generate_paydays(monthly, start, end) == [
        date(2026, 9, 15),
        date(2026, 10, 15),
    ]


def test_auto_link_within_three_days(db):
    source = add_source(
        db, frequency=PayFrequency.BIWEEKLY, anchor_date=date(2026, 9, 1)
    )
    start, end = date(2026, 9, 1), date(2026, 9, 30)
    linked = suggest_link(source, date(2026, 9, 17), [], start, end)
    assert linked == date(2026, 9, 15)
    add_check(
        db,
        source.id,
        date(2026, 9, 15),
        "2000",
        occurrence_date=date(2026, 9, 15),
    )
    checks = db.paychecks.list_all()
    assert suggest_link(source, date(2026, 9, 16), checks, start, end) is None
    leftover = unmatched_paydays(source, checks, start, end)
    assert date(2026, 9, 15) not in leftover
    assert date(2026, 9, 1) in leftover
    assert date(2026, 9, 29) in leftover


def test_auto_link_ignores_dates_outside_tolerance():
    source = PaySource(
        id=1,
        name="Mine",
        frequency=PayFrequency.BIWEEKLY,
        anchor_date=date(2026, 9, 1),
    )
    assert (
        suggest_link(source, date(2026, 9, 20), [], date(2026, 9, 1), date(2026, 9, 30))
        is None
    )


def test_inactive_source_has_no_paydays():
    source = PaySource(
        name="Old job",
        frequency=PayFrequency.WEEKLY,
        anchor_date=date(2026, 9, 1),
        active=False,
    )
    assert generate_paydays(source, date(2026, 9, 1), date(2026, 9, 30)) == []
