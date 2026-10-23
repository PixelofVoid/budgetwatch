SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pay_sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    frequency TEXT NOT NULL,
    anchor_date TEXT,
    weekday INTEGER,
    amount_override TEXT,
    include_in_typical INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS paychecks (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    amount TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    include_in_average INTEGER NOT NULL DEFAULT 1,
    occurrence_date TEXT,
    FOREIGN KEY (source_id) REFERENCES pay_sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    amount_estimate TEXT NOT NULL,
    frequency TEXT NOT NULL,
    due_day INTEGER,
    next_due_date TEXT,
    category TEXT NOT NULL DEFAULT 'other',
    variable INTEGER NOT NULL DEFAULT 0,
    estimate_mode TEXT NOT NULL DEFAULT 'manual',
    average_actuals_n INTEGER NOT NULL DEFAULT 6,
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bill_occurrences (
    id INTEGER PRIMARY KEY,
    bill_id INTEGER NOT NULL,
    due_date TEXT NOT NULL,
    amount_actual TEXT,
    paid INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE (bill_id, due_date),
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_paychecks_source_date ON paychecks(source_id, date);
CREATE INDEX IF NOT EXISTS idx_paychecks_occurrence ON paychecks(source_id, occurrence_date);
CREATE INDEX IF NOT EXISTS idx_bill_occ_bill_date ON bill_occurrences(bill_id, due_date);
"""

NEW_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    payee TEXT NOT NULL,
    amount TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    kind TEXT NOT NULL DEFAULT 'expense',
    notes TEXT NOT NULL DEFAULT '',
    occurrence_id INTEGER,
    paycheck_id INTEGER
);

CREATE TABLE IF NOT EXISTS category_plans (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    category TEXT NOT NULL,
    planned TEXT NOT NULL,
    UNIQUE (year, month, category)
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_occurrence ON transactions(occurrence_id);
CREATE INDEX IF NOT EXISTS idx_category_plans_month ON category_plans(year, month);
"""

DEFAULT_SETTINGS = {
    "average_window_days": "90",
    "savings_target_monthly": "0.00",
    "currency_symbol": "$",
    "theme": "dark",
    "other_monthly_spending": "0.00",
}

SEED_SOURCES = (
    ("Income 1", "biweekly"),
    ("Income 2", "weekly"),
)


def apply_schema(conn) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.executescript(NEW_TABLES_SQL)
    conn.execute("PRAGMA foreign_keys = ON")


def ensure_settings(conn) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )


def seed_sources_if_empty(conn) -> None:
    count = conn.execute("SELECT COUNT(*) FROM pay_sources").fetchone()[0]
    if count:
        return
    for name, frequency in SEED_SOURCES:
        conn.execute(
            """
            INSERT INTO pay_sources (
                name, frequency, include_in_typical, active
            ) VALUES (?, ?, 1, 1)
            """,
            (name, frequency),
        )
