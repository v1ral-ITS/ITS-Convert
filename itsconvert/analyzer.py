from __future__ import annotations

from collections import Counter
from typing import Any

from itsconvert.ir import (
    ScriptIR, IRNode, Value,
    Assign, FunctionDef, For, ForRange, ForEnumerate, ForKeys, While,
    If, TryCatch, Switch, ClassDef, Lambda, WithBlock,
)


# ---------------------------------------------------------------------------
# Type-inference pass
# ---------------------------------------------------------------------------

def infer_types(ir: ScriptIR) -> dict[str, str]:
    """Walk IR nodes and infer simple types for assigned variables.

    Returns a mapping ``{var_name: type_str}`` where *type_str* is one of
    ``"int"``, ``"float"``, ``"str"``, ``"bool"``, ``"list"``, ``"dict"`` or
    ``"any"``.
    """
    type_map: dict[str, str] = {}
    _walk_nodes(ir.nodes, type_map)
    return type_map


def _infer_value_type(val: Value | None) -> str:
    if val is None:
        return "any"
    kind = val.kind
    if kind == "int":
        return "int"
    if kind == "float":
        return "float"
    if kind in ("string", "fstring"):
        return "str"
    if kind == "bool":
        return "bool"
    if kind in ("list",):
        return "list"
    if kind == "dict":
        return "dict"
    return "any"


def _walk_nodes(nodes: list[IRNode], type_map: dict[str, str]) -> None:
    for node in nodes:
        if isinstance(node, Assign):
            t = _infer_value_type(node.value)
            if t != "any":
                type_map[node.name] = t
        elif isinstance(node, FunctionDef):
            _walk_nodes(node.body, type_map)
        elif isinstance(node, If):
            _walk_nodes(node.then_body, type_map)
            for branch in (node.elif_branches or []):
                _walk_nodes(branch.body, type_map)
            _walk_nodes(node.else_body or [], type_map)
        elif isinstance(node, (For, ForRange, ForEnumerate, ForKeys, While)):
            _walk_nodes(node.body, type_map)
        elif isinstance(node, TryCatch):
            _walk_nodes(node.try_body, type_map)
            _walk_nodes(node.catch_body or [], type_map)
            _walk_nodes(node.finally_body or [], type_map)
        elif isinstance(node, Switch):
            for case in node.cases:
                _walk_nodes(case.body, type_map)
            _walk_nodes(node.default_body or [], type_map)
        elif isinstance(node, ClassDef):
            for method in node.methods:
                _walk_nodes(method.body, type_map)
        elif isinstance(node, WithBlock):
            _walk_nodes(node.body, type_map)


# ---------------------------------------------------------------------------
# IR summary helpers
# ---------------------------------------------------------------------------

def _count_nodes(nodes: list[IRNode], counter: Counter) -> None:  # type: ignore[type-arg]
    for node in nodes:
        counter[node.type] += 1
        # Recurse into compound nodes
        for attr in ("body", "then_body", "else_body", "try_body", "catch_body", "finally_body"):
            child = getattr(node, attr, None)
            if isinstance(child, list):
                _count_nodes(child, counter)
        if hasattr(node, "elif_branches"):
            for branch in (node.elif_branches or []):
                _count_nodes(branch.body, counter)
        if hasattr(node, "cases"):
            for case in (node.cases or []):
                _count_nodes(case.body, counter)


def summarize_ir(ir: ScriptIR) -> str:
    """Return a human-readable summary of a ScriptIR."""
    counter: Counter = Counter()  # type: ignore[type-arg]
    _count_nodes(ir.nodes, counter)

    lines = [
        f"Source language : {ir.source_language}",
        f"Total nodes     : {sum(counter.values())}",
        f"Confidence      : {ir.confidence:.0%}",
    ]

    if counter:
        lines.append("Node breakdown  :")
        for node_type, count in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  {node_type:<20} {count}")

    raw_count = counter.get("raw_block", 0) + counter.get("command", 0)
    if raw_count:
        lines.append(f"Opaque nodes    : {raw_count} (raw_block + command — may lose fidelity)")

    if ir.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {w}" for w in ir.warnings)

    return "\n".join(lines)


def inspect_rich(ir: ScriptIR) -> None:
    """Print a rich-formatted IR tree to the terminal (uses rich if available)."""
    try:
        from rich.tree import Tree
        from rich import print as rprint
    except ImportError:
        print(summarize_ir(ir))
        return

    root = Tree(f"[bold cyan]{ir.source_language}[/] IR  [dim]({len(ir.nodes)} top-level nodes, confidence {ir.confidence:.0%})[/]")
    _build_rich_tree(ir.nodes, root)
    if ir.warnings:
        w_branch = root.add("[yellow]⚠ Warnings[/]")
        for w in ir.warnings:
            w_branch.add(f"[yellow]{w}[/]")
    rprint(root)


def _node_label(node: IRNode) -> str:
    t = node.type
    if t == "assign":
        return f"[green]assign[/] [bold]{node.name}[/]"
    if t == "print":
        return "[blue]print[/]"
    if t == "if":
        return "[magenta]if[/]"
    if t == "for":
        return f"[magenta]for[/] [bold]{getattr(node, 'var', '')}[/]"
    if t == "for_range":
        return f"[magenta]for_range[/] [bold]{node.var}[/]"
    if t == "function_def":
        return f"[cyan]def[/] [bold]{node.name}[/]"
    if t == "class_def":
        return f"[cyan]class[/] [bold]{node.name}[/]"
    if t == "switch":
        return "[magenta]switch[/]"
    if t == "try_catch":
        return "[red]try_catch[/]"
    if t == "with_block":
        return "[cyan]with[/]"
    if t == "comment":
        return f"[dim]# {node.text[:50]}[/]"
    if t == "command":
        return f"[yellow]cmd[/] {node.command}"
    if t == "raw_block":
        return "[red]raw_block[/]"
    return f"[white]{t}[/]"


def _build_rich_tree(nodes: list[IRNode], parent: Any) -> None:
    for node in nodes:
        branch = parent.add(_node_label(node))
        for attr in ("body", "then_body"):
            child = getattr(node, attr, None)
            if isinstance(child, list) and child:
                sub = branch.add(f"[dim]{attr}[/]")
                _build_rich_tree(child, sub)
        if hasattr(node, "elif_branches"):
            for eb in (node.elif_branches or []):
                sub = branch.add("[dim]elif[/]")
                _build_rich_tree(eb.body, sub)
        else_body = getattr(node, "else_body", None)
        if isinstance(else_body, list) and else_body:
            sub = branch.add("[dim]else[/]")
            _build_rich_tree(else_body, sub)
        if hasattr(node, "cases"):
            for case in (node.cases or []):
                sub = branch.add(f"[dim]case {case.pattern.value}[/]")
                _build_rich_tree(case.body, sub)
        if hasattr(node, "methods"):
            for method in (node.methods or []):
                sub = branch.add(f"[dim]method {method.name}[/]")
                _build_rich_tree(method.body, sub)

