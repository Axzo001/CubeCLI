"""WCA-compliant statistics calculations for speedcubing solve times."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

# A solve time value: int (milliseconds) or None (DNF)
Time = int | None


def _trim_average(times: Sequence[Time], trim: int) -> Time:
    """Calculate a WCA-style trimmed mean over a fixed-size window.

    - DNF (``None``) is treated as the worst possible time.
    - If more than ``trim`` DNFs exist, the result is DNF (``None``).
    - ``trim`` elements are removed from each end after sorting.

    Args:
        times: Exactly the window of times to average.
        trim:  Number of values to remove from each end.

    Returns:
        Averaged time in milliseconds, or ``None`` if result is DNF.
    """
    n = len(times)
    dnf_count = sum(1 for t in times if t is None)

    if dnf_count > trim:
        return None

    # Sort: valid times ascending, then DNFs at the end (as +inf)
    sorted_vals = sorted(t if t is not None else float("inf") for t in times)
    trimmed = sorted_vals[trim : n - trim]
    valid = [v for v in trimmed if v != float("inf")]

    if not valid:
        return None

    return int(statistics.mean(valid))


# ── Public API ────────────────────────────────────────────────────────────────


def calculate_mo3(times: Sequence[Time]) -> Time:
    """Mean of 3 (no trimming). Returns None if any solve is DNF."""
    if len(times) < 3:
        return None
    window = times[-3:]
    if None in window:
        return None
    return int(statistics.mean(t for t in window if t is not None))


def calculate_ao5(times: Sequence[Time]) -> Time:
    """Average of 5 — removes best and worst (WCA-compliant)."""
    if len(times) < 5:
        return None
    return _trim_average(times[-5:], trim=1)


def calculate_ao12(times: Sequence[Time]) -> Time:
    """Average of 12 — removes best and worst (WCA-compliant)."""
    if len(times) < 12:
        return None
    return _trim_average(times[-12:], trim=1)


def calculate_ao50(times: Sequence[Time]) -> Time:
    """Average of 50 — removes top/bottom 3."""
    if len(times) < 50:
        return None
    return _trim_average(times[-50:], trim=3)


def calculate_ao100(times: Sequence[Time]) -> Time:
    """Average of 100 — removes top/bottom 5."""
    if len(times) < 100:
        return None
    return _trim_average(times[-100:], trim=5)


def best_time(times: Sequence[Time]) -> Time:
    """Return the fastest non-DNF time from the list."""
    valid = [t for t in times if t is not None]
    return min(valid) if valid else None


def session_mean(times: Sequence[Time]) -> Time:
    """Mean of all non-DNF times in the session."""
    valid = [t for t in times if t is not None]
    return int(statistics.mean(valid)) if valid else None


def session_stddev(times: Sequence[Time]) -> float | None:
    """Population standard deviation of non-DNF times (in milliseconds)."""
    valid = [t for t in times if t is not None]
    return statistics.stdev(valid) if len(valid) >= 2 else None


def sub_x_count(times: Sequence[Time], threshold_ms: int) -> int:
    """Count how many non-DNF solves are strictly under ``threshold_ms``."""
    return sum(1 for t in times if t is not None and t < threshold_ms)


def get_rolling_averages(times: Sequence[Time], window: int, trim: int) -> list[Time]:
    """Calculate rolling WCA-style averages across a list of times."""
    averages: list[Time] = []
    for i in range(len(times)):
        if i < window - 1:
            averages.append(None)
        else:
            averages.append(_trim_average(times[i - window + 1 : i + 1], trim))
    return averages


def get_rolling_mo3(times: Sequence[Time]) -> list[Time]:
    """Mean of 3 (no trimming) rolling average."""
    averages: list[Time] = []
    for i in range(len(times)):
        if i < 2:
            averages.append(None)
        else:
            w = times[i - 2 : i + 1]
            if None in w:
                averages.append(None)
            else:
                averages.append(int(statistics.mean(t for t in w if t is not None)))
    return averages


def get_rolling_ao5(times: Sequence[Time]) -> list[Time]:
    return get_rolling_averages(times, 5, 1)


def get_rolling_ao12(times: Sequence[Time]) -> list[Time]:
    return get_rolling_averages(times, 12, 1)


def get_rolling_ao50(times: Sequence[Time]) -> list[Time]:
    return get_rolling_averages(times, 50, 3)


def get_rolling_ao100(times: Sequence[Time]) -> list[Time]:
    return get_rolling_averages(times, 100, 5)


def best_rolling_average(averages: Sequence[Time]) -> Time:
    """Return the minimum (best) value in a rolling average list."""
    valid = [a for a in averages if a is not None]
    return min(valid) if valid else None
