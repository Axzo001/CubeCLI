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

import pyperclip
from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.geometry import Size
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Button, Input, Label

from cubecli.config import Config
from cubecli.core import scramble as scr_mod
from cubecli.core import stats as stats_mod
from cubecli.core.timer import PrecisionTimer, TimerState
from cubecli.data import db
from cubecli.data.models import Session, Solve
from cubecli.ui.screens.stats_screen import StatsScreen
from cubecli.ui.screens.train_screen import TrainScreen
from cubecli.ui.widgets.cube_preview import CubePreview
from cubecli.ui.widgets.scramble_panel import ScramblePanel
from cubecli.ui.widgets.sidebar_btn import SidebarButton
from cubecli.ui.widgets.solve_list import SolveList
from cubecli.ui.widgets.stats_panel import StatsPanel
from cubecli.ui.widgets.timer_display import TimerDisplay

if TYPE_CHECKING:
    from textual.events import Key

# ── Constants ──────────────────────────────────────────────────────────────────
_HOLD_MS = 500  # ms to hold before READY state
_RELEASE_DELAY = 0.15  # seconds with no space event → key released
_TICK_INTERVAL = 0.01  # seconds between display refreshes while RUNNING


class TimerScreen(Screen[None]):
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

        # BLD states
        self._bld_phase: str | None = None
        self._bld_start_time: float | None = None
        self._bld_exec_start: float | None = None
        self._bld_memo_ms: int = 0
        self._bld_exec_ms: int = 0

        # CFOP split states
        self._cfop_stage: int = 0
        self._cfop_split_times: list[int] = []
        self._cfop_start_time: float = 0.0
        self._cfop_last_split_time: float = 0.0

        # WCA Inspection states
        self._is_inspecting: bool = False
        self._inspection_start: float = 0.0
        self._inspection_beeps: set[str] = set()
        self._solve_penalty: str | None = None

        # Metronome states
        self._metronome_timer: Timer | None = None

        # FMC states
        self._fmc_seconds_left: int = 3600
        self._fmc_interval_timer: Timer | None = None

    def on_mount(self) -> None:
        """Initialise DB, load session, generate first scramble."""
        db.ensure_schema()
        self._session = db.get_or_create_session(self.cfg.session_name, self.cfg.puzzle)
        self._solves = db.get_solves(self._session.id)  # type: ignore[arg-type]
        self._new_scramble()
        self._refresh_stats()
        self._refresh_solve_list()
        self._update_header()

        # Restore FMC layout if enabled in config
        if self.cfg.fmc_mode_enabled:
            self._set_fmc_layout(True)

    def watch_size(self, size: Size) -> None:
        """Handle screen resizing to dynamically toggle the cube preview."""
        self._adjust_layout_for_size(size)

    def _adjust_layout_for_size(self, size: Size | None = None) -> None:
        if self.cfg.fmc_mode_enabled:
            return
        if size is None:
            try:
                size = self.size
            except Exception:
                # App size is not available (e.g. screen not mounted in tests)
                return
        try:
            preview = self.query_one("#cube-preview", CubePreview)
            bottom_section = self.query_one("#bottom-section", Horizontal)
        except Exception:
            return

        # Auto-hide cube preview if terminal height is too small
        puzzle = self.cfg.puzzle
        size_val = None
        if puzzle == "2x2":
            size_val = 2
        elif puzzle == "3x3":
            size_val = 3
        elif puzzle == "4x4":
            size_val = 4
        elif puzzle == "5x5":
            size_val = 5
        elif puzzle == "6x6":
            size_val = 6
        elif puzzle == "7x7":
            size_val = 7

        required_height = 20
        if size_val is not None:
            # Net height is 3 * size_val + 4. Other UI parts need ~10 lines.
            required_height = (3 * size_val + 4) + 10

        if size.height < required_height:
            preview.display = False
        else:
            preview.display = self.cfg.show_cube_preview and self.cfg.puzzle in (
                "2x2",
                "3x3",
                "4x4",
                "5x5",
                "6x6",
                "7x7",
            )
            if preview.display and self._scramble:
                preview.set_scramble(self._scramble, self.cfg.puzzle)

        if preview.display and size_val is not None:
            bottom_section.styles.height = (3 * size_val + 4) + 2
        else:
            bottom_section.styles.height = 8

    # ── Layout ─────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        # Left sidebar
        with Vertical(id="sidebar"):
            yield Label("🧊 CubeCLI", id="sidebar-title")
            yield SidebarButton("⏱ Timer", id="btn-timer", classes="sidebar-btn active")
            yield SidebarButton("📊 Stats", id="btn-stats", classes="sidebar-btn")
            yield SidebarButton("🏋 Trainer", id="btn-trainer", classes="sidebar-btn")
            yield SidebarButton("⚙ Settings", id="btn-settings", classes="sidebar-btn")
            yield SidebarButton("🧩 Puzzle", id="btn-puzzle", classes="sidebar-btn")
            yield SidebarButton("📂 Session", id="btn-session", classes="sidebar-btn")

        # Header strip
        yield Label("", id="app-header")

        # Central timer area
        with Container(id="timer-section"):
            yield ScramblePanel(id="scramble-panel")
            yield TimerDisplay(id="timer-widget")
            yield Label(
                "[dim]Hold [bold]SPACE[/bold] to ready, release to start[/dim]",
                id="status-label",
            )

        # FMC Section (hidden by default, disabled to prevent keyboard focus lockout)
        with Container(id="fmc-section", disabled=True):
            yield Label("Time Remaining: [bold red]60:00[/bold red]", id="fmc-timer")
            yield Input(
                placeholder="Enter your solution (e.g. R U R' U')...", id="fmc-solution-input"
            )
            yield Label("Moves: 0 (valid)", id="fmc-status-label")
            with Horizontal(id="fmc-buttons-container"):
                yield Button("Submit", variant="success", id="fmc-submit-btn")
                yield Button("Cancel", variant="error", id="fmc-cancel-btn")

        # Bottom: solve list + stats + scramble preview
        with Horizontal(id="bottom-section"):
            with Vertical(id="solve-list-panel"):
                yield SolveList(id="solve-list-widget")
            with Vertical(id="stats-panel"):
                yield StatsPanel(id="stats-widget")
            yield CubePreview(id="cube-preview")

        # Key hints footer
        yield Label(
            "[dim]"
            "[bold]SPACE[/bold] time  "
            "[bold]d[/bold] DNF  "
            "[bold]p[/bold] +2  "
            "[bold]z[/bold] undo  "
            "[bold]r[/bold] scramble  "
            "[bold]c[/bold] copy  "
            "[bold]v[/bold] preview  "
            "[bold]s/g[/bold] stats  "
            "[bold]T[/bold] train  "
            "[bold]b[/bold] bld  "
            "[bold]f[/bold] fmc  "
            "[bold]o[/bold] cfop  "
            "[bold]q[/bold] quit"
            "[/dim]",
            id="key-hints",
        )

    # ── Key handling ───────────────────────────────────────────────────────

    def on_key(self, event: Key) -> None:
        if self.cfg.fmc_mode_enabled and self.focused and self.focused.id == "fmc-solution-input":
            if event.key == "escape":
                self.focused.blur()
                event.stop()
                return
            elif event.key == "enter":
                self._submit_fmc_solution()
                event.stop()
                return
            else:
                # Let key events bubble to the Input widget for typing
                return

        from cubecli.ui.widgets.sidebar_btn import handle_sidebar_navigation

        if self._state not in (TimerState.RUNNING,) and handle_sidebar_navigation(self, event.key):
            event.stop()
            return

        event.stop()

        match event.key:
            case "space":
                self._handle_space()
            case "enter" if self._state == TimerState.RUNNING:
                if self.cfg.cfop_splits_enabled:
                    self._record_cfop_split()
            case "d" if self._state == TimerState.STOPPED:
                self._apply_penalty("DNF")
            case "p" if self._state == TimerState.STOPPED:
                self._apply_penalty("+2")
            case "z" | "ctrl+z":
                self._undo_delete()
            case "r" if self._state not in (TimerState.RUNNING,):
                self._new_scramble()
            case "c":
                self._copy_scramble()
            case "v":
                self._toggle_preview()
            case "s" | "g" if self._state not in (TimerState.RUNNING,):
                assert self._session is not None
                assert self._session.id is not None
                self.app.push_screen(StatsScreen(self.cfg, self._session.id))
            case "T" if self._state not in (TimerState.RUNNING,):
                self.app.push_screen(TrainScreen(self.cfg))
            case "P" if self._state not in (TimerState.RUNNING,):
                self._open_puzzle_picker()
            case "b" if self._state not in (TimerState.RUNNING,):
                self._toggle_bld_mode()
            case "f" if self._state not in (TimerState.RUNNING,):
                self._toggle_fmc_mode()
            case "o" if self._state not in (TimerState.RUNNING,):
                self._toggle_cfop_splits()
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
                if self.cfg.bld_mode_enabled and self._bld_phase == "memo":
                    self._transition_bld_to_exec()
                else:
                    self._stop_solve()

            case TimerState.IDLE | TimerState.STOPPED:
                if self.cfg.inspection_enabled and not self._is_inspecting:
                    # Start inspection on first press
                    self._is_inspecting = True
                    self._inspection_start = time.perf_counter()
                    self._inspection_beeps = set()
                    self._solve_penalty = None
                    self._tick_timer = self.set_interval(_TICK_INTERVAL, self._tick)
                    self._update_status(
                        "[bold yellow]INSPECTING[/bold yellow] · Hold SPACE to start solve"
                    )
                    self._reset_release_timer()
                    return

                if self._hold_start is None:
                    self._hold_start = time.perf_counter()
                    self._set_state(TimerState.HOLDING)

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
        self._release_timer = self.set_timer(_RELEASE_DELAY, self._on_space_released)

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
                if self._is_inspecting:
                    self._update_status(
                        "[bold yellow]INSPECTING[/bold yellow] · Hold SPACE to start solve"
                    )

    # ── Solve lifecycle ────────────────────────────────────────────────────

    def _start_solve(self) -> None:
        """Begin timing a new solve."""
        self._hold_start = None

        # Determine inspection penalty if inspection was active
        penalty = None
        if self._is_inspecting:
            self._is_inspecting = False
            if self._tick_timer is not None:
                self._tick_timer.stop()
                self._tick_timer = None

            elapsed = time.perf_counter() - self._inspection_start
            if elapsed > 15.0:
                penalty = "+2"
            if elapsed > 17.0:
                penalty = "DNF"

        self._solve_penalty = penalty
        self._precision_timer.start()
        self._set_state(TimerState.RUNNING)

        # Initialize BLD split timer
        if self.cfg.bld_mode_enabled:
            self._bld_phase = "memo"
            self._bld_start_time = time.perf_counter()
            self._update_status(
                "[bold yellow]MEMORIZATION[/bold yellow] · Press SPACE to start execution"
            )
        # Initialize CFOP split timer
        elif self.cfg.cfop_splits_enabled:
            self._cfop_stage = 0
            self._cfop_split_times = []
            self._cfop_start_time = time.perf_counter()
            self._cfop_last_split_time = self._cfop_start_time
            self._update_status("[bold magenta]CROSS[/bold magenta] · Press ENTER for F2L")

        # Initialize metronome
        if self.cfg.metronome_enabled:
            interval = 1.0 / self.cfg.metronome_tps
            self._metronome_timer = self.set_interval(interval, self._play_metronome_tick)

        # Live tick to update the display
        self._tick_timer = self.set_interval(_TICK_INTERVAL, self._tick)

    def _tick(self) -> None:
        """Called repeatedly while RUNNING (or inspecting) to update the displayed time."""
        if self._is_inspecting:
            elapsed = time.perf_counter() - self._inspection_start
            if elapsed < 15.0:
                remaining = 15 - int(elapsed)
                self._timer_display.time_str = str(remaining)

                # Check for beeps
                if elapsed >= 8.0 and "8s" not in self._inspection_beeps:
                    self._inspection_beeps.add("8s")
                    from cubecli.core.audio import play_beep_async

                    play_beep_async("ping")
                if elapsed >= 12.0 and "12s" not in self._inspection_beeps:
                    self._inspection_beeps.add("12s")
                    from cubecli.core.audio import play_beep_async

                    play_beep_async("ping")
            elif elapsed < 17.0:
                self._timer_display.time_str = "+2"
            else:
                self._timer_display.time_str = "DNF"
                self._is_inspecting = False
                if self._tick_timer is not None:
                    self._tick_timer.stop()
                    self._tick_timer = None
                self._record_inspection_dnf()
        elif self._state == TimerState.RUNNING:
            if self.cfg.bld_mode_enabled:
                if self._bld_phase == "memo":
                    assert self._bld_start_time is not None
                    ms = int((time.perf_counter() - self._bld_start_time) * 1000)
                else:
                    assert self._bld_exec_start is not None
                    ms = int((time.perf_counter() - self._bld_exec_start) * 1000)
            else:
                ms = self._precision_timer.elapsed_ms
            self._timer_display.set_ms(ms)

    def _stop_solve(self) -> None:
        """Stop timing and record the result."""
        # Cancel live updates
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer = None

        # Stop metronome
        if self._metronome_timer is not None:
            self._metronome_timer.stop()
            self._metronome_timer = None

        solve_notes = ""
        if self.cfg.bld_mode_enabled:
            now = time.perf_counter()
            if self._bld_exec_start is not None:
                self._bld_exec_ms = int((now - self._bld_exec_start) * 1000)
            else:
                self._bld_exec_ms = 0
            elapsed_ms = self._bld_memo_ms + self._bld_exec_ms
            solve_notes = f"memo:{self._bld_memo_ms}|exec:{self._bld_exec_ms}"
            self._bld_phase = None
            # BLD computes elapsed_ms manually, so stop the timer to reset its
            # internal state — prevents it from continuing to tick.
            self._precision_timer.stop()
        elif self.cfg.cfop_splits_enabled:
            elapsed_ms = self._precision_timer.stop()
            # If there are remaining splits, fill them
            total_recorded = sum(self._cfop_split_times)
            remaining = max(0, elapsed_ms - total_recorded)
            if len(self._cfop_split_times) < 4:
                self._cfop_split_times.append(remaining)
                while len(self._cfop_split_times) < 4:
                    self._cfop_split_times.append(0)
            solve_notes = "splits:" + "|".join(str(t) for t in self._cfop_split_times)
        else:
            elapsed_ms = self._precision_timer.stop()

        self._set_state(TimerState.STOPPED)

        # Retrieve starting penalty (from inspection)
        penalty = getattr(self, "_solve_penalty", None)
        self._solve_penalty = None

        # Persist
        assert self._session is not None
        solve = Solve(
            time_ms=elapsed_ms,
            scramble=self._scramble,
            puzzle=self.cfg.puzzle,
            session_id=self._session.id,
            penalty=penalty,
            notes=solve_notes,
        )
        db.insert_solve(solve)
        self._solves.append(solve)
        self._last_solve = solve

        # Show the final time
        self._timer_display.set_ms(solve.effective_ms or solve.time_ms)

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
        self._update_status(f"[dim]Penalty: [bold]{solve.penalty or 'cleared'}[/bold][/dim]")

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
        """Generate a new scramble in a background thread (non-blocking).

        The puzzle is captured here — before the background thread runs —
        to avoid a race condition where cfg.puzzle changes between generation
        and the UI update in _apply_scramble.
        """
        puzzle = self.cfg.puzzle  # capture now, before any potential puzzle change
        scramble = scr_mod.get_scramble(puzzle)
        self.app.call_from_thread(self._apply_scramble, scramble, puzzle)

    def _apply_scramble(self, scramble: str, puzzle: str) -> None:
        self._scramble = scramble
        try:
            panel = self.query_one("#scramble-panel", ScramblePanel)
            panel.set_scramble(scramble, puzzle)
        except Exception:
            pass
        try:
            preview = self.query_one("#cube-preview", CubePreview)
            if self.cfg.show_cube_preview:
                preview.set_scramble(scramble, puzzle)
        except Exception:
            pass

    def _copy_scramble(self) -> None:
        if self._scramble:
            try:
                pyperclip.copy(self._scramble)
                self.notify("Scramble copied!", timeout=2)
            except Exception:
                self.notify("Clipboard not available", severity="warning", timeout=2)

    def _toggle_preview(self) -> None:
        """Toggle the cube net preview on/off and persist the setting."""
        self.cfg.show_cube_preview = not self.cfg.show_cube_preview
        self.cfg.save()
        self._adjust_layout_for_size()
        state = "on" if self.cfg.show_cube_preview else "off"
        self.notify(f"Cube preview {state}", timeout=2)

    # ── Puzzle picker ──────────────────────────────────────────────────────

    def _open_puzzle_picker(self) -> None:
        """Open the puzzle picker selection screen."""
        if self._state == TimerState.RUNNING:
            return

        def on_picker_close(selected_puzzle: str | None) -> None:
            if selected_puzzle and selected_puzzle != self.cfg.puzzle:
                self.cfg.puzzle = selected_puzzle
                self.cfg.save()
                # Create/load session for new puzzle
                assert self._session is not None
                self._session = db.get_or_create_session(self.cfg.session_name, self.cfg.puzzle)
                self._solves = db.get_solves(self._session.id)  # type: ignore[arg-type]
                self._last_solve = None
                self._set_state(TimerState.IDLE)
                self._timer_display.reset()
                self._new_scramble()
                self._refresh_stats()
                self._refresh_solve_list()
                self._update_header()
                self._adjust_layout_for_size()
                self.notify(f"Puzzle: {self.cfg.puzzle}", timeout=2)

        from cubecli.ui.screens.puzzle_picker import PuzzlePicker

        self.app.push_screen(PuzzlePicker(self.cfg.puzzle), on_picker_close)

    # ── Display helpers ────────────────────────────────────────────────────

    def _set_state(self, state: TimerState) -> None:
        self._state = state
        self._timer_display.set_state(state)

        match state:
            case TimerState.IDLE:
                self._update_status("[dim]Hold [bold]SPACE[/bold] to ready, release to start[/dim]")
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

        mode_str = ""
        if self.cfg.bld_mode_enabled:
            mode_str = " [bold yellow][BLD Mode][/bold yellow]"
        elif self.cfg.fmc_mode_enabled:
            mode_str = " [bold green][FMC Mode][/bold green]"
        elif self.cfg.cfop_splits_enabled:
            mode_str = " [bold magenta][CFOP Splits][/bold magenta]"

        try:
            self.query_one("#app-header", Label).update(
                f"  🧊 [bold cyan]CubeCLI[/bold cyan]"
                f"  [dim]│[/dim]  {puzzle}{mode_str}"
                f"  [dim]│[/dim]  {session_name}"
                f"  [dim]│[/dim]  {solve_count} solves"
            )
        except Exception:
            pass

    # ── Phase 5 helper methods ─────────────────────────────────────────────

    def _transition_bld_to_exec(self) -> None:
        """Transition from memorization phase to execution phase in BLD mode."""
        now = time.perf_counter()
        assert self._bld_start_time is not None
        self._bld_memo_ms = int((now - self._bld_start_time) * 1000)
        self._bld_phase = "exec"
        self._bld_exec_start = now
        # Visual and audio confirmation
        from cubecli.core.audio import play_beep_async

        play_beep_async("ping")
        self._update_status("[bold green]EXECUTION[/bold green] · Press SPACE to stop")

    def _record_cfop_split(self) -> None:
        """Record a CFOP split time and advance to the next stage."""
        if self._state != TimerState.RUNNING or not self.cfg.cfop_splits_enabled:
            return

        now = time.perf_counter()
        split_ms = int((now - self._cfop_last_split_time) * 1000)
        self._cfop_split_times.append(split_ms)
        self._cfop_last_split_time = now
        self._cfop_stage += 1

        stages = ["CROSS", "F2L", "OLL", "PLL"]
        from cubecli.core.audio import play_beep_async

        play_beep_async("ping")

        if self._cfop_stage < 4:
            next_stage = stages[self._cfop_stage]
            next_prompt = stages[self._cfop_stage + 1] if self._cfop_stage < 3 else "STOP"
            action_prompt = "ENTER" if self._cfop_stage < 3 else "SPACE"
            self._update_status(
                f"[bold magenta]{next_stage}[/bold magenta] · Press {action_prompt} for {next_prompt}"
            )
        else:
            self._stop_solve()

    def _toggle_bld_mode(self) -> None:
        """Toggle BLD split timing mode."""
        self.cfg.bld_mode_enabled = not self.cfg.bld_mode_enabled
        if self.cfg.bld_mode_enabled:
            self.cfg.fmc_mode_enabled = False
            self.cfg.cfop_splits_enabled = False
            self._set_fmc_layout(False)
        self.cfg.save()
        self._update_header()
        status = "enabled" if self.cfg.bld_mode_enabled else "disabled"
        self.notify(f"BLD Mode {status}", timeout=2)

    def _toggle_fmc_mode(self) -> None:
        """Toggle FMC timing mode."""
        self.cfg.fmc_mode_enabled = not self.cfg.fmc_mode_enabled
        if self.cfg.fmc_mode_enabled:
            self.cfg.bld_mode_enabled = False
            self.cfg.cfop_splits_enabled = False
            self._set_fmc_layout(True)
        else:
            self._set_fmc_layout(False)
        self.cfg.save()
        self._update_header()
        status = "enabled" if self.cfg.fmc_mode_enabled else "disabled"
        self.notify(f"FMC Mode {status}", timeout=2)

    def _toggle_cfop_splits(self) -> None:
        """Toggle CFOP split timing mode."""
        self.cfg.cfop_splits_enabled = not self.cfg.cfop_splits_enabled
        if self.cfg.cfop_splits_enabled:
            self.cfg.bld_mode_enabled = False
            self.cfg.fmc_mode_enabled = False
            self._set_fmc_layout(False)
        self.cfg.save()
        self._update_header()
        status = "enabled" if self.cfg.cfop_splits_enabled else "disabled"
        self.notify(f"CFOP Splits {status}", timeout=2)

    def _record_inspection_dnf(self) -> None:
        """Record a DNF solve due to inspection timeout."""
        self._set_state(TimerState.STOPPED)
        assert self._session is not None
        # Record the actual elapsed time at the point of DNF, not zero.
        # If the penalty is ever cleared, the stored time will be meaningful.
        dnf_time_ms = 0
        if hasattr(self, "_inspection_start") and self._inspection_start is not None:
            dnf_time_ms = int((time.perf_counter() - self._inspection_start) * 1000)
        solve = Solve(
            time_ms=dnf_time_ms,
            scramble=self._scramble,
            puzzle=self.cfg.puzzle,
            session_id=self._session.id,
            penalty="DNF",
            notes="Inspection timeout",
        )
        db.insert_solve(solve)
        self._solves.append(solve)
        self._last_solve = solve

        self._new_scramble()
        self._refresh_stats()
        self._refresh_solve_list()
        self._update_status("[red bold]DNF (Inspection Timeout)[/red bold]")

    def _play_metronome_tick(self) -> None:
        """Play a single metronome tick beep."""
        from cubecli.core.audio import play_beep_async

        play_beep_async(1)

    def _set_fmc_layout(self, active: bool) -> None:
        """Toggle widgets and timers for FMC mode."""
        try:
            fmc_section = self.query_one("#fmc-section", Container)
            timer_section = self.query_one("#timer-section", Container)
            bottom_section = self.query_one("#bottom-section", Horizontal)
            preview = self.query_one("#cube-preview", CubePreview)
        except Exception:
            return

        if active:
            # Hide normal panels
            timer_section.display = False
            bottom_section.display = False
            preview.display = False

            # Enable and show FMC panel
            fmc_section.disabled = False
            fmc_section.display = True

            # Setup countdown
            self._fmc_seconds_left = 3600
            self.query_one("#fmc-timer", Label).update("Time Remaining: [bold red]60:00[/bold red]")
            self.query_one("#fmc-solution-input", Input).value = ""
            self._update_fmc_status("")

            # Start timer
            if hasattr(self, "_fmc_interval_timer") and self._fmc_interval_timer is not None:
                self._fmc_interval_timer.stop()
            self._fmc_interval_timer = self.set_interval(1.0, self._fmc_tick)

            # Focus input
            self.query_one("#fmc-solution-input", Input).focus()
        else:
            # Disable and hide FMC panel
            fmc_section.disabled = True
            fmc_section.display = False

            # Stop timer
            if hasattr(self, "_fmc_interval_timer") and self._fmc_interval_timer is not None:
                self._fmc_interval_timer.stop()
                self._fmc_interval_timer = None

            # Restore normal panels
            timer_section.display = True
            bottom_section.display = True
            self._adjust_layout_for_size()

    def _fmc_tick(self) -> None:
        """Update FMC countdown timer once per second."""
        if not self.cfg.fmc_mode_enabled:
            return
        self._fmc_seconds_left -= 1
        if self._fmc_seconds_left <= 0:
            # Time's up! Play beep and submit automatically
            from cubecli.core.audio import play_beep_async

            play_beep_async("error")
            self._submit_fmc_solution()
            self.notify(
                "Time's up! FMC solution submitted automatically.", severity="warning", timeout=5
            )
        else:
            # Format time remaining
            mins = self._fmc_seconds_left // 60
            secs = self._fmc_seconds_left % 60
            timer_lbl = self.query_one("#fmc-timer", Label)
            timer_lbl.update(f"Time Remaining: [bold red]{mins:02d}:{secs:02d}[/bold red]")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "fmc-solution-input":
            self._update_fmc_status(event.value)

    def _update_fmc_status(self, value: str) -> None:
        from cubecli.core.fmc import count_fmc_moves

        moves = count_fmc_moves(value)
        try:
            status_lbl = self.query_one("#fmc-status-label", Label)
            submit_btn = self.query_one("#fmc-submit-btn", Button)
        except Exception:
            return
        if moves >= 0:
            status_lbl.update(f"[green]Moves: {moves} (valid)[/green]")
            submit_btn.disabled = False
        else:
            status_lbl.update("[red]Invalid move token detected[/red]")
            submit_btn.disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fmc-submit-btn":
            self._submit_fmc_solution()
            return
        elif event.button.id == "fmc-cancel-btn":
            self._cancel_fmc()
            return

        # Sidebar buttons
        match event.button.id:
            case "btn-timer":
                pass
            case "btn-stats":
                self.action_open_stats()
            case "btn-trainer":
                self.action_open_trainer()
            case "btn-settings":
                self.action_open_settings()
            case "btn-puzzle":
                self.action_open_puzzle_picker()
            case "btn-session":
                self.action_open_session_picker()

    def action_open_stats(self) -> None:
        if self._state == TimerState.RUNNING:
            return
        assert self._session is not None
        assert self._session.id is not None
        self.app.push_screen(StatsScreen(self.cfg, self._session.id))

    def action_open_trainer(self) -> None:
        if self._state == TimerState.RUNNING:
            return
        self.app.push_screen(TrainScreen(self.cfg))

    def action_open_settings(self) -> None:
        if self._state == TimerState.RUNNING:
            return

        def on_settings_close(result: None) -> None:
            self._adjust_layout_for_size()
            self._update_header()
            self._refresh_stats()
            self._refresh_solve_list()
            if self._metronome_timer:
                self._metronome_timer.stop()
                self._metronome_timer = None
            self._new_scramble()

        from cubecli.ui.screens.settings_screen import SettingsScreen

        self.app.push_screen(SettingsScreen(self.cfg), on_settings_close)

    def action_open_puzzle_picker(self) -> None:
        self._open_puzzle_picker()

    def action_open_session_picker(self) -> None:
        if self._state == TimerState.RUNNING:
            return

        def on_session_close(selected_session: str | None) -> None:
            if selected_session and selected_session != self.cfg.session_name:
                self.cfg.session_name = selected_session
                self.cfg.save()
                self._session = db.get_or_create_session(self.cfg.session_name, self.cfg.puzzle)
                self._solves = db.get_solves(self._session.id)  # type: ignore[arg-type]
                self._last_solve = None
                self._set_state(TimerState.IDLE)
                self._timer_display.reset()
                self._new_scramble()
                self._refresh_stats()
                self._refresh_solve_list()
                self._update_header()
                self.notify(f"Session: {selected_session}", timeout=2)

        from cubecli.ui.screens.session_picker import SessionPicker

        self.app.push_screen(
            SessionPicker(self.cfg.session_name, self.cfg.puzzle), on_session_close
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "fmc-solution-input":
            self._submit_fmc_solution()

    def _submit_fmc_solution(self) -> None:
        """Process and save the FMC solution."""
        if not self.cfg.fmc_mode_enabled:
            return
        try:
            input_widget = self.query_one("#fmc-solution-input", Input)
        except Exception:
            return
        solution = input_widget.value.strip()
        from cubecli.core.fmc import count_fmc_moves

        moves = count_fmc_moves(solution)
        if moves < 0:
            self.notify("Cannot submit: invalid solution", severity="error", timeout=2)
            return

        # Scale move count by 1000 for database compatibility
        elapsed_ms = moves * 1000
        assert self._session is not None
        solve = Solve(
            time_ms=elapsed_ms,
            scramble=self._scramble,
            puzzle=self.cfg.puzzle,
            session_id=self._session.id,
            notes=f"fmc_sol:{solution}",
        )
        db.insert_solve(solve)
        self._solves.append(solve)
        self._last_solve = solve

        # Disable FMC layout and mode
        self._toggle_fmc_mode()

        # Clear the input value for next time
        input_widget.value = ""

        # Notification
        self.notify(f"FMC Solution saved: {moves} moves!", timeout=2)

    def _cancel_fmc(self) -> None:
        """Cancel FMC mode and discard input."""
        try:
            input_widget = self.query_one("#fmc-solution-input", Input)
            input_widget.value = ""
        except Exception:
            pass
        self._toggle_fmc_mode()
        self.notify("FMC solve cancelled", timeout=2)

    # ── Stats refresh ──────────────────────────────────────────────────────

    def _refresh_stats(self) -> None:
        # Exclude FMC solves from timed-solve statistics — FMC stores move
        # count × 1000 as time_ms, which would skew rolling averages.
        # FMC solves are identified by notes starting with 'fmc_sol:'.
        timed_solves = [s for s in self._solves if not s.notes.startswith("fmc_sol:")]
        times = [s.effective_ms for s in timed_solves]

        last_timed = timed_solves[-1] if timed_solves else None
        single = last_timed.effective_ms if last_timed else None
        mo3 = stats_mod.calculate_mo3(times)
        ao5 = stats_mod.calculate_ao5(times)
        ao12 = stats_mod.calculate_ao12(times)
        ao50 = stats_mod.calculate_ao50(times)
        best = stats_mod.best_time(times)
        mean = stats_mod.session_mean(times)

        # Is single a new session PB?
        # Compare raw ms values instead of formatted strings to avoid edge cases.
        single_is_pb = (
            single is not None
            and best is not None
            and single == best
        )

        try:
            self.query_one("#stats-widget", StatsPanel).update_stats(
                single, mo3, ao5, ao12, ao50, best, mean, len(self._solves), single_is_pb
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
