"""Query transformation and classification screen."""

from __future__ import annotations

from astro_context import (
    CallbackClassifier,
    DecompositionTransformer,
    HyDETransformer,
    KeywordClassifier,
    MultiQueryTransformer,
    QueryBundle,
    QueryTransformPipeline,
    StepBackTransformer,
)
from textual.app import ComposeResult
from textual.containers import Horizontal
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

from astro_tui.demo_data import (
    fake_decompose_fn,
    fake_generate_fn,
    fake_multi_query_fn,
    fake_stepback_fn,
)

_TRUNC = 90


def _trunc(text: str, n: int = _TRUNC) -> str:
    return text[:n] + "..." if len(text) > n else text


# Pre-build transformers (cheap, no API key needed)
_hyde = HyDETransformer(generate_fn=fake_generate_fn)
_multi = MultiQueryTransformer(
    generate_fn=fake_multi_query_fn,
    num_queries=3,
)
_decomp = DecompositionTransformer(generate_fn=fake_decompose_fn)
_stepback = StepBackTransformer(generate_fn=fake_stepback_fn)

_TRANSFORMER_MAP: dict[str, HyDETransformer
    | MultiQueryTransformer
    | DecompositionTransformer
    | StepBackTransformer] = {
    "hyde": _hyde,
    "multi": _multi,
    "decomp": _decomp,
    "stepback": _stepback,
}


# ═══════════════════════════════════════════════════════════════════════════
# Screen
# ═══════════════════════════════════════════════════════════════════════════


