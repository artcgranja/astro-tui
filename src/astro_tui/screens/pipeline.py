"""Pipeline screen — build, execute, and visualise context pipelines.

Three tabs let the user assemble pipeline steps, run a query through
the pipeline, and inspect token-budget allocations across presets.
"""

from __future__ import annotations

from typing import Any

from astro_context import (
    AnthropicFormatter,
    ContextPipeline,
    GenericTextFormatter,
    OpenAIFormatter,
    ScoreReranker,
    default_agent_budget,
    default_chat_budget,
    default_rag_budget,
    filter_step,
    postprocessor_step,
    reranker_step,
    retriever_step,
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
    RichLog,
    Select,
    TabbedContent,
    TabPane,
)

from astro_tui.demo_data import (
    build_demo_retriever,
    fake_similarity_fn,
)

# ---- constants -------------------------------------------------------------

STEP_TYPES: list[tuple[str, str]] = [
    ("Retriever", "retriever"),
    ("Reranker", "reranker"),
    ("Filter", "filter"),
    ("Postprocessor", "postprocessor"),
]

FORMATTER_OPTS: list[tuple[str, str]] = [
    ("GenericText", "generic"),
    ("Anthropic", "anthropic"),
    ("OpenAI", "openai"),
]

BUDGET_PRESETS: list[tuple[str, str]] = [
    ("default_chat", "chat"),
    ("default_rag", "rag"),
    ("default_agent", "agent"),
]


# ---- helpers ---------------------------------------------------------------

def _make_bar(used: int, total: int, width: int = 30) -> str:
    """Render a simple text progress bar."""
    if total <= 0:
        return "[" + " " * width + "]"
    ratio = min(used / total, 1.0)
    filled = int(ratio * width)
    return (
        "["
        + "#" * filled
        + "-" * (width - filled)
        + f"] {used}/{total}"
    )


# ---- screen ----------------------------------------------------------------


