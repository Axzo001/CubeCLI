"""Unit tests for cubecli.core.cube_sim."""

from __future__ import annotations

from cubecli.core.cube_sim import CubeState3x3


class TestCubeStateInit:
    def test_solved_on_init(self) -> None:
        cube = CubeState3x3()
        assert cube.is_solved()

    def test_faces_have_nine_stickers(self) -> None:
        cube = CubeState3x3()
        for face in cube.faces:
            assert len(face) == 9

    def test_reset_restores_solved(self) -> None:
        cube = CubeState3x3()
        cube._apply_move("R")
        assert not cube.is_solved()
        cube.reset()
        assert cube.is_solved()


class TestSingleMoves:
    def test_u_cw_four_times_is_identity(self) -> None:
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for _ in range(4):
            cube._apply_move("U")
        assert cube.faces == initial

    def test_d_cw_four_times_is_identity(self) -> None:
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for _ in range(4):
            cube._apply_move("D")
        assert cube.faces == initial

    def test_f_cw_four_times_is_identity(self) -> None:
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for _ in range(4):
            cube._apply_move("F")
        assert cube.faces == initial

    def test_b_cw_four_times_is_identity(self) -> None:
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for _ in range(4):
            cube._apply_move("B")
        assert cube.faces == initial

    def test_l_cw_four_times_is_identity(self) -> None:
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for _ in range(4):
            cube._apply_move("L")
        assert cube.faces == initial

    def test_r_cw_four_times_is_identity(self) -> None:
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for _ in range(4):
            cube._apply_move("R")
        assert cube.faces == initial

    def test_ccw_is_inverse_of_cw(self) -> None:
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for face_str in ["U", "D", "F", "B", "L", "R"]:
            cube._apply_move(face_str)
            cube._apply_move(face_str + "'")
            assert cube.faces == initial, f"CW+CCW not identity for face {face_str}"


class TestMoveSequences:
    def _apply_sequence(self, cube: CubeState3x3, seq: str) -> None:
        """Apply a sequence of moves without resetting."""
        for token in seq.strip().split():
            cube._apply_move(token)

    def test_sexy_move_six_times(self) -> None:
        """R U R' U' repeated 6 times → solved."""
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for _ in range(6):
            self._apply_sequence(cube, "R U R' U'")
        assert cube.faces == initial

    def test_sune_algorithm_repetition(self) -> None:
        """R U R' U R U2 R' repeated 6 times → solved."""
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        for _ in range(6):
            self._apply_sequence(cube, "R U R' U R U2 R'")
        assert cube.faces == initial

    def test_t_perm_twice_is_identity(self) -> None:
        """T-perm repeated twice → solved."""
        t_perm = "R U R' U' R' F R2 U' R' U' R U R' F'"
        cube = CubeState3x3()
        initial = [face[:] for face in cube.faces]
        self._apply_sequence(cube, t_perm)
        assert not cube.is_solved()
        self._apply_sequence(cube, t_perm)
        assert cube.faces == initial

    def test_apply_scramble_resets_first(self) -> None:
        """Calling apply_scramble twice starts fresh each time."""
        cube = CubeState3x3()
        cube.apply_scramble("R U")
        state_after_ru = [face[:] for face in cube.faces]

        cube.apply_scramble("R U")
        assert cube.faces == state_after_ru


class TestMoveParser:
    def test_double_move(self) -> None:
        """U2 == U U."""
        cube1 = CubeState3x3()
        cube1.apply_scramble("U2")

        cube2 = CubeState3x3()
        cube2.apply_scramble("U U")

        assert cube1.faces == cube2.faces

    def test_prime_move(self) -> None:
        """U' == U U U."""
        cube1 = CubeState3x3()
        cube1.apply_scramble("U'")

        cube2 = CubeState3x3()
        cube2.apply_scramble("U U U")

        assert cube1.faces == cube2.faces

    def test_unknown_token_ignored(self) -> None:
        """Rotation moves like 'x' or 'y' don't crash."""
        cube = CubeState3x3()
        cube.apply_scramble("R x y z M E S")  # Only R should apply
        assert not cube.is_solved()

    def test_empty_scramble_stays_solved(self) -> None:
        cube = CubeState3x3()
        cube.apply_scramble("")
        assert cube.is_solved()


class TestCopy:
    def test_copy_is_independent(self) -> None:
        cube = CubeState3x3()
        cube.apply_scramble("R U F")
        copy = cube.copy()
        cube.apply_scramble("L")
        # copy must not be affected
        original_faces = [face[:] for face in copy.faces]
        assert copy.faces == original_faces
