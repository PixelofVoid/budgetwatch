from datetime import date
from decimal import Decimal

from budgetwatch.models.entities import PayFrequency, Paycheck
from helpers import AS_OF, add_source


def test_create_paycheck_auto_links_nearby_payday(service, db):
    source = add_source(
        db,
        name="My paycheck",
        frequency=PayFrequency.BIWEEKLY,
        anchor_date=date(2026, 9, 1),
    )
    db.commit()
    seen = []
    service.bus.subscribe(lambda: seen.append(True))
    created = service.create_paycheck(
        Paycheck(
            source_id=source.id,
            date=date(2026, 9, 17),
            amount=Decimal("2100.00"),
        ),
        as_of=AS_OF,
    )
    assert created.occurrence_date == date(2026, 9, 15)
    assert seen == [True]


def test_unlink_stays_unlinked(service, db):
    source = add_source(
        db,
        frequency=PayFrequency.BIWEEKLY,
        anchor_date=date(2026, 9, 1),
    )
    db.commit()
    created = service.create_paycheck(
        Paycheck(
            source_id=source.id,
            date=date(2026, 9, 16),
            amount=Decimal("2000.00"),
            occurrence_date=None,
        ),
        auto_link=False,
        as_of=AS_OF,
    )
    assert created.occurrence_date is None
