from datetime import date
from decimal import Decimal

from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    BillOccurrence,
    EstimateMode,
)
from budgetwatch.services.bills import (
    generate_bill_dates,
    monthly_equivalent,
    occurrence_amount,
    working_amount,
)
from helpers import add_bill


def test_monthly_bills_use_due_day():
    bill = Bill(
        name="Rent",
        amount_estimate=Decimal("1400"),
        frequency=BillFrequency.MONTHLY,
        due_day=1,
    )
    dates = generate_bill_dates(bill, date(2026, 9, 1), date(2027, 2, 28))
    assert dates == [
        date(2026, 9, 1),
        date(2026, 10, 1),
        date(2026, 11, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
        date(2027, 2, 1),
    ]


def test_yearly_and_quarterly_only_hit_their_months():
    yearly = Bill(
        name="Insurance",
        amount_estimate=Decimal("1200"),
        frequency=BillFrequency.YEARLY,
        next_due_date=date(2026, 12, 15),
        category=BillCategory.INSURANCE,
    )
    quarterly = Bill(
        name="Water",
        amount_estimate=Decimal("90"),
        frequency=BillFrequency.QUARTERLY,
        next_due_date=date(2026, 9, 10),
        category=BillCategory.UTILITIES,
    )
    start, end = date(2026, 9, 1), date(2027, 2, 28)
    assert generate_bill_dates(yearly, start, end) == [date(2026, 12, 15)]
    assert generate_bill_dates(quarterly, start, end) == [
        date(2026, 9, 10),
        date(2026, 12, 10),
    ]


def test_one_time_does_not_contribute_to_typical_month():
    bill = Bill(
        name="Fridge",
        amount_estimate=Decimal("800"),
        frequency=BillFrequency.ONE_TIME,
        next_due_date=date(2026, 10, 5),
    )
    assert monthly_equivalent(bill.frequency, bill.amount_estimate) == Decimal("0.00")
    assert generate_bill_dates(bill, date(2026, 9, 1), date(2027, 2, 28)) == [
        date(2026, 10, 5)
    ]


def test_monthly_equivalent_factors():
    assert monthly_equivalent(BillFrequency.WEEKLY, Decimal("50")) == Decimal("217.25")
    assert monthly_equivalent(BillFrequency.BIWEEKLY, Decimal("100")) == Decimal("217.20")
    assert monthly_equivalent(BillFrequency.MONTHLY, Decimal("150")) == Decimal("150.00")
    assert monthly_equivalent(BillFrequency.QUARTERLY, Decimal("300")) == Decimal("100.00")
    assert monthly_equivalent(BillFrequency.YEARLY, Decimal("1200")) == Decimal("100.00")


def test_electric_without_actuals_uses_estimate():
    electric = Bill(
        id=1,
        name="Electric",
        amount_estimate=Decimal("150.00"),
        frequency=BillFrequency.MONTHLY,
        due_day=15,
        category=BillCategory.UTILITIES,
        variable=True,
        estimate_mode=EstimateMode.AVERAGE_ACTUALS,
    )
    working = working_amount(electric, [])
    assert working == Decimal("150.00")
    occ = BillOccurrence(bill_id=1, due_date=date(2026, 9, 15))
    assert occurrence_amount(electric, occ, working) == Decimal("150.00")


def test_electric_with_actuals_uses_average_and_prefers_logged_actual():
    electric = Bill(
        id=1,
        name="Electric",
        amount_estimate=Decimal("150.00"),
        frequency=BillFrequency.MONTHLY,
        due_day=15,
        category=BillCategory.UTILITIES,
        variable=True,
        estimate_mode=EstimateMode.AVERAGE_ACTUALS,
        average_actuals_n=6,
    )
    history = [
        BillOccurrence(
            bill_id=1, due_date=date(2026, 4, 15), amount_actual=Decimal("100.00")
        ),
        BillOccurrence(
            bill_id=1, due_date=date(2026, 5, 15), amount_actual=Decimal("120.00")
        ),
        BillOccurrence(
            bill_id=1, due_date=date(2026, 6, 15), amount_actual=Decimal("140.00")
        ),
    ]
    working = working_amount(electric, history)
    assert working == Decimal("120.00")
    open_occ = BillOccurrence(bill_id=1, due_date=date(2026, 9, 15))
    assert occurrence_amount(electric, open_occ, working) == Decimal("120.00")
    logged = BillOccurrence(
        bill_id=1, due_date=date(2026, 9, 15), amount_actual=Decimal("200.00")
    )
    assert occurrence_amount(electric, logged, working) == Decimal("200.00")


def test_one_actual_is_not_enough_to_replace_estimate():
    electric = Bill(
        id=1,
        name="Electric",
        amount_estimate=Decimal("150.00"),
        frequency=BillFrequency.MONTHLY,
        variable=True,
        estimate_mode=EstimateMode.AVERAGE_ACTUALS,
    )
    history = [
        BillOccurrence(
            bill_id=1, due_date=date(2026, 8, 15), amount_actual=Decimal("90.00")
        )
    ]
    assert working_amount(electric, history) == Decimal("150.00")


def test_fixed_bills_ignore_average_mode():
    rent = Bill(
        id=2,
        name="Rent",
        amount_estimate=Decimal("1400"),
        frequency=BillFrequency.MONTHLY,
        due_day=1,
        variable=False,
        estimate_mode=EstimateMode.AVERAGE_ACTUALS,
    )
    history = [
        BillOccurrence(
            bill_id=2, due_date=date(2026, 8, 1), amount_actual=Decimal("999")
        ),
        BillOccurrence(
            bill_id=2, due_date=date(2026, 7, 1), amount_actual=Decimal("999")
        ),
    ]
    assert working_amount(rent, history) == Decimal("1400.00")


def test_inactive_bill_has_no_dates():
    bill = Bill(
        name="Old",
        amount_estimate=Decimal("10"),
        frequency=BillFrequency.MONTHLY,
        due_day=1,
        active=False,
    )
    assert generate_bill_dates(bill, date(2026, 9, 1), date(2026, 9, 30)) == []


def test_bill_repository_roundtrip(db):
    bill = add_bill(
        db,
        name="Electric",
        amount_estimate="150",
        frequency=BillFrequency.MONTHLY,
        due_day=12,
        category=BillCategory.UTILITIES,
        variable=True,
        estimate_mode=EstimateMode.AVERAGE_ACTUALS,
    )
    loaded = db.bills.get(bill.id)
    assert loaded is not None
    assert loaded.variable
    assert loaded.estimate_mode == EstimateMode.AVERAGE_ACTUALS
    assert loaded.due_day == 12