class QueryScreen(Screen):
    """Interactive demo of query transformers and classifiers."""

    DEFAULT_CSS = """
    QueryScreen {
        layout: vertical;
    }
    .q-input-row {
        layout: horizontal;
        height: auto;
        padding: 1 0;
        align: left middle;
    }
    .q-input-row Input {
        width: 1fr;
        margin: 0 1;
    }
    .q-input-row Button {
        margin: 0 1;
    }
    .q-input-row Select {
        width: 30;
        margin: 0 1;
    }
    .q-result {
        height: auto;
        padding: 1;
        text-style: bold;
    }
    .q-pipeline-info {
        height: auto;
        padding: 1;
    }
    """

    # ── compose ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Transformers", id="tab-transformers"):
                yield from self._compose_transformers()
            with TabPane("Pipeline", id="tab-pipeline"):
                yield from self._compose_pipeline()
            with TabPane("Classifiers", id="tab-classifiers"):
                yield from self._compose_classifiers()
        yield Footer()

    # ── Tab 1: Transformers ────────────────────────────────────────────────

    def _compose_transformers(self) -> ComposeResult:
        with Horizontal(classes="q-input-row"):
            yield Input(
                placeholder="Enter a query to transform...",
                id="tr-query",
            )
            yield Select(
                [
                    ("HyDE", "hyde"),
                    ("MultiQuery", "multi"),
                    ("Decomposition", "decomp"),
                    ("StepBack", "stepback"),
                ],
                value="hyde",
                id="tr-select",
            )
            yield Button(
                "Transform", id="tr-go", variant="primary",
            )
        yield Label("Generated Queries:")
        yield DataTable(id="tr-table")

    # ── Tab 2: Pipeline ───────────────────────────────────────────────────

    def _compose_pipeline(self) -> ComposeResult:
        yield Static(
            "Pipeline: HyDE -> MultiQuery -> Decomposition\n"
            "Each transformer feeds its output into the next stage.",
            classes="q-pipeline-info",
        )
        with Horizontal(classes="q-input-row"):
            yield Input(
                placeholder="Enter a query for the pipeline...",
                id="pp-query",
            )
            yield Button(
                "Run Pipeline", id="pp-go", variant="primary",
            )
        yield Label("Pipeline Output:")
        yield DataTable(id="pp-table")

    # ── Tab 3: Classifiers ────────────────────────────────────────────────

    def _compose_classifiers(self) -> ComposeResult:
        yield Static(
            "Keyword rules:\n"
            "  planets   -> planet, mercury, venus, earth, mars, "
            "jupiter, saturn\n"
            "  stars     -> star, sun, neutron, supernova, pulsar\n"
            "  cosmology -> universe, big bang, dark matter, "
            "dark energy\n"
            "  tech      -> telescope, hubble, jwst, webb, ligo\n"
            "  default   -> general",
            classes="q-pipeline-info",
        )
        with Horizontal(classes="q-input-row"):
            yield Input(
                placeholder="Enter a query to classify...",
                id="cl-query",
            )
            yield Button(
                "Classify", id="cl-go", variant="primary",
            )
        yield Static("", id="cl-keyword-result", classes="q-result")
        yield Static("", id="cl-callback-result", classes="q-result")

    # ── on_mount ───────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        tr_table: DataTable = self.query_one("#tr-table", DataTable)
        tr_table.add_columns("#", "Type", "Query Text")

        pp_table: DataTable = self.query_one("#pp-table", DataTable)
        pp_table.add_columns("#", "Stage", "Query Text")

    # ── event handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "tr-go":
            self._do_transform()
        elif btn_id == "pp-go":
            self._do_pipeline()
        elif btn_id == "cl-go":
            self._do_classify()

    # ── Tab 1 logic ────────────────────────────────────────────────────────

    def _do_transform(self) -> None:
        query_text = self.query_one("#tr-query", Input).value.strip()
        if not query_text:
            query_text = (
                "What is the largest planet in our solar system?"
            )
        select: Select = self.query_one("#tr-select", Select)
        transformer_key = select.value
        transformer = _TRANSFORMER_MAP[str(transformer_key)]

        qb = QueryBundle(query_str=query_text)
        results = transformer.transform(qb)

        table: DataTable = self.query_one("#tr-table", DataTable)
        table.clear()
        type_label = {
            "hyde": "HyDE",
            "multi": "MultiQuery",
            "decomp": "Decomposition",
            "stepback": "StepBack",
        }.get(str(transformer_key), "?")

        for i, r in enumerate(results):
            table.add_row(
                str(i + 1),
                type_label,
                _trunc(r.query_str),
            )

    # ── Tab 2 logic ────────────────────────────────────────────────────────

    def _do_pipeline(self) -> None:
        query_text = self.query_one("#pp-query", Input).value.strip()
        if not query_text:
            query_text = (
                "How do black holes and neutron stars form?"
            )
        qb = QueryBundle(query_str=query_text)
        table: DataTable = self.query_one("#pp-table", DataTable)
        table.clear()

        # Show original
        table.add_row("0", "Original", _trunc(qb.query_str))

        # Stage 1: HyDE
        hyde_out = _hyde.transform(qb)
        for i, r in enumerate(hyde_out):
            table.add_row(str(i + 1), "HyDE", _trunc(r.query_str))

        # Stage 2: MultiQuery on first HyDE result
        if hyde_out:
            mq_out = _multi.transform(hyde_out[0])
            for i, r in enumerate(mq_out):
                table.add_row(
                    str(len(hyde_out) + i + 1),
                    "MultiQuery",
                    _trunc(r.query_str),
                )
        else:
            mq_out = []

        # Stage 3: full pipeline for comparison
        pipeline = QueryTransformPipeline(
            transformers=[_hyde, _multi, _decomp],
        )
        pipe_out = pipeline.transform(qb)
        for i, r in enumerate(pipe_out):
            table.add_row(
                str(len(hyde_out) + len(mq_out) + i + 1),
                "Pipeline",
                _trunc(r.query_str),
            )

    # ── Tab 3 logic ────────────────────────────────────────────────────────

    def _do_classify(self) -> None:
        query_text = self.query_one("#cl-query", Input).value.strip()
        if not query_text:
            query_text = "Tell me about the planet Jupiter"
        qb = QueryBundle(query_str=query_text)

        # Keyword classifier
        kw = KeywordClassifier(
            rules={
                "planets": [
                    "planet", "mercury", "venus", "earth",
                    "mars", "jupiter", "saturn",
                ],
                "stars": [
                    "star", "sun", "neutron", "supernova", "pulsar",
                ],
                "cosmology": [
                    "universe", "big bang", "dark matter", "dark energy",
                ],
                "tech": [
                    "telescope", "hubble", "jwst", "webb", "ligo",
                ],
            },
            default="general",
        )
        kw_category = kw.classify(qb)

        # Find which keywords matched
        query_lower = query_text.lower()
        matched = []
        for cat, keywords in kw.rules.items():
            for word in keywords:
                if word in query_lower:
                    matched.append(f"{word} -> {cat}")
        match_str = ", ".join(matched) if matched else "(none)"

        kw_label: Static = self.query_one(
            "#cl-keyword-result", Static,
        )
        kw_label.update(
            f"KeywordClassifier:  category = [{kw_category}]  |  "
            f"matched keywords: {match_str}"
        )

        # Callback classifier
        def _classify_cb(q: QueryBundle) -> str:
            ql = q.query_str.lower()
            if any(w in ql for w in ("planet", "mars", "jupiter")):
                return "planets"
            if any(w in ql for w in ("star", "sun", "neutron")):
                return "stars"
            if any(w in ql for w in ("universe", "dark")):
                return "cosmology"
            return "general"

        cb = CallbackClassifier(classify_fn=_classify_cb)
        cb_category = cb.classify(qb)

        cb_label: Static = self.query_one(
            "#cl-callback-result", Static,
        )
        cb_label.update(
            f"CallbackClassifier: category = [{cb_category}]"
        )
