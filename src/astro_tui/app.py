"""astro-tui: Terminal showcase for the astro-context library.

A Textual TUI with 10 interactive screens demonstrating every major
module of astro-context — from ingestion and retrieval to evaluation
and observability. Only the Chat screen requires an API key.

Usage:
    uv run astro-tui
"""

from __future__ import annotations

from dotenv import load_dotenv
from textual.app import App
from textual.binding import Binding

from astro_tui.commands import AstroCommands
from astro_tui.screens.catalog import CatalogScreen
from astro_tui.screens.chat_screen import ChatScreen
from astro_tui.screens.evaluation import EvaluationScreen
from astro_tui.screens.home import HomeScreen
from astro_tui.screens.ingestion import IngestionScreen
from astro_tui.screens.memory import MemoryScreen
from astro_tui.screens.observability import ObservabilityScreen
from astro_tui.screens.pipeline import PipelineScreen
from astro_tui.screens.query import QueryScreen
from astro_tui.screens.retrieval import RetrievalScreen

# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


class AstroTUI(App):
    """Textual showcase application for the astro-context library."""

    CSS_PATH = "app.tcss"
    TITLE = "astro-tui"
    SUB_TITLE = "astro-context showcase"

    MODES = {
        "home": HomeScreen,
        "chat": ChatScreen,
        "pipeline": PipelineScreen,
        "ingestion": IngestionScreen,
        "retrieval": RetrievalScreen,
        "query": QueryScreen,
        "memory": MemoryScreen,
        "evaluation": EvaluationScreen,
        "observability": ObservabilityScreen,
        "catalog": CatalogScreen,
    }

    DEFAULT_MODE = "home"

    BINDINGS = [
        Binding("h", "switch_mode('home')", "Home", tooltip="Welcome dashboard"),
        Binding("c", "switch_mode('chat')", "Chat", tooltip="AI chat (requires API key)"),
        Binding("p", "switch_mode('pipeline')", "Pipeline", tooltip="Pipeline builder"),
        Binding("i", "switch_mode('ingestion')", "Ingestion", tooltip="Chunker explorer"),
        Binding("r", "switch_mode('retrieval')", "Retrieval", tooltip="Retrieval strategies"),
        Binding("q", "switch_mode('query')", "Query", tooltip="Query transformations"),
        Binding("m", "switch_mode('memory')", "Memory", tooltip="Memory management"),
        Binding("e", "switch_mode('evaluation')", "Eval", tooltip="Evaluation metrics"),
        Binding("o", "switch_mode('observability')", "Observe", tooltip="Tracing & cost"),
        Binding("a", "switch_mode('catalog')", "Catalog", tooltip="Class reference"),
    ]

    COMMANDS = App.COMMANDS | {AstroCommands}


def main() -> None:
    """Entry point for astro-tui."""
    load_dotenv()
    app = AstroTUI()
    app.run()


if __name__ == "__main__":
    main()
