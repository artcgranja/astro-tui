"""Retrieval strategies screen — Dense, Sparse, Hybrid, Reranking, Routing."""

from __future__ import annotations

from astro_context import (
    KeywordRouter,
    QueryBundle,
    RoundRobinReranker,
    RoutedRetriever,
    ScoreReranker,
    rrf_fuse,
)
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from astro_tui.demo_data import build_demo_retriever, fake_similarity_fn

# ── module-level singletons (built once) ──────────────────────────────────
_dense, _sparse = build_demo_retriever()

_TRUNC = 60  # max content chars shown in tables


def _trunc(text: str, n: int = _TRUNC) -> str:
    return text[:n] + "..." if len(text) > n else text


# ═══════════════════════════════════════════════════════════════════════════
# Screen
# ═══════════════════════════════════════════════════════════════════════════


class RetrievalScreen(Screen):
    """Interactive demo of retrieval strategies in astro-context."""

    DEFAULT_CSS = """
    RetrievalScreen {
        layout: vertical;
    }
    .ret-input-row {
        layout: horizontal;
        height: auto;
        padding: 1 0;
        align: left middle;
    }
    .ret-input-row Input {
        width: 1fr;
        margin: 0 1;
    }
    .ret-input-row Button {
        margin: 0 1;
    }
    .ret-tables {
        layout: horizontal;
        height: 1fr;
    }
    .ret-half {
        width: 1fr;
        padding: 0 1;
    }
    .ret-third {
        width: 1fr;
        padding: 0 1;
    }
    .ret-select-row {
        layout: horizontal;
        height: auto;
        padding: 1 0;
        align: left middle;
    }
    .ret-select-row Select {
        width: 30;
        margin: 0 1;
    }
    .ret-route-inputs {
        height: auto;
        padding: 1;
    }
    .ret-route-inputs Input {
        margin: 0 1 1 1;
    }
    .ret-route-result {
        height: auto;
        padding: 1;
        text-style: bold;
    }
    """

    # ── compose ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Dense vs Sparse", id="tab-dense-sparse"):
                yield from self._compose_dense_sparse()
            with TabPane("Hybrid + RRF", id="tab-rrf"):
                yield from self._compose_rrf()
            with TabPane("Reranking", id="tab-rerank"):
                yield from self._compose_rerank()
            with TabPane("Routing", id="tab-route"):
                yield from self._compose_routing()
        yield Footer()

    # ── Tab 1: Dense vs Sparse ─────────────────────────────────────────────

    def _compose_dense_sparse(self) -> ComposeResult:
        with Horizontal(classes="ret-input-row"):
            yield Input(
                placeholder="Enter a query...",
                id="ds-query",
            )
            yield Button("Search", id="ds-search", variant="primary")
        with Horizontal(classes="ret-tables"):
            with Vertical(classes="ret-half"):
                yield Label("Dense Results")
                yield DataTable(id="ds-dense-table")
            with Vertical(classes="ret-half"):
                yield Label("Sparse Results")
                yield DataTable(id="ds-sparse-table")

    # ── Tab 2: Hybrid + RRF ───────────────────────────────────────────────

    def _compose_rrf(self) -> ComposeResult:
        with Horizontal(classes="ret-input-row"):
            yield Input(
                placeholder="Enter a query...",
                id="rrf-query",
            )
            yield Button("Fuse", id="rrf-fuse", variant="primary")
        with Horizontal(classes="ret-tables"):
            with Vertical(classes="ret-third"):
                yield Label("Dense")
                yield DataTable(id="rrf-dense-table")
            with Vertical(classes="ret-third"):
                yield Label("Sparse")
                yield DataTable(id="rrf-sparse-table")
            with Vertical(classes="ret-third"):
                yield Label("Fused (RRF)")
                yield DataTable(id="rrf-fused-table")

    # ── Tab 3: Reranking ──────────────────────────────────────────────────

    def _compose_rerank(self) -> ComposeResult:
        with Horizontal(classes="ret-input-row"):
            yield Input(
                placeholder="Enter a query...",
                id="rr-query",
            )
            yield Select(
                [
                    ("ScoreReranker", "score"),
                    ("RoundRobinReranker", "roundrobin"),
                ],
                value="score",
                id="rr-select",
            )
            yield Button("Rerank", id="rr-go", variant="primary")
        with Horizontal(classes="ret-tables"):
            with Vertical(classes="ret-half"):
                yield Label("Before Reranking")
                yield DataTable(id="rr-before-table")
            with Vertical(classes="ret-half"):
                yield Label("After Reranking")
                yield DataTable(id="rr-after-table")

    # ── Tab 4: Routing ────────────────────────────────────────────────────

    def _compose_routing(self) -> ComposeResult:
        yield Static(
            "Pre-configured keyword routes:\n"
            "  planets -> planet, mercury, venus, earth, mars, "
            "jupiter, saturn\n"
            "  stars   -> star, sun, neutron, supernova, pulsar\n"
            "  cosmos  -> universe, big bang, dark matter, "
            "dark energy, expansion\n"
            "  default -> general (sparse retriever)",
            classes="ret-route-inputs",
        )
        with Horizontal(classes="ret-input-row"):
            yield Input(
                placeholder="Enter a query to route...",
                id="rt-query",
            )
            yield Button("Route & Retrieve", id="rt-go", variant="primary")
        yield Static("", id="rt-result", classes="ret-route-result")
        yield DataTable(id="rt-table")

    # ── on_mount: set up DataTable columns ─────────────────────────────────

    def on_mount(self) -> None:
        cols = ("Rank", "ID", "Content", "Score")
        table_ids = [
            "ds-dense-table",
            "ds-sparse-table",
            "rrf-dense-table",
            "rrf-sparse-table",
            "rrf-fused-table",
            "rr-before-table",
            "rr-after-table",
            "rt-table",
        ]
        for tid in table_ids:
            table: DataTable = self.query_one(f"#{tid}", DataTable)
            table.add_columns(*cols)

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _rows_from(items: list, start: int = 1) -> list[tuple]:
        return [
            (
                str(start + i),
                item.id,
                _trunc(item.content),
                f"{item.score:.4f}",
            )
            for i, item in enumerate(items)
        ]

    @staticmethod
    def _fill_table(table: DataTable, items: list) -> None:
        table.clear()
        for row in RetrievalScreen._rows_from(items):
            table.add_row(*row)

    # ── event handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "ds-search":
            self._do_dense_sparse()
        elif btn_id == "rrf-fuse":
            self._do_rrf()
        elif btn_id == "rr-go":
            self._do_rerank()
        elif btn_id == "rt-go":
            self._do_route()

    # ── Tab 1 logic ────────────────────────────────────────────────────────

    def _do_dense_sparse(self) -> None:
        query_text = self.query_one("#ds-query", Input).value.strip()
        if not query_text:
            query_text = "What is the largest planet?"
        qb = QueryBundle(query_str=query_text)
        dense_results = _dense.retrieve(qb, top_k=8)
        sparse_results = _sparse.retrieve(qb, top_k=8)
        self._fill_table(
            self.query_one("#ds-dense-table", DataTable),
            dense_results,
        )
        self._fill_table(
            self.query_one("#ds-sparse-table", DataTable),
            sparse_results,
        )

    # ── Tab 2 logic ────────────────────────────────────────────────────────

    def _do_rrf(self) -> None:
        query_text = self.query_one("#rrf-query", Input).value.strip()
        if not query_text:
            query_text = "Tell me about dark matter and black holes"
        qb = QueryBundle(query_str=query_text)
        dense_results = _dense.retrieve(qb, top_k=8)
        sparse_results = _sparse.retrieve(qb, top_k=8)
        fused = rrf_fuse(
            [dense_results, sparse_results],
            top_k=8,
        )
        self._fill_table(
            self.query_one("#rrf-dense-table", DataTable),
            dense_results,
        )
        self._fill_table(
            self.query_one("#rrf-sparse-table", DataTable),
            sparse_results,
        )
        self._fill_table(
            self.query_one("#rrf-fused-table", DataTable),
            fused,
        )

    # ── Tab 3 logic ────────────────────────────────────────────────────────

    def _do_rerank(self) -> None:
        query_text = self.query_one("#rr-query", Input).value.strip()
        if not query_text:
            query_text = "How do telescopes observe distant galaxies?"
        select: Select = self.query_one("#rr-select", Select)
        reranker_type = select.value
        qb = QueryBundle(query_str=query_text)
        original = _dense.retrieve(qb, top_k=8)

        if reranker_type == "score":
            reranker = ScoreReranker(
                score_fn=fake_similarity_fn,
                top_k=8,
            )
            reranked = reranker.process(original, query=qb)
        else:
            reranker = RoundRobinReranker(top_k=8)
            reranked = reranker.rerank(qb, original, top_k=8)

        self._fill_table(
            self.query_one("#rr-before-table", DataTable),
            original,
        )
        self._fill_table(
            self.query_one("#rr-after-table", DataTable),
            reranked,
        )

    # ── Tab 4 logic ────────────────────────────────────────────────────────

    def _do_route(self) -> None:
        query_text = self.query_one("#rt-query", Input).value.strip()
        if not query_text:
            query_text = "Tell me about planet Mars"

        router = KeywordRouter(
            routes={
                "planets": [
                    "planet", "mercury", "venus", "earth",
                    "mars", "jupiter", "saturn",
                ],
                "stars": [
                    "star", "sun", "neutron", "supernova", "pulsar",
                ],
                "cosmos": [
                    "universe", "big bang", "dark matter",
                    "dark energy", "expansion",
                ],
            },
            default="general",
        )
        routed = RoutedRetriever(
            router=router,
            retrievers={
                "planets": _dense,
                "stars": _sparse,
                "cosmos": _dense,
                "general": _sparse,
            },
        )

        qb = QueryBundle(query_str=query_text)
        route = router.route(qb)
        results = routed.retrieve(qb, top_k=8)

        label: Static = self.query_one("#rt-result", Static)
        label.update(
            f"Route selected: [{route}]  |  "
            f"Retriever: "
            f"{'Dense' if route in ('planets', 'cosmos') else 'Sparse'}"
        )
        self._fill_table(
            self.query_one("#rt-table", DataTable),
            results,
        )
