"""Integration tests for the SQLite persistence layer (db.py).

Uses a temporary database file so the user's real solve history is never touched.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cubecli.data import db
from cubecli.data.models import Session, Solve


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a fresh temporary database and patch DB_FILE."""
    db_path = tmp_path / "test_solves.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        yield db_path


def _make_solve(session_id: int, time_ms: int, penalty: str | None = None, notes: str = "") -> Solve:
    return Solve(
        time_ms=time_ms,
        scramble="R U R' U'",
        puzzle="3x3",
        session_id=session_id,
        penalty=penalty,
        notes=notes,
    )


# ── ensure_schema ─────────────────────────────────────────────────────────────


def test_ensure_schema_creates_tables(tmp_path: Path) -> None:
    """ensure_schema() should create sessions and solves tables."""
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        assert db_path.exists()
        # Verify both tables exist
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "sessions" in tables
        assert "solves" in tables


def test_ensure_schema_is_idempotent(tmp_path: Path) -> None:
    """Calling ensure_schema() multiple times must not raise."""
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        db.ensure_schema()  # second call must not fail


# ── sessions ──────────────────────────────────────────────────────────────────


def test_create_and_get_session(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        session = db.get_or_create_session("Test Session", "3x3")
        assert session.id is not None
        assert session.name == "Test Session"
        assert session.puzzle == "3x3"

        # get_or_create should return the same session
        session2 = db.get_or_create_session("Test Session", "3x3")
        assert session2.id == session.id


def test_list_sessions(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        db.get_or_create_session("Session A", "3x3")
        db.get_or_create_session("Session B", "2x2")
        sessions = db.list_sessions()
        names = [s.name for s in sessions]
        assert "Session A" in names
        assert "Session B" in names


def test_delete_session_cascades(tmp_path: Path) -> None:
    """Deleting a session should cascade-delete its solves."""
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        session = db.get_or_create_session("Cascade Test", "3x3")
        assert session.id is not None
        solve = _make_solve(session.id, 10000)
        db.insert_solve(solve)
        assert db.count_solves(session.id) == 1

        db.delete_session(session.id)
        # After cascade delete, solves should be gone
        assert db.count_solves(session.id) == 0


# ── solves ────────────────────────────────────────────────────────────────────


def test_insert_and_get_solves(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        session = db.get_or_create_session("Solve Test", "3x3")
        assert session.id is not None

        s1 = _make_solve(session.id, 10500)
        s2 = _make_solve(session.id, 9800)
        db.insert_solve(s1)
        db.insert_solve(s2)

        solves = db.get_solves(session.id)
        assert len(solves) == 2
        assert solves[0].time_ms == 10500
        assert solves[1].time_ms == 9800


def test_delete_solve(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        session = db.get_or_create_session("Del Test", "3x3")
        assert session.id is not None

        solve = db.insert_solve(_make_solve(session.id, 12000))
        assert solve.id is not None
        assert db.count_solves(session.id) == 1

        db.delete_solve(solve.id)
        assert db.count_solves(session.id) == 0


def test_update_solve_penalty(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        session = db.get_or_create_session("Penalty Test", "3x3")
        assert session.id is not None

        solve = db.insert_solve(_make_solve(session.id, 10000))
        assert solve.id is not None

        # Apply +2
        db.update_solve_penalty(solve.id, "+2")
        updated = db.get_last_solve(session.id)
        assert updated is not None
        assert updated.penalty == "+2"
        assert updated.effective_ms == 12000  # 10000 + 2000

        # Apply DNF
        db.update_solve_penalty(solve.id, "DNF")
        updated2 = db.get_last_solve(session.id)
        assert updated2 is not None
        assert updated2.penalty == "DNF"
        assert updated2.effective_ms is None

        # Clear penalty
        db.update_solve_penalty(solve.id, None)
        updated3 = db.get_last_solve(session.id)
        assert updated3 is not None
        assert updated3.penalty is None
        assert updated3.effective_ms == 10000


def test_get_effective_times(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        session = db.get_or_create_session("Eff Times Test", "3x3")
        assert session.id is not None

        db.insert_solve(_make_solve(session.id, 10000))
        db.insert_solve(_make_solve(session.id, 9000, penalty="DNF"))
        db.insert_solve(_make_solve(session.id, 8000, penalty="+2"))

        times = db.get_effective_times(session.id)
        assert times == [10000, None, 10000]  # DNF -> None, +2 -> 8000+2000=10000


def test_get_alltime_best(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        session = db.get_or_create_session("Best Test", "3x3")
        assert session.id is not None

        db.insert_solve(_make_solve(session.id, 12000))
        db.insert_solve(_make_solve(session.id, 8500))
        db.insert_solve(_make_solve(session.id, 9000, penalty="DNF"))

        best = db.get_alltime_best("3x3")
        assert best == 8500  # DNF excluded, 8500 < 12000


def test_get_solves_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", db_path):
        db.ensure_schema()
        session = db.get_or_create_session("Limit Test", "3x3")
        assert session.id is not None

        for t in range(10):
            db.insert_solve(_make_solve(session.id, t * 1000 + 5000))

        limited = db.get_solves(session.id, limit=3)
        assert len(limited) == 3
