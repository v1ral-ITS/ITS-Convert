from __future__ import annotations

from pathlib import Path
import json

import typer
from rich import print

from itsconvert.analyzer import summarize_ir
from itsconvert.packagers import get_packager, available_packagers
from itsconvert.errors import PackagingError, UnsupportedConstructError
from itsconvert.translators import get_emitter, get_parser, available_emitters, available_parsers
from itsconvert.utils import infer_language, read_text, write_text

app = typer.Typer(add_completion=False, help="ITS-Convert | ImPerial TeK. Solutions — translate, inspect, batch, and package automation scripts.")

_SUFFIX_MAP = {
    "py": ".py", "sh": ".sh", "ps1": ".ps1", "cmd": ".cmd",
    "js": ".js", "ts": ".ts", "rb": ".rb", "pl": ".pl",
    "lua": ".lua", "php": ".php", "go": ".go", "rs": ".rs",
    "java": ".java", "c": ".c", "cpp": ".cpp", "cs": ".cs",
    "swift": ".swift", "kt": ".kt", "dart": ".dart", "r": ".R",
    "scala": ".scala", "nim": ".nim", "zig": ".zig", "v": ".v",
    "jl": ".jl", "ex": ".exs",
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
    to: str = typer.Option(..., "--to", prompt="Target language (run languages to list choices)", envvar="ITSCONVERT_TARGET", help=f"Target language: {', '.join(available_emitters())}"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file"),
    force: bool = typer.Option(False, "--force", help="Allow replacing an existing output file"),
    strict: bool = typer.Option(False, "--strict", help="Reject parser warnings and unsupported output markers"),
) -> None:
    """Translate a source script into another supported language."""
    from_lang = infer_language(source)
    parser = get_parser(from_lang)
    emitter = get_emitter(to)
    ir = parser.parse(read_text(source))
    rendered = emitter.emit(ir)
    _check_translation(ir, rendered, strict)

    if output is None:
        suffix = _SUFFIX_MAP.get(to, f".{to}")
        output = source.with_suffix(suffix)
        if output.resolve() == source.resolve():
            output = source.with_name(f"{source.stem}.converted{suffix}")

    if output.resolve() == source.resolve():
        raise typer.BadParameter("Output must be different from the source file")
    if output.exists() and not force:
        raise typer.BadParameter("Output exists; choose another path or use --force")

    write_text(output, rendered)
    print(f"[green]Wrote[/green] {output}")


@app.command()
def languages() -> None:
    """List available parsers and emitters."""
    print(f"[bold]Parsers[/bold] (source languages): {', '.join(available_parsers())}")
    print(f"[bold]Emitters[/bold] (target languages): {', '.join(available_emitters())}")


def _check_translation(ir, rendered: str, strict: bool) -> None:
    warnings = list(ir.warnings)
    if any(marker in rendered for marker in ("FIXME:", "Unsupported IR node:", "raw (", "raw py:", "raw ps1:", "raw sh:", "raw cmd:")):
        warnings.append("Output contains untranslated or unsupported constructs; review it before running")
    for warning in warnings:
        print(f"[yellow]Warning:[/yellow] {warning}")
    if strict and warnings:
        raise typer.BadParameter("Strict translation rejected unsupported constructs")


@app.command()
def builders() -> None:
    """List registered packaging adapters (external tools may be required)."""
    print(', '.join(available_packagers()))


@app.command()
def batch(
    source: Path,
    to: list[str] = typer.Option(..., "--to", help="Repeat for each target language"),
    output_dir: Path = typer.Option(Path("build"), "--output-dir", "-d"),
    force: bool = typer.Option(False, "--force"),
    strict: bool = typer.Option(False, "--strict"),
) -> None:
    """Translate one source file into multiple target languages."""
    targets = list(dict.fromkeys(to))
    unknown = sorted(set(targets) - set(available_emitters()))
    if unknown:
        raise typer.BadParameter(f"Unsupported target(s): {', '.join(unknown)}", param_hint="--to")
    parser = get_parser(infer_language(source))
    ir = parser.parse(read_text(source))
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for target in targets:
        destination = output_dir / f"{source.stem}{_SUFFIX_MAP[target]}"
        if destination.resolve() == source.resolve():
            raise typer.BadParameter("Output must be different from the source file")
        if destination.exists() and not force:
            raise typer.BadParameter(f"Output exists: {destination}; use --force to replace")
        rendered = get_emitter(target).emit(ir)
        _check_translation(ir, rendered, strict)
        outputs.append((destination, rendered))
    for destination, rendered in outputs:
        write_text(destination, rendered)
        print(f"[green]Wrote[/green] {destination}")


@app.command()
def build(
    source: Path,
    builder: str = typer.Option(..., "--builder", prompt="Builder (run builders to list choices)", envvar="ITSCONVERT_BUILDER", help=", ".join(available_packagers())),
    output_dir: Path = typer.Option(Path("dist"), "--output-dir", envvar="ITSCONVERT_OUTPUT_DIR", help="Build output directory"),
    use_linuxdeploy: bool = typer.Option(True, "--use-linuxdeploy/--use-appimagetool", help="AppImage backend"),
) -> None:
    """Package a translated or native script using a supported builder."""
    if not source.is_file():
        raise typer.BadParameter(f"Source file does not exist: {source}")
    suffixes = {"shc": {".sh", ".bash"}, "ps2exe": {".ps1"}, "wrapper": {".py", ".ps1", ".sh", ".bash"}}
    if builder != "appimage" and source.suffix.lower() not in suffixes.get(builder, {".py"}):
        raise typer.BadParameter(f"Builder {builder} does not support {source.suffix} input")
    output_dir.mkdir(parents=True, exist_ok=True)
    packager = get_packager(builder)
    if builder == "appimage":
        packager.use_linuxdeploy = use_linuxdeploy
    try:
        built = packager.build(source.resolve(), output_dir.resolve())
    except (PackagingError, OSError) as error:
        print(f"[red]Build failed:[/red] {error}")
        raise typer.Exit(1) from error
    if not built.exists():
        raise typer.BadParameter(f"Builder returned a missing artifact: {built}")
    print(f"[green]Built[/green] {built}")


if __name__ == "__main__":
    app()
