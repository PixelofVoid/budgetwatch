from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class PayFrequency(StrEnum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"
    IRREGULAR = "irregular"


class BillFrequency(StrEnum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ONE_TIME = "one_time"


class BillCategory(StrEnum):
    HOUSING = "housing"
    UTILITIES = "utilities"
    GROCERIES = "groceries"
    INSURANCE = "insurance"
    DEBT = "debt"
    SUBSCRIPTIONS = "subscriptions"
    TRANSPORT = "transport"
    OTHER = "other"


class EstimateMode(StrEnum):
    MANUAL = "manual"
    AVERAGE_ACTUALS = "average_actuals"


@dataclass
class PaySource:
    name: str
    frequency: PayFrequency
    id: int | None = None
    anchor_date: date | None = None
    weekday: int | None = None
    amount_override: Decimal | None = None
    include_in_typical: bool = True
    active: bool = True


@dataclass
class Paycheck:
    source_id: int
    date: date
    amount: Decimal
    id: int | None = None
    notes: str = ""
    include_in_average: bool = True
    occurrence_date: date | None = None


@dataclass
class Bill:
    name: str
    amount_estimate: Decimal
    frequency: BillFrequency
    category: BillCategory = BillCategory.OTHER
    id: int | None = None
    due_day: int | None = None
    next_due_date: date | None = None
    variable: bool = False
    estimate_mode: EstimateMode = EstimateMode.MANUAL
    average_actuals_n: int = 6
    active: bool = True
    notes: str = ""


@dataclass
class BillOccurrence:
    bill_id: int
    due_date: date
    id: int | None = None
    amount_actual: Decimal | None = None
    paid: bool = False
    notes: str = ""


@dataclass
class LedgerEntry:
    date: date
    payee: str
    amount: Decimal
    category: BillCategory = BillCategory.OTHER
    kind: str = "expense"  # expense | income
    id: int | None = None
    notes: str = ""
    occurrence_id: int | None = None
    paycheck_id: int | None = None


@dataclass
class Settings:
    average_window_days: int = 90
    savings_target_monthly: Decimal = Decimal("0.00")
    currency_symbol: str = "$"


@dataclass
class RecipePart:
    source_name: str
    frequency: PayFrequency
    average: Decimal | None
    typical_monthly: Decimal | None
    unknown: bool
    check_count: int = 0


@dataclass
class TypicalIncomeResult:
    total: Decimal | None
    is_complete: bool
    household_insufficient: bool
    unknown_sources: list[str] = field(default_factory=list)
    parts: list[RecipePart] = field(default_factory=list)
    included_check_count: int = 0


@dataclass
class PayItem:
    source_id: int
    source_name: str
    date: date
    amount: Decimal | None
    expected: Decimal | None
    actual: Decimal | None
    projected: bool
    unknown: bool
    paycheck_id: int | None = None
    linked: bool = False
    notes: str = ""


@dataclass
class BillItem:
    bill_id: int
    bill_name: str
    due_date: date
    amount: Decimal
    actual: Decimal | None
    projected: bool
    paid: bool = False
    variable: bool = False
    occurrence_id: int | None = None
    notes: str = ""
    category: BillCategory = BillCategory.OTHER


@dataclass
class MonthRollup:
    month_start: date
    income: Decimal
    bills: Decimal
    leftover: Decimal
    leftover_after_savings: Decimal
    income_is_partial: bool
    unknown_sources: list[str] = field(default_factory=list)
    pay_items: list[PayItem] = field(default_factory=list)
    bill_items: list[BillItem] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.month_start.strftime("%b %y")


@dataclass
class TypicalBillsResult:
    total: Decimal
    items: list[tuple[Bill, Decimal, Decimal]]  # bill, working, monthly eq


@dataclass
class UpcomingBillItem:
    bill_id: int
    name: str
    due_date: date
    amount: Decimal
    actual: Decimal | None
    paid: bool
    variable: bool
    group: str  # "overdue" | "this_week" | "later"


@dataclass
class UpcomingEvent:
    date: date
    kind: str  # "pay" or "bill"
    name: str
    expected: Decimal | None
    actual: Decimal | None
    unknown: bool = False
    paid: bool = False
    linked: bool = False
    source_id: int | None = None
    bill_id: int | None = None


@dataclass
class OverviewData:
    typical_income: TypicalIncomeResult
    typical_bills: Decimal
    leftover_after_bills: Decimal | None
    leftover_after_savings: Decimal | None
    this_month: MonthRollup
    months: list[MonthRollup]
    upcoming: list[UpcomingEvent]
    recipe: str
    missing_anchors: list[str]
    warnings: list[str]
    currency_symbol: str
    savings_target: Decimal
    has_bills: bool
    active_bill_count: int = 0
