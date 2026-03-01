"""Command palette providers for the astro-tui application."""

from __future__ import annotations

from textual.command import DiscoveryHit, Hit, Hits, Provider


class AstroCommands(Provider):
    """Command palette provider for navigating between screens."""

    _SCREENS = [
        ("Home", "home", "Welcome dashboard and feature overview"),
        ("Chat", "chat", "Interactive chat with AI agent (requires API key)"),
        ("Pipeline", "pipeline", "Context pipeline builder and executor"),
        ("Ingestion", "ingestion", "Document chunker explorer and comparison"),
        ("Retrieval", "retrieval", "Retrieval strategies and RRF fusion"),
        ("Query", "query", "Query transformation playground"),
        ("Memory", "memory", "Memory management and eviction explorer"),
        ("Evaluation", "evaluation", "Evaluation metrics and A/B testing"),
        ("Observability", "observability", "Tracing and cost tracking"),
        ("Catalog", "catalog", "Full class and protocol reference"),
    ]

    async def discover(self) -> Hits:
        """Yield all available screen navigation commands."""
        for name, mode, help_text in self._SCREENS:
            yield DiscoveryHit(
                f"Go to {name}",
                self._make_callback(mode),
                help=help_text,
            )

    async def search(self, query: str) -> Hits:
        """Search for screen navigation commands."""
        matcher = self.matcher(query)
        for name, mode, help_text in self._SCREENS:
            command = f"Go to {name}"
            score = matcher.match(command)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(command),
                    self._make_callback(mode),
                    help=help_text,
                )

    def _make_callback(self, mode: str):  # noqa: ANN202
        """Create a callback that switches to the given mode."""

        def callback() -> None:
            self.app.switch_mode(mode)

        return callback
