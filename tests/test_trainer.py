"""Tests for algorithm training logic."""

from __future__ import annotations

import pytest

from cubecli.data.models import Solve
from cubecli.training.trainer import (
    Case,
    get_setup_scramble,
    invert_algorithm,
    invert_move,
    load_cases,
    select_next_case,
)


def test_invert_move() -> None:
    assert invert_move("R") == "R'"
    assert invert_move("R'") == "R"
    assert invert_move("R2") == "R2"
    assert invert_move("R2'") == "R2"
    assert invert_move("(R)") == "R'"
    assert invert_move("[R']") == "R"
    assert invert_move("") == ""


def test_invert_algorithm() -> None:
    assert invert_algorithm("R U R' U'") == "U R U' R'"
    assert invert_algorithm("F R U R' U' F'") == "F U R U' R' F'"
    assert invert_algorithm("(R U R' U') (R' F R F')") == "F R' F' R U R U' R'"
    assert invert_algorithm("") == ""


def test_get_setup_scramble() -> None:
    scramble = get_setup_scramble("R U R' U'")
    assert "U R U' R'" in scramble
    # Pre and post-rotations should be valid U-layer moves
    parts = scramble.split()
    for part in parts:
        assert part.replace("'", "").replace("2", "") in ("U", "R")


def test_load_cases() -> None:
    oll_cases = load_cases("oll")
    assert len(oll_cases) == 57
    assert oll_cases[0].id == "1"
    assert oll_cases[26].name == "Sune"

    pll_cases = load_cases("pll")
    assert len(pll_cases) == 21
    assert pll_cases[0].id == "Aa"

    with pytest.raises(ValueError):
        load_cases("invalid")


def test_select_next_case() -> None:
    cases = [
        Case(id="1", name="Case 1", algorithm="R U R'", diagram="", group="OLL"),
        Case(id="2", name="Case 2", algorithm="L U L'", diagram="", group="OLL"),
    ]
    # No solves: equal chance (roughly)
    c = select_next_case(cases, [])
    assert c in cases

    # Case 1 has a slow solve, Case 2 has a fast solve
    solves = [
        Solve(time_ms=5000, scramble="", puzzle="oll", notes="1", session_id=1),
        Solve(time_ms=1000, scramble="", puzzle="oll", notes="2", session_id=1),
    ]
    # Spaced rep should prioritize Case 1 (higher weight)
    # We run it multiple times to ensure Case 1 gets chosen more
    chosen = [select_next_case(cases, solves).id for _ in range(100)]
    assert chosen.count("1") > chosen.count("2")

    # Case 2 last solve DNF
    solves_dnf = [
        Solve(time_ms=5000, scramble="", puzzle="oll", notes="1", session_id=1),
        Solve(time_ms=1000, scramble="", puzzle="oll", notes="2", penalty="DNF", session_id=1),
    ]
    chosen_dnf = [select_next_case(cases, solves_dnf).id for _ in range(100)]
    assert chosen_dnf.count("2") > chosen_dnf.count("1")
