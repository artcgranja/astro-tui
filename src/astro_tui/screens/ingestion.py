"""Ingestion screen — interactive chunker explorer.

Lets the user paste text, pick a chunking strategy, and see how the text
is split into chunks.  A "Compare All" mode runs every chunker on the
same input and shows a summary comparison.
"""

from __future__ import annotations

from typing import Any

from astro_context import (
    CodeChunker,
    FixedSizeChunker,
    ParentChildChunker,
    RecursiveCharacterChunker,
    SemanticChunker,
    SentenceChunker,
    TableAwareChunker,
    TiktokenCounter,
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
    RichLog,
    Select,
    TextArea,
)
from textual.worker import Worker, get_current_worker  # noqa: F401

from astro_tui.demo_data import (
    fake_embed_fn,
    sample_code,
    sample_markdown,
)

# ---- helpers ---------------------------------------------------------------

CHUNKER_TYPES: list[tuple[str, str]] = [
    ("Fixed", "Fixed"),
    ("Recursive", "Recursive"),
    ("Sentence", "Sentence"),
    ("Semantic", "Semantic"),
    ("Code", "Code"),
    ("Table", "Table"),
    ("ParentChild", "ParentChild"),
]

_counter = TiktokenCounter()


def _batch_embed(texts: list[str]) -> list[list[float]]:
    """Wrap the single-text fake_embed_fn for SemanticChunker."""
    return [fake_embed_fn(t) for t in texts]


