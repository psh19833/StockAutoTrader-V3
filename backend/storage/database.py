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
    conn.commit()


def reset_db(conn: sqlite3.Connection) -> None:
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    for row in tables:
        conn.execute(f"DROP TABLE IF EXISTS [{row['name']}]")
    conn.commit()
