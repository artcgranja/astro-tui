"""Catalog screen — class browser and protocol reference."""

from __future__ import annotations

import inspect

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Markdown,
    TabbedContent,
    TabPane,
    Tree,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_all_exports() -> dict[str, object]:
    """Import astro_context and return all __all__ exports."""
    import astro_context
    return {name: getattr(astro_context, name) for name in astro_context.__all__}


def _module_short(obj: object) -> str:
    """Return shortened module path for display."""
    mod = getattr(obj, "__module__", "")
    return mod.replace("astro_context.", "")


def _classify(obj: object) -> str:
    """Classify an export as class, protocol, function, or other."""
    if inspect.isfunction(obj):
        return "function"
    if inspect.isclass(obj):
        # Check if it's a Protocol (runtime_checkable or has _ProtocolMeta)
        meta = type(obj).__name__
        if "Protocol" in meta or "_ProtocolMeta" in meta:
            return "protocol"
        if issubclass(obj, Exception):
            return "exception"
        if issubclass(obj, type) and obj is not type:
            return "class"
        return "class"
    return "other"


def _get_signature_str(obj: object) -> str:
    """Get the constructor or function signature as a string."""
    try:
        if inspect.isclass(obj):
            sig = inspect.signature(obj.__init__)
            # Remove 'self' param
            params = list(sig.parameters.values())
            if params and params[0].name == "self":
                params = params[1:]
            return "(" + ", ".join(str(p) for p in params) + ")"
        elif inspect.isfunction(obj):
            return str(inspect.signature(obj))
    except (ValueError, TypeError):
        pass
    return "()"


def _get_methods(obj: object) -> list[tuple[str, str]]:
    """Return list of (name, signature) for public methods."""
    if not inspect.isclass(obj):
        return []
    methods: list[tuple[str, str]] = []
    for name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        try:
            sig = str(inspect.signature(method))
        except (ValueError, TypeError):
            sig = "(...)"
        methods.append((name, sig))
    return methods


# ---------------------------------------------------------------------------
# Catalog Screen
# ---------------------------------------------------------------------------


class CatalogScreen(Screen):
    """Browse all astro-context exports, docstrings, and protocols."""

    DEFAULT_CSS = """
    CatalogScreen {
        layout: vertical;
    }
    .browser-pane {
        layout: horizontal;
        height: 1fr;
    }
    .browser-tree {
        width: 35%;
        border-right: solid $secondary;
    }
    .browser-detail {
        width: 65%;
        padding: 0 1;
    }
    .filter-row {
        height: auto;
        padding: 1 0;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._exports: dict[str, object] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Class Browser", id="tab-browser"):
                yield from self._compose_browser()
            with TabPane("Protocols", id="tab-protocols"):
                yield from self._compose_protocols()
        yield Footer()

    def _compose_browser(self) -> ComposeResult:
        with Horizontal(classes="filter-row"):
            yield Input(
                placeholder="Filter by name...",
                id="browser-filter",
            )
        with Horizontal(classes="browser-pane"):
            yield Tree("astro_context", id="browser-tree", classes="browser-tree")
            yield Markdown(
                "Select a class or function from the tree.",
                id="browser-detail",
                classes="browser-detail",
            )

    def _compose_protocols(self) -> ComposeResult:
        yield DataTable(id="protocol-table")

    def on_mount(self) -> None:
        self._exports = _get_all_exports()
        self._build_tree()
        self._build_protocol_table()

    def _build_tree(self, filter_text: str = "") -> None:
        tree = self.query_one("#browser-tree", Tree)
        tree.clear()
        tree.root.expand()

        # Group by module
        modules: dict[str, list[tuple[str, object]]] = {}
        for name, obj in sorted(self._exports.items()):
            if filter_text and filter_text.lower() not in name.lower():
                continue
            mod = _module_short(obj)
            modules.setdefault(mod, []).append((name, obj))

        for mod, items in sorted(modules.items()):
            mod_node = tree.root.add(f"[b]{mod}[/b]", expand=False)
            for name, obj in items:
                kind = _classify(obj)
                if kind == "protocol":
                    label = f"[magenta]{name}[/magenta] (protocol)"
                elif kind == "function":
                    label = f"[yellow]{name}[/yellow] (fn)"
                elif kind == "exception":
                    label = f"[red]{name}[/red] (exception)"
                else:
                    label = f"[cyan]{name}[/cyan] (class)"
                mod_node.add_leaf(label, data=name)

    def _build_protocol_table(self) -> None:
        tbl = self.query_one("#protocol-table", DataTable)
        tbl.add_columns("Name", "Module", "Methods")

        for name, obj in sorted(self._exports.items()):
            if _classify(obj) != "protocol":
                continue
            mod = _module_short(obj)
            methods = _get_methods(obj)
            method_names = ", ".join(m[0] for m in methods)
            if not method_names:
                method_names = "(none)"
            tbl.add_row(name, mod, method_names)

    # ---- Events ----

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "browser-filter":
            self._build_tree(filter_text=event.value)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if node.data is None:
            return
        name = node.data
        obj = self._exports.get(name)
        if obj is None:
            return

        # Build markdown detail
        lines: list[str] = []
        lines.append(f"# {name}")
        lines.append("")

        kind = _classify(obj)
        mod = _module_short(obj)
        lines.append(f"**Type:** {kind}  ")
        lines.append(f"**Module:** `{mod}`  ")
        lines.append("")

        # Signature
        sig = _get_signature_str(obj)
        lines.append("## Signature")
        lines.append("")
        lines.append(f"```python\n{name}{sig}\n```")
        lines.append("")

        # Docstring
        doc = inspect.getdoc(obj)
        if doc:
            lines.append("## Documentation")
            lines.append("")
            lines.append(doc)
            lines.append("")

        # Methods
        if inspect.isclass(obj):
            methods = _get_methods(obj)
            if methods:
                lines.append("## Public Methods")
                lines.append("")
                for mname, msig in methods:
                    lines.append(f"- `{mname}{msig}`")
                lines.append("")

        # Fields (Pydantic models)
        if inspect.isclass(obj) and hasattr(obj, "model_fields"):
            fields = obj.model_fields
            if fields:
                lines.append("## Fields")
                lines.append("")
                lines.append("| Field | Type | Default |")
                lines.append("|-------|------|---------|")
                for fname, finfo in fields.items():
                    ftype = str(finfo.annotation).replace(
                        "typing.", ""
                    )
                    fdef = finfo.default
                    if str(fdef) == "PydanticUndefined":
                        fdef = "*required*"
                    lines.append(f"| `{fname}` | `{ftype}` | {fdef} |")
                lines.append("")

        detail = self.query_one("#browser-detail", Markdown)
        detail.update("\n".join(lines))
