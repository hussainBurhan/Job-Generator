import json
import sqlite3
from pathlib import Path

from models import Job

DB_PATH = Path("jobs.db")


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id      TEXT PRIMARY KEY,
                title       TEXT,
                company     TEXT,
                location    TEXT,
                is_remote   INTEGER,
                salary_min  INTEGER,
                salary_max  INTEGER,
                salary_raw  TEXT,
                job_type    TEXT,
                posted_at   TEXT,
                apply_url   TEXT,
                source      TEXT,
                description TEXT,
                tech_stack  TEXT,
                scraped_at  TEXT
            )
        """)


def save_jobs(jobs: list[Job]) -> int:
    """Upsert jobs. Returns count of newly inserted rows."""
    new_count = 0
    with _connect() as conn:
        for job in jobs:
            try:
                conn.execute(
                    """
                    INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        job.job_id, job.title, job.company, job.location,
                        int(job.is_remote), job.salary_min, job.salary_max,
                        job.salary_raw, job.job_type, job.posted_at,
                        job.apply_url, job.source, job.description,
                        json.dumps(job.tech_stack), job.scraped_at,
                    ),
                )
                new_count += 1
            except sqlite3.IntegrityError:
                pass  # Already exists — skip
    return new_count


def load_jobs(
    salary_min: int | None = None,
    remote_only: bool = True,
    limit: int = 100,
) -> list[Job]:
    query = "SELECT * FROM jobs WHERE 1=1"
    params: list = []

    if remote_only:
        query += " AND is_remote = 1"
    if salary_min is not None:
        query += " AND (salary_min >= ? OR salary_max >= ?)"
        params += [salary_min, salary_min]

    query += " ORDER BY scraped_at DESC LIMIT ?"
    params.append(limit)

    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    return [_row_to_job(r) for r in rows]


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _row_to_job(row: sqlite3.Row) -> Job:
    d = dict(row)
    d["is_remote"] = bool(d["is_remote"])
    d["tech_stack"] = json.loads(d["tech_stack"] or "[]")
    return Job(**d)
