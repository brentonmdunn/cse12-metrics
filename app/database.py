import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "/data/usage.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_events (
            event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            submission_num INTEGER NOT NULL,
            assignment_id TEXT    NOT NULL,
            question_num  INTEGER NOT NULL,
            input_tokens  INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            grading_run   INTEGER NOT NULL DEFAULT 1,
            UNIQUE (name, submission_num, assignment_id, question_num, grading_run)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_name_id ON usage_events (name, submission_num)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_tokens (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            submission_num INTEGER NOT NULL,
            run_token     TEXT    NOT NULL,
            grading_run   INTEGER NOT NULL,
            UNIQUE (name, submission_num, run_token)
        )
    """)
    conn.commit()
    conn.close()