class PipelineScreen(Screen):
    """Pipeline builder, executor and budget visualiser."""

    DEFAULT_CSS = """
    PipelineScreen {
        layout: vertical;
    }
    #pipeline-tabs {
        height: 1fr;
    }
    .ctrl-row {
        layout: horizontal;
        height: auto;
        padding: 1 0;
        align: left middle;
    }
    .ctrl-row Label {
        width: auto;
        padding: 0 1;
    }
    .ctrl-row Input {
        width: 1fr;
        margin: 0 1;
    }
    .ctrl-row Select {
        width: 28;
        margin: 0 1;
    }
    .ctrl-row Button {
        margin: 0 1;
    }
    #step-table {
        height: 1fr;
    }
    #exec-results {
        height: 1fr;
    }
    #exec-log {
        height: 10;
        border-top: solid $secondary;
    }
    #budget-log {
        height: 1fr;
    }
    #query-input {
        width: 1fr;
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._steps: list[dict[str, str]] = []
        # Pre-build demo retrievers once
        self._dense, self._sparse = build_demo_retriever()

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="pipeline-tabs"):
            with TabPane("Builder", id="tab-builder"):
                with Horizontal(classes="ctrl-row"):
                    yield Label("Type")
                    yield Select(
                        STEP_TYPES,
                        value="retriever",
                        id="step-type-select",
                        allow_blank=False,
                    )
                    yield Label("Name")
                    yield Input(
                        value="dense-retriever",
                        id="step-name",
                    )
                with Horizontal(classes="ctrl-row"):
                    yield Button(
                        "Add Step",
                        id="btn-add-step",
                        variant="primary",
                    )
                    yield Button(
                        "Remove Last",
                        id="btn-remove-step",
                        variant="error",
                    )
                yield DataTable(id="step-table")

            with TabPane("Execute", id="tab-execute"):
                with Horizontal(classes="ctrl-row"):
                    yield Label("Query")
                    yield Input(
                        value="What is the largest planet?",
                        id="query-input",
                    )
                with Horizontal(classes="ctrl-row"):
                    yield Label("Formatter")
                    yield Select(
                        FORMATTER_OPTS,
                        value="generic",
                        id="formatter-select",
                        allow_blank=False,
                    )
                    yield Button(
                        "Run Pipeline",
                        id="btn-run",
                        variant="primary",
                    )
                yield DataTable(id="exec-results")
                yield RichLog(id="exec-log", markup=True)

            with TabPane("Budget", id="tab-budget"):
                with Horizontal(classes="ctrl-row"):
                    yield Label("Preset")
                    yield Select(
                        BUDGET_PRESETS,
                        value="chat",
                        id="budget-select",
                        allow_blank=False,
                    )
                yield RichLog(id="budget-log", markup=True)
        yield Footer()

    # ---- mount -------------------------------------------------------------

    def on_mount(self) -> None:
        step_tbl = self.query_one("#step-table", DataTable)
        step_tbl.cursor_type = "row"
        step_tbl.add_columns("#", "Name", "Type")

        exec_tbl = self.query_one("#exec-results", DataTable)
        exec_tbl.cursor_type = "row"
        exec_tbl.add_columns(
            "#", "ID", "Source", "Score", "Tokens", "Content",
        )

        # Show initial budget
        self._show_budget("chat")

    # ---- events ------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-add-step":
                self._add_step()
            case "btn-remove-step":
                self._remove_step()
            case "btn-run":
                self._run_pipeline()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "budget-select" and isinstance(
            event.value, str,
        ):
            self._show_budget(event.value)

    # ---- builder tab -------------------------------------------------------

    def _add_step(self) -> None:
        step_type = self.query_one(
            "#step-type-select", Select,
        ).value
        step_name = self.query_one("#step-name", Input).value.strip()
        if not step_name:
            step_name = f"step-{len(self._steps)}"
        if not isinstance(step_type, str):
            step_type = "retriever"

        self._steps.append({"name": step_name, "type": step_type})
        self._refresh_step_table()

    def _remove_step(self) -> None:
        if self._steps:
            self._steps.pop()
            self._refresh_step_table()

    def _refresh_step_table(self) -> None:
        table = self.query_one("#step-table", DataTable)
        table.clear()
        for i, s in enumerate(self._steps):
            table.add_row(str(i + 1), s["name"], s["type"])

    # ---- execute tab -------------------------------------------------------

    def _build_pipeline_step(self, info: dict[str, str]) -> Any:
        """Convert a step dict into a real PipelineStep."""
        name = info["name"]
        match info["type"]:
            case "retriever":
                return retriever_step(name, self._dense, top_k=5)
            case "reranker":
                reranker = ScoreReranker(
                    score_fn=fake_similarity_fn, top_k=5,
                )
                return reranker_step(name, reranker, top_k=5)
            case "filter":
                return filter_step(
                    name,
                    predicate=lambda item: item.score >= 0.1,
                )
            case "postprocessor":
                return postprocessor_step(
                    name,
                    processor=_DemoPostProcessor(),
                )
            case _:
                return retriever_step(name, self._dense, top_k=5)

    def _run_pipeline(self) -> None:
        query = self.query_one("#query-input", Input).value.strip()
        if not query:
            query = "What is the largest planet?"

        fmt_choice = self.query_one(
            "#formatter-select", Select,
        ).value

        exec_log = self.query_one("#exec-log", RichLog)
        exec_log.clear()

        # Use configured steps, or a default retriever
        steps_to_use = list(self._steps)
        if not steps_to_use:
            steps_to_use = [
                {"name": "default-retriever", "type": "retriever"},
            ]

        pipe = ContextPipeline(max_tokens=4096)
        for info in steps_to_use:
            try:
                ps = self._build_pipeline_step(info)
                pipe.add_step(ps)
            except Exception as exc:
                exec_log.write(
                    f"[red]Error adding step "
                    f"'{info['name']}': {exc}[/red]",
                )
                return

        # Attach formatter
        match fmt_choice:
            case "anthropic":
                pipe.with_formatter(AnthropicFormatter())
            case "openai":
                pipe.with_formatter(OpenAIFormatter())
            case _:
                pipe.with_formatter(GenericTextFormatter())

        # Run
        try:
            result = pipe.build(query)
        except Exception as exc:
            exec_log.write(f"[red]Pipeline error: {exc}[/red]")
            return

        # Populate results table
        table = self.query_one("#exec-results", DataTable)
        table.clear()
        items = result.window.items if result.window else []
        for i, item in enumerate(items):
            preview = item.content.replace("\n", " ")[:60]
            table.add_row(
                str(i + 1),
                item.id[:12],
                item.source.value,
                f"{item.score:.3f}",
                str(item.token_count),
                preview,
            )

        # Log diagnostics
        diag = result.diagnostics or {}
        exec_log.write(
            f"[bold]Pipeline completed[/bold] in "
            f"{result.build_time_ms:.1f}ms",
        )
        exec_log.write(
            f"Items: {len(items)}, "
            f"format: {result.format_type}",
        )
        step_diags = diag.get("steps", [])
        for sd in step_diags:
            exec_log.write(
                f"  step '{sd['name']}': "
                f"{sd['items_after']} items, "
                f"{sd['time_ms']:.1f}ms",
            )

        # Show formatted output
        fmt_out = str(result.formatted_output)
        if fmt_out:
            exec_log.write("")
            exec_log.write("[bold]Formatted output:[/bold]")
            # Truncate to keep log readable
            if len(fmt_out) > 600:
                exec_log.write(fmt_out[:600] + "\n...")
            else:
                exec_log.write(fmt_out)

    # ---- budget tab --------------------------------------------------------

    def _show_budget(self, preset: str) -> None:
        log = self.query_one("#budget-log", RichLog)
        log.clear()

        max_tokens = 8192
        match preset:
            case "chat":
                budget = default_chat_budget(max_tokens)
            case "rag":
                budget = default_rag_budget(max_tokens)
            case "agent":
                budget = default_agent_budget(max_tokens)
            case _:
                budget = default_chat_budget(max_tokens)

        log.write(
            f"[bold]{preset}[/bold] budget "
            f"(total={budget.total_tokens}, "
            f"reserve={budget.reserve_tokens})",
        )
        log.write("")

        for alloc in budget.allocations:
            bar = _make_bar(alloc.max_tokens, max_tokens)
            log.write(
                f"  [bold]{alloc.source.value:<14}[/bold] "
                f"{bar}  "
                f"(priority={alloc.priority}, "
                f"overflow={alloc.overflow_strategy})",
            )

        alloc_total = sum(a.max_tokens for a in budget.allocations)
        log.write("")
        log.write(
            f"  Allocated: {alloc_total} / {max_tokens} "
            f"({alloc_total * 100 // max_tokens}%)",
        )
        log.write(
            f"  Reserved:  {budget.reserve_tokens} "
            f"({budget.reserve_tokens * 100 // max_tokens}%)",
        )


# ---- tiny helper classes ---------------------------------------------------


class _DemoPostProcessor:
    """Trivial postprocessor that adds a metadata tag to each item."""

    def process(
        self,
        items: list[Any],
        query: str,
    ) -> list[Any]:
        for item in items:
            item.metadata["postprocessed"] = True
        return items
