"""Colored status indicator widget."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

_STATUS_STYLES: dict[str, tuple[str, str]] = {
    "ok": ("\u25cf", "green"),       # Filled circle
    "warning": ("\u25cf", "yellow"),
    "error": ("\u25cf", "red"),
}


class StatusIndicator(Static):
    """A colored dot with a label indicating system status.

    Set the ``status`` reactive to one of: "ok", "warning", "error".
    Set ``label`` to change the accompanying text.
    """

    status: reactive[str] = reactive("ok")
    label: reactive[str] = reactive("Ready")

    def render(self) -> Text:  # type: ignore[override]
        """Render the status dot and label."""
        dot, color = _STATUS_STYLES.get(
            self.status, ("\u25cf", "dim"),
        )
        text = Text()
        text.append(f" {dot} ", style=color)
        text.append(self.label)
        return text

    def watch_status(self) -> None:
        """React to status changes by refreshing the display."""
        self.refresh()

    def watch_label(self) -> None:
        """React to label changes by refreshing the display."""
        self.refresh()
