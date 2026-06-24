"""Scramble display panel widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label

from cubecli.core.scramble import count_moves


class ScramblePanel(Widget):
    """Displays the current scramble string with a move-count badge.

    The scramble text wraps over two lines when needed so it never
    gets clipped in narrow terminals.
    """

    DEFAULT_CSS = ""

    scramble: reactive[str] = reactive("")
    puzzle: reactive[str] = reactive("3x3")

    def compose(self) -> ComposeResult:
        yield Label("", id="scramble-header")
        yield Label("", id="scramble-text")

    def on_mount(self) -> None:
        self._refresh()

    def watch_scramble(self, _: str) -> None:
        self._refresh()

    def watch_puzzle(self, _: str) -> None:
        self._refresh()

    def set_scramble(self, scramble: str, puzzle: str = "3x3") -> None:
        """Update both the scramble and puzzle at once."""
        self.puzzle = puzzle
        self.scramble = scramble

    def _refresh(self) -> None:
        moves = count_moves(self.scramble)
        try:
            self.query_one("#scramble-header", Label).update(
                f"[dim]── {self.puzzle}  ·  {moves} moves ──  "
                f"\\[r] new  \\[c] copy[/dim]"
            )
            self.query_one("#scramble-text", Label).update(
                f"[bold]{self.scramble or '…generating…'}[/bold]"
            )
        except Exception:
            pass
