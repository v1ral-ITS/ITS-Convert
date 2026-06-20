"""Tests for itsconvert — round-trip and unit tests."""
import pytest
from pathlib import Path

from itsconvert.ir import ScriptIR, Assign, Print, Input, If, ForRange, While, FunctionDef, Exit, Value, Condition
from itsconvert.translators.py_parser import PythonParser
from itsconvert.translators.sh_emitter import BashEmitter
from itsconvert.translators.ps1_emitter import PowerShellEmitter
from itsconvert.translators.cmd_emitter import CMDEmitter
from itsconvert.translators.py_emitter import PyEmitter
from itsconvert.translators.sh_parser import BashParser
from itsconvert.translators.ps1_parser import PS1Parser
from itsconvert.utils import infer_language


EXAMPLES = Path(__file__).parent.parent / "examples"


# --- Python Parser Tests ---

class TestPythonParser:
    def setup_method(self):
        self.parser = PythonParser()

    def test_simple_assign(self):
        ir = self.parser.parse('x = 42\n')
        assert len(ir.nodes) == 1
        node = ir.nodes[0]
        assert isinstance(node, Assign)
        assert node.name == "x"
        assert node.value.kind == "int"
        assert node.value.value == 42

    def test_string_assign(self):
        ir = self.parser.parse('name = "hello"\n')
        assert ir.nodes[0].name == "name"
        assert ir.nodes[0].value.kind == "string"

    def test_print(self):
        ir = self.parser.parse('print("hello")\n')
        assert ir.nodes[0].type == "print"

    def test_input(self):
        ir = self.parser.parse('x = input("prompt")\n')
        assert ir.nodes[0].type == "input"
        assert ir.nodes[0].name == "x"
        assert ir.nodes[0].prompt == "prompt"

    def test_if_else(self):
        ir = self.parser.parse('if x > 5:\n    print("big")\nelse:\n    print("small")\n')
        node = ir.nodes[0]
        assert isinstance(node, If)
        assert len(node.then_body) == 1
        assert len(node.else_body) == 1

    def test_for_range(self):
        ir = self.parser.parse('for i in range(10):\n    print(i)\n')
        node = ir.nodes[0]
        assert isinstance(node, ForRange)
        assert node.var == "i"

    def test_while(self):
        ir = self.parser.parse('while x < 5:\n    x += 1\n')
        node = ir.nodes[0]
        assert isinstance(node, While)

    def test_function_def(self):
        ir = self.parser.parse('def greet(name):\n    print(name)\n')
        node = ir.nodes[0]
        assert isinstance(node, FunctionDef)
        assert node.name == "greet"
        assert len(node.params) == 1

    def test_exit(self):
        ir = self.parser.parse('import sys\nsys.exit(1)\n')
        # should find an Exit node
        exits = [n for n in ir.nodes if n.type == "exit"]
        assert len(exits) == 1
        assert exits[0].code == 1

    def test_try_catch(self):
        ir = self.parser.parse('try:\n    x = 1\nexcept Exception as e:\n    print(e)\n')
        node = ir.nodes[0]
        assert node.type == "try_catch"

    def test_fstring(self):
        ir = self.parser.parse('name = f"hello {x}"\n')
        node = ir.nodes[0]
        assert isinstance(node, Assign)

    def test_demo_file(self):
        source = (EXAMPLES / "demo.py").read_text()
        ir = self.parser.parse(source)
        assert len(ir.nodes) > 10  # should parse many nodes


# --- Emitter Tests ---

class TestBashEmitter:
    def setup_method(self):
        self.emitter = BashEmitter()

    def test_simple_assign(self):
        ir = ScriptIR(source_language="py", nodes=[Assign(name="x", value=Value(kind="int", value=42))])
        result = self.emitter.emit(ir)
        assert "x=" in result

    def test_print(self):
        ir = ScriptIR(source_language="py", nodes=[Print(values=[Value(kind="string", value="hello")])])
        result = self.emitter.emit(ir)
        assert "echo" in result

    def test_if(self):
        ir = ScriptIR(source_language="py", nodes=[
            If(condition=Condition(left=Value(kind="var", value="x"), op=">", right=Value(kind="int", value=5)),
               then_body=[Print(values=[Value(kind="string", value="big")])],
               else_body=[Print(values=[Value(kind="string", value="small")])])
        ])
        result = self.emitter.emit(ir)
        assert "if" in result
        assert "fi" in result


class TestPS1Emitter:
    def setup_method(self):
        self.emitter = PowerShellEmitter()

    def test_assign(self):
        ir = ScriptIR(source_language="py", nodes=[Assign(name="x", value=Value(kind="string", value="hello"))])
        result = self.emitter.emit(ir)
        assert "$x" in result

    def test_print(self):
        ir = ScriptIR(source_language="py", nodes=[Print(values=[Value(kind="string", value="hello")])])
        result = self.emitter.emit(ir)
        assert "Write-Host" in result


