from __future__ import annotations

import csv
from pathlib import Path

from budgetwatch.models.entities import (
    Bill,
    BillOccurrence,
    PaySource,
    Paycheck,
)


def _money(value) -> str:
    return "" if value is None else f"{value:.2f}"


def _date(value) -> str:
    return "" if value is None else value.isoformat()


def _bool(value: bool) -> str:
    return "true" if value else "false"


def export_sources(path: Path, sources: list[PaySource]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "name",
                "frequency",
                "anchor_date",
                "weekday",
                "amount_override",
                "include_in_typical",
                "active",
            ]
        )
        for source in sources:
            writer.writerow(
                [
                    source.id,
                    source.name,
                    source.frequency.value,
                    _date(source.anchor_date),
                    source.weekday if source.weekday is not None else "",
                    _money(source.amount_override),
                    _bool(source.include_in_typical),
                    _bool(source.active),
                ]
            )


def export_paychecks(path: Path, paychecks: list[Paycheck]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "source_id",
                "date",
                "amount",
                "notes",
                "include_in_average",
                "occurrence_date",
            ]
        )
        for paycheck in paychecks:
            writer.writerow(
                [
                    paycheck.id,
                    paycheck.source_id,
                    _date(paycheck.date),
                    _money(paycheck.amount),
                    paycheck.notes,
                    _bool(paycheck.include_in_average),
                    _date(paycheck.occurrence_date),
                ]
            )


def export_bills(path: Path, bills: list[Bill]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "name",
                "amount_estimate",
                "frequency",
                "due_day",
                "next_due_date",
                "category",
                "variable",
                "estimate_mode",
                "average_actuals_n",
                "active",
                "notes",
            ]
        )
        for bill in bills:
            writer.writerow(
                [
                    bill.id,
                    bill.name,
                    _money(bill.amount_estimate),
                    bill.frequency.value,
                    bill.due_day if bill.due_day is not None else "",
                    _date(bill.next_due_date),
                    bill.category.value,
                    _bool(bill.variable),
                    bill.estimate_mode.value,
                    bill.average_actuals_n,
                    _bool(bill.active),
                    bill.notes,
                ]
            )


def export_occurrences(path: Path, occurrences: list[BillOccurrence]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["id", "bill_id", "due_date", "amount_actual", "paid", "notes"]
        )
        for occ in occurrences:
            writer.writerow(
                [
                    occ.id if occ.id is not None else "",
                    occ.bill_id,
                    _date(occ.due_date),
                    _money(occ.amount_actual),
                    _bool(occ.paid),
                    occ.notes,
                ]
            )


def export_all(
    directory: Path,
    sources: list[PaySource],
    paychecks: list[Paycheck],
    bills: list[Bill],
    occurrences: list[BillOccurrence],
) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = [
        directory / "pay_sources.csv",
        directory / "paychecks.csv",
        directory / "bills.csv",
        directory / "bill_occurrences.csv",
    ]
    export_sources(written[0], sources)
    export_paychecks(written[1], paychecks)
    export_bills(written[2], bills)
    export_occurrences(written[3], occurrences)
    return written
