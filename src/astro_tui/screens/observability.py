"""Observability screen — tracing, cost tracking, metrics."""

from __future__ import annotations

from datetime import datetime, timezone

from astro_context import (
    CostSummary,
    CostTracker,
    InMemoryMetricsCollector,
    InMemorySpanExporter,
    MetricPoint,
    Span,
    SpanKind,
    Tracer,
    TraceRecord,
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
    Tree,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cost_bar(value: float, max_val: float, width: int = 30) -> str:
    """Render a proportional bar for cost values."""
    ratio = min(1.0, value / max_val) if max_val > 0 else 0
    filled = round(ratio * width)
    return "[cyan]" + "\u2588" * filled + "[/]" + "\u2591" * (width - filled)


def _dur(ms: float | None) -> str:
    """Format duration in ms."""
    if ms is None:
        return "--"
    return f"{ms:.1f}ms"


# ---------------------------------------------------------------------------
# Observability Screen
# ---------------------------------------------------------------------------


class ObservabilityScreen(Screen):
    """Interactive explorer for tracing, cost, and metrics."""

    DEFAULT_CSS = """
    ObservabilityScreen {
        layout: vertical;
    }
    .obs-summary {
        height: auto;
        padding: 1;
        border: solid $primary;
        margin: 0 0 1 0;
    }
    .cost-bars {
        height: auto;
        padding: 1;
        border: solid $accent;
        margin: 1 0;
    }
    .metrics-panel {
        height: auto;
        padding: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._tracer = Tracer()
        self._exporter = InMemorySpanExporter()
        self._cost_tracker = CostTracker()
        self._metrics = InMemoryMetricsCollector()

        # Pre-seed cost data
        self._seed_costs()
        self._seed_metrics()

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Trace Viewer", id="tab-trace"):
                yield from self._compose_trace()
            with TabPane("Cost", id="tab-cost"):
                yield from self._compose_cost()
            with TabPane("Metrics", id="tab-metrics"):
                yield from self._compose_metrics()
        yield Footer()

    # ---- Tab: Trace Viewer ----

    def _compose_trace(self) -> ComposeResult:
        with Horizontal(classes="button-row"):
            yield Button(
                "Run Demo Pipeline", id="btn-trace-run", variant="primary"
            )
            yield Button("Clear", id="btn-trace-clear", variant="error")
        yield Static(
            "Press 'Run Demo Pipeline' to generate a trace.",
            id="trace-info",
            classes="obs-summary",
        )
        yield Tree("Traces", id="trace-tree")

    # ---- Tab: Cost ----

    def _compose_cost(self) -> ComposeResult:
        yield Static("", id="cost-summary", classes="obs-summary")
        yield Static("", id="cost-bars", classes="cost-bars")
        yield DataTable(id="cost-table")

    # ---- Tab: Metrics ----

    def _compose_metrics(self) -> ComposeResult:
        with Horizontal(classes="button-row"):
            yield Button(
                "Record Sample", id="btn-metric-add", variant="primary"
            )
        yield Static("", id="metrics-summary", classes="obs-summary")
        yield DataTable(id="metrics-table")

    # ---- mount ----

    def on_mount(self) -> None:
        # Cost table
        ct = self.query_one("#cost-table", DataTable)
        ct.add_columns(
            "Operation", "Model", "In Tokens", "Out Tokens", "Cost (USD)"
        )

        # Metrics table
        mt = self.query_one("#metrics-table", DataTable)
        mt.add_columns("Name", "Value", "Timestamp", "Tags")

        # Render initial data
        self._refresh_cost()
        self._refresh_metrics()

        # Trace tree
        tree = self.query_one("#trace-tree", Tree)
        tree.root.expand()

    # ---- Button handler ----

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-trace-run":
            self._run_demo_trace()
        elif bid == "btn-trace-clear":
            self._clear_traces()
        elif bid == "btn-metric-add":
            self._add_sample_metric()

    # ---- Trace logic ----

    def _run_demo_trace(self) -> None:
        trace = self._tracer.start_trace(
            "demo-pipeline",
            attributes={"query": "What is the largest planet?"},
        )

        # Simulate pipeline steps
        steps = [
            ("query_transform", SpanKind.QUERY_TRANSFORM, 12.3),
            ("dense_retrieval", SpanKind.RETRIEVAL, 45.7),
            ("reranking", SpanKind.RERANKING, 23.1),
            ("formatting", SpanKind.FORMATTING, 5.4),
        ]

        root_span = self._tracer.start_span(
            trace.trace_id,
            "pipeline",
            SpanKind.PIPELINE,
            attributes={"steps": len(steps)},
        )

        child_spans: list[Span] = []
        for name, kind, dur in steps:
            span = self._tracer.start_span(
                trace.trace_id,
                name,
                kind,
                parent_span_id=root_span.span_id,
                attributes={"simulated_duration_ms": dur},
            )
            span = self._tracer.end_span(
                span, status="ok", attributes={"items_out": 5}
            )
            child_spans.append(span)

        root_span = self._tracer.end_span(root_span, status="ok")
        trace = self._tracer.end_trace(trace)

        # Export all spans
        all_spans = [root_span] + child_spans
        self._exporter.export(all_spans)

        self._refresh_traces(trace, root_span, child_spans)
        self.notify("Demo trace generated.")

    def _refresh_traces(
        self,
        trace: TraceRecord,
        root: Span,
        children: list[Span],
    ) -> None:
        tree = self.query_one("#trace-tree", Tree)

        trace_node = tree.root.add(
            f"[b]Trace:[/b] {trace.trace_id[:12]}...",
            expand=True,
        )

        root_label = (
            f"[cyan]{root.name}[/cyan]  "
            f"[{root.kind.value}]  "
            f"status={root.status}  "
            f"dur={_dur(root.duration_ms)}"
        )
        root_node = trace_node.add(root_label, expand=True)

        for span in children:
            attrs = span.attributes
            items = attrs.get("items_out", "?")
            child_label = (
                f"[yellow]{span.name}[/yellow]  "
                f"[{span.kind.value}]  "
                f"dur={_dur(span.duration_ms)}  "
                f"items={items}"
            )
            root_node.add_leaf(child_label)

        info = self.query_one("#trace-info", Static)
        exported = len(self._exporter.get_spans())
        info.update(
            f"[b]Total exported spans:[/b] {exported}  |  "
            f"Trace: {trace.trace_id[:16]}..."
        )

    def _clear_traces(self) -> None:
        self._exporter.clear()
        tree = self.query_one("#trace-tree", Tree)
        tree.clear()
        tree.root.expand()
        info = self.query_one("#trace-info", Static)
        info.update("Traces cleared.")

    # ---- Cost logic ----

    def _seed_costs(self) -> None:
        cost_data = [
            ("embedding", "text-embedding-3-small", 1500, 0, 0.00002, 0.0),
            ("embedding", "text-embedding-3-small", 800, 0, 0.00002, 0.0),
            ("reranking", "cohere-rerank-v3", 2000, 0, 0.00001, 0.0),
            ("generation", "gpt-4o-mini", 500, 200, 0.00015, 0.0006),
            ("generation", "gpt-4o", 800, 350, 0.005, 0.015),
            ("generation", "claude-3-haiku", 600, 180, 0.00025, 0.00125),
            ("summarization", "gpt-4o-mini", 1200, 400, 0.00015, 0.0006),
            ("query_transform", "gpt-4o-mini", 100, 50, 0.00015, 0.0006),
        ]
        for op, model, inp, out, cpi, cpo in cost_data:
            self._cost_tracker.record(
                operation=op,
                model=model,
                input_tokens=inp,
                output_tokens=out,
                cost_per_input_token=cpi,
                cost_per_output_token=cpo,
            )

    def _refresh_cost(self) -> None:
        summary: CostSummary = self._cost_tracker.summary()

        # Summary text
        info = self.query_one("#cost-summary", Static)
        info.update(
            f"[b]Total Cost:[/b] ${summary.total_cost_usd:.4f}  |  "
            f"[b]Input Tokens:[/b] {summary.total_input_tokens:,}  |  "
            f"[b]Output Tokens:[/b] {summary.total_output_tokens:,}  |  "
            f"[b]Entries:[/b] {len(summary.entries)}"
        )

        # Cost bars by model and operation
        lines: list[str] = ["[b]Cost by Model:[/b]"]
        max_model = max(summary.by_model.values()) if summary.by_model else 1
        for model, cost in sorted(
            summary.by_model.items(), key=lambda x: -x[1]
        ):
            lines.append(
                f"  {model:30s}  ${cost:.6f}  {_cost_bar(cost, max_model)}"
            )

        lines.append("")
        lines.append("[b]Cost by Operation:[/b]")
        max_op = (
            max(summary.by_operation.values()) if summary.by_operation else 1
        )
        for op, cost in sorted(
            summary.by_operation.items(), key=lambda x: -x[1]
        ):
            lines.append(
                f"  {op:30s}  ${cost:.6f}  {_cost_bar(cost, max_op)}"
            )

        bars = self.query_one("#cost-bars", Static)
        bars.update("\n".join(lines))

        # Entries table
        tbl = self.query_one("#cost-table", DataTable)
        tbl.clear()
        for entry in summary.entries:
            tbl.add_row(
                entry.operation,
                entry.model,
                str(entry.input_tokens),
                str(entry.output_tokens),
                f"${entry.cost_usd:.6f}",
            )

    # ---- Metrics logic ----

    def _seed_metrics(self) -> None:
        now = datetime.now(timezone.utc)
        metrics_data = [
            ("retrieval.latency_ms", 45.2, {"step": "dense"}),
            ("retrieval.latency_ms", 12.8, {"step": "sparse"}),
            ("retrieval.items_returned", 10.0, {"step": "dense"}),
            ("retrieval.items_returned", 8.0, {"step": "sparse"}),
            ("reranking.latency_ms", 23.1, {"model": "cohere"}),
            ("pipeline.total_ms", 86.5, {}),
            ("pipeline.total_ms", 92.3, {}),
            ("pipeline.total_ms", 78.1, {}),
            ("memory.tokens_used", 512.0, {}),
            ("memory.entries_count", 8.0, {}),
        ]
        for name, value, tags in metrics_data:
            self._metrics.record(
                MetricPoint(
                    name=name,
                    value=value,
                    timestamp=now,
                    tags=tags,
                )
            )

    def _refresh_metrics(self) -> None:
        tbl = self.query_one("#metrics-table", DataTable)
        tbl.clear()

        all_points = self._metrics.get_metrics()
        for pt in all_points:
            tags_str = ", ".join(f"{k}={v}" for k, v in pt.tags.items())
            tbl.add_row(
                pt.name,
                f"{pt.value:.2f}",
                pt.timestamp.strftime("%H:%M:%S"),
                tags_str,
            )

        # Summary for known metrics
        info = self.query_one("#metrics-summary", Static)
        parts: list[str] = []
        for name in ("pipeline.total_ms", "retrieval.latency_ms"):
            summary = self._metrics.get_summary(name)
            if summary:
                parts.append(
                    f"[b]{name}:[/b] "
                    f"count={summary.get('count', 0)}  "
                    f"mean={summary.get('mean', 0):.1f}  "
                    f"min={summary.get('min', 0):.1f}  "
                    f"max={summary.get('max', 0):.1f}"
                )
        info.update("\n".join(parts) if parts else "No summaries available.")

    def _add_sample_metric(self) -> None:
        import random

        now = datetime.now(timezone.utc)
        latency = random.uniform(30.0, 120.0)
        self._metrics.record(
            MetricPoint(
                name="pipeline.total_ms",
                value=latency,
                timestamp=now,
                tags={"source": "demo"},
            )
        )
        self._refresh_metrics()
        self.notify(f"Recorded pipeline.total_ms = {latency:.1f}")
