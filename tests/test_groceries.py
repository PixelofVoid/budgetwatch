from datetime import date
from decimal import Decimal
from pathlib import Path

from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    BillOccurrence,
    EstimateMode,
)
from budgetwatch.services.bills import monthly_equivalent
from budgetwatch.services.calendar_math import WEEKLY_MONTHLY_FACTOR, q2
from budgetwatch.services.export import export_bills
from budgetwatch.services.rollup import calendar_month, typical_bills
from helpers import AS_OF, add_bill, settings


def test_category_list_includes_groceries_in_order():
    assert [c.value for c in BillCategory] == [
        "housing",
        "utilities",
        "groceries",
        "insurance",
        "debt",
        "subscriptions",
        "transport",
        "other",
    ]


def test_save_groceries_bill(service):
    created = service.create_bill(
        Bill(
            name="Groceries",
            amount_estimate=Decimal("150.00"),
            frequency=BillFrequency.WEEKLY,
            next_due_date=date(2026, 9, 4),
            category=BillCategory.GROCERIES,
            variable=True,
            estimate_mode=EstimateMode.AVERAGE_ACTUALS,
        )
    )
    loaded = service.get_bill(created.id)
    assert loaded is not None
    assert loaded.category == BillCategory.GROCERIES
    assert loaded.frequency == BillFrequency.WEEKLY
    assert loaded.variable is True
    assert loaded.estimate_mode == EstimateMode.AVERAGE_ACTUALS
    assert loaded.amount_estimate == Decimal("150.00")


def test_old_bill_categories_still_load(db):
    for name, category in (
        ("Rent", "housing"),
        ("Power", "utilities"),
        ("Insure", "insurance"),
        ("Loan", "debt"),
        ("Stream", "subscriptions"),
        ("Bus", "transport"),
        ("Misc", "other"),
    ):
        db.conn.execute(
            "INSERT INTO bills (name, amount_estimate, frequency, category) "
            "VALUES (?, '10.00', 'monthly', ?)",
            (name, category),
        )
    db.commit()
    loaded = {bill.name: bill.category.value for bill in db.bills.list_all()}
    assert loaded["Rent"] == "housing"
    assert loaded["Power"] == "utilities"
    assert loaded["Insure"] == "insurance"
    assert loaded["Loan"] == "debt"
    assert loaded["Stream"] == "subscriptions"
    assert loaded["Bus"] == "transport"
    assert loaded["Misc"] == "other"


def test_unknown_category_falls_back_to_other(db):
    db.conn.execute(
        "INSERT INTO bills (name, amount_estimate, frequency, category) "
        "VALUES ('Legacy', '10.00', 'monthly', 'legacy_bucket')"
    )
    db.commit()
    bill = db.bills.list_all()[0]
    assert bill.category == BillCategory.OTHER


def test_weekly_groceries_in_typical_and_calendar_leftover(db):
    add_bill(
        db,
        name="Groceries",
        amount_estimate="100",
        frequency=BillFrequency.WEEKLY,
        due_day=None,
        next_due_date=date(2026, 9, 1),
        category=BillCategory.GROCERIES,
        variable=True,
        estimate_mode=EstimateMode.AVERAGE_ACTUALS,
    )
    bills = db.bills.list_all()
    typical = typical_bills(bills, {})
    assert typical.total == q2(Decimal("100") * WEEKLY_MONTHLY_FACTOR)
    assert typical.total == Decimal("434.50")
    month = calendar_month(
        date(2026, 9, 1),
        [],
        [],
        bills,
        {},
        settings(),
        AS_OF,
    )
    # Sep 1, 8, 15, 22, 29
    assert month.bills == Decimal("500.00")
    assert month.leftover == Decimal("-500.00")
    assert all(item.bill_name == "Groceries" for item in month.bill_items)


def test_groceries_actual_replaces_estimate_and_inactive_drops_out(service, db):
    created = service.create_bill(
        Bill(
            name="Groceries",
            amount_estimate=Decimal("100.00"),
            frequency=BillFrequency.WEEKLY,
            next_due_date=date(2026, 9, 1),
            category=BillCategory.GROCERIES,
            variable=True,
            estimate_mode=EstimateMode.AVERAGE_ACTUALS,
        )
    )
    service.set_bill_actual(
        created.id,
        date(2026, 9, 1),
        amount_actual=Decimal("80.00"),
        paid=True,
    )
    occ_index = {created.id: service.list_occurrences(created.id)}
    month = calendar_month(
        date(2026, 9, 1),
        [],
        [],
        service.list_bills(),
        occ_index,
        settings(),
        AS_OF,
    )
    assert month.bills == Decimal("480.00")  # 80 + 4 * 100
    first = [item for item in month.bill_items if item.due_date == date(2026, 9, 1)][0]
    assert first.actual == Decimal("80.00")
    assert first.amount == Decimal("80.00")

    created.active = False
    service.update_bill(created)
    typical = typical_bills(service.list_bills(), occ_index)
    month_off = calendar_month(
        date(2026, 9, 1),
        [],
        [],
        service.list_bills(),
        occ_index,
        settings(),
        AS_OF,
    )
    assert typical.total == Decimal("0.00")
    assert month_off.bills == Decimal("0.00")


def test_csv_export_includes_groceries_category(service, tmp_path):
    service.create_bill(
        Bill(
            name="Groceries",
            amount_estimate=Decimal("75.00"),
            frequency=BillFrequency.WEEKLY,
            next_due_date=date(2026, 9, 4),
            category=BillCategory.GROCERIES,
            variable=True,
            estimate_mode=EstimateMode.AVERAGE_ACTUALS,
        )
    )
    path = Path(tmp_path) / "bills.csv"
    export_bills(path, service.list_bills())
    text = path.read_text(encoding="utf-8")
    assert "category" in text.splitlines()[0]
    assert "groceries" in text


def test_weekly_monthly_equivalent_uses_existing_factor():
    assert monthly_equivalent(BillFrequency.WEEKLY, Decimal("100")) == Decimal("434.50")
