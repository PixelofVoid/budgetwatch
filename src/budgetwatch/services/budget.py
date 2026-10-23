from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from budgetwatch.db.connection import Database
from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    BillOccurrence,
    EstimateMode,
    LedgerEntry,
    OverviewData,
    Paycheck,
    PaySource,
    Settings,
    UpcomingBillItem,
)
from budgetwatch.services.bills import (
    merge_occurrences,
    monthly_equivalent,
    recent_actual_average,
    upcoming_bill_items,
    working_amount,
)
from budgetwatch.services.bus import DataBus
from budgetwatch.services.calendar_math import (
    month_start,
    projection_window,
    q2,
)
from budgetwatch.services.export import export_all
from budgetwatch.services.income import (
    expected_payday_amount,
    included_in_window,
    income_recipe,
    source_average,
    typical_income,
)
from budgetwatch.services.payday import (
    generate_paydays,
    needs_anchor,
    suggest_link,
)
from budgetwatch.services.rollup import (
    calendar_month,
    occurrences_index,
    six_month_rollups,
    typical_bills,
    upcoming_events,
)


class ValidationError(ValueError):
    pass


def _require_name(name: str, kind: str = "item") -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        if kind == "bill":
            raise ValidationError("Give this bill a name")
        if kind == "source":
            raise ValidationError("Give this pay source a name")
        raise ValidationError("Name is required.")
    return cleaned


def _require_positive_amount(amount: Decimal | int | float | str, label: str = "Amount") -> Decimal:
    try:
        value = q2(Decimal(str(amount)))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError("Enter an amount greater than 0") from exc
    if value <= 0:
        raise ValidationError("Enter an amount greater than 0")
    return value


def _money_or_zero(amount: Decimal | int | float | str) -> Decimal:
    try:
        value = q2(Decimal(str(amount)))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError("Amount must be a number.") from exc
    if value < 0:
        raise ValidationError("Amount cannot be negative.")
    return value


