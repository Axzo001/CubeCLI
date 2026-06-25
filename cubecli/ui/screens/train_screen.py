"""OLL/PLL Training Screen TUI."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Label

from cubecli.config import Config
from cubecli.core.timer import PrecisionTimer, TimerState
from cubecli.data import db
from cubecli.data.models import Session, Solve
from cubecli.training import trainer
from cubecli.ui.screens.case_picker import CasePicker
from cubecli.ui.widgets.timer_display import TimerDisplay

if TYPE_CHECKING:
    from textual.events import Key

_HOLD_MS = 500  # ms to hold before READY state
_RELEASE_DELAY = 0.15  # seconds with no space event -> key released
_TICK_INTERVAL = 0.01  # seconds between display refreshes while RUNNING


class TrainScreen(Screen[None]):
    """Dedicated TUI dashboard for algorithm training."""

    BINDINGS = []  # Handled manually for spacebar repeat detection

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.cfg = config
        self.mode = "oll"  # starts in OLL mode by default

        # State machine
        self._state = TimerState.IDLE
        self._hold_start: float | None = None
        self._precision_timer = PrecisionTimer()
        self._tick_timer: Timer | None = None
        self._release_timer: Timer | None = None

        # Data sets
        self.all_cases: list[trainer.Case] = []
        self.active_cases: list[trainer.Case] = []
        self.active_case_ids: list[str] = []
        self.current_case: trainer.Case | None = None
        self._session: Session | None = None
        self._solves: list[Solve] = []
        self._scramble = ""

    def on_mount(self) -> None:
        """Initialize cases, training session, and fetch solves."""
        db.ensure_schema()
        self._init_mode()

    def _init_mode(self) -> None:
        """Initialize the current mode (OLL/PLL)."""
        self.all_cases = trainer.load_cases(self.mode)
        # By default all cases are active
        self.active_case_ids = [c.id for c in self.all_cases]
        self.active_cases = list(self.all_cases)

        self._session = db.get_or_create_session(f"{self.mode.upper()} Training", self.mode)
        assert self._session.id is not None
        self._solves = db.get_solves(self._session.id)

        self._next_case()
        self._update_all()

    def compose(self) -> ComposeResult:
        # App Header
        yield Label("", id="train-app-header")

        # Scramble display panel
        yield Label("", id="train-scramble-panel")

        # Central grid
        with Horizontal(id="train-middle-layout"):
            with Container(id="train-diagram-panel"):
                yield Label("", id="case-diagram")

            with Container(id="train-timer-panel"):
                yield TimerDisplay(id="train-timer-widget")
                yield Label(
                    "[dim]Hold [bold]SPACE[/bold] to ready, release to start[/dim]",
                    id="train-status-label",
                )

        # Algorithm reference drawer
        with Container(id="train-reference-drawer"):
            yield Label("", id="reference-content")

        # Footer
        yield Label(
            "[dim]"
            "[bold]SPACE[/bold] time  "
            "[bold]a[/bold] toggle reference  "
            "[bold]s[/bold] skip case  "
            "[bold]p[/bold] case picker  "
            "[bold]TAB[/bold] switch mode  "
            "[bold]d[/bold] DNF last  "
            "[bold]z[/bold] delete last  "
            "[bold]escape/q[/bold] exit"
            "[/dim]",
            id="train-key-hints",
        )

    # ── Key Handling ─────────────────────────────────────────────────────────

    def on_key(self, event: Key) -> None:
        event.stop()

        match event.key:
            case "space":
                self._handle_space()
            case "escape" | "q" if self._state not in (TimerState.RUNNING,):
                self.dismiss()
            case "tab" if self._state not in (TimerState.RUNNING,):
                self._toggle_mode()
            case "a" if self._state not in (TimerState.RUNNING,):
                self._toggle_reference()
            case "s" if self._state not in (TimerState.RUNNING,):
                self._next_case()
                self._update_all()
                self.notify("Case skipped", severity="warning", timeout=2)
            case "p" if self._state not in (TimerState.RUNNING,):
                self._open_picker()
            case "d" if self._state not in (TimerState.RUNNING,):
                self._apply_penalty_dnf()
            case "z" if self._state not in (TimerState.RUNNING,):
                self._delete_last()
            case _:
                pass

    # ── Spacebar Repeat / Release State Machine ───────────────────────────────

    def _handle_space(self) -> None:
        """Entry point for every SPACE key event."""
        match self._state:
            case TimerState.RUNNING:
                self._stop_solve()

            case TimerState.IDLE | TimerState.STOPPED:
                if self._hold_start is None:
                    self._hold_start = time.perf_counter()
                    self._set_state(TimerState.HOLDING)
                self._reset_release_timer()

            case TimerState.HOLDING | TimerState.READY:
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
        """Called ~150 ms after the last space event."""
        self._release_timer = None

        match self._state:
            case TimerState.READY:
                self._start_solve()
            case TimerState.HOLDING:
                self._hold_start = None
                self._set_state(TimerState.IDLE)

    # ── Solve Lifecycle ───────────────────────────────────────────────────────

    def _start_solve(self) -> None:
        """Begin timing the attempt."""
        self._hold_start = None
        self._precision_timer.start()
        self._set_state(TimerState.RUNNING)
        self._tick_timer = self.set_interval(_TICK_INTERVAL, self._tick)

    def _tick(self) -> None:
        """Update live timer value."""
        if self._state == TimerState.RUNNING:
            ms = self._precision_timer.elapsed_ms
            self._timer_widget.set_ms(ms)

    def _stop_solve(self) -> None:
        """Stop timing and record solve results."""
        elapsed_ms = self._precision_timer.stop()
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer = None

        self._timer_widget.set_ms(elapsed_ms)
        self._set_state(TimerState.STOPPED)

        # Save to DB
        assert self._session is not None
        assert self.current_case is not None
        solve = Solve(
            time_ms=elapsed_ms,
            scramble=self._scramble,
            puzzle=self.mode,
            session_id=self._session.id,
            notes=self.current_case.id,  # Save the case ID in the notes field!
        )
        db.insert_solve(solve)
        self._solves.append(solve)

        # Move to the next case immediately
        self._next_case()
        self._update_all()
        self.notify(f"Time: {solve.display_time}", timeout=2)

    # ── Case Operations ───────────────────────────────────────────────────────

    def _next_case(self) -> None:
        """Choose next case using spaced repetition selection."""
        if not self.active_cases:
            return
        self.current_case = trainer.select_next_case(self.active_cases, self._solves)
        self._scramble = trainer.get_setup_scramble(self.current_case.algorithm)

    def _toggle_mode(self) -> None:
        """Switch between OLL and PLL training modes."""
        self.mode = "pll" if self.mode == "oll" else "oll"
        self._init_mode()
        self.notify(f"Mode switched to {self.mode.upper()}", timeout=2)

    def _toggle_reference(self) -> None:
        """Toggle algorithm reference drawer."""
        drawer = self.query_one("#train-reference-drawer", Container)
        drawer.display = not drawer.display

    def _open_picker(self) -> None:
        """Push the case picker selection dialog."""

        def on_picker_close(selected_ids: list[str] | None) -> None:
            if selected_ids:
                self.active_case_ids = selected_ids
                self.active_cases = [c for c in self.all_cases if c.id in self.active_case_ids]
                self._next_case()
                self._update_all()
                self.notify(f"Active pool: {len(self.active_cases)} cases", timeout=2)

        self.app.push_screen(CasePicker(self.mode, self.active_case_ids), on_picker_close)

    def _apply_penalty_dnf(self) -> None:
        """Apply DNF to the last solve attempt in this session."""
        if not self._session or self._session.id is None:
            return
        last = db.get_last_solve(self._session.id)
        if not last or last.id is None:
            return

        # Toggle DNF
        new_penalty = None if last.penalty == "DNF" else "DNF"
        db.update_solve_penalty(last.id, new_penalty)

        # Re-fetch solves and refresh statistics
        self._solves = db.get_solves(self._session.id)
        self._update_all()
        status = "DNF applied" if new_penalty else "DNF cleared"
        self.notify(status, severity="warning", timeout=2)

    def _delete_last(self) -> None:
        """Delete the last solve attempt."""
        if not self._session or self._session.id is None:
            return
        last = db.get_last_solve(self._session.id)
        if not last or last.id is None:
            return

        db.delete_solve(last.id)
        self._solves = db.get_solves(self._session.id)
        self._update_all()
        self.notify("Last solve deleted", severity="warning", timeout=2)

    # ── Display Formatting & Updates ──────────────────────────────────────────

    def _set_state(self, state: TimerState) -> None:
        self._state = state
        self._timer_widget.set_state(state)

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
                pass

    def _update_status(self, markup: str) -> None:
        try:
            self.query_one("#train-status-label", Label).update(markup)
        except Exception:
            pass

    def _update_all(self) -> None:
        """Update header, diagrams, drawer, and scramble texts."""
        if not self.current_case:
            return

        case = self.current_case

        # Calculate statistics
        case_solves = [s for s in self._solves if s.notes == case.id]
        seen_count = len(case_solves)

        # Average of last 5 solves for this case
        valid_times = [s.effective_ms for s in case_solves[-5:] if s.effective_ms is not None]
        case_avg = f"{sum(valid_times) / len(valid_times) / 1000.0:.3f}s" if valid_times else "N/A"

        # Update Header label
        header_text = (
            f"  🧊 [bold cyan]CubeCLI Algorithm Trainer[/bold cyan] "
            f"  [dim]│[/dim]  [bold yellow]{self.mode.upper()}[/bold yellow] "
            f"  [dim]│[/dim]  Case {case.id}: {case.name} ({case.group}) "
            f"  [dim]│[/dim]  Drilling {len(self.active_cases)} cases "
            f"  [dim]│[/dim]  Seen {seen_count} times "
            f"  [dim]│[/dim]  Case Avg (last 5): {case_avg}"
        )
        self.query_one("#train-app-header", Label).update(header_text)

        # Update scramble panel
        scramble_text = (
            f"[dim]Setup Scramble (perform on a solved cube):[/dim]\n"
            f"[bold green]{self._scramble}[/bold green]"
        )
        self.query_one("#train-scramble-panel", Label).update(scramble_text)

        # Update diagram
        diagram_widget = self.query_one("#case-diagram", Label)
        if self.mode == "oll":
            # Format OLL diagram
            lines = []
            for line in case.diagram.split("\n"):
                formatted = ""
                for char in line:
                    if char == "#":
                        formatted += "[bold yellow]█[/bold yellow]"
                    elif char == ".":
                        formatted += "[dim bright_black]░[/dim bright_black]"
                    else:
                        formatted += " "
                lines.append(formatted)
            diagram_widget.update("\n".join(lines))
        else:
            # Format PLL diagram
            diagram_widget.update(case.diagram.replace("█", "[bold green]█[/bold green]"))

        # Update reference content
        ref_text = (
            f"[dim]Algorithm Reference (Case {case.id}: {case.name}):[/dim]\n"
            f"[bold cyan]{case.algorithm}[/bold cyan]"
        )
        self.query_one("#reference-content", Label).update(ref_text)

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def _timer_widget(self) -> TimerDisplay:
        return self.query_one("#train-timer-widget", TimerDisplay)
