"""Evaluation screen — retrieval metrics, A/B testing, human eval."""

from __future__ import annotations

from astro_context import (
    ABTestResult,
    ABTestRunner,
    HumanEvaluationCollector,
    HumanJudgment,
    PipelineEvaluator,
    QueryBundle,
    RetrievalMetricsCalculator,
)
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Static,
    TabbedContent,
    TabPane,
)

from astro_tui.demo_data import (
    build_demo_retriever,
    build_evaluation_dataset,
    fake_embed_fn,
    sample_documents,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _color_bar(value: float, width: int = 25) -> str:
    """Render a colored bar for a 0..1 metric value."""
    filled = round(value * width)
    if value >= 0.8:
        color = "green"
    elif value >= 0.5:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]" + "\u2588" * filled + "[/]" + "\u2591" * (width - filled)


# ---------------------------------------------------------------------------
# Evaluation Screen
# ---------------------------------------------------------------------------


class EvaluationScreen(Screen):
    """Interactive evaluation metrics explorer."""

    DEFAULT_CSS = """
    EvaluationScreen {
        layout: vertical;
    }
    .eval-summary {
        height: auto;
        padding: 1;
        border: solid $primary;
        margin: 0 0 1 0;
    }
    .metric-row {
        height: auto;
        padding: 0 1;
    }
    .ab-result {
        height: auto;
        padding: 1;
        border: solid $accent;
        margin: 1 0;
    }
    .human-controls {
        height: auto;
        padding: 1 0;
    }
    .score-btn {
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._dataset = build_evaluation_dataset()
        self._dense, self._sparse = build_demo_retriever()
        self._calculator = RetrievalMetricsCalculator(k=5)
        self._evaluator = PipelineEvaluator(
            retrieval_calculator=self._calculator
        )
        self._human_collector = HumanEvaluationCollector()

        # Pre-built human eval items
        docs = sample_documents()
        self._human_items: list[dict[str, str]] = [
            {
                "query": "What is the largest planet?",
                "item_id": d["id"],
                "title": d["title"],
                "content": d["content"][:80],
            }
            for d in docs[:6]
        ]
        self._human_idx = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Retrieval Metrics", id="tab-ret-metrics"):
                yield from self._compose_retrieval()
            with TabPane("A/B Testing", id="tab-ab"):
                yield from self._compose_ab()
            with TabPane("Human Eval", id="tab-human"):
                yield from self._compose_human()
        yield Footer()

    # ---- Tab: Retrieval Metrics ----

    def _compose_retrieval(self) -> ComposeResult:
        with Horizontal(classes="button-row"):
            yield Button(
                "Run Evaluation", id="btn-run-eval", variant="primary"
            )
        yield Static("Press 'Run Evaluation' to compute metrics.", id="eval-info")
        yield DataTable(id="eval-table")

    # ---- Tab: A/B Testing ----

    def _compose_ab(self) -> ComposeResult:
        with Horizontal(classes="button-row"):
            yield Button(
                "Run A/B Test", id="btn-run-ab", variant="primary"
            )
        yield Static(
            "Compare Dense vs Sparse retrieval.", id="ab-info"
        )
        yield Static("", id="ab-result", classes="ab-result")
        yield DataTable(id="ab-table")

    # ---- Tab: Human Eval ----

    def _compose_human(self) -> ComposeResult:
        yield Static("", id="human-prompt", classes="eval-summary")
        with Horizontal(classes="human-controls"):
            yield Button("0 - Irrelevant", id="btn-h0", classes="score-btn")
            yield Button(
                "1 - Marginal", id="btn-h1", classes="score-btn"
            )
            yield Button(
                "2 - Relevant", id="btn-h2", classes="score-btn",
                variant="primary",
            )
            yield Button(
                "3 - Perfect", id="btn-h3", classes="score-btn",
                variant="success",
            )
        yield Static("", id="human-stats", classes="metric-row")
        yield DataTable(id="human-table")

    # ---- mount ----

    def on_mount(self) -> None:
        # Retrieval metrics table
        tbl = self.query_one("#eval-table", DataTable)
        tbl.add_columns(
            "Query", "P@k", "P@k Bar",
            "Recall", "Recall Bar", "MRR", "NDCG",
        )

        # A/B table
        ab_tbl = self.query_one("#ab-table", DataTable)
        ab_tbl.add_columns("Metric", "Dense (A)", "Sparse (B)", "Delta")

        # Human table
        h_tbl = self.query_one("#human-table", DataTable)
        h_tbl.add_columns("Query", "Item", "Relevance", "Annotator")

        # Show first human eval item
        self._show_human_item()

    # ---- Button handler ----

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-run-eval":
            self._run_evaluation()
        elif bid == "btn-run-ab":
            self._run_ab_test()
        elif bid and bid.startswith("btn-h"):
            score = int(bid[-1])
            self._record_human(score)

    # ---- Retrieval metrics logic ----

    def _run_evaluation(self) -> None:
        tbl = self.query_one("#eval-table", DataTable)
        tbl.clear()

        total_p = 0.0
        total_r = 0.0
        total_mrr = 0.0
        total_ndcg = 0.0
        n = len(self._dataset.samples)

        for sample in self._dataset.samples:
            query_bundle = QueryBundle(
                original=sample.query,
                embedding=fake_embed_fn(sample.query),
            )
            items = self._dense.retrieve(query_bundle, top_k=5)
            metrics = self._calculator.evaluate(items, sample.relevant_ids)

            query_short = (
                sample.query[:35]
                + ("..." if len(sample.query) > 35 else "")
            )
            tbl.add_row(
                query_short,
                f"{metrics.precision_at_k:.2f}",
                _color_bar(metrics.precision_at_k),
                f"{metrics.recall_at_k:.2f}",
                _color_bar(metrics.recall_at_k),
                f"{metrics.mrr:.2f}",
                f"{metrics.ndcg:.2f}",
            )

            total_p += metrics.precision_at_k
            total_r += metrics.recall_at_k
            total_mrr += metrics.mrr
            total_ndcg += metrics.ndcg

        avg_p = total_p / n if n else 0
        avg_r = total_r / n if n else 0
        avg_mrr = total_mrr / n if n else 0
        avg_ndcg = total_ndcg / n if n else 0

        info = self.query_one("#eval-info", Static)
        info.update(
            f"[b]Averages:[/b]  P@5={avg_p:.3f}  "
            f"Recall={avg_r:.3f}  MRR={avg_mrr:.3f}  "
            f"NDCG={avg_ndcg:.3f}  ({n} queries)"
        )

    # ---- A/B test logic ----

    def _run_ab_test(self) -> None:
        runner = ABTestRunner(
            evaluator=self._evaluator,
            dataset=self._dataset,
        )

        result: ABTestResult = runner.run(
            retriever_a=self._dense,
            retriever_b=self._sparse,
            k=5,
            significance_level=0.05,
        )

        # Summary
        summary = self.query_one("#ab-result", Static)
        winner = result.winner
        sig = "Yes" if result.is_significant else "No"
        summary.update(
            f"[b]Winner:[/b] {winner}  |  "
            f"[b]p-value:[/b] {result.p_value:.4f}  |  "
            f"[b]Significant:[/b] {sig}"
        )

        # Per-metric table
        tbl = self.query_one("#ab-table", DataTable)
        tbl.clear()
        for metric_name, detail in result.per_metric_comparison.items():
            val_a = detail.get("mean_a", detail.get("a", 0.0))
            val_b = detail.get("mean_b", detail.get("b", 0.0))
            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                delta = val_a - val_b
                tbl.add_row(
                    metric_name,
                    f"{val_a:.4f}",
                    f"{val_b:.4f}",
                    f"{delta:+.4f}",
                )
            else:
                tbl.add_row(metric_name, str(val_a), str(val_b), "--")

        info = self.query_one("#ab-info", Static)
        info.update(
            f"A/B test complete. Dense (A) vs Sparse (B) over "
            f"{len(self._dataset.samples)} queries."
        )

    # ---- Human eval logic ----

    def _show_human_item(self) -> None:
        prompt = self.query_one("#human-prompt", Static)
        if self._human_idx >= len(self._human_items):
            prompt.update("[b]All items scored.[/b] Review judgments below.")
            return
        item = self._human_items[self._human_idx]
        prompt.update(
            f"[b]Query:[/b] {item['query']}\n"
            f"[b]Document:[/b] {item['title']} ({item['item_id']})\n"
            f"[b]Content:[/b] {item['content']}...\n\n"
            f"Rate relevance 0-3:  "
            f"({self._human_idx + 1}/{len(self._human_items)})"
        )

    def _record_human(self, score: int) -> None:
        if self._human_idx >= len(self._human_items):
            self.notify("All items already scored.", severity="warning")
            return
        item = self._human_items[self._human_idx]
        judgment = HumanJudgment(
            query=item["query"],
            item_id=item["item_id"],
            relevance=score,
            annotator="demo-user",
            metadata={},
        )
        self._human_collector.add_judgment(judgment)
        self._human_idx += 1

        # Refresh table
        tbl = self.query_one("#human-table", DataTable)
        tbl.add_row(
            item["query"][:30],
            item["item_id"],
            str(score),
            "demo-user",
        )

        # Update stats
        metrics = self._human_collector.compute_metrics()
        stats = self.query_one("#human-stats", Static)
        parts = [f"{k}: {v:.2f}" for k, v in metrics.items()]
        stats.update("[b]Metrics:[/b]  " + "  |  ".join(parts))

        self._show_human_item()
