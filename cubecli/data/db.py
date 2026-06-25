"""SQLite persistence layer for CubeCLI solve history."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from cubecli.config import DB_FILE
from cubecli.data.models import Session, Solve

# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    puzzle     TEXT    NOT NULL DEFAULT '3x3',
    created_at REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS solves (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    time_ms    INTEGER NOT NULL,
    scramble   TEXT    NOT NULL,
    puzzle     TEXT    NOT NULL DEFAULT '3x3',
    penalty    TEXT,                        -- NULL | '+2' | 'DNF'
    notes      TEXT    NOT NULL DEFAULT '',
    timestamp  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_solves_session ON solves(session_id);
CREATE INDEX IF NOT EXISTS idx_solves_timestamp ON solves(timestamp);
"""


# ── Connection helper ─────────────────────────────────────────────────────────


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_DDL)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Public API ────────────────────────────────────────────────────────────────


def ensure_schema() -> None:
    """Create tables if they don't exist yet (idempotent)."""
    with _connect():
        pass


# ── Sessions ──────────────────────────────────────────────────────────────────


def create_session(session: Session) -> Session:
    """Insert a new session row and return it with its assigned ``id``."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (name, puzzle, created_at) VALUES (?,?,?)",
            (session.name, session.puzzle, session.created_at),
        )
        session.id = cur.lastrowid
    return session


def get_or_create_session(name: str, puzzle: str) -> Session:
    """Return the most recent session with this name+puzzle, or create one."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE name=? AND puzzle=? ORDER BY created_at DESC LIMIT 1",
            (name, puzzle),
        ).fetchone()
        if row:
            return Session(
                id=row["id"],
                name=row["name"],
                puzzle=row["puzzle"],
                created_at=row["created_at"],
            )
    session = Session(name=name, puzzle=puzzle)
    return create_session(session)


def list_sessions() -> list[Session]:
    """Return all sessions, newest first."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    return [
        Session(id=r["id"], name=r["name"], puzzle=r["puzzle"], created_at=r["created_at"])
        for r in rows
    ]


def rename_session(session_id: int, new_name: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE sessions SET name=? WHERE id=?", (new_name, session_id))


def delete_session(session_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))


# ── Solves ────────────────────────────────────────────────────────────────────


def insert_solve(solve: Solve) -> Solve:
    """Persist a solve and return it with its assigned ``id``."""
    assert solve.session_id is not None, "solve.session_id must be set before inserting"
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO solves
               (session_id, time_ms, scramble, puzzle, penalty, notes, timestamp)
               VALUES (?,?,?,?,?,?,?)""",
            (
                solve.session_id,
                solve.time_ms,
                solve.scramble,
                solve.puzzle,
                solve.penalty,
                solve.notes,
                solve.timestamp,
            ),
        )
        solve.id = cur.lastrowid
    return solve


def update_solve_penalty(solve_id: int, penalty: str | None) -> None:
    """Update the penalty for an existing solve (for +2/DNF edits)."""
    with _connect() as conn:
        conn.execute("UPDATE solves SET penalty=? WHERE id=?", (penalty, solve_id))


def update_solve_notes(solve_id: int, notes: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE solves SET notes=? WHERE id=?", (notes, solve_id))


def delete_solve(solve_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM solves WHERE id=?", (solve_id,))


def get_solves(session_id: int, limit: int | None = None) -> list[Solve]:
    """Return solves for a session, oldest first."""
    sql = "SELECT * FROM solves WHERE session_id=? ORDER BY timestamp ASC"
    params: tuple[int, ...] = (session_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (session_id, limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_solve(r) for r in rows]


def get_last_solve(session_id: int) -> Solve | None:
    """Return the most recent solve in a session, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM solves WHERE session_id=? ORDER BY timestamp DESC LIMIT 1",
            (session_id,),
        ).fetchone()
    return _row_to_solve(row) if row else None


def count_solves(session_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM solves WHERE session_id=?", (session_id,)
        ).fetchone()
    return row["n"] if row else 0


def get_effective_times(session_id: int) -> list[int | None]:
    """Return effective times (ms) for all solves, DNF→None, oldest first."""
    solves = get_solves(session_id)
    return [s.effective_ms for s in solves]


# ── All-time records ──────────────────────────────────────────────────────────


def get_alltime_best(puzzle: str) -> int | None:
    """Return the fastest non-DNF time ever for the given puzzle (ms)."""
    with _connect() as conn:
        row = conn.execute(
            """SELECT MIN(
                   CASE WHEN penalty='DNF' THEN NULL
                        WHEN penalty='+2'  THEN time_ms + 2000
                        ELSE time_ms END
               ) as best
               FROM solves WHERE puzzle=?""",
            (puzzle,),
        ).fetchone()
    return row["best"] if row and row["best"] is not None else None


# ── Internal helpers ──────────────────────────────────────────────────────────


def _row_to_solve(row: sqlite3.Row) -> Solve:
    return Solve(
        id=row["id"],
        session_id=row["session_id"],
        time_ms=row["time_ms"],
        scramble=row["scramble"],
        puzzle=row["puzzle"],
        penalty=row["penalty"],
        notes=row["notes"] or "",
        timestamp=row["timestamp"],
    )
