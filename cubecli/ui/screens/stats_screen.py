"""Screen for advanced session statistics and line plots."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rich.table import Table
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, Static
from textual_plot import DurationFormatter, HiResMode, NumericAxisFormatter, PlotWidget

from cubecli.config import Config
from cubecli.core import stats as stats_mod
from cubecli.core.timer import format_time
from cubecli.data import db

if TYPE_CHECKING:
    from textual.events import Key


class StatsScreen(Screen[None]):
    """Unified stats dashboard and plot screen."""

    BINDINGS = []

    def __init__(self, config: Config, session_id: int) -> None:
        super().__init__()
        self.cfg = config
        self.session_id = session_id

    def compose(self) -> ComposeResult:
        # Title bar / Header
        yield Label("", id="stats-header")

        # Layout containing comparison tables and the plot widget side-by-side
        with Horizontal(id="stats-middle-layout"):
            with Vertical(id="stats-tables-col"):
                yield Static(id="stats-comparison-table")

            with Vertical(id="stats-plot-col"):
                # Full-featured plot widget
                plot = PlotWidget(id="stats-plot")
                plot.border_title = "Solve Time History & Ao5 Trend"
                yield plot

        # Bottom section: solve history table
        with Container(id="stats-history-section"):
            yield Label(
                "[bold cyan]Recent Solve Details (last 10)[/bold cyan]", id="stats-history-title"
            )
            yield Static(id="stats-history-table")

        # Footer
        yield Label(
            "[dim]Press [bold]ESCAPE[/bold], [bold]q[/bold], [bold]s[/bold], or [bold]g[/bold] to return to timer[/dim]",
            id="stats-footer",
        )

    def on_mount(self) -> None:
        """Load data and populate all widgets."""
        self._refresh()

    def on_key(self, event: Key) -> None:
        """Close stats screen and return to timer."""
        event.stop()
        if event.key in ("escape", "q", "s", "g"):
            self.app.pop_screen()

    def _refresh(self) -> None:
        """Query databases and update UI elements."""
        solves = db.get_solves(self.session_id)
        times = [s.effective_ms for s in solves]
        valid_times = [t for t in times if t is not None]
        puzzle = self.cfg.puzzle

        # 1. Header Calculations
        solve_count = len(solves)
        session_mean = stats_mod.session_mean(times)
        session_std = stats_mod.session_stddev(times)

        # Dynamic sub-X threshold calculation (e.g. 14.3s avg -> Sub-15)
        mean_s = (session_mean / 1000.0) if session_mean else 0.0
        threshold_s = max(5, math.ceil(mean_s / 5.0) * 5) if mean_s else 15
        sub_x_threshold_ms = threshold_s * 1000

        sub_x = stats_mod.sub_x_count(times, sub_x_threshold_ms)
        valid_count = len(valid_times)
        sub_x_pct = (sub_x / valid_count * 100.0) if valid_count > 0 else 0.0

        mean_str = format_time(session_mean) if session_mean is not None else "─"
        std_str = f"{(session_std / 1000.0):.3f}s" if session_std is not None else "─"
        sub_x_str = f"{sub_x}/{valid_count} ({sub_x_pct:.1f}%)" if valid_count > 0 else "─"

        header_markup = (
            f" 📊 [bold cyan]CubeCLI Analytics[/bold cyan]  [dim]│[/dim]  "
            f"Puzzle: [bold]{puzzle}[/bold]  [dim]│[/dim]  "
            f"Solves: [bold]{solve_count}[/bold]  [dim]│[/dim]  "
            f"Mean: [bold]{mean_str}[/bold]  [dim]│[/dim]  "
            f"σ: [bold]{std_str}[/bold]  [dim]│[/dim]  "
            f"Sub-{threshold_s}s: [bold]{sub_x_str}[/bold]"
        )
        self.query_one("#stats-header", Label).update(header_markup)

        # 2. Advanced Rolling Averages Comparison
        all_solves = db.get_all_solves_for_puzzle(puzzle)
        all_times = [s.effective_ms for s in all_solves]

        # Calculate current values
        curr_single = times[-1] if times else None
        curr_mo3 = stats_mod.calculate_mo3(times)
        curr_ao5 = stats_mod.calculate_ao5(times)
        curr_ao12 = stats_mod.calculate_ao12(times)
        curr_ao50 = stats_mod.calculate_ao50(times)
        curr_ao100 = stats_mod.calculate_ao100(times)

        # Calculate session bests
        best_single = stats_mod.best_time(times)
        best_mo3 = stats_mod.best_rolling_average(stats_mod.get_rolling_mo3(times))
        best_ao5 = stats_mod.best_rolling_average(stats_mod.get_rolling_ao5(times))
        best_ao12 = stats_mod.best_rolling_average(stats_mod.get_rolling_ao12(times))
        best_ao50 = stats_mod.best_rolling_average(stats_mod.get_rolling_ao50(times))
        best_ao100 = stats_mod.best_rolling_average(stats_mod.get_rolling_ao100(times))

        # Calculate all-time bests
        all_single = stats_mod.best_time(all_times)
        all_mo3 = stats_mod.best_rolling_average(stats_mod.get_rolling_mo3(all_times))
        all_ao5 = stats_mod.best_rolling_average(stats_mod.get_rolling_ao5(all_times))
        all_ao12 = stats_mod.best_rolling_average(stats_mod.get_rolling_ao12(all_times))
        all_ao50 = stats_mod.best_rolling_average(stats_mod.get_rolling_ao50(all_times))
        all_ao100 = stats_mod.best_rolling_average(stats_mod.get_rolling_ao100(all_times))

        def _fmt(val: int | None) -> str:
            return format_time(val) if val is not None else "─"

        comp_table = Table(
            show_header=True,
            header_style="bold cyan",
            expand=True,
            box=None,
        )
        comp_table.add_column("Statistic")
        comp_table.add_column("Current", justify="right")
        comp_table.add_column("Session Best", justify="right")
        comp_table.add_column("All-Time Best", justify="right")

        rows = [
            ("Single", _fmt(curr_single), _fmt(best_single), _fmt(all_single)),
            ("Mo3", _fmt(curr_mo3), _fmt(best_mo3), _fmt(all_mo3)),
            ("Ao5", _fmt(curr_ao5), _fmt(best_ao5), _fmt(all_ao5)),
            ("Ao12", _fmt(curr_ao12), _fmt(best_ao12), _fmt(all_ao12)),
            ("Ao50", _fmt(curr_ao50), _fmt(best_ao50), _fmt(all_ao50)),
            ("Ao100", _fmt(curr_ao100), _fmt(best_ao100), _fmt(all_ao100)),
        ]
        for name, curr, s_best, a_best in rows:
            # Highlight PBs
            is_pb = (
                s_best != "─"
                and s_best == a_best
                and (name == "Single" or name in ("Mo3", "Ao5", "Ao12", "Ao50", "Ao100"))
            )
            a_best_fmt = f"[bold green]{a_best} 🏆[/bold green]" if is_pb else a_best
            comp_table.add_row(name, curr, s_best, a_best_fmt)

        self.query_one("#stats-comparison-table", Static).update(comp_table)

        # 3. Setup Plot
        plot = self.query_one("#stats-plot", PlotWidget)
        plot.clear()

        # Build coordinate arrays
        x_solves: list[int] = []
        y_solves: list[float] = []
        for i, t in enumerate(times):
            if t is not None:
                x_solves.append(i + 1)
                y_solves.append(t / 1000.0)

        x_ao5: list[int] = []
        y_ao5: list[float] = []
        rolling_ao5 = stats_mod.get_rolling_ao5(times)
        for i, t in enumerate(rolling_ao5):
            if t is not None:
                x_ao5.append(i + 1)
                y_ao5.append(t / 1000.0)

        # Format axes
        plot.set_y_formatter(DurationFormatter())
        plot.set_x_formatter(NumericAxisFormatter())
        plot.set_xlabel("Solve Index")
        plot.set_ylabel("Duration")

        # Scatter solves (individual points) and plot trend line
        if x_solves:
            # We can use PlotWidget.scatter for individual solve points
            plot.scatter(
                x_solves,
                y_solves,
                marker="o",
                marker_style="bold cyan",
                hires_mode=HiResMode.BRAILLE,
                label="Solves",
            )
        if x_ao5:
            # Plot the rolling average line
            plot.plot(
                x_ao5,
                y_ao5,
                line_style="bold green",
                hires_mode=HiResMode.BRAILLE,
                label="Ao5 Trend",
            )

        # 4. Solve History Table (last 10 solves, newest first)
        recent_solves = list(reversed(solves[-10:]))
        hist_table = Table(
            show_header=True,
            header_style="bold cyan",
            expand=True,
            box=None,
        )
        hist_table.add_column("Index", width=6)
        hist_table.add_column("Time", width=12)
        hist_table.add_column("Penalty", width=10)
        hist_table.add_column("Scramble")
        hist_table.add_column("Notes")

        for s in recent_solves:
            idx_markup = f"[dim]#{s.id}[/dim]"
            time_str = s.display_time
            if s.penalty == "DNF":
                time_markup = f"[bold red]{time_str}[/bold red]"
            elif s.penalty == "+2":
                time_markup = f"[bold yellow]{time_str}[/bold yellow]"
            else:
                time_markup = f"[bold]{time_str}[/bold]"

            penalty_str = s.penalty or "─"
            scr_short = s.scramble[:60] + "…" if len(s.scramble) > 60 else s.scramble
            notes_str = s.notes or "─"

            hist_table.add_row(
                idx_markup, time_markup, penalty_str, f"[dim]{scr_short}[/dim]", notes_str
            )

        self.query_one("#stats-history-table", Static).update(hist_table)
