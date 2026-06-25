"""Case Picker dialog for selecting active training cases."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, SelectionList
from textual.widgets.selection_list import Selection

from cubecli.training.trainer import load_cases


class CasePicker(Screen[list[str]]):
    """A side-by-side selection dialog for groups and individual cases."""

    BINDINGS = [
        ("enter", "save", "Save & Exit"),
        ("escape", "cancel", "Cancel"),
        ("a", "select_all", "Select All"),
        ("n", "select_none", "Select None"),
    ]

    def __init__(self, mode: str, active_case_ids: list[str]) -> None:
        super().__init__()
        self.mode = mode
        self.all_cases = load_cases(mode)
        self.selected_ids = set(active_case_ids)

        self.groups = sorted({c.group for c in self.all_cases})
        self._updating = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label(
            f"[bold cyan]Select {self.mode.upper()} Cases to Drill[/bold cyan]\n"
            "[dim]Toggle groups on the left, or individual cases on the right. Press Enter to save.[/dim]",
            id="picker-title",
        )

        with Horizontal(id="picker-body"):
            with Vertical(id="picker-groups-panel"):
                yield Label("[bold]Groups[/bold]")
                yield SelectionList[str](id="group-list")

            with Vertical(id="picker-cases-panel"):
                yield Label("[bold]Individual Cases[/bold]")
                yield SelectionList[str](id="case-list")

        yield Footer()

    def on_mount(self) -> None:
        """Populate the selection lists."""
        self._updating = True

        # Group list
        group_list = self.query_one("#group-list", SelectionList)
        group_selections = []
        for g in self.groups:
            # A group is checked initially if all its cases are currently selected
            g_cases = [c for c in self.all_cases if c.group == g]
            checked = all(c.id in self.selected_ids for c in g_cases) if g_cases else False
            group_selections.append(Selection(g, g, checked))
        group_list.add_options(group_selections)

        # Case list
        case_list = self.query_one("#case-list", SelectionList)
        case_selections = []
        for c in self.all_cases:
            label = f"{c.id}: {c.name}" if self.mode == "oll" else f"{c.id}-Perm: {c.name}"
            checked = c.id in self.selected_ids
            case_selections.append(Selection(label, c.id, checked))
        case_list.add_options(case_selections)

        self._updating = False

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged[str]) -> None:
        """Synchronize selection list states without feedback loops."""
        if self._updating:
            return

        self._updating = True

        list_id = event.selection_list.id
        if list_id == "group-list":
            # Group toggled -> Update all cases in that group
            group_list = event.selection_list
            selected_groups = set(group_list.selected)

            for g in self.groups:
                g_cases = [c for c in self.all_cases if c.group == g]
                is_selected = g in selected_groups
                for c in g_cases:
                    if is_selected:
                        self.selected_ids.add(c.id)
                    else:
                        self.selected_ids.discard(c.id)

            # Refresh case list selections
            case_list = self.query_one("#case-list", SelectionList)
            case_list.deselect_all()
            for cid in self.selected_ids:
                case_list.select(cid)

        elif list_id == "case-list":
            # Case toggled -> Update selected set and sync group check status
            case_list = event.selection_list
            self.selected_ids = set(case_list.selected)

            group_list = self.query_one("#group-list", SelectionList)
            for g in self.groups:
                g_cases = [c for c in self.all_cases if c.group == g]
                if g_cases and all(c.id in self.selected_ids for c in g_cases):
                    group_list.select(g)
                else:
                    group_list.deselect(g)

        self._updating = False

    def action_save(self) -> None:
        """Return the final selected case IDs to the parent screen."""
        # Ensure at least one case is selected to prevent crash
        if not self.selected_ids:
            self.notify("Please select at least one case to practice.", severity="error")
            return
        self.dismiss(list(self.selected_ids))

    def action_cancel(self) -> None:
        """Close picker without saving."""
        self.dismiss(None)

    def action_select_all(self) -> None:
        """Check all groups and cases."""
        self._updating = True
        self.selected_ids = {c.id for c in self.all_cases}

        group_list = self.query_one("#group-list", SelectionList)
        group_list.select_all()

        case_list = self.query_one("#case-list", SelectionList)
        case_list.select_all()
        self._updating = False

    def action_select_none(self) -> None:
        """Uncheck all groups and cases."""
        self._updating = True
        self.selected_ids.clear()

        group_list = self.query_one("#group-list", SelectionList)
        group_list.deselect_all()

        case_list = self.query_one("#case-list", SelectionList)
        case_list.deselect_all()
        self._updating = False
