"""Behavioral checks for defects found in the October 2026 audit."""
import contextlib
import ast
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest
from typer.testing import CliRunner
from itsconvert.cli import app
from itsconvert.errors import PackagingError, UnsupportedConstructError
from itsconvert.translators import get_parser, get_emitter, available_emitters
from itsconvert.packagers import get_packager, available_packagers

def translate(source, target='py'):
    return get_emitter(target).emit(get_parser('py').parse(source))

def execute(source):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        exec(compile(source, '<regression>', 'exec'), {})
    return stream.getvalue()

@pytest.mark.parametrize('source', [
    'print(True and True and False)\n',
    'print(False or False or True)\n',
    'print((1 + 2) * 3)\n',
    'try:\n    raise ValueError("test")\nexcept Exception as e:\n    print(e)\n',
    'def add(a, b):\n    return a + b\nprint(add(2, 3))\n',
    'x = 4\nprint(f"value {x}")\n',
    'print("a", end="")\nprint("b")\n',
    'data = {"key": 3}\nprint(data["key"])\n',
])
def test_python_preserves_behavior(source):
    assert execute(translate(source)) == execute(source)

@pytest.mark.parametrize('source', ['print(2 in [1, 2])', 'if 2 not in [1]:\n    print("yes")'])
def test_membership_rejected_instead_of_changed(source):
    with pytest.raises(UnsupportedConstructError):
        translate(source)

@pytest.mark.parametrize('source, expected', [
    ('x = 1\nx = 2\nprint(x)', '2\n'),
    ('for i in range(0, 5, 2):\n    print(i)', '0\n2\n4\n'),
    ('for i in range(3, 0, -1):\n    print(i)', '3\n2\n1\n'),
    ('x = 2\nif x != None:\n    print("ok")', 'ok\n'),
    ('x = 2\nprint(f"hello {x}")', 'hello 2\n'),
])
def test_javascript_executes(tmp_path, source, expected):
    node = os.environ.get('AUDIT_NODE') or shutil.which('node')
    if not node:
        pytest.skip('Node.js is required for JavaScript execution tests')
    output = tmp_path / 'test.js'
    output.write_text(translate(source, 'js'), encoding='utf-8')
    run = subprocess.run([node, str(output)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    assert run.stdout == expected

def test_cli_preserves_source_and_existing_output(tmp_path):
    source = tmp_path / 'hello.py'
    original = 'print("hello")\n'
    source.write_text(original)
    runner = CliRunner()
    first = runner.invoke(app, ['translate', str(source), '--to', 'py'])
    assert first.exit_code == 0, first.output
    assert source.read_text() == original
    second = runner.invoke(app, ['translate', str(source), '--to', 'py'])
    assert second.exit_code != 0
    assert 'Output exists' in second.output

def test_registry_exposes_ten_adapters():
    assert len(available_packagers()) == 10
    for name in available_packagers():
        assert callable(get_packager(name).build)
    assert len(available_emitters()) == 26

def test_shell_wrapper_copies_source_and_uses_bash(tmp_path):
    source = tmp_path / 'hello.sh'
    source.write_text('echo hello\n')
    output = tmp_path / 'output'
    launcher = get_packager('wrapper').build(source, output)
    assert 'exec bash' in launcher.read_text()
    assert (output / source.name).read_text() == source.read_text()

def test_nuitka_interpolates_output_and_checks_artifact(tmp_path):
    source = tmp_path / 'hello.py'
    source.write_text('print("hello")')
    output = tmp_path / 'output'
    with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
        with pytest.raises(PackagingError, match='did not create'):
            get_packager('nuitka').build(source, output)
    command = run.call_args.args[0]
    assert command[0] == sys.executable
    assert f'--output-dir={output.resolve()}' in command

def test_cli_strict_rejects_unsupported_class(tmp_path):
    source = tmp_path / 'class.py'
    source.write_text('class Example:\n    pass\n')
    result = CliRunner().invoke(app, ['translate', str(source), '--to', 'js', '--strict'])
    assert result.exit_code != 0
    assert not source.with_suffix('.js').exists()

def test_appimage_entrypoint_uses_original_filename(tmp_path):
    source = tmp_path / 'private name.py'
    source.write_text('print("demo")')
    output = tmp_path / 'output'
    def fake_run(command, **kwargs):
        Path(kwargs['env']['OUTPUT']).touch()
        return subprocess.CompletedProcess(command, 0, '', '')
    with patch('shutil.which', return_value='/mock/appimagetool'), patch('subprocess.run', side_effect=fake_run):
        packager = get_packager('appimage')
        packager.use_linuxdeploy = False
        artifact = packager.build(source, output)
    assert artifact.exists()
    entrypoint = next(output.glob('AppDir-*/AppRun')).read_text()
    assert "'private name.py'" in entrypoint
    assert '$(basename "$SELF")' not in entrypoint


@pytest.mark.parametrize('builder, platform, extension', [
    ('cx_freeze', 'linux', ''), ('py2exe', 'win32', '.exe'), ('py2app', 'darwin', '.app'),
])
def test_generated_setup_is_valid_and_returns_artifact(tmp_path, builder, platform, extension):
    source = tmp_path / 'hello.py'
    source.write_text('print("hello")')
    output = tmp_path / 'bundle'
    def fake_run(command, **kwargs):
        ast.parse(Path(command[1]).read_text())
        target = output / 'dist' / ('hello' + extension)
        target.parent.mkdir(parents=True, exist_ok=True)
        if extension == '.app':
            target.mkdir()
        else:
            target.touch()
        return subprocess.CompletedProcess(command, 0, '', '')
    with patch('importlib.util.find_spec', return_value=object()), patch('sys.platform', platform), patch('subprocess.run', side_effect=fake_run):
        artifact = get_packager(builder).build(source, output)
    assert artifact.exists()
