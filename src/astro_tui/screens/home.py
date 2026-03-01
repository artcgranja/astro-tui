"""Home screen with feature cards for each astro-context module."""

from __future__ import annotations

import astro_context
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

# ---------------------------------------------------------------------------
# Feature card data — one per astro-context module
# ---------------------------------------------------------------------------

_FEATURES: list[tuple[str, str, str]] = [
    (
        "Pipeline",
        "Build and execute context pipelines with composable steps, "
        "token budgets, and overflow handling.",
        "pipeline",
    ),
    (
        "Ingestion",
        "Chunk documents with fixed-size, recursive, sentence, semantic, "
        "code-aware, and table-aware chunkers.",
        "ingestion",
    ),
    (
        "Retrieval",
        "Dense, sparse, and hybrid retrieval with RRF fusion, reranking, "
        "and late interaction scoring.",
        "retrieval",
    ),
    (
        "Query",
        "Transform queries with HyDE, multi-query, decomposition, "
        "step-back, and conversation rewriting.",
        "query",
    ),
    (
        "Memory",
        "Manage conversation memory with sliding windows, fact extraction, "
        "graph memory, and eviction policies.",
        "memory",
    ),
    (
        "Evaluation",
        "Evaluate pipelines with retrieval metrics, RAG quality, "
        "A/B testing, batch runs, and human review.",
        "evaluation",
    ),
    (
        "Observability",
        "Trace pipeline execution with span trees, cost tracking, "
        "and OTLP-compatible exporters.",
        "observability",
    ),
    (
        "Chat",
        "Interactive AI chat with Agent, MemoryManager, and "
        "SimpleGraphMemory (requires API key).",
        "chat",
    ),
    (
        "Catalog",
        "Browse every class, protocol, and function exported by "
        "astro-context in an interactive reference.",
        "catalog",
    ),
    (
        "Formatters",
        "Format context windows for Anthropic and OpenAI APIs "
        "with automatic token budgeting.",
        "home",
    ),
]


class _FeatureCard(Static):
    """A single feature card with module name, description, and button."""

    DEFAULT_CSS = """
    _FeatureCard {
        height: auto;
    }
    """

    def __init__(
        self,
        title: str,
        description: str,
        mode: str,
    ) -> None:
        super().__init__(classes="feature-card")
        self._title = title
        self._description = description
        self._mode = mode

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold cyan]{self._title}[/bold cyan]\n{self._description}",
        )
        yield Button(
            f"Explore {self._title} \u2192",
            id=f"explore-{self._mode}",
            variant="primary",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Switch to the corresponding mode when the button is clicked."""
        event.stop()
        self.app.switch_mode(self._mode)


class HomeScreen(Screen):
    """Welcome dashboard with feature cards for every astro-context module."""

    def compose(self) -> ComposeResult:
        version = getattr(astro_context, "__version__", "dev")
        yield Header()
        with VerticalScroll():
            yield Static(
                f"[bold]astro-context[/bold]  v{version}",
                classes="welcome-title",
            )
            yield Static(
                "A modular context-engineering toolkit for LLM applications.\n"
                "Explore each module below or press the key shortcut "
                "shown in the footer.",
                classes="welcome-subtitle",
            )
            for title, description, mode in _FEATURES:
                yield _FeatureCard(title, description, mode)
        yield Footer()
