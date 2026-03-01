"""Memory management screen — sliding window, eviction, decay, graph."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from astro_context import (
    ConversationTurn,
    EbbinghausDecay,
    FIFOEviction,
    ImportanceEviction,
    LinearDecay,
    MemoryEntry,
    PairedEviction,
    SimpleGraphMemory,
    SlidingWindowMemory,
)
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)

from astro_tui.demo_data import sample_conversation_turns, sample_facts

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bar(value: float, width: int = 20) -> str:
    """Render a text bar of given width for a 0..1 value."""
    filled = round(value * width)
    return "[green]" + "\u2588" * filled + "[/]" + "\u2591" * (width - filled)


def _importance(turn: ConversationTurn) -> float:
    """Naive importance scorer: longer content = more important."""
    return min(1.0, turn.token_count / 20.0)


# ---------------------------------------------------------------------------
# Memory Screen
# ---------------------------------------------------------------------------


class MemoryScreen(Screen):
    """Interactive explorer for astro-context memory management."""

    DEFAULT_CSS = """
    MemoryScreen {
        layout: vertical;
    }
    .mem-status {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    .eviction-col {
        width: 1fr;
        padding: 0 1;
    }
    .decay-chart {
        height: auto;
        padding: 1;
        border: solid $primary;
        margin: 0 0 1 0;
    }
    .graph-pane {
        height: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._turns_data = sample_conversation_turns()
        self._turn_idx = 0
        self._facts = sample_facts()

        # Sliding window memory
        self._sw = SlidingWindowMemory(max_tokens=120)

        # Eviction memories
        self._fifo_sw = SlidingWindowMemory(
            max_tokens=80, eviction_policy=FIFOEviction()
        )
        self._imp_sw = SlidingWindowMemory(
            max_tokens=80,
            eviction_policy=ImportanceEviction(importance_fn=_importance),
        )
        self._pair_sw = SlidingWindowMemory(
            max_tokens=80, eviction_policy=PairedEviction()
        )

        # Graph memory
        self._graph = SimpleGraphMemory()

        # Decay time offset (hours)
        self._decay_hours = 0.0

    # ---- compose ----

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Sliding Window", id="tab-sw"):
                yield from self._compose_sliding()
            with TabPane("Eviction", id="tab-evict"):
                yield from self._compose_eviction()
            with TabPane("Decay", id="tab-decay"):
                yield from self._compose_decay()
            with TabPane("Graph", id="tab-graph"):
                yield from self._compose_graph()
        yield Footer()

    # ---- Tab: Sliding Window ----

    def _compose_sliding(self) -> ComposeResult:
        with Horizontal(classes="button-row"):
            yield Button("Add Turn", id="btn-add-turn", variant="primary")
            yield Button("Clear", id="btn-clear-sw", variant="error")
        yield Static("No turns yet.", id="sw-status", classes="mem-status")
        yield DataTable(id="sw-table")

    # ---- Tab: Eviction ----

    def _compose_eviction(self) -> ComposeResult:
        yield Static(
            "Side-by-side comparison — same turns, different eviction.",
            classes="mem-status",
        )
        with Horizontal(classes="button-row"):
            yield Button(
                "Add All Turns", id="btn-evict-fill", variant="primary"
            )
        with Horizontal():
            with Vertical(classes="eviction-col"):
                yield Static("[b]FIFO Eviction[/b]")
                yield DataTable(id="evict-fifo")
            with Vertical(classes="eviction-col"):
                yield Static("[b]Importance Eviction[/b]")
                yield DataTable(id="evict-imp")
            with Vertical(classes="eviction-col"):
                yield Static("[b]Paired Eviction[/b]")
                yield DataTable(id="evict-pair")

    # ---- Tab: Decay ----

    def _compose_decay(self) -> ComposeResult:
        with Horizontal(classes="button-row"):
            yield Button(
                "Advance +24h", id="btn-decay-adv", variant="primary"
            )
            yield Button("Reset", id="btn-decay-reset", variant="error")
        yield Static("", id="decay-hours", classes="mem-status")
        with ScrollableContainer():
            yield Static("", id="decay-chart", classes="decay-chart")

    # ---- Tab: Graph ----

    def _compose_graph(self) -> ComposeResult:
        with Horizontal(classes="input-row"):
            yield Input(
                placeholder="entity (e.g. Mars)",
                id="graph-entity",
            )
            yield Button(
                "Add Entity", id="btn-graph-entity", variant="primary"
            )
        with Horizontal(classes="input-row"):
            yield Input(placeholder="source", id="graph-src")
            yield Input(placeholder="relation", id="graph-rel")
            yield Input(placeholder="target", id="graph-tgt")
            yield Button(
                "Add Relation", id="btn-graph-rel", variant="primary"
            )
        with Horizontal(classes="graph-pane"):
            yield Tree("Knowledge Graph", id="graph-tree")
            yield DataTable(id="graph-triples")

    # ---- mount ----

    def on_mount(self) -> None:
        # Sliding window table
        tbl = self.query_one("#sw-table", DataTable)
        tbl.add_columns("#", "Role", "Content", "Tokens")

        # Eviction tables
        for tid in ("evict-fifo", "evict-imp", "evict-pair"):
            t = self.query_one(f"#{tid}", DataTable)
            t.add_columns("#", "Role", "Content", "Tokens")

        # Graph triples table
        gt = self.query_one("#graph-triples", DataTable)
        gt.add_columns("Source", "Relation", "Target")

        # Seed graph with sample entities
        self._seed_graph()
        self._refresh_graph()

        # Decay initial render
        self._render_decay()

    # ---- Button handlers ----

    def on_button_pressed(self, event: Button.Pressed) -> None:  # noqa: C901
        bid = event.button.id
        if bid == "btn-add-turn":
            self._add_next_turn()
        elif bid == "btn-clear-sw":
            self._clear_sliding()
        elif bid == "btn-evict-fill":
            self._fill_eviction()
        elif bid == "btn-decay-adv":
            self._decay_hours += 24.0
            self._render_decay()
        elif bid == "btn-decay-reset":
            self._decay_hours = 0.0
            self._render_decay()
        elif bid == "btn-graph-entity":
            self._add_graph_entity()
        elif bid == "btn-graph-rel":
            self._add_graph_relation()

    # ---- Sliding window logic ----

    def _add_next_turn(self) -> None:
        if self._turn_idx >= len(self._turns_data):
            self.notify("All turns added.", severity="warning")
            return
        user_msg, asst_msg = self._turns_data[self._turn_idx]
        self._sw.add_turn("user", user_msg)
        self._sw.add_turn("assistant", asst_msg)
        self._turn_idx += 1
        self._refresh_sliding()

    def _clear_sliding(self) -> None:
        self._sw.clear()
        self._turn_idx = 0
        self._refresh_sliding()

    def _refresh_sliding(self) -> None:
        tbl = self.query_one("#sw-table", DataTable)
        tbl.clear()
        for i, turn in enumerate(self._sw.turns, 1):
            content = turn.content[:60] + ("..." if len(turn.content) > 60 else "")
            tbl.add_row(str(i), turn.role, content, str(turn.token_count))
        status = self.query_one("#sw-status", Static)
        count = len(self._sw.turns)
        tokens = self._sw.total_tokens
        status.update(
            f"Turns: {count}  |  Tokens: {tokens} / {self._sw.max_tokens}"
        )

    # ---- Eviction logic ----

    def _fill_eviction(self) -> None:
        for mem in (self._fifo_sw, self._imp_sw, self._pair_sw):
            mem.clear()
        for user_msg, asst_msg in self._turns_data:
            for mem in (self._fifo_sw, self._imp_sw, self._pair_sw):
                mem.add_turn("user", user_msg)
                mem.add_turn("assistant", asst_msg)
        self._refresh_eviction()

    def _refresh_eviction(self) -> None:
        mapping = {
            "evict-fifo": self._fifo_sw,
            "evict-imp": self._imp_sw,
            "evict-pair": self._pair_sw,
        }
        for tid, mem in mapping.items():
            tbl = self.query_one(f"#{tid}", DataTable)
            tbl.clear()
            for i, turn in enumerate(mem.turns, 1):
                content = (
                    turn.content[:40]
                    + ("..." if len(turn.content) > 40 else "")
                )
                tbl.add_row(
                    str(i), turn.role, content, str(turn.token_count)
                )

    # ---- Decay logic ----

    def _render_decay(self) -> None:
        hours_label = self.query_one("#decay-hours", Static)
        hours_label.update(f"Time elapsed: {self._decay_hours:.0f} hours")

        eb_decay = EbbinghausDecay(base_strength=1.0, reinforcement_factor=0.5)
        lin_decay = LinearDecay(half_life_hours=168.0)

        now = datetime.now(timezone.utc)

        lines: list[str] = []
        lines.append("[b]Ebbinghaus vs Linear Decay over Time[/b]\n")
        lines.append(
            f"{'Hours':>6}  {'Ebbinghaus':>12}  {'Linear':>12}  "
            f"{'Ebbinghaus Bar':20}  {'Linear Bar':20}"
        )
        lines.append("-" * 80)

        for h in range(0, 337, 24):
            entry = MemoryEntry(
                id=f"e-{h}",
                content="test fact",
                relevance_score=0.8,
                access_count=1,
                last_accessed=now - timedelta(hours=h),
                created_at=now - timedelta(hours=h),
                tags=["test"],
                metadata={},
                source_turns=[],
                links=[],
            )

            eb_val = eb_decay.compute_retention(entry)
            lin_val = lin_decay.compute_retention(entry)

            # Highlight current position
            marker = " <--" if abs(h - self._decay_hours) < 12 else ""
            lines.append(
                f"{h:>6}  {eb_val:>12.4f}  {lin_val:>12.4f}  "
                f"{_bar(eb_val)}  {_bar(lin_val)}{marker}"
            )

        chart = self.query_one("#decay-chart", Static)
        chart.update("\n".join(lines))

    # ---- Graph logic ----

    def _seed_graph(self) -> None:
        entities = [
            "Sun", "Mercury", "Venus", "Earth", "Mars", "Jupiter",
        ]
        for e in entities:
            self._graph.add_entity(e)
        relations = [
            ("Mercury", "orbits", "Sun"),
            ("Venus", "orbits", "Sun"),
            ("Earth", "orbits", "Sun"),
            ("Mars", "orbits", "Sun"),
            ("Jupiter", "orbits", "Sun"),
            ("Earth", "has_moon", "Moon"),
        ]
        # Moon entity
        self._graph.add_entity("Moon")
        for src, rel, tgt in relations:
            self._graph.add_relationship(src, rel, tgt)
        self._graph_triples: list[tuple[str, str, str]] = list(relations)

    def _add_graph_entity(self) -> None:
        inp = self.query_one("#graph-entity", Input)
        name = inp.value.strip()
        if not name:
            self.notify("Enter an entity name.", severity="warning")
            return
        self._graph.add_entity(name)
        inp.value = ""
        self._refresh_graph()
        self.notify(f"Entity '{name}' added.")

    def _add_graph_relation(self) -> None:
        src = self.query_one("#graph-src", Input).value.strip()
        rel = self.query_one("#graph-rel", Input).value.strip()
        tgt = self.query_one("#graph-tgt", Input).value.strip()
        if not (src and rel and tgt):
            self.notify("Fill source, relation, and target.", severity="warning")
            return
        # Ensure entities exist
        self._graph.add_entity(src)
        self._graph.add_entity(tgt)
        self._graph.add_relationship(src, rel, tgt)
        self._graph_triples.append((src, rel, tgt))
        # Clear inputs
        for iid in ("graph-src", "graph-rel", "graph-tgt"):
            self.query_one(f"#{iid}", Input).value = ""
        self._refresh_graph()
        self.notify(f"Relation '{src} --{rel}--> {tgt}' added.")

    def _refresh_graph(self) -> None:
        # Rebuild tree
        tree = self.query_one("#graph-tree", Tree)
        tree.clear()
        tree.root.expand()

        # Build adjacency from triples
        adj: dict[str, list[tuple[str, str]]] = {}
        for src, rel, tgt in self._graph_triples:
            adj.setdefault(src, []).append((rel, tgt))

        shown: set[str] = set()
        for src, edges in sorted(adj.items()):
            node = tree.root.add(f"[b]{src}[/b]", expand=True)
            shown.add(src)
            for rel, tgt in edges:
                node.add_leaf(f"--{rel}--> {tgt}")
                shown.add(tgt)

        # Triples table
        tbl = self.query_one("#graph-triples", DataTable)
        tbl.clear()
        for src, rel, tgt in self._graph_triples:
            tbl.add_row(src, rel, tgt)
