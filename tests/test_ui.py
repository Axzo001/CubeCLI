"""Basic sanity tests for the UI screens to ensure no syntax/import errors."""

from __future__ import annotations

from cubecli.config import Config
from cubecli.ui.screens.case_picker import CasePicker
from cubecli.ui.screens.train_screen import TrainScreen


def test_instantiate_train_screen() -> None:
    cfg = Config()
    screen = TrainScreen(cfg)
    assert screen.mode == "oll"
    assert screen.current_case is None


def test_instantiate_case_picker() -> None:
    picker = CasePicker("pll", ["Aa", "Ab"])
    assert picker.mode == "pll"
    assert "Aa" in picker.selected_ids


def test_instantiate_puzzle_picker() -> None:
    from cubecli.ui.screens.puzzle_picker import PuzzlePicker

    picker = PuzzlePicker("3x3")
    assert picker.current_puzzle == "3x3"
