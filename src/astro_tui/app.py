"""Interactive terminal chatbot showcasing astro-context.

A Rich-powered terminal chat with:
  - Short-term memory (SlidingWindowMemory)
  - Long-term facts (JsonFileMemoryStore, persists across sessions)
  - Graph memory (SimpleGraphMemory, keyword entity extraction)
  - Streaming responses with live Markdown rendering
  - Inline diagnostics after each turn

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    uv run astro-tui
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from astro_tui.chat import ChatEngine

_theme = Theme({
    "info": "dim cyan",
    "user": "bold green",
    "assistant": "bold blue",
    "warning": "yellow",
    "danger": "bold red",
    "muted": "dim",
    "accent": "bold cyan",
})
console = Console(theme=_theme)


# -- Display helpers --


def _print_banner() -> None:
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]astro-tui[/]\n"
            "[dim]Terminal chatbot powered by astro-context[/]\n\n"
            "[dim]Features: short-term memory | long-term facts | graph memory[/]\n"
            "[dim]Type [bold]/help[/bold] for commands, [bold]quit[/bold] to exit.[/dim]",
            border_style="cyan",
            padding=(1, 4),
        )
    )
    console.print()


def _print_diagnostics(engine: ChatEngine) -> None:
    """Print inline diagnostics after each turn."""
    result = engine.last_result
    if result is None:
        return

    w = result.window
    d = result.diagnostics
    utilization = d.get("token_utilization", 0) * 100
    items_count = d.get("items_included", 0)

    sources: dict[str, int] = {}
    for item in w.items:
        key = item.source.value
        sources[key] = sources.get(key, 0) + 1

    facts = engine.all_facts
    turns = engine.conversation_turns
    src_str = " ".join(f"{k}={v}" for k, v in sorted(sources.items()))

    console.print(
        f"  [{items_count} items | {w.used_tokens}/{w.max_tokens} tokens "
        f"({utilization:.0f}%) | {result.build_time_ms:.0f}ms | {src_str} | "
        f"facts: {len(facts)} | turns: {len(turns)}]",
        style="info",
    )


def _print_graph(engine: ChatEngine) -> None:
    """Print the entity graph as a rich table."""
    entities = engine.graph_entities
    rels = engine.graph_relationships

    if not entities:
        console.print("  No entities in graph yet. Save some facts first!", style="info")
        return

    table = Table(title=f"Entity Graph ({len(entities)} nodes, {len(rels)} edges)", show_lines=True)
    table.add_column("Source", style="cyan")
    table.add_column("Relation", style="dim")
    table.add_column("Target", style="cyan")

    for s, r, t in rels:
        table.add_row(s, r, t)

    console.print(table)


def _print_facts(engine: ChatEngine) -> None:
    """Print all saved facts as a rich table."""
    facts = engine.all_facts
    if not facts:
        console.print("  No facts saved yet.", style="info")
        return

    table = Table(title=f"Saved Facts ({len(facts)})")
    table.add_column("ID", style="cyan", width=8)
    table.add_column("Content")
    table.add_column("Tags", style="dim")

    for f in facts:
        tags = ", ".join(f.tags) if f.tags else "-"
        table.add_row(f.id[:8], f.content, tags)

    console.print(table)


def _print_memory(engine: ChatEngine) -> None:
    """Print recent conversation turns."""
    turns = engine.conversation_turns
    if not turns:
        console.print("  No conversation history yet.", style="info")
        return

    table = Table(title=f"Conversation Memory ({len(turns)} turns)")
    table.add_column("Role", width=10)
    table.add_column("Tokens", justify="right", width=6)
    table.add_column("Content")

    colors = {"user": "green", "assistant": "blue", "tool": "yellow", "system": "magenta"}
    for turn in turns[-15:]:
        color = colors.get(turn.role, "white")
        content = turn.content[:80]
        if len(turn.content) > 80:
            content += "..."
        table.add_row(f"[{color}]{turn.role}[/]", str(turn.token_count), content)

    console.print(table)


def _print_stats(engine: ChatEngine) -> None:
    """Print detailed pipeline diagnostics."""
    result = engine.last_result
    if result is None:
        console.print("  No diagnostics yet. Send a message first.", style="info")
        return

    w = result.window

    table = Table(title="Pipeline Diagnostics", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Tokens used", f"{w.used_tokens}/{w.max_tokens}")
    table.add_row("Utilization", f"{w.utilization * 100:.1f}%")
    table.add_row("Build time", f"{result.build_time_ms:.0f}ms")
    table.add_row("Items included", str(len(w.items)))
    table.add_row("Overflow items", str(len(result.overflow_items)))
    table.add_row("Conversation turns", str(len(engine.conversation_turns)))
    table.add_row("Saved facts", str(len(engine.all_facts)))

    entities = engine.graph_entities
    rels = engine.graph_relationships
    table.add_row("Graph", f"{len(entities)} entities, {len(rels)} edges")

    # Source breakdown
    source_counts: dict[str, int] = {}
    for item in w.items:
        key = item.source.value
        source_counts[key] = source_counts.get(key, 0) + 1
    if source_counts:
        src_str = ", ".join(f"{k}: {v}" for k, v in sorted(source_counts.items()))
        table.add_row("By source", src_str)

    console.print(table)


def _handle_command(text: str, engine: ChatEngine) -> bool:
    """Handle slash commands. Returns True if it was a command."""
    cmd = text.strip().lower()

    if cmd == "/help":
        console.print()
        console.print(Panel(
            "[bold]/facts[/]    - List all saved long-term facts\n"
            "[bold]/memory[/]   - Show recent conversation turns\n"
            "[bold]/graph[/]    - Show entity relationship graph\n"
            "[bold]/stats[/]    - Show pipeline diagnostics\n"
            "[bold]/clear[/]    - Clear conversation memory (facts preserved)\n"
            "[bold]/help[/]     - Show this help\n"
            "[bold]quit[/]      - Exit",
            title="Commands",
            border_style="cyan",
        ))
        return True

    if cmd == "/facts":
        console.print()
        _print_facts(engine)
        return True

    if cmd == "/memory":
        console.print()
        _print_memory(engine)
        return True

    if cmd == "/graph":
        console.print()
        _print_graph(engine)
        return True

    if cmd == "/stats":
        console.print()
        _print_stats(engine)
        return True

    if cmd == "/clear":
        engine.handle_command("/clear")
        console.print("  Conversation memory cleared. Saved facts are preserved.", style="info")
        return True

    return False


def main() -> None:
    """Entry point for astro-tui."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            "\n[danger]ANTHROPIC_API_KEY not set.[/]\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n",
        )
        sys.exit(1)

    data_dir = Path.home() / ".astro-tui"
    engine = ChatEngine(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        data_dir=data_dir,
    )

    _print_banner()

    # Show persisted facts from previous sessions
    facts = engine.all_facts
    if facts:
        console.print(f"  Loaded {len(facts)} fact(s) from previous sessions.", style="info")
        console.print(f"  Data: {data_dir / 'facts.json'}", style="muted")
        console.print()

    while True:
        try:
            user_input = console.input("[user]You:[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye!", style="accent")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            console.print("Goodbye!", style="accent")
            break
        if _handle_command(user_input, engine):
            console.print()
            continue

        # Stream the response
        console.print("[assistant]Astro:[/]", end=" ")
        response_text = ""
        try:
            for chunk in engine.send(user_input):
                response_text += chunk
        except Exception as exc:
            console.print(f"\n[danger]Error: {exc}[/]")
            console.print()
            continue

        # Render the full response as Markdown
        console.print()
        console.print(Markdown(response_text))
        _print_diagnostics(engine)
        console.print()


if __name__ == "__main__":
    main()
