"""DataTable widget pre-configured for displaying ContextItem lists."""

from __future__ import annotations

from astro_context import ContextItem
from textual.widgets import DataTable


class ContextItemsTable(DataTable):
    """A DataTable pre-configured to display a list of ContextItem objects.

    Columns: ID (8 chars), Content (truncated 60 chars), Source,
    Score (2 decimals), Priority, Tokens.
    """

    def on_mount(self) -> None:
        """Set up columns when the widget is mounted."""
        self.add_columns(
            "ID", "Content", "Source", "Score", "Priority", "Tokens",
        )

    def load_items(self, items: list[ContextItem]) -> None:
        """Clear the table and load a list of ContextItem objects."""
        self.clear()
        for item in items:
            content_preview = item.content[:60]
            if len(item.content) > 60:
                content_preview = content_preview[:57] + "..."
            self.add_row(
                item.id[:8],
                content_preview,
                item.source.value if hasattr(item.source, "value") else str(item.source),
                f"{item.score:.2f}",
                str(item.priority),
                str(item.token_count),
                key=item.id,
            )
