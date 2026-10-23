from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from budgetwatch.models.entities import (
    Bill,
    BillCategory,
    BillFrequency,
    BillOccurrence,
    EstimateMode,
    LedgerEntry,
    Paycheck,
    PayFrequency,
    PaySource,
    Settings,
)


def _d(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _dec(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(value)


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _money(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _bool(value: object) -> bool:
    return bool(int(value))


def _category(value: str | None) -> BillCategory:
    raw = (value or BillCategory.OTHER.value).strip()
    try:
        return BillCategory(raw)
    except ValueError:
        return BillCategory.OTHER


class SourceRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _row(self, row: sqlite3.Row) -> PaySource:
        return PaySource(
            id=row["id"],
            name=row["name"],
            frequency=PayFrequency(row["frequency"]),
            anchor_date=_d(row["anchor_date"]),
            weekday=row["weekday"],
            amount_override=_dec(row["amount_override"]),
            include_in_typical=_bool(row["include_in_typical"]),
            active=_bool(row["active"]),
        )

    def list_all(self) -> list[PaySource]:
        rows = self.conn.execute(
            "SELECT * FROM pay_sources ORDER BY id"
        ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, source_id: int) -> PaySource | None:
        row = self.conn.execute(
            "SELECT * FROM pay_sources WHERE id = ?", (source_id,)
        ).fetchone()
        return self._row(row) if row else None

    def insert(self, source: PaySource) -> PaySource:
        cur = self.conn.execute(
            """
            INSERT INTO pay_sources (
                name, frequency, anchor_date, weekday, amount_override,
                include_in_typical, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.name,
                source.frequency.value,
                _iso(source.anchor_date),
                source.weekday,
                _money(source.amount_override),
                int(source.include_in_typical),
                int(source.active),
            ),
        )
        source.id = cur.lastrowid
        return source

    def update(self, source: PaySource) -> None:
        self.conn.execute(
            """
            UPDATE pay_sources SET
                name = ?, frequency = ?, anchor_date = ?, weekday = ?,
                amount_override = ?, include_in_typical = ?, active = ?
            WHERE id = ?
            """,
            (
                source.name,
                source.frequency.value,
                _iso(source.anchor_date),
                source.weekday,
                _money(source.amount_override),
                int(source.include_in_typical),
                int(source.active),
                source.id,
            ),
        )

    def delete(self, source_id: int) -> None:
        self.conn.execute("DELETE FROM pay_sources WHERE id = ?", (source_id,))


class PaycheckRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _row(self, row: sqlite3.Row) -> Paycheck:
        return Paycheck(
            id=row["id"],
            source_id=row["source_id"],
            date=_d(row["date"]),  # type: ignore[arg-type]
            amount=_dec(row["amount"]),  # type: ignore[arg-type]
            notes=row["notes"] or "",
            include_in_average=_bool(row["include_in_average"]),
            occurrence_date=_d(row["occurrence_date"]),
        )

    def list_all(self) -> list[Paycheck]:
        rows = self.conn.execute(
            "SELECT * FROM paychecks ORDER BY date DESC, id DESC"
        ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, paycheck_id: int) -> Paycheck | None:
        row = self.conn.execute(
            "SELECT * FROM paychecks WHERE id = ?", (paycheck_id,)
        ).fetchone()
        return self._row(row) if row else None

    def insert(self, paycheck: Paycheck) -> Paycheck:
        cur = self.conn.execute(
            """
            INSERT INTO paychecks (
                source_id, date, amount, notes, include_in_average, occurrence_date
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                paycheck.source_id,
                _iso(paycheck.date),
                _money(paycheck.amount),
                paycheck.notes or "",
                int(paycheck.include_in_average),
                _iso(paycheck.occurrence_date),
            ),
        )
        paycheck.id = cur.lastrowid
        return paycheck

    def update(self, paycheck: Paycheck) -> None:
        self.conn.execute(
            """
            UPDATE paychecks SET
                source_id = ?, date = ?, amount = ?, notes = ?,
                include_in_average = ?, occurrence_date = ?
            WHERE id = ?
            """,
            (
                paycheck.source_id,
                _iso(paycheck.date),
                _money(paycheck.amount),
                paycheck.notes or "",
                int(paycheck.include_in_average),
                _iso(paycheck.occurrence_date),
                paycheck.id,
            ),
        )

    def delete(self, paycheck_id: int) -> None:
        self.conn.execute("DELETE FROM paychecks WHERE id = ?", (paycheck_id,))


class BillRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _row(self, row: sqlite3.Row) -> Bill:
        return Bill(
            id=row["id"],
            name=row["name"],
            amount_estimate=_dec(row["amount_estimate"]),  # type: ignore[arg-type]
            frequency=BillFrequency(row["frequency"]),
            due_day=row["due_day"],
            next_due_date=_d(row["next_due_date"]),
            category=_category(row["category"]),
            variable=_bool(row["variable"]),
            estimate_mode=EstimateMode(row["estimate_mode"]),
            average_actuals_n=int(row["average_actuals_n"]),
            active=_bool(row["active"]),
            notes=row["notes"] or "",
        )

    def list_all(self) -> list[Bill]:
        rows = self.conn.execute("SELECT * FROM bills ORDER BY name, id").fetchall()
        return [self._row(r) for r in rows]

    def get(self, bill_id: int) -> Bill | None:
        row = self.conn.execute(
            "SELECT * FROM bills WHERE id = ?", (bill_id,)
        ).fetchone()
        return self._row(row) if row else None

    def insert(self, bill: Bill) -> Bill:
        cur = self.conn.execute(
            """
            INSERT INTO bills (
                name, amount_estimate, frequency, due_day, next_due_date,
                category, variable, estimate_mode, average_actuals_n, active, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bill.name,
                _money(bill.amount_estimate),
                bill.frequency.value,
                bill.due_day,
                _iso(bill.next_due_date),
                bill.category.value,
                int(bill.variable),
                bill.estimate_mode.value,
                bill.average_actuals_n,
                int(bill.active),
                bill.notes or "",
            ),
        )
        bill.id = cur.lastrowid
        return bill

    def update(self, bill: Bill) -> None:
        self.conn.execute(
            """
            UPDATE bills SET
                name = ?, amount_estimate = ?, frequency = ?, due_day = ?,
                next_due_date = ?, category = ?, variable = ?, estimate_mode = ?,
                average_actuals_n = ?, active = ?, notes = ?
            WHERE id = ?
            """,
            (
                bill.name,
                _money(bill.amount_estimate),
                bill.frequency.value,
                bill.due_day,
                _iso(bill.next_due_date),
                bill.category.value,
                int(bill.variable),
                bill.estimate_mode.value,
                bill.average_actuals_n,
                int(bill.active),
                bill.notes or "",
                bill.id,
            ),
        )

    def delete(self, bill_id: int) -> None:
        self.conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))


class BillOccurrenceRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _row(self, row: sqlite3.Row) -> BillOccurrence:
        return BillOccurrence(
            id=row["id"],
            bill_id=row["bill_id"],
            due_date=_d(row["due_date"]),  # type: ignore[arg-type]
            amount_actual=_dec(row["amount_actual"]),
            paid=_bool(row["paid"]),
            notes=row["notes"] or "",
        )

    def list_all(self) -> list[BillOccurrence]:
        rows = self.conn.execute(
            "SELECT * FROM bill_occurrences ORDER BY due_date, id"
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_for_bill(self, bill_id: int) -> list[BillOccurrence]:
        rows = self.conn.execute(
            "SELECT * FROM bill_occurrences WHERE bill_id = ? ORDER BY due_date",
            (bill_id,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def get_by_bill_date(self, bill_id: int, due_date: date) -> BillOccurrence | None:
        row = self.conn.execute(
            "SELECT * FROM bill_occurrences WHERE bill_id = ? AND due_date = ?",
            (bill_id, due_date.isoformat()),
        ).fetchone()
        return self._row(row) if row else None

    def upsert(self, occurrence: BillOccurrence) -> BillOccurrence:
        existing = self.get_by_bill_date(occurrence.bill_id, occurrence.due_date)
        if existing is None:
            cur = self.conn.execute(
                """
                INSERT INTO bill_occurrences (
                    bill_id, due_date, amount_actual, paid, notes
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    occurrence.bill_id,
                    _iso(occurrence.due_date),
                    _money(occurrence.amount_actual),
                    int(occurrence.paid),
                    occurrence.notes or "",
                ),
            )
            occurrence.id = cur.lastrowid
            return occurrence
        occurrence.id = existing.id
        self.conn.execute(
            """
            UPDATE bill_occurrences SET
                amount_actual = ?, paid = ?, notes = ?
            WHERE id = ?
            """,
            (
                _money(occurrence.amount_actual),
                int(occurrence.paid),
                occurrence.notes or "",
                existing.id,
            ),
        )
        return occurrence

    def delete(self, occurrence_id: int) -> None:
        self.conn.execute(
            "DELETE FROM bill_occurrences WHERE id = ?", (occurrence_id,)
        )


class SettingsRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self) -> Settings:
        rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        raw = {r["key"]: r["value"] for r in rows}
        return Settings(
            average_window_days=int(raw.get("average_window_days", "90")),
            savings_target_monthly=Decimal(raw.get("savings_target_monthly", "0.00")),
            currency_symbol=raw.get("currency_symbol", "$") or "$",
        )

    def update(self, settings: Settings) -> None:
        pairs = {
            "average_window_days": str(int(settings.average_window_days)),
            "savings_target_monthly": str(settings.savings_target_monthly),
            "currency_symbol": settings.currency_symbol,
        }
        for key, value in pairs.items():
            self.set_value(key, value)

    def get_value(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return default
        return row[0]

    def set_value(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


class TransactionRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _row(self, row: sqlite3.Row) -> LedgerEntry:
        return LedgerEntry(
            id=row["id"],
            date=_d(row["date"]),  # type: ignore[arg-type]
            payee=row["payee"],
            amount=_dec(row["amount"]),  # type: ignore[arg-type]
            category=_category(row["category"]),
            kind=row["kind"] or "expense",
            notes=row["notes"] or "",
            occurrence_id=row["occurrence_id"],
            paycheck_id=row["paycheck_id"],
        )

    def list_all(self) -> list[LedgerEntry]:
        rows = self.conn.execute(
            "SELECT * FROM transactions ORDER BY date DESC, id DESC"
        ).fetchall()
        return [self._row(r) for r in rows]

    def list_in_month(self, year: int, month: int) -> list[LedgerEntry]:
        start = date(year, month, 1).isoformat()
        if month == 12:
            end = date(year + 1, 1, 1).isoformat()
        else:
            end = date(year, month + 1, 1).isoformat()
        rows = self.conn.execute(
            "SELECT * FROM transactions WHERE date >= ? AND date < ? ORDER BY date, id",
            (start, end),
        ).fetchall()
        return [self._row(r) for r in rows]

    def insert(self, entry: LedgerEntry) -> LedgerEntry:
        cur = self.conn.execute(
            """
            INSERT INTO transactions (
                date, payee, amount, category, kind, notes, occurrence_id, paycheck_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _iso(entry.date),
                entry.payee,
                _money(entry.amount),
                entry.category.value,
                entry.kind,
                entry.notes or "",
                entry.occurrence_id,
                entry.paycheck_id,
            ),
        )
        entry.id = cur.lastrowid
        return entry

    def delete(self, entry_id: int) -> None:
        self.conn.execute("DELETE FROM transactions WHERE id = ?", (entry_id,))


class PlanRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, year: int, month: int, category: str) -> Decimal | None:
        row = self.conn.execute(
            "SELECT planned FROM category_plans WHERE year = ? AND month = ? AND category = ?",
            (year, month, category),
        ).fetchone()
        return _dec(row["planned"]) if row else None

    def list_month(self, year: int, month: int) -> dict[str, Decimal]:
        rows = self.conn.execute(
            "SELECT category, planned FROM category_plans WHERE year = ? AND month = ?",
            (year, month),
        ).fetchall()
        return {r["category"]: _dec(r["planned"]) for r in rows if _dec(r["planned"]) is not None}

    def upsert(self, year: int, month: int, category: str, planned: Decimal) -> None:
        self.conn.execute(
            """
            INSERT INTO category_plans (year, month, category, planned)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(year, month, category) DO UPDATE SET planned = excluded.planned
            """,
            (year, month, category, _money(planned)),
        )
