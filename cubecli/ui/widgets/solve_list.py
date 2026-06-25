"""Recent solve list widget with sparkline."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from cubecli.data.models import Solve

# Braille-based sparkline characters (8 levels)
_SPARK_CHARS = " ▁▂▃▄▅▆▇█"
_MAX_SPARK = 12  # number of solves shown in sparkline


def _sparkline(times: list[int | None]) -> str:
    """Build a sparkline string from a list of effective ms times."""
    valid = [t for t in times if t is not None]
    if len(valid) < 2:
        return ""
    lo, hi = min(valid), max(valid)
    rng = hi - lo or 1
    chars = []
    for t in times:
        if t is None:
            chars.append("[red]✕[/red]")
        else:
            idx = int((t - lo) / rng * (len(_SPARK_CHARS) - 1))
            # Invert: lower time = taller bar (better)
            inv_idx = len(_SPARK_CHARS) - 1 - idx
            chars.append(f"[green]{_SPARK_CHARS[inv_idx]}[/green]")
    return "".join(chars)


class SolveList(Widget):
    """Right panel: sparkline + last N solves in reverse-chronological order.

    Call :meth:`update_solves` whenever the solve list changes.
    """

    DEFAULT_CSS = ""
    _MAX_SHOWN = 8  # rows shown in the list area

    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]  Recent Solves[/bold cyan]", id="solve-list-title")
        yield Label("", id="sparkline-bar")
        for i in range(self._MAX_SHOWN):
            yield Label("", classes="solve-item", id=f"solve-row-{i}")

    def on_mount(self) -> None:
        self._clear()

    def update_solves(self, solves: list[Solve]) -> None:
        """Refresh the list with the provided solves (all for the session).

        The most recent ``_MAX_SHOWN`` solves are displayed newest-first.
        The sparkline shows the last ``_MAX_SPARK`` effective times.
        """
        # ── Sparkline ──────────────────────────────────────────────────
        spark_times = [s.effective_ms for s in solves[-_MAX_SPARK:]]
        spark = _sparkline(spark_times)
        try:
            self.query_one("#sparkline-bar", Label).update(
                f" {spark}  [dim](last {min(len(solves), _MAX_SPARK)})[/dim]" if spark else ""
            )
        except Exception:
            pass

        # ── Solve rows ──────────────────────────────────────────────────
        # Show newest first
        recent = list(reversed(solves[-self._MAX_SHOWN :]))
        total = len(solves)

        for i in range(self._MAX_SHOWN):
            try:
                lbl = self.query_one(f"#solve-row-{i}", Label)
            except Exception:
                continue

            if i >= len(recent):
                lbl.update("")
                continue

            solve = recent[i]
            num = total - i
            time_str = solve.display_time

            # Colour-code by penalty
            if solve.penalty == "DNF":
                time_markup = f"[red bold]{time_str}[/red bold]"
            elif solve.penalty == "+2":
                time_markup = f"[yellow bold]{time_str}[/yellow bold]"
            else:
                time_markup = f"[bold]{time_str}[/bold]"

            # Truncate scramble for display
            scr = solve.scramble
            scr_short = scr[:40] + "…" if len(scr) > 40 else scr

            lbl.update(f" [dim]#{num:>3}[/dim]  {time_markup}  [dim]{scr_short}[/dim]")

    def _clear(self) -> None:
        """Reset all rows to empty."""
        try:
            self.query_one("#sparkline-bar", Label).update("")
        except Exception:
            pass
        for i in range(self._MAX_SHOWN):
            try:
                self.query_one(f"#solve-row-{i}", Label).update(
                    " [dim]No solves yet — hold SPACE to start![/dim]" if i == 0 else ""
                )
            except Exception:
                pass
