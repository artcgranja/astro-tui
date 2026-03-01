"""Widget for rendering an entity graph as a Rich Tree."""

from __future__ import annotations

from rich.text import Text
from rich.tree import Tree
from textual.widgets import Static


class GraphView(Static):
    """Renders a knowledge graph as a Rich Tree widget.

    Entities are top-level nodes; relationships are shown as branches
    with labeled edges.
    """

    def update_graph(
        self,
        entities: list[str],
        relationships: list[tuple[str, str, str]],
    ) -> None:
        """Update the graph display.

        Args:
            entities: List of entity names/IDs.
            relationships: List of (source, relation, target) triples.
        """
        if not entities:
            self.update(Text("No entities in graph.", style="dim"))
            return

        tree = Tree(
            Text("Knowledge Graph", style="bold cyan"),
            guide_style="dim",
        )

        # Build adjacency from relationships
        adjacency: dict[str, list[tuple[str, str]]] = {}
        connected: set[str] = set()
        for source, relation, target in relationships:
            adjacency.setdefault(source, []).append((relation, target))
            connected.add(source)
            connected.add(target)

        # Add entities that have outgoing relationships
        added: set[str] = set()
        for source in sorted(adjacency):
            node = tree.add(Text(source, style="green"))
            added.add(source)
            for relation, target in adjacency[source]:
                label = Text()
                label.append(f"--[{relation}]--> ", style="yellow")
                label.append(target, style="cyan")
                node.add(label)

        # Add isolated entities (no relationships)
        for entity in sorted(entities):
            if entity not in added:
                tree.add(Text(entity, style="dim green"))

        self.update(tree)
