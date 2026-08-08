"""Sidebar Button widget with disabled keyboard focus."""

from __future__ import annotations

from typing import Any

from textual.screen import Screen
from textual.widgets import Button


class SidebarButton(Button):
    """A button that cannot receive keyboard focus, protecting timer hold-space logic."""

    can_focus = False


SIDEBAR_IDS = [
    "btn-timer",
    "btn-stats",
    "btn-trainer",
    "btn-settings",
    "btn-puzzle",
    "btn-session",
]


def handle_sidebar_navigation(screen: Screen[Any], key: str) -> bool:
    """Handle Up/Down/Enter navigation for the sidebar buttons.

    Returns True if the key was handled, False otherwise.
    """
    if key not in ("up", "down", "enter"):
        return False

    # Get all sidebar buttons that exist on the screen
    buttons = []
    for bid in SIDEBAR_IDS:
        try:
            btn = screen.query_one(f"#{bid}", Button)
            buttons.append(btn)
        except Exception:
            # Skip buttons that don't exist on this screen rather than aborting.
            continue

    if not buttons:
        return False

    # Find current selected index, or fallback to active index
    selected_idx = -1
    active_idx = -1
    for i, btn in enumerate(buttons):
        if btn.has_class("selected"):
            selected_idx = i
        if btn.has_class("active"):
            active_idx = i

    current_idx = selected_idx if selected_idx != -1 else active_idx
    if current_idx == -1:
        current_idx = 0

    if key == "down":
        next_idx = (current_idx + 1) % len(buttons)
        for i, btn in enumerate(buttons):
            if i == next_idx:
                btn.add_class("selected")
            else:
                btn.remove_class("selected")
        return True

    elif key == "up":
        next_idx = (current_idx - 1) % len(buttons)
        for i, btn in enumerate(buttons):
            if i == next_idx:
                btn.add_class("selected")
            else:
                btn.remove_class("selected")
        return True

    elif key == "enter":
        if selected_idx != -1:
            buttons[selected_idx].press()
            return True

    return False
