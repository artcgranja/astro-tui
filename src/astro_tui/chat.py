"""Chat engine that wires astro-context Agent + Memory + Graph."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from astro_context import (
    Agent,
    MemoryManager,
    SimpleGraphMemory,
)
from astro_context.agent.tools import memory_tools
from astro_context.models.context import ContextResult
from astro_context.models.memory import ConversationTurn, MemoryEntry
from astro_context.storage.json_file_store import JsonFileMemoryStore

# Words to skip when extracting simple entity keywords from facts.
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "like",
    "through", "after", "over", "between", "out", "that", "this", "it",
    "not", "no", "but", "or", "and", "if", "so", "than", "very",
    "i", "me", "my", "we", "you", "your", "he", "she", "they", "their",
})


class ChatEngine:
    """Wires Agent + MemoryManager + SimpleGraphMemory + JsonFileMemoryStore.

    This is the non-UI layer: it has zero Rich/display imports.
    The terminal app calls into this class for chat and data.
    """

    __slots__ = ("_agent", "_fact_store", "_graph", "_memory", "_synced_fact_ids")

    def __init__(self, api_key: str, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)

        # Persistent fact store — survives across sessions
        self._fact_store = JsonFileMemoryStore(data_dir / "facts.json")

        # Graph memory — in-memory, rebuilt from facts on startup
        self._graph = SimpleGraphMemory()

        # Memory manager with sliding window + persistent store
        self._memory = MemoryManager(
            conversation_tokens=8192,
            persistent_store=self._fact_store,
        )

        # Track which facts have been synced to the graph (by ID)
        self._synced_fact_ids: set[str] = {f.id for f in self._fact_store.list_all()}

        # Agent with system prompt, memory, and tools
        self._agent = (
            Agent(
                model="claude-sonnet-4-20250514",
                api_key=api_key,
                max_tokens=16384,
                max_response_tokens=2048,
            )
            .with_system_prompt(
                "You are Astro, a helpful AI assistant with long-term memory.\n\n"
                "## Memory Management Rules\n"
                "You have access to persistent memory tools: save_fact, search_facts, "
                "update_fact, and delete_fact.\n\n"
                "CRITICAL: Previously saved facts are already visible in your context. "
                "Do NOT re-save facts that you can already see.\n\n"
                "Before saving a new fact:\n"
                "1. Check if the information is already in your context (it usually is).\n"
                "2. If unsure, use search_facts to verify.\n"
                "3. If a similar fact exists but needs updating, use update_fact with its ID.\n"
                "4. Only use save_fact for genuinely NEW information.\n\n"
                "When information changes (e.g., user corrects their age), "
                "use update_fact on the existing fact instead of saving a duplicate.\n"
                "Use delete_fact to remove outdated or incorrect facts.\n\n"
                "Do NOT save trivial or transient information "
                "(e.g., greetings, small talk, questions about capabilities).\n\n"
                "You are running inside astro-tui, a terminal chat app powered by astro-context."
            )
            .with_memory(self._memory)
            .with_tools(memory_tools(self._memory))
        )

        # Rebuild graph from any existing persisted facts
        self._rebuild_graph()

    # -- Public API --

    def send(self, message: str) -> Iterator[str]:
        """Send a user message and yield streaming response chunks."""
        for chunk in self._agent.chat(message):
            yield chunk
        # After streaming completes, check if new facts were saved
        self._sync_graph()

    def handle_command(self, text: str) -> str | None:
        """Handle slash commands. Returns None if not a command."""
        cmd = text.strip().lower()

        if cmd == "/help":
            return (
                "Available commands:\n"
                "  /facts  - List all saved facts\n"
                "  /clear  - Clear conversation memory\n"
                "  /graph  - Show entity graph\n"
                "  /stats  - Show last pipeline diagnostics\n"
                "  /help   - Show this help\n"
                "  /quit   - Exit the app"
            )

        if cmd == "/facts":
            facts = self._memory.get_all_facts()
            if not facts:
                return "No facts saved yet."
            lines = [f"{len(facts)} saved fact(s):"]
            for f in facts:
                tags = ", ".join(f.tags) if f.tags else "none"
                lines.append(f"  [{f.id[:8]}] {f.content}  (tags: {tags})")
            return "\n".join(lines)

        if cmd == "/clear":
            self._memory.conversation.clear()
            return "Conversation memory cleared. Saved facts are preserved."

        if cmd == "/graph":
            entities = self._graph.entities
            rels = self._graph.relationships
            if not entities:
                return "No entities in graph yet. Save some facts first!"
            lines = [f"{len(entities)} entities, {len(rels)} relationships:"]
            for s, r, t in rels:
                lines.append(f"  {s} --[{r}]--> {t}")
            if not rels:
                for e in entities:
                    lines.append(f"  {e}")
            return "\n".join(lines)

        if cmd == "/stats":
            return self._format_stats()

        if cmd == "/quit":
            return "__QUIT__"

        return None

    # -- Data accessors --

    @property
    def conversation_turns(self) -> list[ConversationTurn]:
        """Recent conversation turns from sliding window."""
        return list(self._memory.conversation.turns)

    @property
    def all_facts(self) -> list[MemoryEntry]:
        """All persistent facts."""
        return self._memory.get_all_facts()

    @property
    def graph_entities(self) -> list[str]:
        """All entity IDs in the graph."""
        return self._graph.entities

    @property
    def graph_relationships(self) -> list[tuple[str, str, str]]:
        """All (source, relation, target) triples."""
        return self._graph.relationships

    @property
    def last_result(self) -> ContextResult | None:
        """Last ContextResult from the pipeline."""
        return self._agent.last_result

    @property
    def last_diagnostics(self) -> dict[str, Any]:
        """Diagnostics dict from the last pipeline run."""
        result = self._agent.last_result
        if result is None:
            return {}
        return dict(result.diagnostics) if result.diagnostics else {}

    # -- Internal helpers --

    def _format_stats(self) -> str:
        result = self._agent.last_result
        if result is None:
            return "No pipeline diagnostics yet. Send a message first."
        w = result.window
        lines = [
            "Pipeline diagnostics:",
            f"  Tokens: {w.used_tokens}/{w.max_tokens} ({w.utilization * 100:.1f}%)",
            f"  Build time: {result.build_time_ms:.0f}ms",
            f"  Items: {len(w.items)} included, {len(result.overflow_items)} overflow",
            f"  Conversation turns: {len(self.conversation_turns)}",
            f"  Saved facts: {len(self.all_facts)}",
            f"  Graph: {len(self.graph_entities)} entities, "
            f"{len(self.graph_relationships)} relationships",
        ]
        return "\n".join(lines)

    def _rebuild_graph(self) -> None:
        """Populate the graph from all persisted facts."""
        self._graph.clear()
        for fact in self._fact_store.list_all():
            self._add_fact_to_graph(fact)

    def _sync_graph(self) -> None:
        """Check for new facts and add them to the graph."""
        for fact in self._fact_store.list_all():
            if fact.id not in self._synced_fact_ids:
                self._add_fact_to_graph(fact)
                self._synced_fact_ids.add(fact.id)

    def _add_fact_to_graph(self, fact: MemoryEntry) -> None:
        """Extract simple keywords from a fact and add to graph."""
        if not fact.content.strip():
            return
        fact_node = f"fact:{fact.id[:8]}"
        self._graph.add_entity(fact_node, {"content": fact.content, "type": "fact"})
        self._graph.link_memory(fact_node, fact.id)

        # Extract keywords as entities and link them
        keywords = self._extract_keywords(fact.content)
        for kw in keywords:
            self._graph.add_entity(kw, {"type": "keyword"})
            self._graph.add_relationship(kw, "mentioned_in", fact_node)

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract simple keyword entities from text (no NLP required)."""
        words = re.findall(r"[a-zA-Z]+", text)
        keywords = []
        seen: set[str] = set()
        for w in words:
            w_lower = w.lower()
            if w_lower not in _STOP_WORDS and len(w) > 2 and w_lower not in seen:
                seen.add(w_lower)
                keywords.append(w)
        return keywords[:5]
