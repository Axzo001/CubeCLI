"""Data models for CubeCLI — Solve and Session."""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field


@dataclass
class Solve:
    """A single timed solve attempt.

    Attributes:
        time_ms:    Raw solve time in milliseconds (ignoring penalty).
        scramble:   The scramble used for this solve.
        puzzle:     Puzzle event name, e.g. ``"3x3"``.
        penalty:    ``None``, ``"+2"``, or ``"DNF"``.
        notes:      Optional user annotation.
        timestamp:  Unix timestamp of when the solve was completed.
        session_id: Foreign key to the owning :class:`Session`.
        id:         Database row ID (``None`` before insertion).
    """

    time_ms: int
    scramble: str
    puzzle: str = "3x3"
    penalty: str | None = None
    notes: str = ""
    timestamp: float = field(default_factory=_time.time)
    session_id: int | None = None
    id: int | None = None

    # ── Derived properties ─────────────────────────────────────────────────

    @property
    def effective_ms(self) -> int | None:
        """Effective solve time accounting for penalty.

        Returns:
            Time in milliseconds, or ``None`` for DNF.
        """
        if self.penalty == "DNF":
            return None
        return self.time_ms + (2000 if self.penalty == "+2" else 0)

    @property
    def display_time(self) -> str:
        """Human-readable time string, e.g. ``"12.347"``, ``"1:05.234+"``, ``"DNF"``."""
        from cubecli.core.timer import format_time

        if self.penalty == "DNF":
            return "DNF"
        ms = self.effective_ms
        assert ms is not None
        suffix = "+" if self.penalty == "+2" else ""
        return format_time(ms) + suffix

    @property
    def has_penalty(self) -> bool:
        return self.penalty is not None

    def apply_penalty(self, penalty: str | None) -> None:
        """Set or clear a penalty in-place."""
        self.penalty = penalty


@dataclass
class Session:
    """A named collection of solves for one puzzle event.

    Attributes:
        name:       User-visible session name, e.g. ``"Morning"``.
        puzzle:     Puzzle event, e.g. ``"3x3"``.
        created_at: Unix timestamp of session creation.
        id:         Database row ID (``None`` before insertion).
    """

    name: str
    puzzle: str = "3x3"
    created_at: float = field(default_factory=_time.time)
    id: int | None = None
