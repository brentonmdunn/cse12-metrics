import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
import os

from .database import get_db

router = APIRouter()


def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.environ["API_KEY"]:
        raise HTTPException(status_code=401, detail="Invalid API key")


auth = Depends(require_api_key)


class UsageEvent(BaseModel):
    name: str
    submission_num: int
    assignment_id: str
    question_num: int
    run_token: str
    input_tokens: int
    output_tokens: int


def resolve_grading_run(db: sqlite3.Connection, name: str, submission_num: int, run_token: str) -> int:
    row = db.execute(
        "SELECT grading_run FROM run_tokens WHERE name = ? AND submission_num = ? AND run_token = ?",
        (name, submission_num, run_token),
    ).fetchone()
    if row:
        return row["grading_run"]
    next_run = db.execute(
        "SELECT COALESCE(MAX(grading_run), 0) + 1 AS n FROM run_tokens WHERE name = ? AND submission_num = ?",
        (name, submission_num),
    ).fetchone()["n"]
    db.execute(
        "INSERT INTO run_tokens (name, submission_num, run_token, grading_run) VALUES (?, ?, ?, ?)",
        (name, submission_num, run_token, next_run),
    )
    return next_run


@router.post("/usage", status_code=201, dependencies=[auth])
def post_usage(event: UsageEvent, db: sqlite3.Connection = Depends(get_db)):
    grading_run = resolve_grading_run(db, event.name, event.submission_num, event.run_token)
    try:
        db.execute(
            """INSERT INTO usage_events
               (name, submission_num, assignment_id, question_num, grading_run, input_tokens, output_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event.name, event.submission_num, event.assignment_id,
             event.question_num, grading_run, event.input_tokens, event.output_tokens),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Event already recorded")
    return {"status": "ok"}


@router.get("/usage/latest-per-name", dependencies=[auth])
def get_latest_per_name(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        WITH latest AS (
            SELECT name, MAX(submission_num) AS submission_num
            FROM usage_events
            GROUP BY name
        )
        SELECT e.name,
               e.submission_num,
               SUM(e.input_tokens)  AS input_tokens,
               SUM(e.output_tokens) AS output_tokens,
               SUM(e.input_tokens + e.output_tokens) AS total_tokens
        FROM usage_events e
        JOIN latest USING (name, submission_num)
        GROUP BY e.name, e.submission_num
        ORDER BY e.name
    """).fetchall()
    return [dict(r) for r in rows]


@router.get("/usage/totals", dependencies=[auth])
def get_totals(db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("""
        WITH latest AS (
            SELECT name, MAX(submission_num) AS submission_num
            FROM usage_events
            GROUP BY name
        )
        SELECT SUM(e.input_tokens)                    AS input_tokens,
               SUM(e.output_tokens)                   AS output_tokens,
               SUM(e.input_tokens + e.output_tokens)  AS total_tokens
        FROM usage_events e
        JOIN latest USING (name, submission_num)
    """).fetchone()
    return dict(row) if row else {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


@router.get("/usage/by-question", dependencies=[auth])
def get_by_question(
    assignment_id: str,
    question_num: int,
    db: sqlite3.Connection = Depends(get_db),
):
    rows = db.execute("""
        WITH latest_sub AS (
            SELECT name, MAX(submission_num) AS submission_num
            FROM usage_events
            GROUP BY name
        ),
        latest_run AS (
            SELECT e.name, e.submission_num, MAX(e.grading_run) AS grading_run
            FROM usage_events e
            JOIN latest_sub USING (name, submission_num)
            GROUP BY e.name, e.submission_num
        )
        SELECT e.name, e.submission_num, e.grading_run, e.input_tokens, e.output_tokens
        FROM usage_events e
        JOIN latest_run USING (name, submission_num, grading_run)
        WHERE e.assignment_id = ? AND e.question_num = ?
        ORDER BY e.name
    """, (assignment_id, question_num)).fetchall()
    return [dict(r) for r in rows]


@router.get("/usage", dependencies=[auth])
def get_usage(
    name: str | None = None,
    submission_num: int | None = None,
    grading_run: int | None = None,
    db: sqlite3.Connection = Depends(get_db),
):
    query = "SELECT * FROM usage_events WHERE 1=1"
    params: list = []
    if name is not None:
        query += " AND name = ?"
        params.append(name)
    if submission_num is not None:
        query += " AND submission_num = ?"
        params.append(submission_num)
    if grading_run is not None:
        query += " AND grading_run = ?"
        params.append(grading_run)
    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]
