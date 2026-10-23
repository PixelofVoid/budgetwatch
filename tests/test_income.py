from datetime import date
from decimal import Decimal

from budgetwatch.models.entities import PayFrequency, PaySource
from budgetwatch.services.calendar_math import q2
from budgetwatch.services.income import (
    expected_payday_amount,
    income_labels,
    income_recipe,
    next_income_name,
    source_average,
    typical_income,
)
from helpers import AS_OF, add_check, add_source, settings


def test_next_income_name_fills_gaps():
    assert next_income_name([]) == "Income 1"
    assert next_income_name(["Income 1"]) == "Income 2"
    assert next_income_name(["Income 1", "Income 2"]) == "Income 3"
    assert next_income_name(["Income 1", "Income 3"]) == "Income 2"


def test_income_labels_number_sources_in_id_order():
    sources = [
        PaySource(id=1, name="My paycheck", frequency=PayFrequency.BIWEEKLY),
        PaySource(id=2, name="Spouse paycheck", frequency=PayFrequency.WEEKLY),
    ]
    assert income_labels(sources) == {1: "Income 1", 2: "Income 2"}
    sources[1].active = False
    assert income_labels(sources)[2] == "Income 2 (inactive)"


def test_average_needs_two_included_checks(db):
    source = add_source(db, name="My paycheck", frequency=PayFrequency.BIWEEKLY)
    add_check(db, source.id, date(2026, 9, 1), "2000")
    checks = db.paychecks.list_all()
    assert source_average(source, checks, date(2026, 6, 17), AS_OF) is None
    add_check(db, source.id, date(2026, 8, 18), "2200")
    checks = db.paychecks.list_all()
    assert source_average(source, checks, date(2026, 6, 17), AS_OF) == Decimal("2100.00")


def test_excluded_checks_are_ignored(db):
    source = add_source(db, frequency=PayFrequency.WEEKLY)
    add_check(db, source.id, date(2026, 9, 1), "800")
    add_check(db, source.id, date(2026, 9, 8), "9999", include_in_average=False)
    add_check(db, source.id, date(2026, 9, 15), "900")
    avg = source_average(source, db.paychecks.list_all(), date(2026, 6, 17), AS_OF)
    assert avg == Decimal("850.00")


def test_override_used_for_typical_monthly_without_two_checks(db):
    source = add_source(
        db,
        name="My paycheck",
        frequency=PayFrequency.BIWEEKLY,
        amount_override=Decimal("2000.00"),
    )
    add_check(db, source.id, date(2026, 9, 1), "1800")
    result = typical_income(
        db.sources.list_all(), db.paychecks.list_all(), settings(), AS_OF
    )
    assert result.is_complete
    assert result.total == q2(Decimal("2000") * Decimal("2.172"))
    assert result.parts[0].average == Decimal("2000.00")


def test_override_used_for_expected_even_without_average(db):
    source = add_source(
        db,
        frequency=PayFrequency.BIWEEKLY,
        amount_override=Decimal("2000.00"),
    )
    assert expected_payday_amount(source, None) == Decimal("2000.00")
    assert expected_payday_amount(source, Decimal("1800.00")) == Decimal("2000.00")


def test_typical_income_weekly_plus_biweekly(db):
    mine = add_source(
        db, name="My paycheck", frequency=PayFrequency.BIWEEKLY
    )
    spouse = add_source(
        db, name="Spouse paycheck", frequency=PayFrequency.WEEKLY
    )
    add_check(db, mine.id, date(2026, 8, 18), "2000")
    add_check(db, mine.id, date(2026, 9, 1), "2000")
    add_check(db, spouse.id, date(2026, 8, 25), "800")
    add_check(db, spouse.id, date(2026, 9, 1), "800")
    result = typical_income(
        db.sources.list_all(), db.paychecks.list_all(), settings(), AS_OF
    )
    assert result.is_complete
    assert result.total == q2(Decimal("2000") * Decimal("2.172") + Decimal("800") * Decimal("4.345"))
    assert result.total == Decimal("7820.00")
    recipe = income_recipe(result.parts, "$")
    assert "My paycheck $2,000.00 biweekly avg" in recipe
    assert "Spouse paycheck $800.00 weekly avg" in recipe


def test_household_under_two_checks_is_unknown(db):
    mine = add_source(db, name="My paycheck", frequency=PayFrequency.BIWEEKLY)
    add_check(db, mine.id, date(2026, 9, 1), "2000")
    result = typical_income(
        db.sources.list_all(), db.paychecks.list_all(), settings(), AS_OF
    )
    assert not result.is_complete
    assert result.household_insufficient
    assert result.total is None


def test_source_without_two_checks_does_not_count_as_zero(db):
    mine = add_source(db, name="My paycheck", frequency=PayFrequency.BIWEEKLY)
    spouse = add_source(db, name="Spouse paycheck", frequency=PayFrequency.WEEKLY)
    add_check(db, mine.id, date(2026, 8, 18), "2000")
    add_check(db, mine.id, date(2026, 9, 1), "2000")
    result = typical_income(
        db.sources.list_all(), db.paychecks.list_all(), settings(), AS_OF
    )
    assert result.total is None
    assert "Spouse paycheck" in result.unknown_sources
    recipe = income_recipe(result.parts, "$")
    assert "Not enough data for Spouse paycheck" in recipe


def test_irregular_uses_window_sum_over_days(db):
    extra = add_source(
        db, name="Extra / irregular", frequency=PayFrequency.IRREGULAR
    )
    add_check(db, extra.id, date(2026, 7, 1), "500")
    add_check(db, extra.id, date(2026, 8, 1), "700")
    add_check(db, extra.id, date(2026, 9, 1), "300")
    result = typical_income(
        db.sources.list_all(), db.paychecks.list_all(), settings(window=90), AS_OF
    )
    expected = q2((Decimal("1500") / Decimal("90")) * Decimal("30.44"))
    assert result.total == expected
    assert result.is_complete


def test_inactive_or_excluded_sources_skipped(db):
    mine = add_source(db, name="My paycheck", frequency=PayFrequency.BIWEEKLY)
    add_source(
        db,
        name="Old job",
        frequency=PayFrequency.WEEKLY,
        active=False,
    )
    skipped = add_source(
        db,
        name="Bonus",
        frequency=PayFrequency.IRREGULAR,
        include_in_typical=False,
    )
    add_check(db, mine.id, date(2026, 8, 18), "2000")
    add_check(db, mine.id, date(2026, 9, 1), "2000")
    add_check(db, skipped.id, date(2026, 8, 1), "5000")
    add_check(db, skipped.id, date(2026, 9, 1), "5000")
    result = typical_income(
        db.sources.list_all(), db.paychecks.list_all(), settings(), AS_OF
    )
    assert result.is_complete
    assert result.total == q2(Decimal("2000") * Decimal("2.172"))
    assert [p.source_name for p in result.parts] == ["My paycheck"]