class TestCMDEmitter:
    def setup_method(self):
        self.emitter = CMDEmitter()

    def test_assign(self):
        ir = ScriptIR(source_language="py", nodes=[Assign(name="x", value=Value(kind="string", value="hello"))])
        result = self.emitter.emit(ir)
        assert "set" in result

    def test_print(self):
        ir = ScriptIR(source_language="py", nodes=[Print(values=[Value(kind="string", value="hello")])])
        result = self.emitter.emit(ir)
        assert "echo" in result


class TestPyEmitter:
    def setup_method(self):
        self.emitter = PyEmitter()

    def test_roundtrip(self):
        ir = ScriptIR(source_language="py", nodes=[
            Assign(name="x", value=Value(kind="int", value=42)),
            Print(values=[Value(kind="string", value="hello")]),
        ])
        result = self.emitter.emit(ir)
        assert "x = 42" in result
        assert "print" in result


# --- Round-trip Tests ---

class TestRoundTrip:
    """Parse Python → IR → emit to target language."""

    def test_py_to_sh(self):
        source = 'print("hello")\n'
        ir = PythonParser().parse(source)
        result = BashEmitter().emit(ir)
        assert "echo" in result

    def test_py_to_ps1(self):
        source = 'print("hello")\n'
        ir = PythonParser().parse(source)
        result = PowerShellEmitter().emit(ir)
        assert "Write-Host" in result

    def test_py_to_cmd(self):
        source = 'print("hello")\n'
        ir = PythonParser().parse(source)
        result = CMDEmitter().emit(ir)
        assert "echo" in result

    def test_demo_py_to_sh(self):
        source = (EXAMPLES / "demo.py").read_text()
        ir = PythonParser().parse(source)
        result = BashEmitter().emit(ir)
        assert "#!/usr/bin/env bash" in result
        assert "echo" in result

    def test_demo_py_to_ps1(self):
        source = (EXAMPLES / "demo.py").read_text()
        ir = PythonParser().parse(source)
        result = PowerShellEmitter().emit(ir)
        assert "Write-Host" in result

    def test_demo_py_to_cmd(self):
        source = (EXAMPLES / "demo.py").read_text()
        ir = PythonParser().parse(source)
        result = CMDEmitter().emit(ir)
        assert "@echo off" in result


# --- Utility Tests ---

class TestUtils:
    def test_infer_language(self):
        assert infer_language(Path("test.py")) == "py"
        assert infer_language(Path("test.sh")) == "sh"
        assert infer_language(Path("test.ps1")) == "ps1"
        assert infer_language(Path("test.cmd")) == "cmd"
        assert infer_language(Path("test.bat")) == "cmd"


# --- Bash Parser Tests ---

class TestBashParser:
    def setup_method(self):
        self.parser = BashParser()

    def test_simple_echo(self):
        ir = self.parser.parse('echo "hello"\n')
        assert ir.nodes[0].type == "print"

    def test_variable(self):
        ir = self.parser.parse('name="World"\n')
        assert ir.nodes[0].type == "assign"


# --- PS1 Parser Tests ---

class TestPS1Parser:
    def setup_method(self):
        self.parser = PS1Parser()

    def test_write_host(self):
        ir = self.parser.parse('Write-Host "hello"\n')
        assert ir.nodes[0].type == "print"

    def test_variable(self):
        ir = self.parser.parse('$name = "World"\n')
        assert ir.nodes[0].type == "assign"


# --- All-Emitters Batch Tests ---

