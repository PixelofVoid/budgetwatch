from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from budgetwatch.db.schema import NEW_TABLES_SQL, SCHEMA_VERSION

log = logging.getLogger("budgetwatch")

BACKUP_DIRNAME = "backups"

# Additive only. Never DROP. Never recreate tables.
ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "pay_sources": [
        ("weekday", "INTEGER"),
        ("amount_override", "TEXT"),
        ("include_in_typical", "INTEGER NOT NULL DEFAULT 1"),
        ("active", "INTEGER NOT NULL DEFAULT 1"),
    ],
    "paychecks": [
        ("notes", "TEXT NOT NULL DEFAULT ''"),
        ("include_in_average", "INTEGER NOT NULL DEFAULT 1"),
        ("occurrence_date", "TEXT"),
    ],
    "bills": [
        ("due_day", "INTEGER"),
        ("next_due_date", "TEXT"),
        ("category", "TEXT NOT NULL DEFAULT 'other'"),
        ("variable", "INTEGER NOT NULL DEFAULT 0"),
        ("estimate_mode", "TEXT NOT NULL DEFAULT 'manual'"),
        ("average_actuals_n", "INTEGER NOT NULL DEFAULT 6"),
        ("active", "INTEGER NOT NULL DEFAULT 1"),
        ("notes", "TEXT NOT NULL DEFAULT ''"),
    ],
    "bill_occurrences": [
        ("amount_actual", "TEXT"),
        ("paid", "INTEGER NOT NULL DEFAULT 0"),
        ("notes", "TEXT NOT NULL DEFAULT ''"),
    ],
}


class DatabaseOpenError(RuntimeError):
    """Raised when the live SQLite file exists but cannot be opened."""


def backup_dir(db_path: Path) -> Path:
    return db_path.parent / BACKUP_DIRNAME


def backup_live_db(db_path: Path) -> Path:
    dest_dir = backup_dir(db_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"budgetwatch-{stamp}.db"
    shutil.copy2(db_path, dest)
    log.info("Backed up database to %s", dest)
    return dest


def open_existing(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=rw"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise DatabaseOpenError(
            f"BudgetWatch cannot open the database at {db_path}: {exc}"
        ) from exc
    conn.row_factory = sqlite3.Row
    return conn


def current_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
        if row is not None:
            return int(row[0])
    except sqlite3.OperationalError:
        pass
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, declaration: str
) -> None:
    if not _table_exists(conn, table):
        return
    if column in _table_columns(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
    log.info("Added column %s.%s", table, column)


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Idempotent additive migration. Safe to run on every launch."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        )
        """
    )
    conn.executescript(NEW_TABLES_SQL)
    for table, columns in ADDITIVE_COLUMNS.items():
        for column, declaration in columns:
            add_column_if_missing(conn, table, column, declaration)
    conn.execute(
        """
        INSERT INTO schema_version (id, version) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET version = excluded.version
        """,
        (SCHEMA_VERSION,),
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def migrate_if_needed(db_path: Path) -> Path | None:
    """Backup the live file when a migration will run, then migrate in place.

    Returns the backup path if a backup was written, otherwise None.
    No-ops (no backup) when the file is already at SCHEMA_VERSION.
    """
    conn = open_existing(db_path)
    try:
        version = current_version(conn)
    finally:
        conn.close()
    backup_path: Path | None = None
    if version < SCHEMA_VERSION:
        backup_path = backup_live_db(db_path)
        conn = open_existing(db_path)
        try:
            migrate_schema(conn)
            conn.commit()
        finally:
            conn.close()
    return backup_path


def smoke_check(conn: sqlite3.Connection, db_path: Path) -> dict[str, int]:
    try:
        sources = conn.execute("SELECT COUNT(*) FROM pay_sources").fetchone()[0]
        paychecks = conn.execute("SELECT COUNT(*) FROM paychecks").fetchone()[0]
        bills = conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
        occurrences = conn.execute("SELECT COUNT(*) FROM bill_occurrences").fetchone()[0]
        settings = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
        version = current_version(conn)
    except sqlite3.Error as exc:
        raise DatabaseOpenError(
            f"BudgetWatch cannot read the database at {db_path}: {exc}"
        ) from exc
    summary = {
        "schema_version": int(version),
        "sources": int(sources),
        "paychecks": int(paychecks),
        "bills": int(bills),
        "occurrences": int(occurrences),
        "settings": int(settings),
    }
    line = (
        f"BudgetWatch database: {db_path}  "
        f"schema_version={summary['schema_version']}  "
        f"sources={summary['sources']}  "
        f"paychecks={summary['paychecks']}  "
        f"bills={summary['bills']}  "
        f"occurrences={summary['occurrences']}  "
        f"settings={summary['settings']}"
    )
    print(line, flush=True)
    log.info(line)
    return summary
