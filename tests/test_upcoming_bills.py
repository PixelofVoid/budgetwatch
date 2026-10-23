from datetime import date

from budgetwatch.models.entities import BillCategory, EstimateMode
from budgetwatch.services.bills import (
    BILL_RANGE_14D,
    BILL_RANGE_MONTH,
    upcoming_bill_items,
)
from budgetwatch.services.rollup import occurrences_index
from helpers import add_bill


def test_upcoming_bills_overdue_first_then_this_week(db):
    as_of = date(2026, 9, 15)
    add_bill(
        db,
        name="Internet",
        amount_estimate="65.42",
        due_day=1,
        category=BillCategory.UTILITIES,
    )
    add_bill(
        db,
        name="Electric",
        amount_estimate="264",
        due_day=15,
        category=BillCategory.UTILITIES,
        variable=True,
        estimate_mode=EstimateMode.AVERAGE_ACTUALS,
    )
    add_bill(
        db,
        name="Phone",
        amount_estimate="195",
        due_day=29,
        category=BillCategory.OTHER,
    )
    items = upcoming_bill_items(
        db.bills.list_all(),
        occurrences_index(db.occurrences.list_all()),
        as_of,
        BILL_RANGE_14D,
    )
    names = [item.name for item in items]
    assert "Internet" in names
    internet = next(
        item
        for item in items
        if item.name == "Internet" and item.due_date == date(2026, 9, 1)
    )
    assert internet.group == "overdue"
    electric = next(item for item in items if item.name == "Electric" and item.due_date == as_of)
    assert electric.group == "this_week"
    assert electric.variable
    assert items[0].group == "overdue"
    phone = [item for item in items if item.name == "Phone"]
    assert phone
    assert all(item.due_date >= as_of or item.group == "overdue" for item in items)


def test_upcoming_empty_range_can_still_show_overdue(db):
    as_of = date(2026, 9, 20)
    add_bill(db, name="Old", amount_estimate="10", due_day=1)
    items = upcoming_bill_items(
        db.bills.list_all(),
        {},
        as_of,
        BILL_RANGE_14D,
    )
    assert items
    assert items[0].group == "overdue"


def test_this_month_range_includes_month_end_bills(db):
    as_of = date(2026, 9, 15)
    add_bill(db, name="Phone", amount_estimate="195", due_day=29)
    items = upcoming_bill_items(
        db.bills.list_all(), {}, as_of, BILL_RANGE_MONTH
    )
    assert any(item.name == "Phone" and item.due_date == date(2026, 9, 29) for item in items)
