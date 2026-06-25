"""Lightweight 3×3 Rubik's Cube state simulator.

Represents a cube as six 3×3 faces (U, D, F, B, L, R).
Each face is a list of 9 stickers in row-major order as seen
**from outside the cube looking in at that face** (left-to-right, top-to-bottom).

Sticker colour codes
---------------------
W = White  (Up)
Y = Yellow (Down)
G = Green  (Front)
B = Blue   (Back)
O = Orange (Left)
R = Red    (Right)

Sticker grid within a face (viewed from outside)
-------------------------------------------------
  0  1  2
  3  4  5
  6  7  8

Moves
-----
Supports all 18 standard WCA outer-layer moves:
U  U' U2   D  D' D2
F  F' F2   B  B' B2
L  L' L2   R  R' R2

Unknown tokens (e.g. rotation moves x/y/z) are silently ignored.

Implementation notes
--------------------
Move logic is ported from the well-tested pglass/cube reference implementation
(https://github.com/pglass/cube) which has been verified correct against known
group-theory move orders (order(R U) = 105, order(T-perm) = 2, etc.).
The 2-D [row][col] indexing from pglass is mapped to our flat [row*3+col] layout.
"""

from __future__ import annotations

import copy
import re

# Face indices
U, D, F, B, L, R = 0, 1, 2, 3, 4, 5

# Default solved colours per face index
_SOLVED_COLOURS = ["W", "Y", "G", "B", "O", "R"]


# ── Internal helpers ──────────────────────────────────────────────────────────


def _rot90_cw(face: list[str]) -> list[str]:
    """Rotate a 9-element face list 90° clockwise (viewed from outside)."""
    # pglass: [[face[n-1-j][i] for j in range(n)] for i in range(n)]
    # n=3, flat index (r,c) = r*3+c  →  new[r*3+c] = old[(n-1-c)*3+r]
    return [
        face[6],
        face[3],
        face[0],
        face[7],
        face[4],
        face[1],
        face[8],
        face[5],
        face[2],
    ]


# ── Main class ────────────────────────────────────────────────────────────────


