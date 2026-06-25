"""Puzzle Picker dialog for selecting WCA puzzles."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList
from textual.widgets.option_list import Option

from cubecli.core.scramble import PUZZLE_NAMES


class PuzzlePicker(Screen[str | None]):
    """A single-selection modal dialog to choose a WCA puzzle."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_puzzle: str) -> None:
        super().__init__()
        self.current_puzzle = current_puzzle

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label(
            "[bold cyan]Select WCA Puzzle[/bold cyan]\n"
            "[dim]Select a puzzle from the list below using the arrow keys/Enter or mouse click.[/dim]",
            id="picker-title",
        )

        with Vertical(id="puzzle-picker-container"):
            # Create OptionList options
            options = [Option(name, id=name) for name in PUZZLE_NAMES]
            yield OptionList(*options, id="puzzle-option-list")

        yield Footer()

    def on_mount(self) -> None:
        """Pre-select the current active puzzle."""
        try:
            option_list = self.query_one("#puzzle-option-list", OptionList)
            # Find the option index
            idx = PUZZLE_NAMES.index(self.current_puzzle)
            option_list.highlighted = idx
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Dismiss the screen with the selected puzzle ID."""
        if event.option.id:
            self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        """Close picker without saving."""
        self.dismiss(None)
