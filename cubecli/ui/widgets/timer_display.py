"""Big timer display widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label

from cubecli.core.timer import TimerState, format_time


_BIG_ZERO = "0.000"


class TimerDisplay(Widget):
    """A large, centrally-placed timer label that reacts to timer state.

    The colour class (idle / holding / ready / running / stopped) is set
    via a CSS class on the ``#timer-display`` label so the TCSS file
    controls colours without any Python colour logic.
    """

    DEFAULT_CSS = ""  # Styles come from app.tcss

    #: Current displayed time string
    time_str: reactive[str] = reactive(_BIG_ZERO)
    #: Current timer state — drives CSS class
    state: reactive[TimerState] = reactive(TimerState.IDLE)

    def compose(self) -> ComposeResult:
        yield Label(self._render_time(), id="timer-display", classes="idle")

    # ── Watchers ──────────────────────────────────────────────────────────

    def watch_time_str(self, value: str) -> None:
        self._refresh_label()

    def watch_state(self, value: TimerState) -> None:
        self._refresh_label()

    # ── Public helpers ────────────────────────────────────────────────────

    def set_ms(self, ms: int) -> None:
        """Update the displayed time from milliseconds."""
        self.time_str = format_time(ms)

    def set_state(self, state: TimerState) -> None:
        """Update the timer state (changes colour via CSS class)."""
        self.state = state

    def reset(self) -> None:
        """Return to idle zero display."""
        self.time_str = _BIG_ZERO
        self.state = TimerState.IDLE

    # ── Internal helpers ──────────────────────────────────────────────────

    def _render_time(self) -> str:
        """Return the time string padded for visual centering."""
        # Pad with spaces for visual weight
        return f"  {self.time_str}  "

    def _refresh_label(self) -> None:
        """Re-render the label with updated text and CSS class."""
        try:
            label = self.query_one("#timer-display", Label)
        except Exception:
            return

        label.update(self._render_time())

        # Toggle CSS classes to match timer state
        state_class = self.state.name.lower()  # idle/holding/ready/running/stopped
        for cls in ("idle", "holding", "ready", "running", "stopped"):
            label.remove_class(cls)
        label.add_class(state_class)
