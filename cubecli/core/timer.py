"""Timer state machine and precision timing utilities."""

from __future__ import annotations

import time
from enum import Enum, auto


class TimerState(Enum):
    """All possible states of the solve timer."""

    IDLE = auto()      # Resting: showing scramble + last time (or 0:00.000)
    HOLDING = auto()   # Space held down, building up to ready
    READY = auto()     # Held long enough — green light, release to start
    RUNNING = auto()   # Timer actively counting up
    STOPPED = auto()   # Solve complete — time saved, penalties can be applied


# Colour to show for each state (maps to Textual/Rich markup colours)
STATE_COLORS: dict[TimerState, str] = {
    TimerState.IDLE: "bright_white",
    TimerState.HOLDING: "yellow",
    TimerState.READY: "green",
    TimerState.RUNNING: "bright_green",
    TimerState.STOPPED: "bright_white",
}


def format_time(ms: int) -> str:
    """Format milliseconds into a human-readable display string.

    Examples:
        >>> format_time(1234)
        '1.234'
        >>> format_time(72500)
        '1:12.500'
    """
    total_s = ms / 1000.0
    minutes = int(total_s // 60)
    seconds = total_s % 60
    if minutes:
        return f"{minutes}:{seconds:06.3f}"
    return f"{seconds:.3f}"


class PrecisionTimer:
    """High-precision wall-clock timer using :func:`time.perf_counter`.

    Usage::

        t = PrecisionTimer()
        t.start()
        # ... solve the cube ...
        elapsed = t.stop()   # returns int (milliseconds)
    """

    def __init__(self) -> None:
        self._start: float | None = None
        self._end: float | None = None

    def start(self) -> None:
        """Record the start time."""
        self._start = time.perf_counter()
        self._end = None

    def stop(self) -> int:
        """Stop the timer and return elapsed milliseconds."""
        self._end = time.perf_counter()
        return self.elapsed_ms

    def reset(self) -> None:
        """Reset to initial state."""
        self._start = None
        self._end = None

    @property
    def elapsed_ms(self) -> int:
        """Live elapsed time in milliseconds (works during and after solve)."""
        if self._start is None:
            return 0
        end = self._end if self._end is not None else time.perf_counter()
        return int((end - self._start) * 1000)

    @property
    def is_running(self) -> bool:
        """True while the timer is actively counting up."""
        return self._start is not None and self._end is None