def _build_chunker(
    name: str,
    chunk_size: int,
    overlap: int,
) -> Any:
    """Instantiate a chunker by its display name."""
    match name:
        case "Fixed":
            return FixedSizeChunker(
                chunk_size=chunk_size, overlap=overlap,
            )
        case "Recursive":
            return RecursiveCharacterChunker(
                chunk_size=chunk_size, overlap=overlap,
            )
        case "Sentence":
            return SentenceChunker(
                chunk_size=chunk_size, overlap=min(overlap, 3),
            )
        case "Semantic":
            return SemanticChunker(
                embed_fn=_batch_embed,
                chunk_size=chunk_size,
            )
        case "Code":
            return CodeChunker(
                language="python",
                chunk_size=chunk_size,
                overlap=overlap,
            )
        case "Table":
            return TableAwareChunker(chunk_size=chunk_size)
        case "ParentChild":
            return ParentChildChunker(
                parent_chunk_size=chunk_size,
                child_chunk_size=max(chunk_size // 4, 64),
                parent_overlap=overlap,
                child_overlap=max(overlap // 4, 10),
            )
        case _:
            return FixedSizeChunker(
                chunk_size=chunk_size, overlap=overlap,
            )


# ---- screen ----------------------------------------------------------------


class IngestionScreen(Screen):
    """Interactive chunker explorer for astro-context ingestion."""

    DEFAULT_CSS = """
    IngestionScreen {
        layout: vertical;
    }
    #ingestion-split {
        height: 1fr;
    }
    #left-pane {
        width: 50%;
        padding: 0 1;
    }
    #right-pane {
        width: 50%;
        border-left: solid $secondary;
        padding: 0 1;
    }
    #text-input {
        height: 1fr;
    }
    #chunk-table {
        height: 1fr;
    }
    #chunk-detail {
        height: 10;
        border-top: solid $secondary;
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
        width: 12;
        margin: 0 1;
    }
    .ctrl-row Select {
        width: 22;
        margin: 0 1;
    }
    .ctrl-row Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="ingestion-split"):
            with Vertical(id="left-pane"):
                yield Label("Input text")
                yield TextArea(
                    sample_markdown(),
                    id="text-input",
                )
                with Horizontal(classes="ctrl-row"):
                    yield Label("Chunker")
                    yield Select(
                        [(label, value) for label, value in CHUNKER_TYPES],
                        value="Fixed",
                        id="chunker-select",
                        allow_blank=False,
                    )
                with Horizontal(classes="ctrl-row"):
                    yield Label("Size")
                    yield Input(
                        value="512",
                        id="chunk-size",
                        type="integer",
                    )
                    yield Label("Overlap")
                    yield Input(
                        value="128",
                        id="overlap",
                        type="integer",
                    )
                with Horizontal(classes="ctrl-row"):
                    yield Button(
                        "Chunk!", id="btn-chunk", variant="primary",
                    )
                    yield Button(
                        "Compare All", id="btn-compare", variant="default",
                    )
            with Vertical(id="right-pane"):
                yield DataTable(id="chunk-table")
                yield RichLog(id="chunk-detail", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#chunk-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Idx", "Content", "Tokens")

    # ---- events ------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-chunk":
            self._run_single_chunker()
        elif event.button.id == "btn-compare":
            self._run_compare_all()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "chunker-select":
            ta = self.query_one("#text-input", TextArea)
            if event.value == "Code":
                ta.load_text(sample_code())
            else:
                # Only reset to markdown if the current text is the code
                current = ta.text
                if current.strip().startswith('"""Example module'):
                    ta.load_text(sample_markdown())

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected,
    ) -> None:
        table = self.query_one("#chunk-table", DataTable)
        log = self.query_one("#chunk-detail", RichLog)
        log.clear()
        row_idx = event.cursor_row
        try:
            row_data = table.get_row_at(row_idx)
        except Exception:
            return
        # row_data is (idx, content_truncated, tokens)
        # Show the full chunk from our cached list
        if hasattr(self, "_chunks") and row_idx < len(self._chunks):
            chunk_text = self._chunks[row_idx]
            log.write(f"[bold]Chunk {row_data[0]}[/bold]  "
                       f"({row_data[2]} tokens)")
            log.write(chunk_text)
        else:
            log.write(str(row_data[1]))

    # ---- chunking logic ----------------------------------------------------

    def _get_params(self) -> tuple[str, int, int]:
        text = self.query_one("#text-input", TextArea).text
        try:
            chunk_size = int(
                self.query_one("#chunk-size", Input).value,
            )
        except ValueError:
            chunk_size = 512
        try:
            overlap = int(
                self.query_one("#overlap", Input).value,
            )
        except ValueError:
            overlap = 128
        return text, max(chunk_size, 32), max(overlap, 0)

    def _run_single_chunker(self) -> None:
        text, chunk_size, overlap = self._get_params()
        chunker_name = self.query_one(
            "#chunker-select", Select,
        ).value
        if not isinstance(chunker_name, str):
            chunker_name = "Fixed"
        chunker = _build_chunker(chunker_name, chunk_size, overlap)
        chunks: list[str] = chunker.chunk(text)
        self._chunks = chunks

        table = self.query_one("#chunk-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Idx", "Content", "Tokens")
        for i, chunk in enumerate(chunks):
            tokens = _counter.count_tokens(chunk)
            preview = chunk.replace("\n", " ")[:80]
            table.add_row(str(i), preview, str(tokens))

        log = self.query_one("#chunk-detail", RichLog)
        log.clear()
        log.write(
            f"[bold]{chunker_name}[/bold]: "
            f"{len(chunks)} chunks from {len(text)} chars",
        )

    def _run_compare_all(self) -> None:
        text, chunk_size, overlap = self._get_params()

        table = self.query_one("#chunk-table", DataTable)
        table.clear(columns=True)
        table.add_columns(
            "Chunker", "Chunks", "Avg Tokens", "Min", "Max",
        )

        log = self.query_one("#chunk-detail", RichLog)
        log.clear()
        log.write("[bold]Comparing all chunkers...[/bold]")

        self._chunks = []

        for label, name in CHUNKER_TYPES:
            try:
                chunker = _build_chunker(name, chunk_size, overlap)
                chunks = chunker.chunk(text)
            except Exception as exc:
                table.add_row(label, "ERR", "-", "-", "-")
                log.write(f"[red]{label}: {exc}[/red]")
                continue

            if not chunks:
                table.add_row(label, "0", "0", "0", "0")
                continue

            token_counts = [
                _counter.count_tokens(c) for c in chunks
            ]
            avg_tok = sum(token_counts) // len(token_counts)
            min_tok = min(token_counts)
            max_tok = max(token_counts)
            table.add_row(
                label,
                str(len(chunks)),
                str(avg_tok),
                str(min_tok),
                str(max_tok),
            )
            log.write(
                f"  {label}: {len(chunks)} chunks, "
                f"avg={avg_tok} tokens",
            )