class CubeState3x3:
    """Mutable 3×3 Rubik's Cube state.

    Attributes
    ----------
    faces : list[list[str]]
        Six faces in order [U, D, F, B, L, R].
        Each face is a flat list of 9 colour characters.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Return cube to the solved (identity) state."""
        self.faces: list[list[str]] = [[c] * 9 for c in _SOLVED_COLOURS]

    def apply_scramble(self, scramble: str) -> None:
        """Reset to solved, then apply every move in *scramble*."""
        self.reset()
        for token in scramble.strip().split():
            self._apply_move(token)

    # ── Internal move dispatcher ──────────────────────────────────────────────

    def _apply_move(self, token: str) -> None:
        """Apply a single WCA move token (e.g. ``"U'"``, ``"R2"``)."""
        m = re.fullmatch(r"([UDFBLR])([2']?)", token.strip())
        if m is None:
            return  # ignore unknown tokens (x/y/z rotation moves, etc.)
        face_char, modifier = m.groups()
        move_fn = {
            "U": self._U_cw,
            "D": self._D_cw,
            "F": self._F_cw,
            "B": self._B_cw,
            "L": self._L_cw,
            "R": self._R_cw,
        }[face_char]
        if modifier == "'":
            for _ in range(3):
                move_fn()
        elif modifier == "2":
            for _ in range(2):
                move_fn()
        else:
            move_fn()

    # ── Individual CW face moves (verified against pglass/cube reference) ─────
    #
    # Mapping: pglass face[row][col] ↔ our flat face[row*3+col]
    # Helper: F(r,c) ≡ face[r*3+c]

    def _U_cw(self) -> None:
        """U face clockwise (looking from above)."""
        f = self.faces
        f[U] = _rot90_cw(f[U])
        # Adjacent: F top row ← R top row ← B top row ← L top row ← F top row
        # (pglass: F[0][c]←R[0][c]←B[0][c]←L[0][c]←tmp)
        tmp = f[F][0], f[F][1], f[F][2]
        f[F][0], f[F][1], f[F][2] = f[R][0], f[R][1], f[R][2]
        f[R][0], f[R][1], f[R][2] = f[B][0], f[B][1], f[B][2]
        f[B][0], f[B][1], f[B][2] = f[L][0], f[L][1], f[L][2]
        f[L][0], f[L][1], f[L][2] = tmp

    def _D_cw(self) -> None:
        """D face clockwise (looking from below)."""
        f = self.faces
        f[D] = _rot90_cw(f[D])
        # Adjacent: F bot row ← L bot row ← B bot row ← R bot row ← F bot row
        # (pglass: F[2][c]←L[2][c]←B[2][c]←R[2][c]←tmp)
        tmp = f[F][6], f[F][7], f[F][8]
        f[F][6], f[F][7], f[F][8] = f[L][6], f[L][7], f[L][8]
        f[L][6], f[L][7], f[L][8] = f[B][6], f[B][7], f[B][8]
        f[B][6], f[B][7], f[B][8] = f[R][6], f[R][7], f[R][8]
        f[R][6], f[R][7], f[R][8] = tmp

    def _F_cw(self) -> None:
        """F face clockwise (looking from front)."""
        f = self.faces
        f[F] = _rot90_cw(f[F])
        # pglass: for c in range(3):
        #   U[2][c] ← L[2-c][2]  →  U[6+c] ← L[(2-c)*3+2]
        #   L[2-c][2] ← D[0][2-c] → L[(2-c)*3+2] ← D[2-c]
        #   D[0][2-c] ← R[c][0]   → D[2-c] ← R[c*3]
        #   R[c][0] ← tmp[c]      → R[c*3] ← tmp[c]
        tmp = f[U][6], f[U][7], f[U][8]
        # c=0: U[6]←L[8], L[8]←D[2], D[2]←R[0]
        # c=1: U[7]←L[5], L[5]←D[1], D[1]←R[3]
        # c=2: U[8]←L[2], L[2]←D[0], D[0]←R[6]
        f[U][6], f[U][7], f[U][8] = f[L][8], f[L][5], f[L][2]
        f[L][8], f[L][5], f[L][2] = f[D][2], f[D][1], f[D][0]
        f[D][2], f[D][1], f[D][0] = f[R][0], f[R][3], f[R][6]
        f[R][0], f[R][3], f[R][6] = tmp[0], tmp[1], tmp[2]

    def _B_cw(self) -> None:
        """B face clockwise (looking from back)."""
        f = self.faces
        f[B] = _rot90_cw(f[B])
        # pglass: for c in range(3):
        #   U[0][c] ← R[c][2]    → U[c] ← R[c*3+2]
        #   R[c][2] ← D[2][2-c]  → R[c*3+2] ← D[6+2-c] = D[8-c]
        #   D[2][2-c] ← L[2-c][0]→ D[8-c] ← L[(2-c)*3]
        #   L[2-c][0] ← tmp[c]   → L[(2-c)*3] ← tmp[c]
        tmp = f[U][0], f[U][1], f[U][2]
        # c=0: U[0]←R[2],  R[2]←D[8],  D[8]←L[6],  L[6]←tmp[0]
        # c=1: U[1]←R[5],  R[5]←D[7],  D[7]←L[3],  L[3]←tmp[1]
        # c=2: U[2]←R[8],  R[8]←D[6],  D[6]←L[0],  L[0]←tmp[2]
        f[U][0], f[U][1], f[U][2] = f[R][2], f[R][5], f[R][8]
        f[R][2], f[R][5], f[R][8] = f[D][8], f[D][7], f[D][6]
        f[D][8], f[D][7], f[D][6] = f[L][6], f[L][3], f[L][0]
        f[L][6], f[L][3], f[L][0] = tmp[0], tmp[1], tmp[2]

    def _L_cw(self) -> None:
        """L face clockwise (looking from left)."""
        f = self.faces
        f[L] = _rot90_cw(f[L])
        # pglass: for r in range(3):
        #   U[r][0] ← B[2-r][2]  → U[r*3] ← B[(2-r)*3+2]
        #   B[2-r][2] ← D[r][0]  → B[(2-r)*3+2] ← D[r*3]
        #   D[r][0] ← F[r][0]    → D[r*3] ← F[r*3]
        #   F[r][0] ← tmp[r]     → F[r*3] ← tmp[r]
        tmp = f[U][0], f[U][3], f[U][6]
        # r=0: U[0]←B[8], B[8]←D[0], D[0]←F[0], F[0]←tmp[0]
        # r=1: U[3]←B[5], B[5]←D[3], D[3]←F[3], F[3]←tmp[1]
        # r=2: U[6]←B[2], B[2]←D[6], D[6]←F[6], F[6]←tmp[2]
        f[U][0], f[U][3], f[U][6] = f[B][8], f[B][5], f[B][2]
        f[B][8], f[B][5], f[B][2] = f[D][0], f[D][3], f[D][6]
        f[D][0], f[D][3], f[D][6] = f[F][0], f[F][3], f[F][6]
        f[F][0], f[F][3], f[F][6] = tmp[0], tmp[1], tmp[2]

    def _R_cw(self) -> None:
        """R face clockwise (looking from right)."""
        f = self.faces
        f[R] = _rot90_cw(f[R])
        # pglass: for r in range(3):
        #   U[r][2] ← F[r][2]    → U[r*3+2] ← F[r*3+2]
        #   F[r][2] ← D[r][2]    → F[r*3+2] ← D[r*3+2]
        #   D[r][2] ← B[2-r][0]  → D[r*3+2] ← B[(2-r)*3]
        #   B[2-r][0] ← tmp[r]   → B[(2-r)*3] ← tmp[r]
        tmp = f[U][2], f[U][5], f[U][8]
        # r=0: U[2]←F[2], F[2]←D[2], D[2]←B[6], B[6]←tmp[0]
        # r=1: U[5]←F[5], F[5]←D[5], D[5]←B[3], B[3]←tmp[1]
        # r=2: U[8]←F[8], F[8]←D[8], D[8]←B[0], B[0]←tmp[2]
        f[U][2], f[U][5], f[U][8] = f[F][2], f[F][5], f[F][8]
        f[F][2], f[F][5], f[F][8] = f[D][2], f[D][5], f[D][8]
        f[D][2], f[D][5], f[D][8] = f[B][6], f[B][3], f[B][0]
        f[B][6], f[B][3], f[B][0] = tmp[0], tmp[1], tmp[2]

    # ── Utilities ──────────────────────────────────────────────────────────────

    def copy(self) -> CubeState3x3:
        """Return a deep copy of this state."""
        new = CubeState3x3.__new__(CubeState3x3)
        new.faces = copy.deepcopy(self.faces)
        return new

    def is_solved(self) -> bool:
        """Return True if all nine stickers on each face share one colour."""
        return all(len(set(face)) == 1 for face in self.faces)
