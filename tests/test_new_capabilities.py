from pathlib import Path

from typer.testing import CliRunner

from itsconvert.cli import app
from itsconvert.ir import Assign, Condition, If, Print, ScriptIR, Value
from itsconvert.translators import available_emitters, get_emitter
from itsconvert.utils import infer_language


def sample_ir() -> ScriptIR:
    return ScriptIR(source_language="py", nodes=[
        Assign(name="name", value=Value(kind="string", value="Bear")),
        If(
            condition=Condition(left=Value(kind="var", value="name"), op="!=", right=Value(kind="null")),
            then_body=[Print(values=[Value(kind="string", value="Hello"), Value(kind="var", value="name")])],
        ),
    ])


def test_new_emitters_are_registered():
    assert {"jl", "ex"}.issubset(available_emitters())


def test_julia_emitter_produces_native_control_flow():
    output = get_emitter("jl").emit(sample_ir())
    assert 'name = "Bear"' in output
    assert "if name != nothing" in output
    assert "println(" in output
    assert output.rstrip().endswith("end")


def test_elixir_emitter_produces_native_control_flow():
    output = get_emitter("ex").emit(sample_ir())
    assert 'name = "Bear"' in output
    assert "if name != nil do" in output
    assert "IO.puts(" in output
    assert output.rstrip().endswith("end")


def test_infer_new_language_extensions():
    assert infer_language(Path("tool.jl")) == "jl"
    assert infer_language(Path("tool.exs")) == "ex"


def test_batch_translates_once_to_multiple_targets(tmp_path):
    source = tmp_path / "hello.py"
    source.write_text('name = "Bear"\nprint(name)\n', encoding="utf-8")
    output_dir = tmp_path / "generated"
    result = CliRunner().invoke(app, [
        "batch", str(source), "--to", "jl", "--to", "ex", "--output-dir", str(output_dir)
    ])
    assert result.exit_code == 0, result.output
    assert (output_dir / "hello.jl").is_file()
    assert (output_dir / "hello.exs").is_file()


def test_batch_rejects_unknown_target(tmp_path):
    source = tmp_path / "hello.py"
    source.write_text('print("hello")\n', encoding="utf-8")
    result = CliRunner().invoke(app, ["batch", str(source), "--to", "made-up"])
    assert result.exit_code != 0
    assert "Unsupported target" in result.output
