"""Panel widget for displaying pipeline diagnostics."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static


class DiagnosticsPanel(Static):
    """Renders pipeline diagnostics as formatted Rich text.

    Shows step timings, token utilization, and overflow counts.
    """

    def update_diagnostics(self, diag: dict) -> None:
        """Update the panel with a diagnostics dictionary.

        Expected keys (all optional):
        - step_timings: dict[str, float] — step name to ms
        - used_tokens / max_tokens: int
        - utilization: float (0.0-1.0)
        - overflow_count: int
        - build_time_ms: float
        - item_count: int
        """
        if not diag:
            self.update(Text("No diagnostics available.", style="dim"))
            return

        lines = Text()
        lines.append("Pipeline Diagnostics\n", style="bold underline")
        lines.append("\n")

        # Token utilization
        used = diag.get("used_tokens", 0)
        total = diag.get("max_tokens", 0)
        utilization = diag.get("utilization", 0.0)
        if total:
            pct = utilization * 100
            style = "green" if pct < 70 else ("yellow" if pct < 90 else "red")
            lines.append(
                f"  Tokens: {used}/{total} ({pct:.1f}%)\n",
                style=style,
            )

        # Build time
        build_time = diag.get("build_time_ms")
        if build_time is not None:
            lines.append(f"  Build time: {build_time:.0f}ms\n")

        # Items
        item_count = diag.get("item_count")
        if item_count is not None:
            lines.append(f"  Items: {item_count}\n")

        # Overflow
        overflow = diag.get("overflow_count", 0)
        if overflow:
            lines.append(f"  Overflow: {overflow} items\n", style="yellow")

        # Step timings
        step_timings = diag.get("step_timings", {})
        if step_timings:
            lines.append("\n")
            lines.append("  Step Timings\n", style="bold")
            for step_name, ms in step_timings.items():
                lines.append(f"    {step_name}: {ms:.1f}ms\n")

        self.update(lines)
