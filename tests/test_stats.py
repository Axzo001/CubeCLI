"""Tests for the stats calculation engine."""

from __future__ import annotations

import pytest

from cubecli.core.stats import (
    best_rolling_average,
    best_time,
    calculate_ao5,
    calculate_ao12,
    calculate_mo3,
    get_rolling_ao5,
    get_rolling_mo3,
    session_mean,
    session_stddev,
    sub_x_count,
)

# ── Mo3 ────────────────────────────────────────────────────────────────────────


def test_mo3_basic() -> None:
    times = [10_000, 12_000, 11_000]
    assert calculate_mo3(times) == 11_000


def test_mo3_uses_last_three() -> None:
    times = [5_000, 10_000, 12_000, 11_000]
    assert calculate_mo3(times) == 11_000


def test_mo3_with_dnf_returns_none() -> None:
    times = [10_000, None, 11_000]
    assert calculate_mo3(times) is None


def test_mo3_too_short() -> None:
    assert calculate_mo3([10_000, 11_000]) is None


# ── Ao5 ────────────────────────────────────────────────────────────────────────


def test_ao5_trims_best_and_worst() -> None:
    # 9, 10, 11, 12, 13 → remove 9 (best) and 13 (worst) → mean(10,11,12) = 11
    times = [9_000, 10_000, 11_000, 12_000, 13_000]
    assert calculate_ao5(times) == 11_000


def test_ao5_uses_last_five() -> None:
    extra = [5_000] * 10
    window = [9_000, 10_000, 11_000, 12_000, 13_000]
    assert calculate_ao5(extra + window) == 11_000


def test_ao5_one_dnf_ok() -> None:
    # DNF counts as worst; trim removes it; mean(10,11,12) = 11
    times = [None, 10_000, 11_000, 12_000, 9_000]
    assert calculate_ao5(times) == 11_000


def test_ao5_two_dnfs_returns_none() -> None:
    times = [None, None, 10_000, 11_000, 12_000]
    assert calculate_ao5(times) is None


def test_ao5_too_short() -> None:
    assert calculate_ao5([10_000, 11_000, 12_000, 13_000]) is None


# ── Ao12 ───────────────────────────────────────────────────────────────────────


def test_ao12_too_short() -> None:
    assert calculate_ao12([10_000] * 11) is None


def test_ao12_trims() -> None:
    # 12 identical times → average equals that time
    times = [15_000] * 12
    assert calculate_ao12(times) == 15_000


# ── Best time ─────────────────────────────────────────────────────────────────


def test_best_ignores_dnf() -> None:
    assert best_time([None, 10_000, 8_000, None]) == 8_000


def test_best_all_dnf() -> None:
    assert best_time([None, None]) is None


def test_best_empty() -> None:
    assert best_time([]) is None


# ── Session mean ──────────────────────────────────────────────────────────────


def test_mean_ignores_dnf() -> None:
    assert session_mean([None, 10_000, 12_000]) == 11_000


def test_mean_all_dnf() -> None:
    assert session_mean([None, None]) is None


# ── Sub-X count ───────────────────────────────────────────────────────────────


def test_sub_x_count() -> None:
    times = [9_000, 14_000, 16_000, None, 13_000]
    assert sub_x_count(times, 15_000) == 3


# ── Stddev ────────────────────────────────────────────────────────────────────


def test_stddev_needs_two() -> None:
    assert session_stddev([10_000]) is None


def test_stddev_consistent_times() -> None:
    # All same → stdev = 0
    assert session_stddev([10_000, 10_000, 10_000]) == pytest.approx(0, abs=1)


# ── Rolling Stats ─────────────────────────────────────────────────────────────


def test_rolling_mo3() -> None:
    times = [10_000, 12_000, 11_000, None, 13_000]
    expected = [None, None, 11_000, None, None]
    assert get_rolling_mo3(times) == expected


def test_rolling_ao5() -> None:
    times = [9_000, 10_000, 11_000, 12_000, 13_000, 14_000]
    # Ao5 at index 4 (first 5 elements): remove 9 and 13 -> mean(10,11,12) = 11
    # Ao5 at index 5 (last 5 elements): remove 10 and 14 -> mean(11,12,13) = 12
    expected = [None, None, None, None, 11_000, 12_000]
    assert get_rolling_ao5(times) == expected


def test_best_rolling_average() -> None:
    averages = [None, None, None, None, 11_000, 10_500, 12_000]
    assert best_rolling_average(averages) == 10_500
    assert best_rolling_average([None, None]) is None
