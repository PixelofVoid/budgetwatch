from datetime import date
from decimal import Decimal

from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    BillOccurrence,
    LedgerEntry,
    PayFrequency,
)
from budgetwatch.services.calendar_math import q2
from budgetwatch.services.planning import category_actual, occurrences_index
from budgetwatch.services.rollup import calendar_month, typical_bills
from helpers import AS_OF, add_bill, add_check, add_source, settings


def test_existing_bill_ids_still_load(service, db):
    first = service.create_bill(
        Bill(
            name="KeepMe",
            amount_estimate=Decimal("10.00"),
            frequency=BillFrequency.MONTHLY,
            due_day=1,
            category=BillCategory.HOUSING,
        )
    )
    bill_id = first.id
    loaded = service.get_bill(bill_id)
    assert loaded is not None
    assert loaded.id == bill_id
    assert loaded.name == "KeepMe"


def test_groceries_and_debt_still_subtract(db):
    add_bill(
        db,
        name="Groceries",
        amount_estimate="100",
        frequency=BillFrequency.WEEKLY,
        due_day=None,
        next_due_date=date(2026, 9, 1),
        category=BillCategory.GROCERIES,
        variable=True,
    )
    add_bill(
        db,
        name="Card payment",
        amount_estimate="200",
        frequency=BillFrequency.MONTHLY,
        due_day=5,
        category=BillCategory.DEBT,
    )
    typical = typical_bills(db.bills.list_all(), {})
    # 100 * 4.345 + 200
    assert typical.total == Decimal("634.50")
    month = calendar_month(
        date(2026, 9, 1), [], [], db.bills.list_all(), {}, settings(), AS_OF
    )
    assert month.bills >= Decimal("200.00")
    assert any(i.bill_name == "Groceries" for i in month.bill_items)
    assert any(i.bill_name == "Card payment" for i in month.bill_items)


def test_leftover_identity_still_holds(service, db):
    add_source(
        db,
        name="Job",
        frequency=PayFrequency.MONTHLY,
        anchor_date=date(2026, 9, 1),
        amount_override=Decimal("3000"),
    )
    add_bill(db, name="Rent", amount_estimate="1000", due_day=1)
    db.commit()
    overview = service.overview(as_of=AS_OF)
    assert overview.typical_income.total is not None
    assert overview.leftover_after_bills == q2(
        overview.typical_income.total - overview.typical_bills
    )
    month = overview.this_month
    assert month.leftover == q2(month.income - month.bills)


def test_paid_occurrence_and_linked_transaction_count_once(service):
    bill = service.create_bill(
        Bill(
            name="Phone",
            amount_estimate=Decimal("50.00"),
            frequency=BillFrequency.MONTHLY,
            due_day=15,
            category=BillCategory.OTHER,
        )
    )
    occ = service.set_bill_actual(
        bill.id,
        date(2026, 9, 15),
        amount_actual=Decimal("50.00"),
        paid=True,
    )
    service.create_transaction(
        LedgerEntry(
            date=date(2026, 9, 15),
            payee="Phone",
            amount=Decimal("50.00"),
            category=BillCategory.OTHER,
            kind="expense",
            occurrence_id=occ.id,
        )
    )
    actual = category_actual(
        BillCategory.OTHER,
        2026,
        9,
        service.list_bills(),
        occurrences_index(service.list_occurrences()),
        service.list_transactions(),
    )
    assert actual == Decimal("50.00")
