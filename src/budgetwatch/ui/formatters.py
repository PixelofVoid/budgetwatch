from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation


def parse_money(text: str) -> Decimal | None:
    cleaned = (text or "").strip().replace(",", "")
    for prefix in ("$", "€", "£", "¥"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def format_money(
    amount: Decimal | None,
    symbol: str = "$",
    *,
    unknown: bool = False,
) -> str:
    if unknown or amount is None:
        return "—"
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"


def leftover_color(amount: Decimal | None) -> str:
    from budgetwatch.ui import theme as t

    if amount is None:
        return t.AMBER
    return t.GREEN if amount >= 0 else t.RED


def format_date(value: date | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%b %d, %Y")


def format_short_date(value: date | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%b %d")


def tone_for_leftover(amount: Decimal | None) -> str:
    if amount is None:
        return "unknown"
    return "good" if amount >= 0 else "bad"


def text_color() -> str:
    from budgetwatch.ui import theme as t

    return t.TEXT
