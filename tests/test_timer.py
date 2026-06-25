"""Tests for timer utilities."""

from __future__ import annotations

from cubecli.core.timer import TimerState, format_time


def test_format_sub_minute() -> None:
    assert format_time(1_234) == "1.234"
    assert format_time(12_847) == "12.847"
    assert format_time(0) == "0.000"


def test_format_over_minute() -> None:
    assert format_time(72_500) == "1:12.500"
    assert format_time(600_000) == "10:00.000"


def test_timer_state_count() -> None:
    # Ensure no state was accidentally removed
    assert len(TimerState) == 5


def test_format_preserves_ms_precision() -> None:
    # 12.003 should not round to 12.000
    assert format_time(12_003) == "12.003"
