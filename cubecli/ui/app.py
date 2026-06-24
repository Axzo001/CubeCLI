"""CubeCLI Textual application."""

from __future__ import annotations

from textual.app import App

from cubecli.config import Config
from cubecli.ui.screens.timer_screen import TimerScreen


class CubeCLIApp(App):
    """The root Textual application for CubeCLI.

    Loads user config, then pushes the :class:`TimerScreen` as the
    initial and only screen for Phase 1.
    """

    CSS_PATH = "app.tcss"
    TITLE = "CubeCLI"
    SUB_TITLE = "Speedcubing Timer"

    def __init__(self) -> None:
        super().__init__()
        self.cfg = Config.load()

    def on_mount(self) -> None:
        self.push_screen(TimerScreen(self.cfg))