class TestAllEmitters:
    """Parse demo.py → IR → emit to every supported language."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from itsconvert.translators import available_emitters, get_emitter
        self.source = (EXAMPLES / "demo.py").read_text()
        self.ir = PythonParser().parse(self.source)
        self.emitters = {lang: get_emitter(lang) for lang in available_emitters()}

    def test_js_emitter(self):
        result = self.emitters["js"].emit(self.ir)
        assert "console.log" in result
        assert "function" in result

    def test_ts_emitter(self):
        result = self.emitters["ts"].emit(self.ir)
        assert "console.log" in result

    def test_rb_emitter(self):
        result = self.emitters["rb"].emit(self.ir)
        assert "puts" in result

    def test_pl_emitter(self):
        result = self.emitters["pl"].emit(self.ir)
        assert "print" in result
        assert "use strict" in result

    def test_lua_emitter(self):
        result = self.emitters["lua"].emit(self.ir)
        assert "print(" in result

    def test_php_emitter(self):
        result = self.emitters["php"].emit(self.ir)
        assert "<?php" in result
        assert "echo" in result

    def test_go_emitter(self):
        result = self.emitters["go"].emit(self.ir)
        assert "package main" in result
        assert "fmt.Println" in result

    def test_rs_emitter(self):
        result = self.emitters["rs"].emit(self.ir)
        assert "fn main()" in result
        assert "println!" in result

    def test_java_emitter(self):
        result = self.emitters["java"].emit(self.ir)
        assert "public class Main" in result
        assert "System.out.println" in result

    def test_c_emitter(self):
        result = self.emitters["c"].emit(self.ir)
        assert "#include <stdio.h>" in result
        assert "printf" in result

    def test_cpp_emitter(self):
        result = self.emitters["cpp"].emit(self.ir)
        assert "#include <iostream>" in result
        assert "cout" in result

    def test_cs_emitter(self):
        result = self.emitters["cs"].emit(self.ir)
        assert "Console.WriteLine" in result

    def test_swift_emitter(self):
        result = self.emitters["swift"].emit(self.ir)
        assert "import Foundation" in result
        assert "print(" in result

    def test_kt_emitter(self):
        result = self.emitters["kt"].emit(self.ir)
        assert "fun main" in result
        assert "println" in result

    def test_dart_emitter(self):
        result = self.emitters["dart"].emit(self.ir)
        assert "import 'dart:io'" in result
        assert "print(" in result

    def test_r_emitter(self):
        result = self.emitters["r"].emit(self.ir)
        assert "cat(" in result

    def test_scala_emitter(self):
        result = self.emitters["scala"].emit(self.ir)
        assert "object Main" in result
        assert "println" in result

    def test_nim_emitter(self):
        result = self.emitters["nim"].emit(self.ir)
        assert "echo" in result

    def test_zig_emitter(self):
        result = self.emitters["zig"].emit(self.ir)
        assert 'const std = @import("std")' in result
        assert "pub fn main" in result

    def test_v_emitter(self):
        result = self.emitters["v"].emit(self.ir)
        assert "module main" in result
        assert "fn main()" in result

    def test_all_emitters_produce_output(self):
        for lang, emitter in self.emitters.items():
            result = emitter.emit(self.ir)
            assert len(result) > 10, f"{lang} emitter produced no output"


# --- Utility Extension Tests ---

class TestUtilsExtended:
    def test_infer_new_languages(self):
        assert infer_language(Path("test.js")) == "js"
        assert infer_language(Path("test.ts")) == "ts"
        assert infer_language(Path("test.rb")) == "rb"
        assert infer_language(Path("test.go")) == "go"
        assert infer_language(Path("test.rs")) == "rs"
        assert infer_language(Path("test.java")) == "java"
        assert infer_language(Path("test.swift")) == "swift"
        assert infer_language(Path("test.kt")) == "kt"
        assert infer_language(Path("test.dart")) == "dart"
        assert infer_language(Path("test.nim")) == "nim"
        assert infer_language(Path("test.zig")) == "zig"


# --- Tar Extract Snippet Tests (blinksh/snippets) ---

class TestTarExtractSnippet:
    """Tests for the tar extract snippet from https://github.com/blinksh/snippets/blob/main/tar/extract.sh"""

    SNIPPET = 'tar xvf ${archive_name}.tar.${extension} -C ${to_path}'

    def setup_method(self):
        self.parser = BashParser()
        self.emitter = BashEmitter()

    def test_parse_produces_command_node(self):
        ir = self.parser.parse(self.SNIPPET + '\n')
        assert len(ir.nodes) == 1
        assert ir.nodes[0].type == "command"

    def test_parse_command_name_is_tar(self):
        ir = self.parser.parse(self.SNIPPET + '\n')
        node = ir.nodes[0]
        assert node.command == "tar"

    def test_parse_flags_arg(self):
        ir = self.parser.parse(self.SNIPPET + '\n')
        node = ir.nodes[0]
        assert len(node.args) == 4
        assert node.args[0].kind == "string"
        assert node.args[0].value == "xvf"

    def test_parse_archive_fstring(self):
        ir = self.parser.parse(self.SNIPPET + '\n')
        node = ir.nodes[0]
        archive_arg = node.args[1]
        # ${archive_name}.tar.${extension} → fstring with var/string/var parts
        assert archive_arg.kind == "fstring"
        var_names = [p.value for p in archive_arg.parts if p.kind == "var"]
        assert "archive_name" in var_names
        assert "extension" in var_names

    def test_parse_target_path_var(self):
        ir = self.parser.parse(self.SNIPPET + '\n')
        node = ir.nodes[0]
        path_arg = node.args[3]
        assert path_arg.kind == "var"
        assert path_arg.value == "to_path"

    def test_emit_bash_contains_tar(self):
        ir = self.parser.parse(self.SNIPPET + '\n')
        result = self.emitter.emit(ir)
        assert 'tar' in result

    def test_emit_bash_roundtrip_variable_interpolation(self):
        ir = self.parser.parse(self.SNIPPET + '\n')
        result = self.emitter.emit(ir)
        assert '${archive_name}' in result
        assert '${extension}' in result
        assert '${to_path}' in result

    def test_emit_bash_from_example_file(self):
        source = (EXAMPLES / "tar_extract.sh").read_text()
        ir = self.parser.parse(source)
        result = self.emitter.emit(ir)
        assert 'tar' in result
        assert '${archive_name}' in result
        assert '${to_path}' in result

    def test_translate_to_python(self):
        from itsconvert.translators import get_emitter
        ir = self.parser.parse(self.SNIPPET + '\n')
        result = get_emitter("py").emit(ir)
        assert 'subprocess' in result
        assert 'tar' in result

    def test_translate_to_powershell(self):
        from itsconvert.translators import get_emitter
        ir = self.parser.parse(self.SNIPPET + '\n')
        result = get_emitter("ps1").emit(ir)
        assert 'tar' in result
