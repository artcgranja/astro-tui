"""Horizontal bar chart widget for displaying 0.0-1.0 metrics."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

# Bar rendering constants
_BAR_WIDTH = 30
_FILL_CHAR = "\u2588"  # Full block
_EMPTY_CHAR = "\u2591"  # Light shade


class MetricBars(Static):
    """Renders horizontal bars for metrics in the 0.0-1.0 range.

    Color coding:
    - Green:  value > 0.7
    - Yellow: value > 0.4
    - Red:    value <= 0.4
    """

    def update_metrics(self, metrics: dict[str, float]) -> None:
        """Update the display with a dictionary of metric_name -> value."""
        if not metrics:
            self.update(Text("No metrics available.", style="dim"))
            return

        lines = Text()
        max_label_len = max(len(name) for name in metrics)

        for name, value in metrics.items():
            clamped = max(0.0, min(1.0, value))
            filled = round(clamped * _BAR_WIDTH)
            empty = _BAR_WIDTH - filled

            if clamped > 0.7:
                color = "green"
            elif clamped > 0.4:
                color = "yellow"
            else:
                color = "red"

            padded_name = name.ljust(max_label_len)
            lines.append(f"  {padded_name}  ", style="bold")
            lines.append(_FILL_CHAR * filled, style=color)
            lines.append(_EMPTY_CHAR * empty, style="dim")
            lines.append(f"  {clamped:.2f}\n", style=color)

        self.update(lines)
