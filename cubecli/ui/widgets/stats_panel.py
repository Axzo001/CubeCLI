"""Statistics sidebar widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from cubecli.core.timer import format_time

_DASH = "[dim]──────[/dim]"


def _fmt(ms: int | None) -> str:
    """Format an optional millisecond time; return dash if None."""
    return format_time(ms) if ms is not None else "─"


class StatsPanel(Widget):
    """Left sidebar showing current session statistics.

    Call :meth:`update_stats` whenever the solve list changes.
    """

    DEFAULT_CSS = ""

    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]  Statistics[/bold cyan]", id="stats-title")
        # Stat rows — updated via update_stats()
        for row_id in ("single", "mo3", "ao5", "ao12", "ao50", "best", "mean", "count"):
            yield Label("", classes="stat-row", id=f"stat-{row_id}")

    def on_mount(self) -> None:
        self.update_stats(None, None, None, None, None, None, None, 0, False)

    def update_stats(
        self,
        single: int | None,
        mo3: int | None,
        ao5: int | None,
        ao12: int | None,
        ao50: int | None,
        best: int | None,
        mean: int | None,
        count: int,
        single_is_pb: bool = False,
    ) -> None:
        """Refresh all stat labels.

        Args:
            single: Most recent effective time (ms) or None.
            mo3, ao5, ao12, ao50: Rolling averages (ms) or None.
            best: Session best (ms) or None.
            mean: Session mean (ms) or None.
            count: Total solve count.
            single_is_pb: If True, highlight single as a PB.
        """
        pb_tag = " [bold green]🏆[/bold green]" if single_is_pb else ""
        rows = [
            ("single", "Single", _fmt(single) + pb_tag),
            ("mo3", "Mo3   ", _fmt(mo3)),
            ("ao5", "Ao5   ", _fmt(ao5)),
            ("ao12", "Ao12  ", _fmt(ao12)),
            ("ao50", "Ao50  ", _fmt(ao50)),
            ("best", "Best  ", _fmt(best)),
            ("mean", "Mean  ", _fmt(mean)),
            ("count", "Solves", str(count)),
        ]
        for row_id, label, value in rows:
            try:
                self.query_one(f"#stat-{row_id}", Label).update(
                    f" [dim]{label}[/dim]  [bold]{value}[/bold]"
                )
            except Exception:
                pass
