"""CubePreview widget — renders a 2D unfolded net of a Rubik's Cube.

Net layout (standard WCA cross):

          ┌─────────┐
          │    U    │
     ┌────┼─────────┼────┬────┐
     │ L  │    F    │ R  │ B  │
     └────┼─────────┼────┴────┘
          │    D    │
          └─────────┘

Each sticker is rendered as two full-block characters (██) with ANSI colour.
Supports 2x2, 3x3, 4x4, 5x5, 6x6, 7x7 using magiccube when available,
and falls back to local 3x3 state simulator.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cubecli.core.cube_sim import CubeState3x3

# Try to import magiccube dynamically
try:
    import magiccube

    _HAS_MAGICCUBE = True
except ImportError:
    _HAS_MAGICCUBE = False

# Face order indices matching cube_sim module
U, D, F, B, L, R = 0, 1, 2, 3, 4, 5

# Map from index to magiccube Face
if _HAS_MAGICCUBE:
    _FACE_MAP = {
        U: magiccube.Face.U,
        D: magiccube.Face.D,
        F: magiccube.Face.F,
        B: magiccube.Face.B,
        L: magiccube.Face.L,
        R: magiccube.Face.R,
    }
    _COLOR_CHAR_MAP = {
        magiccube.Color.W: "W",
        magiccube.Color.Y: "Y",
        magiccube.Color.G: "G",
        magiccube.Color.B: "B",
        magiccube.Color.O: "O",
        magiccube.Color.R: "R",
    }

# ── WCA standard sticker colours → Rich colour strings ──────────────────────
_BORDER_BG = "on #30363d"
_COLOUR_MAP: dict[str, str] = {
    "W": "#ffffff " + _BORDER_BG,  # Pure White
    "Y": "#ffd700 " + _BORDER_BG,  # Golden Yellow
    "G": "#00a651 " + _BORDER_BG,  # WCA Green
    "O": "#ff5800 " + _BORDER_BG,  # WCA Orange
    "R": "#e31b23 " + _BORDER_BG,  # WCA Red
    "B": "#0051ba " + _BORDER_BG,  # WCA Blue
}

# Character pair rendered as a single sticker
_STICKER = "▀▀"  # two upper half-blocks with coloured foreground


def _get_cube_size(puzzle: str) -> int | None:
    """Return the cube size N for a puzzle string (e.g. '3x3' -> 3, 'Pyraminx' -> None)."""
    if puzzle == "2x2":
        return 2
    elif puzzle == "3x3":
        return 3
    elif puzzle == "4x4":
        return 4
    elif puzzle == "5x5":
        return 5
    elif puzzle == "6x6":
        return 6
    elif puzzle == "7x7":
        return 7
    return None


def _sticker(colour_code: str) -> str:
    """Return a Rich markup string for one sticker."""
    rich_colour = _COLOUR_MAP.get(colour_code, "on #ffffff")
    # Use [/] as the closing tag — Rich does not support 'on' or spaces in
    # closing tags, so [/{rich_colour}] would be malformed markup.
    return f"[{rich_colour}]{_STICKER}[/]"


class CubePreview(Widget):
    """2D unfolded net preview of WCA cube states.

    Call :meth:`set_scramble` to update the displayed state.
    The widget hides itself automatically for non-cubic puzzles.
    """

    DEFAULT_CSS = ""

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)
        self._cube = CubeState3x3()
        # Use object | None so this annotation is safe even when magiccube is
        # not installed (avoids NameError at runtime on the class body).
        self._mc_cube: object | None = None
        self._use_mc = False
        self._puzzle = "3x3"

    def compose(self) -> ComposeResult:
        yield Static("", id="cube-net", markup=True)

    def set_scramble(self, scramble: str, puzzle: str = "3x3") -> None:
        """Apply *scramble* to a fresh solved cube and redraw."""
        self._puzzle = puzzle
        size = _get_cube_size(puzzle)
        if size is not None:
            if _HAS_MAGICCUBE:
                try:
                    cube = magiccube.Cube(size)
                    for move in scramble.strip().split():
                        try:
                            cube.rotate(move)
                        except Exception:
                            # Ignore invalid/unsupported moves
                            pass
                    self._mc_cube = cube
                    self._use_mc = True
                    self.display = True
                    self._redraw()
                except Exception:
                    self.display = False
            elif size == 3:
                # Fallback to local 3x3 simulator
                self._cube.apply_scramble(scramble)
                self._use_mc = False
                self.display = True
                self._redraw()
            else:
                self.display = False
        else:
            # Hide preview for non-cube puzzles (Pyraminx, Megaminx, etc.)
            self.display = False

    def _redraw(self) -> None:
        """Regenerate the net markup and push it into the Static widget."""
        try:
            net = self.query_one("#cube-net", Static)
        except Exception:
            return

        lines = self._build_net_lines()
        net.update("\n".join(lines))

    def _build_net_lines(self) -> list[str]:
        """Build the cross-shaped net as a list of Rich markup lines."""
        if self._use_mc:
            cube = self._mc_cube
            assert cube is not None
            N = cube.size
        else:
            cube = None
            N = 3

        # Dark grey border style tag
        bc = "[#444950 on #30363d]"
        ec = "[/#444950 on #30363d]"

        def get_face_row_stickers(face_idx: int, row: int) -> str:
            """Return a concatenated string of sticker markups for a face row."""
            stickers = []
            if cube is not None:
                mc_face = _FACE_MAP[face_idx]
                grid = cube.get_face(mc_face)
                row_stickers = grid[row]
                for col in range(N):
                    color_enum = row_stickers[col]
                    color_char = _COLOR_CHAR_MAP.get(color_enum, "W")
                    stickers.append(_sticker(color_char))
            else:
                face = self._cube.faces[face_idx]
                base = row * 3
                for col in range(3):
                    stickers.append(_sticker(face[base + col]))
            # Join with a styled space to create horizontal gaps
            return "[on #30363d] [/on #30363d]".join(stickers)

        face_width = 3 * N - 1
        indent = " " * (face_width + 1)
        dashes = "─" * face_width

        lines: list[str] = []

        # 1. U top border
        lines.append(indent + f"{bc}┌{dashes}┐{ec}")

        # 2. U rows
        for row in range(N):
            lines.append(indent + f"{bc}│{ec}" + get_face_row_stickers(U, row) + f"{bc}│{ec}")

        # 3. Middle row top border (shared with U's bottom)
        left_top = "┌" + dashes
        f_top = "┼" + dashes
        r_top = "┼" + dashes
        b_top = "┬" + dashes + "┐"
        lines.append(f"{bc}" + left_top + f_top + r_top + b_top + f"{ec}")

        # 4. Middle rows (L, F, R, B)
        for row in range(N):
            left = get_face_row_stickers(L, row)
            front = get_face_row_stickers(F, row)
            right = get_face_row_stickers(R, row)
            back = get_face_row_stickers(B, row)
            lines.append(
                f"{bc}│{ec}"
                + left
                + f"{bc}│{ec}"
                + front
                + f"{bc}│{ec}"
                + right
                + f"{bc}│{ec}"
                + back
                + f"{bc}│{ec}"
            )

        # 5. Middle row bottom border (shared with D's top)
        left_bot = "└" + dashes
        f_bot = "┼" + dashes
        r_bot = "┼" + dashes
        b_bot = "┴" + dashes + "┘"
        lines.append(f"{bc}" + left_bot + f_bot + r_bot + b_bot + f"{ec}")

        # 6. D rows
        for row in range(N):
            lines.append(indent + f"{bc}│{ec}" + get_face_row_stickers(D, row) + f"{bc}│{ec}")

        # 7. D bottom border
        lines.append(indent + f"{bc}└{dashes}┘{ec}")

        return lines
