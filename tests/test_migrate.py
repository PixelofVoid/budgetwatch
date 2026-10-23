from pathlib import Path

from budgetwatch.db.connection import Database
from budgetwatch.db.migrate import current_version, migrate_if_needed, migrate_schema
from budgetwatch.db.schema import SCHEMA_VERSION, apply_schema
from helpers import add_bill, add_check, add_source


def _legacy_file(path: Path) -> None:
    import sqlite3

    conn = sqlite3.connect(path)
    apply_schema(conn)
    conn.execute("DELETE FROM schema_version")
    conn.execute("PRAGMA user_version = 0")
    conn.execute(
        "INSERT INTO pay_sources (name, frequency, include_in_typical, active) "
        "VALUES ('My paycheck', 'biweekly', 1, 1)"
    )
    conn.execute(
        "INSERT INTO paychecks (source_id, date, amount) VALUES (1, '2026-09-03', '2302.43')"
    )
    conn.execute(
        "INSERT INTO bills (name, amount_estimate, frequency, due_day, category) "
        "VALUES ('Electric', '264.00', 'monthly', 15, 'utilities')"
    )
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('currency_symbol', '$')"
    )
    conn.commit()
    conn.close()


def test_migrate_backs_up_then_preserves_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "budgetwatch.db"
    _legacy_file(db_path)
    backup = migrate_if_needed(db_path)
    assert backup is not None
    assert backup.exists()
    assert backup.parent.name == "backups"
    assert backup.name.startswith("budgetwatch-")
    assert backup.suffix == ".db"

    db = Database(db_path)
    db.initialize(seed=True)
    sources = db.sources.list_all()
    paychecks = db.paychecks.list_all()
    bills = db.bills.list_all()
    assert [s.name for s in sources] == ["My paycheck"]
    assert len(paychecks) == 1
    assert paychecks[0].amount == __import__("decimal").Decimal("2302.43")
    assert [b.name for b in bills] == ["Electric"]
    assert current_version(db.conn) == SCHEMA_VERSION
    db.close()

    second = migrate_if_needed(db_path)
    assert second is None
    backups = list((tmp_path / "backups").glob("*.db"))
    assert len(backups) == 1


def test_in_memory_stamps_schema_version(db):
    assert current_version(db.conn) == SCHEMA_VERSION


def test_migrate_schema_is_idempotent(db):
    migrate_schema(db.conn)
    migrate_schema(db.conn)
    add_source(db, name="Keep me")
    add_check(db, 1, __import__("datetime").date(2026, 9, 1), "100")
    add_bill(db, name="Rent")
    db.commit()
    migrate_schema(db.conn)
    assert db.sources.list_all()[0].name == "Keep me"
    assert len(db.paychecks.list_all()) == 1
    assert db.bills.list_all()[0].name == "Rent"
