from __future__ import annotations

import sqlite3
from pathlib import Path

from budgetwatch.db.migrate import (
    DatabaseOpenError,
    migrate_if_needed,
    migrate_schema,
    smoke_check,
)
from budgetwatch.db.repositories import (
    BillOccurrenceRepo,
    BillRepo,
    PaycheckRepo,
    PlanRepo,
    SettingsRepo,
    SourceRepo,
    TransactionRepo,
)
from budgetwatch.db.schema import apply_schema, ensure_settings, seed_sources_if_empty

DATA_DIR = Path.home() / ".local/share/budgetwatch"
DEFAULT_DB_NAME = "budgetwatch.db"

__all__ = [
    "DATA_DIR",
    "Database",
    "DatabaseOpenError",
    "default_data_dir",
    "default_db_path",
]


def default_db_path() -> Path:
    return DATA_DIR / DEFAULT_DB_NAME


def default_data_dir() -> Path:
    return DATA_DIR


class Database:
    def __init__(self, path: str | Path, conn: sqlite3.Connection | None = None):
        self.path = Path(path)
        if conn is not None:
            self.conn = conn
        else:
            if str(self.path) != ":memory:" and self.path.name != ":memory:":
                self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.conn = sqlite3.connect(str(self.path))
            except sqlite3.Error as exc:
                raise DatabaseOpenError(
                    f"BudgetWatch cannot open the database at {self.path}: {exc}"
                ) from exc
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.sources = SourceRepo(self.conn)
        self.paychecks = PaycheckRepo(self.conn)
        self.bills = BillRepo(self.conn)
        self.occurrences = BillOccurrenceRepo(self.conn)
        self.settings = SettingsRepo(self.conn)
        self.transactions = TransactionRepo(self.conn)
        self.plans = PlanRepo(self.conn)

    @classmethod
    def open_default(cls) -> Database:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = default_db_path()
        existed = path.exists()
        if existed:
            migrate_if_needed(path)
        db = cls(path)
        db.initialize(seed=True)
        if existed:
            smoke_check(db.conn, path)
        return db

    @classmethod
    def in_memory(cls, seed: bool = False) -> Database:
        conn = sqlite3.connect(":memory:")
        db = cls(Path(":memory:"), conn=conn)
        db.initialize(seed=seed)
        return db

    def initialize(self, seed: bool = True) -> None:
        apply_schema(self.conn)
        migrate_schema(self.conn)
        ensure_settings(self.conn)
        if seed:
            seed_sources_if_empty(self.conn)
        self.conn.commit()

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
