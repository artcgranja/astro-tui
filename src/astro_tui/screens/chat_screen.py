"""Chat screen with AI agent, sidebar tabs, and streaming responses."""

from __future__ import annotations

import os
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Input,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from astro_tui.widgets.graph_view import GraphView


class ChatScreen(Screen):
    """Interactive chat screen with AI agent and context sidebar.

    The chat area occupies 70% of the width; a sidebar with tabbed
    context, facts, and graph views occupies the remaining 30%.

    Requires ANTHROPIC_API_KEY in the environment. If absent, the
    screen displays setup instructions instead.
    """

    _engine: object | None = None  # Will be ChatEngine if key present

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(classes="split-horizontal"):
            with Vertical(classes="main-content"):
                yield RichLog(
                    highlight=True,
                    markup=True,
                    id="chat-log",
                    classes="chat-log",
                )
                yield Input(
                    placeholder="Type a message... (/help for commands)",
                    id="chat-input",
                    classes="chat-input",
                )
            with Vertical(classes="sidebar"):
                with TabbedContent("Context", "Facts", "Graph"):
                    with TabPane("Context", id="tab-context"):
                        yield Static(
                            "Context items will appear here "
                            "after a response.",
                            id="context-info",
                        )
                    with TabPane("Facts", id="tab-facts"):
                        yield Static(
                            "Saved facts will appear here.",
                            id="facts-info",
                        )
                    with TabPane("Graph", id="tab-graph"):
                        yield GraphView(id="graph-view")
        yield Footer()

    def on_mount(self) -> None:
        """Check for API key and initialize ChatEngine if available."""
        log = self.query_one("#chat-log", RichLog)
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            log.write(
                "[bold yellow]No ANTHROPIC_API_KEY found.[/bold yellow]\n\n"
                "To enable the AI chat, set your API key:\n\n"
                "  [cyan]export ANTHROPIC_API_KEY=sk-ant-...[/cyan]\n\n"
                "Then restart astro-tui. The other screens work "
                "without an API key."
            )
            inp = self.query_one("#chat-input", Input)
            inp.disabled = True
            return

        # Lazy import to avoid requiring anthropic when no key
        from astro_tui.chat import ChatEngine

        data_dir = Path.home() / ".astro-tui" / "chat_data"
        self._engine = ChatEngine(api_key=api_key, data_dir=data_dir)
        log.write(
            "[bold green]Chat engine ready.[/bold green] "
            "Type a message or /help for commands.\n"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        text = event.value.strip()
        if not text:
            return

        event.input.clear()
        log = self.query_one("#chat-log", RichLog)

        if self._engine is None:
            log.write("[dim]Chat engine not initialized.[/dim]")
            return

        # Handle slash commands synchronously
        cmd_result = self._engine.handle_command(text)  # type: ignore[union-attr]
        if cmd_result is not None:
            if cmd_result == "__QUIT__":
                self.app.exit()
                return
            log.write(f"[dim]{cmd_result}[/dim]\n")
            return

        # Show user message
        log.write(f"[bold blue]You:[/bold blue] {text}\n")

        # Stream AI response in a worker thread
        self._stream_response(text)

    @work(exclusive=True, thread=True)
    def _stream_response(self, message: str) -> None:
        """Send message to ChatEngine and stream response chunks."""
        log = self.query_one("#chat-log", RichLog)
        self.app.call_from_thread(
            log.write, "[bold magenta]Astro:[/bold magenta] ",
        )

        chunks: list[str] = []
        try:
            for chunk in self._engine.send(message):  # type: ignore[union-attr]
                chunks.append(chunk)
                self.app.call_from_thread(log.write, chunk)
        except Exception as exc:  # noqa: BLE001
            self.app.call_from_thread(
                log.write,
                f"\n[bold red]Error: {exc}[/bold red]\n",
            )
            return

        self.app.call_from_thread(log.write, "\n")

        # Update sidebar tabs after response
        self.app.call_from_thread(self._update_sidebar)

    def _update_sidebar(self) -> None:
        """Refresh sidebar tabs with latest engine data."""
        if self._engine is None:
            return

        # Update context tab
        context_info = self.query_one("#context-info", Static)
        result = self._engine.last_result  # type: ignore[union-attr]
        if result and hasattr(result, "window") and result.window:
            items = result.window.items
            lines = [f"[bold]Context items: {len(items)}[/bold]"]
            for item in items[:10]:
                preview = item.content[:50]
                if len(item.content) > 50:
                    preview = preview[:47] + "..."
                src = (
                    item.source.value
                    if hasattr(item.source, "value")
                    else str(item.source)
                )
                lines.append(
                    f"  [{item.id[:8]}] {src}: {preview}"
                )
            if len(items) > 10:
                lines.append(f"  ... and {len(items) - 10} more")
            context_info.update("\n".join(lines))
        else:
            context_info.update("No context items yet.")

        # Update facts tab
        facts_info = self.query_one("#facts-info", Static)
        facts = self._engine.all_facts  # type: ignore[union-attr]
        if facts:
            lines = [f"[bold]Saved facts: {len(facts)}[/bold]"]
            for fact in facts:
                tags = ", ".join(fact.tags) if fact.tags else ""
                tag_str = f" ({tags})" if tags else ""
                lines.append(
                    f"  {fact.content[:60]}{tag_str}"
                )
            facts_info.update("\n".join(lines))
        else:
            facts_info.update("No saved facts yet.")

        # Update graph tab
        graph_view = self.query_one("#graph-view", GraphView)
        entities = self._engine.graph_entities  # type: ignore[union-attr]
        rels = self._engine.graph_relationships  # type: ignore[union-attr]
        graph_view.update_graph(entities, rels)
