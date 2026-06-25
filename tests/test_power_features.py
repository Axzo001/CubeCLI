"""Tests for Phase 5 Power Features: BLD, FMC, CFOP splits, metronome, and inspection."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from cubecli.config import Config
from cubecli.core.timer import TimerState
from cubecli.data.models import Solve
from cubecli.ui.screens.timer_screen import TimerScreen


def _setup_mock_screen(cfg: Config) -> TimerScreen:
    # Use patch to mock screen.app property during instantiation
    with patch("cubecli.ui.screens.timer_screen.TimerScreen.app", new_callable=MagicMock):
        screen = TimerScreen(cfg)

    # Mock instance app and other TUI methods using setattr to bypass mypy method-assign rules
    setattr(screen, "notify", MagicMock())  # noqa: B010
    setattr(screen, "set_timer", MagicMock())  # noqa: B010
    setattr(screen, "set_interval", MagicMock())  # noqa: B010
    setattr(screen, "_new_scramble", MagicMock())  # noqa: B010

    # Mock query_one and child widgets
    mock_timer_widget = MagicMock()
    mock_timer_widget.time_str = "0.000"

    mock_label = MagicMock()
    mock_button = MagicMock()
    mock_container = MagicMock()

    def query_one_mock(selector: str, expect_type: type | None = None) -> MagicMock:
        if selector == "#timer-widget":
            return mock_timer_widget
        elif selector == "#fmc-solution-input":
            return mock_label
        elif selector == "#fmc-status-label":
            return mock_label
        elif selector == "#fmc-submit-btn":
            return mock_button
        elif selector == "#fmc-cancel-btn":
            return mock_button
        elif selector == "#fmc-timer":
            return mock_label
        elif selector == "#status-label":
            return mock_label
        elif selector in ("#fmc-section", "#timer-section", "#bottom-section", "#cube-preview"):
            return mock_container
        return MagicMock()

    setattr(screen, "query_one", MagicMock(side_effect=query_one_mock))  # noqa: B010
    return screen


def test_timer_screen_power_features_init() -> None:
    cfg = Config()
    screen = _setup_mock_screen(cfg)
    assert not screen._is_inspecting
    assert screen._solve_penalty is None
    assert screen._metronome_timer is None
    assert screen._fmc_interval_timer is None
    assert screen._cfop_stage == 0


def test_bld_mode_split_notes() -> None:
    cfg = Config()
    cfg.bld_mode_enabled = True
    screen = _setup_mock_screen(cfg)
    screen._session = MagicMock()
    screen._session.id = 1
    screen._scramble = "R U R' U'"

    with patch.object(TimerScreen, "_timer_display", new_callable=MagicMock):
        # Start solve
        screen._start_solve()
        assert screen._bld_phase == "memo"
        assert screen._bld_start_time is not None

        # Transition to exec
        screen._transition_bld_to_exec()
        assert screen._bld_phase == "exec"
        assert screen._bld_exec_start is not None
        assert screen._bld_memo_ms >= 0

        # Stop solve
        with patch("cubecli.data.db.insert_solve") as mock_insert:
            screen._stop_solve()
            assert screen._state == TimerState.STOPPED
            assert screen._bld_phase is None
            assert mock_insert.call_count == 1
            solve = mock_insert.call_args[0][0]
            assert isinstance(solve, Solve)
            assert "memo:" in solve.notes
            assert "exec:" in solve.notes


def test_cfop_splits_notes() -> None:
    cfg = Config()
    cfg.cfop_splits_enabled = True
    screen = _setup_mock_screen(cfg)
    screen._session = MagicMock()
    screen._session.id = 1
    screen._scramble = "R U R' U'"

    with patch.object(TimerScreen, "_timer_display", new_callable=MagicMock):
        # Start solve
        screen._start_solve()
        assert screen._cfop_stage == 0
        assert len(screen._cfop_split_times) == 0

        # Record first split
        screen._record_cfop_split()
        assert screen._cfop_stage == 1
        assert len(screen._cfop_split_times) == 1

        # Record second split
        screen._record_cfop_split()
        assert screen._cfop_stage == 2
        assert len(screen._cfop_split_times) == 2

        # Stop solve
        with patch("cubecli.data.db.insert_solve") as mock_insert:
            screen._stop_solve()
            assert screen._state == TimerState.STOPPED
            assert mock_insert.call_count == 1
            solve = mock_insert.call_args[0][0]
            assert isinstance(solve, Solve)
            assert solve.notes.startswith("splits:")
            splits = solve.notes.replace("splits:", "").split("|")
            assert len(splits) == 4


def test_wca_inspection_penalties() -> None:
    cfg = Config()
    cfg.inspection_enabled = True
    screen = _setup_mock_screen(cfg)
    screen._session = MagicMock()
    screen._session.id = 1
    screen._scramble = "R U R' U'"

    with patch.object(TimerScreen, "_timer_display", new_callable=MagicMock):
        # Trigger first SPACE to start inspection
        screen._handle_space()
        assert screen._is_inspecting
        assert screen._inspection_start > 0

        # Let 16 seconds pass (mock time)
        screen._inspection_start = time.perf_counter() - 16.0
        screen._start_solve()
        assert not screen._is_inspecting
        assert screen._solve_penalty == "+2"

        # Stop solve and check penalty saved
        with patch("cubecli.data.db.insert_solve") as mock_insert:
            screen._stop_solve()
            assert mock_insert.call_count == 1
            solve = mock_insert.call_args[0][0]
            assert solve.penalty == "+2"


def test_wca_inspection_dnf_timeout() -> None:
    cfg = Config()
    cfg.inspection_enabled = True
    screen = _setup_mock_screen(cfg)
    screen._session = MagicMock()
    screen._session.id = 1
    screen._scramble = "R U R' U'"

    with patch.object(TimerScreen, "_timer_display", new_callable=MagicMock):
        # Start inspection
        screen._handle_space()
        assert screen._is_inspecting

        # Let 18 seconds pass, trigger _tick
        screen._inspection_start = time.perf_counter() - 18.0
        with patch("cubecli.data.db.insert_solve") as mock_insert:
            screen._tick()
            assert not screen._is_inspecting
            assert mock_insert.call_count == 1
            solve = mock_insert.call_args[0][0]
            assert solve.penalty == "DNF"


def test_metronome_toggles() -> None:
    cfg = Config()
    cfg.metronome_enabled = True
    screen = _setup_mock_screen(cfg)
    screen._session = MagicMock()
    screen._session.id = 1
    screen._scramble = "R U R' U'"

    with patch.object(TimerScreen, "_timer_display", new_callable=MagicMock):
        with patch.object(screen, "set_interval") as mock_set_interval:
            screen._start_solve()
            # Verify interval timer is set
            assert mock_set_interval.call_count >= 1

        # Play metronome tick
        with patch("cubecli.core.audio.play_beep_async") as mock_play:
            screen._play_metronome_tick()
            assert mock_play.call_count == 1
            assert mock_play.call_args[0][0] == 1


def test_fmc_mode_submission() -> None:
    cfg = Config()
    cfg.fmc_mode_enabled = True
    screen = _setup_mock_screen(cfg)
    screen._session = MagicMock()
    screen._session.id = 1
    screen._scramble = "R U R' U'"

    mock_input = MagicMock()
    mock_input.value = "R U R' U'"

    def query_one_mock(selector: str, expect_type: type | None = None) -> MagicMock:
        if selector == "#fmc-solution-input":
            return mock_input
        return MagicMock()

    setattr(screen, "query_one", MagicMock(side_effect=query_one_mock))  # noqa: B010

    with patch.object(TimerScreen, "_timer_display", new_callable=MagicMock):
        with patch("cubecli.data.db.insert_solve") as mock_insert:
            screen._submit_fmc_solution()
            assert mock_insert.call_count == 1
            solve = mock_insert.call_args[0][0]
            assert solve.notes == "fmc_sol:R U R' U'"
            assert solve.time_ms == 4000
