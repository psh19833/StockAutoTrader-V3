"""Database — SQLite connection management"""
import sqlite3
from pathlib import Path


def get_connection(db_path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    from storage.schema import SCHEMA_SQL
    conn.executescript(SCHEMA_SQL)
    _ensure_audit_event_columns(conn)
    conn.commit()


def _ensure_audit_event_columns(conn: sqlite3.Connection) -> None:
    """Best-effort migration for audit_events table.

    SQLite CREATE TABLE IF NOT EXISTS does not add new columns on existing tables.
    This function adds missing columns to keep live timeline compatible.
    """

    existing = {
        r[1] for r in conn.execute("PRAGMA table_info(audit_events)").fetchall()
    }

    def add(col_sql: str, col_name: str) -> None:
        if col_name in existing:
            return
        conn.execute(f"ALTER TABLE audit_events ADD COLUMN {col_sql}")

    add("event_id TEXT", "event_id")
    add("event_time TEXT", "event_time")
    add("strategy_name TEXT DEFAULT ''", "strategy_name")
    add("status TEXT DEFAULT ''", "status")
    add("summary TEXT DEFAULT ''", "summary")
    add("has_checklist INTEGER DEFAULT 0", "has_checklist")

    # Index creation is idempotent
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_event_id ON audit_events(event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_event_time ON audit_events(event_time)")


def reset_db(conn: sqlite3.Connection) -> None:
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    for row in tables:
        conn.execute(f"DROP TABLE IF EXISTS [{row['name']}]")
    conn.commit()
