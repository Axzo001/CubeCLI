"""Unit tests for FMC move validation and counting logic."""

from __future__ import annotations

from cubecli.core.fmc import count_fmc_moves, validate_fmc_move


def test_validate_fmc_move_standard() -> None:
    # Standard face turns
    for face in ("U", "D", "R", "L", "F", "B"):
        assert validate_fmc_move(face)
        assert validate_fmc_move(f"{face}'")
        assert validate_fmc_move(f"{face}2")
        assert validate_fmc_move(f"{face}2'")


def test_validate_fmc_move_wide() -> None:
    # Wide turns (capital with w)
    for face in ("Uw", "Dw", "Rw", "Lw", "Fw", "Bw"):
        assert validate_fmc_move(face)
        assert validate_fmc_move(f"{face}'")
        assert validate_fmc_move(f"{face}2")
        assert validate_fmc_move(f"{face}2'")

    # Wide turns (lowercase)
    for face in ("u", "d", "r", "l", "f", "b"):
        assert validate_fmc_move(face)
        assert validate_fmc_move(f"{face}'")
        assert validate_fmc_move(f"{face}2")
        assert validate_fmc_move(f"{face}2'")


def test_validate_fmc_move_rotations() -> None:
    # Rotations
    for rot in ("x", "y", "z"):
        assert validate_fmc_move(rot)
        assert validate_fmc_move(f"{rot}'")
        assert validate_fmc_move(f"{rot}2")
        assert validate_fmc_move(f"{rot}2'")


def test_validate_fmc_move_invalid() -> None:
    # Invalid characters or formats
    assert not validate_fmc_move("")
    assert not validate_fmc_move(" ")
    assert not validate_fmc_move("M")  # Slice moves not allowed in written FMC solutions
    assert not validate_fmc_move("E")
    assert not validate_fmc_move("S")
    assert not validate_fmc_move("R3")
    assert not validate_fmc_move("U''")
    assert not validate_fmc_move("random")


def test_count_fmc_moves_basic() -> None:
    # Standard sequence
    sol = "R U R' U'"
    assert count_fmc_moves(sol) == 4

    # Sequence with wide moves
    sol_wide = "Rw U R' U' Lw' U2"
    assert count_fmc_moves(sol_wide) == 6


def test_count_fmc_moves_with_rotations() -> None:
    # Rotations should count as 0 moves
    sol = "R U R' U' y2 R U R' U'"
    assert count_fmc_moves(sol) == 8

    sol_only_rot = "x y z x2 y' z2'"
    assert count_fmc_moves(sol_only_rot) == 0


def test_count_fmc_moves_invalid() -> None:
    # Contains invalid move
    sol = "R U R' U' M R U"
    assert count_fmc_moves(sol) == -1

    assert count_fmc_moves("") == 0
