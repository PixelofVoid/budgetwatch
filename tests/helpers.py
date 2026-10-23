from datetime import date
from decimal import Decimal

from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    EstimateMode,
    PayFrequency,
    PaySource,
    Paycheck,
    Settings,
)

AS_OF = date(2026, 9, 15)


def add_source(db, **kwargs) -> PaySource:
    source = PaySource(
        name=kwargs.get("name", "Job"),
        frequency=kwargs.get("frequency", PayFrequency.BIWEEKLY),
        anchor_date=kwargs.get("anchor_date"),
        amount_override=kwargs.get("amount_override"),
        include_in_typical=kwargs.get("include_in_typical", True),
        active=kwargs.get("active", True),
    )
    return db.sources.insert(source)


def add_check(db, source_id: int, when: date, amount, **kwargs) -> Paycheck:
    paycheck = Paycheck(
        source_id=source_id,
        date=when,
        amount=Decimal(str(amount)),
        include_in_average=kwargs.get("include_in_average", True),
        occurrence_date=kwargs.get("occurrence_date"),
        notes=kwargs.get("notes", ""),
    )
    return db.paychecks.insert(paycheck)


def add_bill(db, **kwargs) -> Bill:
    bill = Bill(
        name=kwargs.get("name", "Rent"),
        amount_estimate=Decimal(str(kwargs.get("amount_estimate", "1200"))),
        frequency=kwargs.get("frequency", BillFrequency.MONTHLY),
        due_day=kwargs.get("due_day", 1),
        next_due_date=kwargs.get("next_due_date"),
        category=kwargs.get("category", BillCategory.HOUSING),
        variable=kwargs.get("variable", False),
        estimate_mode=kwargs.get("estimate_mode", EstimateMode.MANUAL),
        average_actuals_n=kwargs.get("average_actuals_n", 6),
        active=kwargs.get("active", True),
        notes=kwargs.get("notes", ""),
    )
    return db.bills.insert(bill)


def settings(window=90, savings="0", symbol="$") -> Settings:
    return Settings(
        average_window_days=window,
        savings_target_monthly=Decimal(str(savings)),
        currency_symbol=symbol,
    )
