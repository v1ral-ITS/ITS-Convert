from __future__ import annotations

from pathlib import Path
import json
import difflib

import typer
from rich import print
from rich.columns import Columns
from rich.panel import Panel
from rich.syntax import Syntax
from rich.console import Console

from itsconvert.analyzer import summarize_ir, inspect_rich, infer_types
from itsconvert.packagers import get_packager
from itsconvert.translators import get_emitter, get_parser, available_emitters, available_parsers
from itsconvert.utils import infer_language, read_text, write_text

app = typer.Typer(add_completion=False, help="Translate simple automation scripts between 25+ languages.")

_SUFFIX_MAP = {
    "py": ".py", "sh": ".sh", "ps1": ".ps1", "cmd": ".cmd",
    "js": ".js", "ts": ".ts", "rb": ".rb", "pl": ".pl",
    "lua": ".lua", "php": ".php", "go": ".go", "rs": ".rs",
    "java": ".java", "c": ".c", "cpp": ".cpp", "cs": ".cs",
    "swift": ".swift", "kt": ".kt", "dart": ".dart", "r": ".R",
    "scala": ".scala", "nim": ".nim", "zig": ".zig", "v": ".v",
}

_LANG_NAMES = {
    "py": "python", "sh": "bash", "ps1": "powershell", "cmd": "batch",
    "js": "javascript", "ts": "typescript", "rb": "ruby", "go": "go",
    "rs": "rust", "java": "java", "c": "c", "cpp": "cpp", "cs": "csharp",
    "kt": "kotlin", "swift": "swift", "dart": "dart", "lua": "lua",
    "nim": "nim", "zig": "zig",
}


@app.command()
def inspect(
    source: Path,
    tree: bool = typer.Option(False, "--tree", help="Show rich tree visualization"),
    types: bool = typer.Option(False, "--types", help="Show inferred variable types"),
) -> None:
    """Parse a script and display its IR summary."""
    lang = infer_language(source)
    parser = get_parser(lang)
    ir = parser.parse(read_text(source))
    if tree:
        inspect_rich(ir)
    else:
        print(summarize_ir(ir))
    if types:
        type_map = infer_types(ir)
        if type_map:
            print("\n[bold]Inferred variable types:[/bold]")
            for name, t in sorted(type_map.items()):
                print(f"  [cyan]{name}[/cyan]: [yellow]{t}[/yellow]")
    if not tree:
        print(json.dumps(ir.model_dump(), indent=2))


@app.command()
def translate(
    source: Path,
    to: str = typer.Option(..., "--to", help=f"Target language: {', '.join(available_emitters())}"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file"),
) -> None:
    """Translate a source script into another supported language."""
    from_lang = infer_language(source)
    parser = get_parser(from_lang)
    emitter = get_emitter(to)
    ir = parser.parse(read_text(source))
    rendered = emitter.emit(ir)

    if output is None:
        suffix = _SUFFIX_MAP.get(to, f".{to}")
        output = source.with_suffix(suffix)

    write_text(output, rendered)
    print(f"[green]Wrote[/green] {output}")


@app.command()
def diff(
    source: Path,
    to: str = typer.Option(..., "--to", help="Target language to translate into"),
) -> None:
    """Show a side-by-side view of the original source and its translation."""
    from_lang = infer_language(source)
    parser = get_parser(from_lang)
    emitter = get_emitter(to)
    ir = parser.parse(read_text(source))
    translated = emitter.emit(ir)
    original = read_text(source)

    console = Console()
    src_syntax = Syntax(original, _LANG_NAMES.get(from_lang, from_lang), line_numbers=True, theme="monokai")
    tgt_syntax = Syntax(translated, _LANG_NAMES.get(to, to), line_numbers=True, theme="monokai")
    console.print(
        Columns([
            Panel(src_syntax, title=f"[bold]Original ({from_lang})[/bold]"),
            Panel(tgt_syntax, title=f"[bold]Translated ({to})[/bold]"),
        ])
    )


@app.command()
def roundtrip(
    source: Path,
    via: str = typer.Option(..., "--via", help="Intermediate language to translate through"),
) -> None:
    """Translate source → via → source language and show diff to check fidelity."""
    from_lang = infer_language(source)
    original = read_text(source)

    # Forward: source → via
    fwd_parser = get_parser(from_lang)
    fwd_emitter = get_emitter(via)
    ir_fwd = fwd_parser.parse(original)
    intermediate = fwd_emitter.emit(ir_fwd)

    # Backward: via → source language
    bwd_parser = get_parser(via)
    bwd_emitter = get_emitter(from_lang)
    ir_bwd = bwd_parser.parse(intermediate)
    roundtripped = bwd_emitter.emit(ir_bwd)

    console = Console()
    diff_lines = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        roundtripped.splitlines(keepends=True),
        fromfile=f"original ({from_lang})",
        tofile=f"roundtripped ({from_lang} → {via} → {from_lang})",
    ))
    if not diff_lines:
        console.print("[green]✓ Perfect round-trip — no differences![/green]")
    else:
        diff_text = "".join(diff_lines)
        console.print(Panel(
            Syntax(diff_text, "diff", theme="monokai"),
            title=f"[bold]Round-trip diff ({from_lang} → {via} → {from_lang})[/bold]",
        ))
    console.print(f"\n[dim]Intermediate ({via}) confidence: {ir_fwd.confidence:.0%}  |  "
                  f"Back-parse confidence: {ir_bwd.confidence:.0%}[/dim]")


@app.command()
def languages() -> None:
    """List available parsers and emitters."""
    print(f"[bold]Parsers[/bold] (source languages): {', '.join(available_parsers())}")
    print(f"[bold]Emitters[/bold] (target languages): {', '.join(available_emitters())}")


@app.command()
def build(
    source: Path,
    builder: str = typer.Option(..., "--builder", help="pyinstaller, nuitka, ps2exe, shc, wrapper"),
    output_dir: Path = typer.Option(Path("dist"), "--output-dir", help="Build output directory"),
) -> None:
    """Package a translated or native script using a supported builder."""
    output_dir.mkdir(parents=True, exist_ok=True)
    packager = get_packager(builder)
    built = packager.build(source, output_dir)
    print(f"[green]Built[/green] {built}")


if __name__ == "__main__":
    app()
