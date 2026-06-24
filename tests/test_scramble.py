"""Tests for scramble generation."""

from __future__ import annotations

from cubecli.core.scramble import PUZZLE_NAMES, count_moves, get_scramble


def test_scramble_is_nonempty():
    s = get_scramble("3x3")
    assert len(s.strip()) > 0


def test_scramble_has_expected_move_count():
    s = get_scramble("3x3")
    moves = count_moves(s)
    # WCA 3x3 scrambles are 20 moves (±1 for orientation)
    assert 15 <= moves <= 25


def test_count_moves_basic():
    assert count_moves("R U R' U'") == 4
    assert count_moves("") == 0


def test_all_puzzles_return_scramble():
    """Every supported puzzle should return a non-empty scramble."""
    for puzzle in PUZZLE_NAMES:
        s = get_scramble(puzzle)
        assert s.strip(), f"Empty scramble for {puzzle}"
