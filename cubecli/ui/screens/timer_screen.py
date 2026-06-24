"""Main timer screen — heart of CubeCLI.

Hold-to-start mechanism
-----------------------
Textual does not expose a reliable key-release event across all terminal
emulators.  Instead we use the fact that held keys produce a rapid stream
of repeat events (~30 Hz) while released keys stop the stream.

Algorithm
~~~~~~~~~
1. Any SPACE event while IDLE/STOPPED → record ``_hold_start`` and
   set state to HOLDING.
2. Keep resetting a 150 ms one-shot timer on every repeat event.
   When the 150 ms timer fires without another space event, the key
   was released → call ``_on_space_released()``.
3. If 500 ms have elapsed since ``_hold_start`` the display turns
   green (READY).
4. Release in READY state → start the precision timer (RUNNING).
5. Release in HOLDING state (< 500 ms) → cancel back to IDLE.
6. Any SPACE event while RUNNING → stop the timer (STOPPED).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pyperclip  # type: ignore[import]
from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Label

from cubecli.config import Config
from cubecli.core import scramble as scr_mod
from cubecli.core import stats as stats_mod
from cubecli.core.timer import PrecisionTimer, TimerState, format_time
from cubecli.data import db
from cubecli.data.models import Session, Solve
from cubecli.ui.widgets.scramble_panel import ScramblePanel
from cubecli.ui.widgets.solve_list import SolveList
from cubecli.ui.widgets.stats_panel import StatsPanel
from cubecli.ui.widgets.timer_display import TimerDisplay

if TYPE_CHECKING:
    from textual.events import Key

# ── Constants ──────────────────────────────────────────────────────────────────
_HOLD_MS = 500          # ms to hold before READY state
_RELEASE_DELAY = 0.15   # seconds with no space event → key released
_TICK_INTERVAL = 0.01   # seconds between display refreshes while RUNNING


class TimerScreen(Screen):
    """Full-screen timer interface."""

    BINDINGS = []  # We handle all keys manually for full control

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.cfg = config

        # Timer state
        self._state = TimerState.IDLE
        self._hold_start: float | None = None
        self._precision_timer = PrecisionTimer()
        self._tick_timer: Timer | None = None
        self._release_timer: Timer | None = None

        # Session + solves
        self._session: Session | None = None
        self._solves: list[Solve] = []
        self._last_solve: Solve | None = None

        # Current scramble
        self._scramble: str = ""

    def on_mount(self) -> None:
        """Initialise DB, load session, generate first scramble."""
        db.ensure_schema()
        self._session = db.get_or_create_session(
            self.cfg.session_name, self.cfg.puzzle
        )
        self._solves = db.get_solves(self._session.id)  # type: ignore[arg-type]
        self._new_scramble()
        self._refresh_stats()
        self._refresh_solve_list()
        self._update_header()

    # ── Layout ─────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        # Header strip
        yield Label("", id="app-header")

        # Scramble section
        with Container(id="scramble-section"):
            yield ScramblePanel(id="scramble-panel")

        # Central timer area
        with Container(id="timer-section"):
            yield TimerDisplay(id="timer-widget")
            yield Label(
                "[dim]Hold [bold]SPACE[/bold] to ready, release to start[/dim]",
                id="status-label",
            )

        # Bottom: stats + solve list
        with Horizontal(id="bottom-section"):
            with Vertical(id="stats-panel"):
                yield StatsPanel(id="stats-widget")
            with Vertical(id="solve-list-panel"):
                yield SolveList(id="solve-list-widget")

        # Key hints footer
        yield Label(
            "[dim]"
            "[bold]SPACE[/bold] time  "
            "[bold]d[/bold] DNF  "
            "[bold]p[/bold] +2  "
            "[bold]z[/bold] undo  "
            "[bold]r[/bold] scramble  "
            "[bold]c[/bold] copy  "
            "[bold]P[/bold] puzzle  "
            "[bold]q[/bold] quit"
            "[/dim]",
            id="key-hints",
        )

    # ── Key handling ───────────────────────────────────────────────────────

    def on_key(self, event: "Key") -> None:
        event.stop()

        match event.key:
            case "space":
                self._handle_space()
            case "d":
                self._apply_penalty("DNF")
            case "p":
                self._apply_penalty("+2")
            case "z" | "ctrl+z":
                self._undo_delete()
            case "r" if self._state not in (TimerState.RUNNING,):
                self._new_scramble()
            case "c":
                self._copy_scramble()
            case "P":
                self._cycle_puzzle()
            case "q" | "escape":
                self.app.exit()
            # Num-pad or digit keys ignored during running
            case _:
                pass

    # ── Space hold / release state machine ────────────────────────────────

    def _handle_space(self) -> None:
        """Entry point for every SPACE key event (press + auto-repeat)."""
        match self._state:
            case TimerState.RUNNING:
                self._stop_solve()

            case TimerState.IDLE | TimerState.STOPPED:
                if self._hold_start is None:
                    self._hold_start = time.perf_counter()
                    self._set_state(TimerState.HOLDING)

                # Check if we've held long enough → READY
                elapsed_ms = (time.perf_counter() - self._hold_start) * 1000
                if elapsed_ms >= _HOLD_MS and self._state == TimerState.HOLDING:
                    self._set_state(TimerState.READY)

                # Reset the release-detector timer on every repeat
                self._reset_release_timer()

            case TimerState.HOLDING | TimerState.READY:
                # Key is still held — keep checking elapsed
                if self._hold_start:
                    elapsed_ms = (time.perf_counter() - self._hold_start) * 1000
                    if elapsed_ms >= _HOLD_MS and self._state == TimerState.HOLDING:
                        self._set_state(TimerState.READY)
                self._reset_release_timer()

    def _reset_release_timer(self) -> None:
        """Reset the 150 ms one-shot that detects key release."""
        if self._release_timer is not None:
            self._release_timer.stop()
        self._release_timer = self.set_timer(
            _RELEASE_DELAY, self._on_space_released
        )

    def _on_space_released(self) -> None:
        """Called ~150 ms after the last space event — the key was released."""
        self._release_timer = None

        match self._state:
            case TimerState.READY:
                self._start_solve()
            case TimerState.HOLDING:
                # Released too early — back to idle
                self._hold_start = None
                self._set_state(TimerState.IDLE)

    # ── Solve lifecycle ────────────────────────────────────────────────────

    def _start_solve(self) -> None:
        """Begin timing a new solve."""
        self._hold_start = None
        self._precision_timer.start()
        self._set_state(TimerState.RUNNING)

        # Live tick to update the display
        self._tick_timer = self.set_interval(_TICK_INTERVAL, self._tick)

    def _tick(self) -> None:
        """Called repeatedly while RUNNING to update the displayed time."""
        if self._state == TimerState.RUNNING:
            ms = self._precision_timer.elapsed_ms
            self._timer_display.set_ms(ms)

    def _stop_solve(self) -> None:
        """Stop timing and record the result."""
        elapsed_ms = self._precision_timer.stop()

        # Cancel live updates
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer = None

        # Show the final time
        self._timer_display.set_ms(elapsed_ms)
        self._set_state(TimerState.STOPPED)

        # Persist
        assert self._session is not None
        solve = Solve(
            time_ms=elapsed_ms,
            scramble=self._scramble,
            puzzle=self.cfg.puzzle,
            session_id=self._session.id,
        )
        db.insert_solve(solve)
        self._solves.append(solve)
        self._last_solve = solve

        # Generate next scramble immediately (background)
        self._new_scramble()
        self._refresh_stats()
        self._refresh_solve_list()
        self._update_status(
            f"[dim]Last: [bold]{solve.display_time}[/bold]  ·  "
            "[bold]d[/bold] DNF  [bold]p[/bold] +2  [bold]z[/bold] undo[/dim]"
        )

    # ── Penalties ──────────────────────────────────────────────────────────

    def _apply_penalty(self, penalty: str) -> None:
        """Toggle a +2/DNF penalty on the last solve."""
        if self._state != TimerState.STOPPED or self._last_solve is None:
            return
        solve = self._last_solve
        # Toggle: if already this penalty, clear it
        if solve.penalty == penalty:
            solve.penalty = None
        else:
            solve.penalty = penalty

        db.update_solve_penalty(solve.id, solve.penalty)  # type: ignore[arg-type]
        self._timer_display.set_ms(solve.effective_ms or solve.time_ms)
        self._refresh_stats()
        self._refresh_solve_list()
        self._update_status(
            f"[dim]Penalty: [bold]{solve.penalty or 'cleared'}[/bold][/dim]"
        )

    def _undo_delete(self) -> None:
        """Delete the most recent solve (acts as 'undo last solve')."""
        if not self._solves:
            return
        last = self._solves[-1]
        if last.id is not None:
            db.delete_solve(last.id)
        self._solves.pop()
        self._last_solve = self._solves[-1] if self._solves else None
        self._set_state(TimerState.IDLE)
        self._timer_display.reset()
        self._refresh_stats()
        self._refresh_solve_list()
        self.notify("Last solve deleted", severity="warning", timeout=2)

    # ── Scramble ───────────────────────────────────────────────────────────

    @work(thread=True)
    def _new_scramble(self) -> None:
        """Generate a new scramble in a background thread (non-blocking)."""
        scramble = scr_mod.get_scramble(self.cfg.puzzle)
        self.call_from_thread(self._apply_scramble, scramble)

    def _apply_scramble(self, scramble: str) -> None:
        self._scramble = scramble
        try:
            panel = self.query_one("#scramble-panel", ScramblePanel)
            panel.set_scramble(scramble, self.cfg.puzzle)
        except Exception:
            pass

    def _copy_scramble(self) -> None:
        if self._scramble:
            try:
                pyperclip.copy(self._scramble)
                self.notify("Scramble copied!", timeout=2)
            except Exception:
                self.notify("Clipboard not available", severity="warning", timeout=2)

    # ── Puzzle cycling ─────────────────────────────────────────────────────

    def _cycle_puzzle(self) -> None:
        """Switch to the next puzzle in the list."""
        if self._state == TimerState.RUNNING:
            return
        self.cfg.next_puzzle()
        self.cfg.save()
        # Create/load session for new puzzle
        assert self._session is not None
        self._session = db.get_or_create_session(
            self.cfg.session_name, self.cfg.puzzle
        )
        self._solves = db.get_solves(self._session.id)  # type: ignore[arg-type]
        self._last_solve = None
        self._set_state(TimerState.IDLE)
        self._timer_display.reset()
        self._new_scramble()
        self._refresh_stats()
        self._refresh_solve_list()
        self._update_header()
        self.notify(f"Puzzle: {self.cfg.puzzle}", timeout=2)

    # ── Display helpers ────────────────────────────────────────────────────

    def _set_state(self, state: TimerState) -> None:
        self._state = state
        self._timer_display.set_state(state)

        match state:
            case TimerState.IDLE:
                self._update_status(
                    "[dim]Hold [bold]SPACE[/bold] to ready, release to start[/dim]"
                )
            case TimerState.HOLDING:
                self._update_status("[yellow]Holding… keep holding…[/yellow]")
            case TimerState.READY:
                self._update_status("[bold green]✓  Release SPACE to start![/bold green]")
            case TimerState.RUNNING:
                self._update_status("[dim]Press [bold]SPACE[/bold] to stop[/dim]")
            case TimerState.STOPPED:
                pass  # Status updated in _stop_solve

    def _update_status(self, markup: str) -> None:
        try:
            self.query_one("#status-label", Label).update(markup)
        except Exception:
            pass

    def _update_header(self) -> None:
        solve_count = len(self._solves)
        session_name = self.cfg.session_name
        puzzle = self.cfg.puzzle
        try:
            self.query_one("#app-header", Label).update(
                f"  🧊 [bold cyan]CubeCLI[/bold cyan]"
                f"  [dim]│[/dim]  {puzzle}"
                f"  [dim]│[/dim]  {session_name}"
                f"  [dim]│[/dim]  {solve_count} solves"
            )
        except Exception:
            pass

    # ── Stats refresh ──────────────────────────────────────────────────────

    def _refresh_stats(self) -> None:
        times = [s.effective_ms for s in self._solves]

        single = self._last_solve.effective_ms if self._last_solve else None
        mo3    = stats_mod.calculate_mo3(times)
        ao5    = stats_mod.calculate_ao5(times)
        ao12   = stats_mod.calculate_ao12(times)
        ao50   = stats_mod.calculate_ao50(times)
        best   = stats_mod.best_time(times)
        mean   = stats_mod.session_mean(times)

        # Is single a new session PB?
        single_is_pb = (
            single is not None
            and best is not None
            and single == best
            and len([t for t in times if t is not None]) > 0
        )

        try:
            self.query_one("#stats-widget", StatsPanel).update_stats(
                single, mo3, ao5, ao12, ao50, best, mean,
                len(self._solves), single_is_pb
            )
        except Exception:
            pass

        self._update_header()

    def _refresh_solve_list(self) -> None:
        try:
            self.query_one("#solve-list-widget", SolveList).update_solves(self._solves)
        except Exception:
            pass

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def _timer_display(self) -> TimerDisplay:
        return self.query_one("#timer-widget", TimerDisplay)
