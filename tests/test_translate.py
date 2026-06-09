from itsconvert.translators.py_parser import PythonParser
from itsconvert.translators.sh_emitter import BashEmitter
from itsconvert.translators.ps1_emitter import PowerShellEmitter


def test_python_to_bash_contains_echo():
    src = 'name = "Ada"\nprint(name)\n'
    ir = PythonParser().parse(src)
    out = BashEmitter().emit(ir)
    assert "echo" in out


def test_python_to_powershell_contains_write_host():
    src = 'print("hello")\n'
    ir = PythonParser().parse(src)
    out = PowerShellEmitter().emit(ir)
    assert "Write-Host" in out
