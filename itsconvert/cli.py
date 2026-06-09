from __future__ import annotations

from pathlib import Path
import json

import typer
from rich import print

from itsconvert.analyzer import summarize_ir
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


@app.command()
def inspect(source: Path) -> None:
    """Parse a script and display its IR summary."""
    lang = infer_language(source)
    parser = get_parser(lang)
    ir = parser.parse(read_text(source))
    print(summarize_ir(ir))
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