class BudgetService:
    def __init__(self, db: Database):
        self.db = db
        self.bus = DataBus()

    def _changed(self) -> None:
        self.db.commit()
        self.bus.emit()

    def db_path(self) -> Path:
        return self.db.path

    def schema_version(self) -> int:
        from budgetwatch.db.migrate import current_version

        return current_version(self.db.conn)

    def get_pref(self, key: str, default: str | None = None) -> str | None:
        return self.db.settings.get_value(key, default)

    def set_pref(self, key: str, value: str) -> None:
        self.db.settings.set_value(key, value)
        self.db.commit()

    def upcoming_bills(
        self, range_key: str = "14d", *, as_of: date | None = None
    ) -> list[UpcomingBillItem]:
        as_of = as_of or date.today()
        return upcoming_bill_items(
            self.db.bills.list_all(),
            occurrences_index(self.db.occurrences.list_all()),
            as_of,
            range_key,
        )

    def get_settings(self) -> Settings:
        return self.db.settings.get()

    def update_settings(
        self,
        *,
        average_window_days: int | None = None,
        savings_target_monthly: Decimal | int | float | str | None = None,
        currency_symbol: str | None = None,
    ) -> Settings:
        settings = self.get_settings()
        if average_window_days is not None:
            days = int(average_window_days)
            if days < 1:
                raise ValidationError("Average window must be at least 1 day.")
            settings.average_window_days = days
        if savings_target_monthly is not None:
            settings.savings_target_monthly = _money_or_zero(savings_target_monthly)
        if currency_symbol is not None:
            symbol = currency_symbol.strip()
            if not symbol:
                raise ValidationError("Currency symbol is required.")
            settings.currency_symbol = symbol[:4]
        self.db.settings.update(settings)
        self._changed()
        return settings

    def list_sources(self) -> list[PaySource]:
        return self.db.sources.list_all()

    def get_source(self, source_id: int) -> PaySource | None:
        return self.db.sources.get(source_id)

    def create_source(self, source: PaySource) -> PaySource:
        source.name = _require_name(source.name, "source")
        if source.amount_override is not None:
            source.amount_override = _require_positive_amount(
                source.amount_override, "Amount override"
            )
        if source.anchor_date is not None:
            source.weekday = source.anchor_date.weekday()
        created = self.db.sources.insert(source)
        self._changed()
        return created

    def update_source(self, source: PaySource) -> PaySource:
        if source.id is None:
            raise ValidationError("Pay source is missing an id.")
        source.name = _require_name(source.name, "source")
        if source.amount_override is not None:
            source.amount_override = _require_positive_amount(
                source.amount_override, "Amount override"
            )
        if source.anchor_date is not None:
            source.weekday = source.anchor_date.weekday()
        self.db.sources.update(source)
        self._changed()
        return source

    def delete_source(self, source_id: int) -> None:
        self.db.sources.delete(source_id)
        self._changed()

    def list_paychecks(self) -> list[Paycheck]:
        return self.db.paychecks.list_all()

    def get_paycheck(self, paycheck_id: int) -> Paycheck | None:
        return self.db.paychecks.get(paycheck_id)

    def create_paycheck(
        self, paycheck: Paycheck, *, auto_link: bool = True, as_of: date | None = None
    ) -> Paycheck:
        paycheck.amount = _require_positive_amount(paycheck.amount)
        if auto_link and paycheck.occurrence_date is None:
            suggested = self.suggest_link(
                paycheck.source_id, paycheck.date, as_of=as_of
            )
            paycheck.occurrence_date = suggested
        created = self.db.paychecks.insert(paycheck)
        self._changed()
        return created

    def update_paycheck(
        self, paycheck: Paycheck, *, auto_link: bool = False, as_of: date | None = None
    ) -> Paycheck:
        if paycheck.id is None:
            raise ValidationError("Paycheck is missing an id.")
        paycheck.amount = _require_positive_amount(paycheck.amount)
        if auto_link and paycheck.occurrence_date is None:
            paycheck.occurrence_date = self.suggest_link(
                paycheck.source_id,
                paycheck.date,
                exclude_paycheck_id=paycheck.id,
                as_of=as_of,
            )
        self.db.paychecks.update(paycheck)
        self._changed()
        return paycheck

    def delete_paycheck(self, paycheck_id: int) -> None:
        self.db.paychecks.delete(paycheck_id)
        self._changed()

    def suggest_link(
        self,
        source_id: int,
        paycheck_date: date,
        *,
        exclude_paycheck_id: int | None = None,
        as_of: date | None = None,
    ) -> date | None:
        source = self.db.sources.get(source_id)
        if source is None:
            return None
        as_of = as_of or date.today()
        start, end = projection_window(as_of)
        return suggest_link(
            source,
            paycheck_date,
            self.db.paychecks.list_all(),
            start,
            end,
            exclude_paycheck_id,
        )

    def list_bills(self) -> list[Bill]:
        return self.db.bills.list_all()

    def get_bill(self, bill_id: int) -> Bill | None:
        return self.db.bills.get(bill_id)

    def _validate_bill(self, bill: Bill) -> Bill:
        bill.name = _require_name(bill.name, "bill")
        bill.amount_estimate = _require_positive_amount(
            bill.amount_estimate, "Estimate"
        )
        if bill.due_day is not None and not (1 <= bill.due_day <= 28):
            raise ValidationError("Due day must be between 1 and 28.")
        if bill.average_actuals_n < 2:
            raise ValidationError("Average actuals window must be at least 2.")
        if not bill.variable:
            bill.estimate_mode = EstimateMode.MANUAL
        needs_schedule = bill.frequency != BillFrequency.ONE_TIME
        if bill.frequency == BillFrequency.MONTHLY and bill.due_day is None and bill.next_due_date is None:
            raise ValidationError("Monthly bills need a due day or next due date.")
        if bill.frequency in {
            BillFrequency.WEEKLY,
            BillFrequency.BIWEEKLY,
            BillFrequency.QUARTERLY,
            BillFrequency.YEARLY,
            BillFrequency.ONE_TIME,
        } and bill.next_due_date is None:
            if needs_schedule or bill.frequency == BillFrequency.ONE_TIME:
                raise ValidationError("This bill needs a next due date.")
        return bill

    def create_bill(self, bill: Bill) -> Bill:
        bill = self._validate_bill(bill)
        created = self.db.bills.insert(bill)
        self._changed()
        return created

    def update_bill(self, bill: Bill) -> Bill:
        if bill.id is None:
            raise ValidationError("Bill is missing an id.")
        bill = self._validate_bill(bill)
        self.db.bills.update(bill)
        self._changed()
        return bill

    def delete_bill(self, bill_id: int) -> None:
        self.db.bills.delete(bill_id)
        self._changed()

    def list_occurrences(self, bill_id: int | None = None) -> list[BillOccurrence]:
        if bill_id is None:
            return self.db.occurrences.list_all()
        return self.db.occurrences.list_for_bill(bill_id)

    def merged_occurrences(
        self, bill_id: int, *, as_of: date | None = None
    ) -> list[BillOccurrence]:
        bill = self.db.bills.get(bill_id)
        if bill is None:
            return []
        as_of = as_of or date.today()
        start, end = projection_window(as_of)
        return merge_occurrences(bill, start, end, self.db.occurrences.list_for_bill(bill_id))

    def set_bill_actual(
        self,
        bill_id: int,
        due_date: date,
        *,
        amount_actual: Decimal | int | float | str | None,
        paid: bool | None = None,
        notes: str | None = None,
    ) -> BillOccurrence:
        existing = self.db.occurrences.get_by_bill_date(bill_id, due_date)
        occ = existing or BillOccurrence(bill_id=bill_id, due_date=due_date)
        if amount_actual is not None and amount_actual != "":
            occ.amount_actual = _require_positive_amount(amount_actual, "Actual amount")
        else:
            occ.amount_actual = None
        if paid is not None:
            occ.paid = paid
        if notes is not None:
            occ.notes = notes
        saved = self.db.occurrences.upsert(occ)
        self._changed()
        return saved

    def set_estimate_from_average(self, bill_id: int) -> Bill:
        bill = self.db.bills.get(bill_id)
        if bill is None:
            raise ValidationError("Bill not found.")
        average = recent_actual_average(
            self.db.occurrences.list_for_bill(bill_id), bill.average_actuals_n
        )
        if average is None:
            raise ValidationError("No actual amounts recorded yet.")
        bill.amount_estimate = average
        self.db.bills.update(bill)
        self._changed()
        return bill

    def bill_working_amount(self, bill: Bill) -> Decimal:
        if bill.id is None:
            return q2(bill.amount_estimate)
        return working_amount(bill, self.db.occurrences.list_for_bill(bill.id))

    def bill_monthly_equivalent(self, bill: Bill) -> Decimal:
        return monthly_equivalent(bill.frequency, self.bill_working_amount(bill))

    def bill_recent_average(self, bill: Bill) -> Decimal | None:
        if bill.id is None:
            return None
        return recent_actual_average(
            self.db.occurrences.list_for_bill(bill.id), bill.average_actuals_n
        )

    def source_stats(self, source: PaySource, *, as_of: date | None = None) -> dict:
        as_of = as_of or date.today()
        settings = self.get_settings()
        window_start = as_of - timedelta(days=settings.average_window_days)
        paychecks = self.db.paychecks.list_all()
        checks = included_in_window(paychecks, source.id, window_start, as_of)
        average = source_average(source, paychecks, window_start, as_of)
        start, end = projection_window(as_of)
        upcoming = [d for d in generate_paydays(source, max(as_of, start), end)][:4]
        if len(upcoming) < 4:
            upcoming = [d for d in generate_paydays(source, as_of, end) if d >= as_of][:4]
        return {
            "check_count": len(checks),
            "average": average,
            "expected": expected_payday_amount(source, average),
            "next_paydays": upcoming,
            "needs_anchor": needs_anchor(source),
        }

    def overview(self, *, as_of: date | None = None) -> OverviewData:
        as_of = as_of or date.today()
        settings = self.get_settings()
        sources = self.db.sources.list_all()
        paychecks = self.db.paychecks.list_all()
        bills = self.db.bills.list_all()
        occ_index = occurrences_index(self.db.occurrences.list_all())
        typical = typical_income(sources, paychecks, settings, as_of)
        bill_result = typical_bills(bills, occ_index)
        months = six_month_rollups(
            sources, paychecks, bills, occ_index, settings, as_of
        )
        this_month = months[0] if months else calendar_month(
            month_start(as_of), sources, paychecks, bills, occ_index, settings, as_of
        )
        leftover = None
        leftover_after = None
        if typical.is_complete and typical.total is not None:
            leftover = q2(typical.total - bill_result.total)
            leftover_after = q2(leftover - settings.savings_target_monthly)
        missing_anchors = [s.name for s in sources if needs_anchor(s)]
        warnings: list[str] = []
        if missing_anchors:
            warnings.append(
                "Set a recent payday before upcoming pay can be predicted"
            )
        for part in typical.parts:
            if part.unknown:
                warnings.append(
                    f"Add at least two paychecks for {part.source_name} to compute its average"
                )
        active_bills = [b for b in bills if b.active]
        if not active_bills:
            warnings.append("Add recurring bills to see monthly costs")
        start, end = projection_window(as_of)
        upcoming = upcoming_events(
            sources, paychecks, bills, occ_index, settings, as_of, as_of, end, 5
        )
        return OverviewData(
            typical_income=typical,
            typical_bills=bill_result.total,
            leftover_after_bills=leftover,
            leftover_after_savings=leftover_after,
            this_month=this_month,
            months=months,
            upcoming=upcoming,
            recipe=income_recipe(typical.parts, settings.currency_symbol),
            missing_anchors=missing_anchors,
            warnings=warnings,
            currency_symbol=settings.currency_symbol,
            savings_target=settings.savings_target_monthly,
            has_bills=bool(active_bills),
            active_bill_count=len(active_bills),
        )

    def month_detail(self, year: int, month: int, *, as_of: date | None = None):
        as_of = as_of or date.today()
        settings = self.get_settings()
        return calendar_month(
            date(year, month, 1),
            self.db.sources.list_all(),
            self.db.paychecks.list_all(),
            self.db.bills.list_all(),
            occurrences_index(self.db.occurrences.list_all()),
            settings,
            as_of,
        )

    def six_months(self, *, as_of: date | None = None):
        as_of = as_of or date.today()
        return six_month_rollups(
            self.db.sources.list_all(),
            self.db.paychecks.list_all(),
            self.db.bills.list_all(),
            occurrences_index(self.db.occurrences.list_all()),
            self.get_settings(),
            as_of,
        )

    def next_paydays(self, source: PaySource, n: int = 4, *, as_of: date | None = None) -> list[date]:
        as_of = as_of or date.today()
        _start, end = projection_window(as_of)
        return [d for d in generate_paydays(source, as_of, end) if d >= as_of][:n]

    def export_csv(self, directory: str | Path, *, as_of: date | None = None) -> list[Path]:
        as_of = as_of or date.today()
        start, end = projection_window(as_of)
        bills = self.db.bills.list_all()
        occ_index = occurrences_index(self.db.occurrences.list_all())
        merged: list[BillOccurrence] = []
        for bill in bills:
            if bill.id is None:
                continue
            merged.extend(merge_occurrences(bill, start, end, occ_index.get(bill.id, [])))
        return export_all(
            Path(directory),
            self.db.sources.list_all(),
            self.db.paychecks.list_all(),
            bills,
            merged,
        )

    def electric_defaults(self) -> Bill:
        today = date.today()
        return Bill(
            name="Electric",
            amount_estimate=Decimal("150.00"),
            frequency=BillFrequency.MONTHLY,
            due_day=min(today.day, 28),
            category=BillCategory.UTILITIES,
            variable=True,
            estimate_mode=EstimateMode.AVERAGE_ACTUALS,
            average_actuals_n=6,
            notes="Variable utility — log actuals so the average can replace the estimate.",
        )

    def list_transactions(self) -> list[LedgerEntry]:
        return self.db.transactions.list_all()

    def create_transaction(self, entry: LedgerEntry) -> LedgerEntry:
        entry.payee = _require_name(entry.payee)
        entry.amount = _require_positive_amount(entry.amount)
        if entry.kind not in {"expense", "income"}:
            entry.kind = "expense"
        created = self.db.transactions.insert(entry)
        self._changed()
        return created

    def delete_transaction(self, entry_id: int) -> None:
        self.db.transactions.delete(entry_id)
        self._changed()

    def other_monthly_spending(self) -> Decimal:
        raw = self.get_pref("other_monthly_spending", "0.00") or "0.00"
        try:
            return _money_or_zero(raw)
        except ValidationError:
            return Decimal("0.00")

    def set_other_monthly_spending(self, amount: Decimal | int | float | str) -> None:
        value = _money_or_zero(amount)
        self.set_pref("other_monthly_spending", str(value))
        self.bus.emit()

    def theme_name(self) -> str:
        value = self.get_pref("theme", "dark") or "dark"
        return "dark" if value != "light" else "light"

    def set_theme_name(self, name: str) -> None:
        self.set_pref("theme", "dark" if name == "dark" else "light")

    def plan_for_month(self, year: int, month: int, *, as_of: date | None = None):
        from budgetwatch.services.planning import build_plan

        as_of = as_of or date.today()
        rollup = self.month_detail(year, month, as_of=as_of)
        overrides = self.db.plans.list_month(year, month)
        return build_plan(
            year,
            month,
            self.db.bills.list_all(),
            self.db.occurrences.list_all(),
            self.db.paychecks.list_all(),
            self.db.transactions.list_in_month(year, month),
            overrides,
            rollup.income,
        )

    def set_plan_amount(self, year: int, month: int, key: str, amount: Decimal | str) -> None:
        planned = _money_or_zero(amount)
        self.db.plans.upsert(year, month, key, planned)
        self._changed()

    def month_expenses(self, year: int, month: int, *, as_of: date | None = None) -> Decimal:
        from budgetwatch.services.planning import month_expense_total

        as_of = as_of or date.today()
        return month_expense_total(
            year,
            month,
            self.db.bills.list_all(),
            self.db.occurrences.list_all(),
            self.db.transactions.list_in_month(year, month),
            self.get_settings(),
            self.db.sources.list_all(),
            self.db.paychecks.list_all(),
            as_of,
        )
