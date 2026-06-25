"""CubePreview widget — renders a 2D unfolded net of a 3×3 Rubik's Cube.

Net layout (standard WCA cross):

         ┌─────────┐
         │    U    │
    ┌────┼─────────┼────┬────┐
    │ L  │    F    │ R  │ B  │
    └────┼─────────┼────┴────┘
         │    D    │
         └─────────┘

Each sticker is rendered as two full-block characters (██) with ANSI colour.
The widget is only visible when the puzzle is 3x3 and preview is enabled.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cubecli.core.cube_sim import CubeState3x3

# Face order indices matching cube_sim module
U, D, F, B, L, R = 0, 1, 2, 3, 4, 5

# ── WCA standard sticker colours → Rich colour strings ──────────────────────
_COLOUR_MAP: dict[str, str] = {
    "W": "on white",
    "Y": "on yellow",
    "G": "on green",
    "O": "on dark_orange",
    "R": "on red",
    "B": "on blue",
}

# Character pair rendered as a single sticker
_STICKER = "  "  # two spaces with coloured background

# Blank / spacer (no sticker)
_BLANK = "   "   # three spaces (matches sticker width + gap)


def _sticker(colour_code: str) -> str:
    """Return a Rich markup string for one sticker."""
    rich_colour = _COLOUR_MAP.get(colour_code, "on white")
    return f"[{rich_colour}]{_STICKER}[/{rich_colour}]"


def _render_face_row(face: list[str], row: int) -> str:
    """Return a Rich markup string for one row (3 stickers) of a face."""
    base = row * 3
    return (
        _sticker(face[base])
        + " "
        + _sticker(face[base + 1])
        + " "
        + _sticker(face[base + 2])
    )


class CubePreview(Widget):
    """2D unfolded net preview of the 3×3 Rubik's Cube state.

    Call :meth:`set_scramble` to update the displayed state.
    The widget hides itself automatically for non-3x3 puzzles.
    """

    DEFAULT_CSS = ""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._cube = CubeState3x3()
        self._puzzle = "3x3"

    def compose(self) -> ComposeResult:
        yield Static("", id="cube-net", markup=True)

    def set_scramble(self, scramble: str, puzzle: str = "3x3") -> None:
        """Apply *scramble* to a fresh solved cube and redraw."""
        self._puzzle = puzzle
        if puzzle == "3x3":
            self._cube.apply_scramble(scramble)
            self.display = True
            self._redraw()
        else:
            # Hide preview for non-3x3 puzzles
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
        f = self._cube.faces

        # Width of one face row in characters:
        #   sticker(2) + space(1) + sticker(2) + space(1) + sticker(2) = 8 chars of markup
        #   but we need to pad/indent with blanks for structural layout.

        # Indent for U/D rows (L face width + separator gap)
        indent = _BLANK * 3 + " "  # 3 blanks = one face width + spacer

        lines: list[str] = []

        # ── Row 0-2: U face (indented) ──────────────────────────────────────
        for row in range(3):
            lines.append(indent + _render_face_row(f[U], row))

        # ── Separator ───────────────────────────────────────────────────────
        lines.append("")

        # ── Row 3-5: L | F | R | B faces (side by side) ────────────────────
        for row in range(3):
            left = _render_face_row(f[L], row)
            front = _render_face_row(f[F], row)
            right = _render_face_row(f[R], row)
            back = _render_face_row(f[B], row)
            lines.append(left + "  " + front + "  " + right + "  " + back)

        # ── Separator ───────────────────────────────────────────────────────
        lines.append("")

        # ── Row 6-8: D face (indented) ──────────────────────────────────────
        for row in range(3):
            lines.append(indent + _render_face_row(f[D], row))

        return lines
