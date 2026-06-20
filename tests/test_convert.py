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
        # tar xvf <archive> -C <path>: xvf, archive fstring, -C, to_path var
        assert any(a.kind == "string" and a.value == "xvf" for a in node.args)
        assert any(a.kind == "string" and a.value == "-C" for a in node.args)

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


# --- New IR node tests ---

class TestCompoundCondition:
    def setup_method(self):
        self.parser = PythonParser()

    def test_and_condition(self):
        from itsconvert.ir import CompoundCondition
        ir = self.parser.parse('if x > 0 and y < 10:\n    pass\n')
        node = ir.nodes[0]
        assert isinstance(node, If)
        assert isinstance(node.condition, CompoundCondition)
        assert node.condition.op == "and"

    def test_or_condition(self):
        from itsconvert.ir import CompoundCondition
        ir = self.parser.parse('if a == 1 or b == 2:\n    pass\n')
        node = ir.nodes[0]
        assert isinstance(node.condition, CompoundCondition)
        assert node.condition.op == "or"

    def test_compound_cond_emitted_in_bash(self):
        from itsconvert.ir import CompoundCondition, Condition
        from itsconvert.translators.sh_emitter import BashEmitter
        ir = ScriptIR(
            source_language="py",
            nodes=[If(
                condition=CompoundCondition(
                    left=Condition(left=Value(kind="var", value="x"), op=">", right=Value(kind="int", value=0)),
                    op="and",
                    right=Condition(left=Value(kind="var", value="y"), op="<", right=Value(kind="int", value=10)),
                ),
                then_body=[Print(values=[Value(kind="string", value="ok")])],
            )],
        )
        result = BashEmitter().emit(ir)
        assert "&&" in result

    def test_compound_cond_emitted_in_js(self):
        from itsconvert.ir import CompoundCondition, Condition
        from itsconvert.translators.js_emitter import JSEmitter
        ir = ScriptIR(
            source_language="py",
            nodes=[If(
                condition=CompoundCondition(
                    left=Condition(left=Value(kind="var", value="x"), op=">", right=Value(kind="int", value=0)),
                    op="or",
                    right=Condition(left=Value(kind="var", value="y"), op="<", right=Value(kind="int", value=5)),
                ),
                then_body=[Print(values=[Value(kind="string", value="ok")])],
            )],
        )
        result = JSEmitter().emit(ir)
        assert "||" in result


class TestSwitchNode:
    def setup_method(self):
        self.parser = PythonParser()

    def test_match_parsed(self):
        from itsconvert.ir import Switch
        ir = self.parser.parse(
            'match x:\n    case 1:\n        print("one")\n    case 2:\n        print("two")\n    case _:\n        print("other")\n'
        )
        nodes = [n for n in ir.nodes if n.type == "switch"]
        assert len(nodes) == 1
        sw = nodes[0]
        assert len(sw.cases) == 2

    def test_switch_emitted_in_go(self):
        from itsconvert.ir import Switch, SwitchCase
        from itsconvert.translators.go_emitter import GoEmitter
        ir = ScriptIR(
            source_language="py",
            nodes=[Switch(
                subject=Value(kind="var", value="x"),
                cases=[
                    SwitchCase(pattern=Value(kind="int", value=1), body=[Print(values=[Value(kind="string", value="one")])]),
                    SwitchCase(pattern=Value(kind="int", value=2), body=[Print(values=[Value(kind="string", value="two")])]),
                ],
                default_body=[Print(values=[Value(kind="string", value="other")])],
            )],
        )
        result = GoEmitter().emit(ir)
        assert "switch" in result
        assert "case" in result

    def test_switch_emitted_in_rust(self):
        from itsconvert.ir import Switch, SwitchCase
        from itsconvert.translators.rs_emitter import RustEmitter
        ir = ScriptIR(
            source_language="py",
            nodes=[Switch(
                subject=Value(kind="var", value="x"),
                cases=[SwitchCase(pattern=Value(kind="int", value=1), body=[Print(values=[Value(kind="string", value="a")])])],
                default_body=[],
            )],
        )
        result = RustEmitter().emit(ir)
        assert "match" in result


class TestClassDef:
    def setup_method(self):
        self.parser = PythonParser()

    def test_class_parsed(self):
        from itsconvert.ir import ClassDef
        ir = self.parser.parse(
            'class Dog:\n    name = "Rex"\n    def bark(self):\n        print("woof")\n'
        )
        classes = [n for n in ir.nodes if n.type == "class_def"]
        assert len(classes) == 1
        assert classes[0].name == "Dog"

    def test_class_emitted_in_java(self):
        from itsconvert.ir import ClassDef, ClassField
        from itsconvert.translators.java_emitter import JavaEmitter
        ir = ScriptIR(
            source_language="py",
            nodes=[ClassDef(
                name="Dog",
                bases=[],
                fields=[ClassField(name="name", value=Value(kind="string", value="Rex"))],
                methods=[FunctionDef(name="bark", params=[], body=[Print(values=[Value(kind="string", value="woof")])])],
            )],
        )
        result = JavaEmitter().emit(ir)
        assert "class Dog" in result


class TestLambdaNode:
    def setup_method(self):
        self.parser = PythonParser()

    def test_lambda_parsed(self):
        from itsconvert.ir import Lambda
        ir = self.parser.parse('double = lambda x: x * 2\n')
        lambdas = [n for n in ir.nodes if n.type == "lambda"]
        assert len(lambdas) == 1
        assert lambdas[0].name == "double"

    def test_lambda_emitted_in_js(self):
        from itsconvert.ir import Lambda, Param
        from itsconvert.translators.js_emitter import JSEmitter
        ir = ScriptIR(
            source_language="py",
            nodes=[Lambda(
                name="double",
                params=[Param(name="x")],
                body=Value(kind="var", value="x"),
            )],
        )
        result = JSEmitter().emit(ir)
        assert "=>" in result


class TestWithBlock:
    def setup_method(self):
        self.parser = PythonParser()

    def test_with_parsed(self):
        from itsconvert.ir import WithBlock
        # Use a non-open context manager so it becomes WithBlock (not file_io)
        ir = self.parser.parse('with Lock() as lock:\n    lock.acquire()\n')
        with_nodes = [n for n in ir.nodes if n.type == "with_block"]
        assert len(with_nodes) == 1

    def test_with_emitted_in_csharp(self):
        from itsconvert.ir import WithBlock
        from itsconvert.translators.cs_emitter import CSharpEmitter
        ir = ScriptIR(
            source_language="py",
            nodes=[WithBlock(
                expr=Value(kind="var", value='open("f.txt")'),
                var="f",
                body=[Assign(name="data", value=Value(kind="var", value="f.read()"))],
            )],
        )
        result = CSharpEmitter().emit(ir)
        assert "using" in result


# --- New parser tests ---

class TestJSParser:
    def setup_method(self):
        from itsconvert.translators.js_parser import JSParser
        self.parser = JSParser()

    def test_const_assign(self):
        ir = self.parser.parse('const x = 42;\n')
        assert ir.nodes[0].type == "assign"
        assert ir.nodes[0].value.kind == "int"

    def test_console_log(self):
        ir = self.parser.parse('console.log("hello");\n')
        assert ir.nodes[0].type == "print"

    def test_template_literal(self):
        ir = self.parser.parse('console.log(`Hello, ${name}!`);\n')
        assert ir.nodes[0].type == "print"
        val = ir.nodes[0].values[0]
        assert val.kind == "fstring"

    def test_function(self):
        ir = self.parser.parse('function greet(x) {\n  console.log(x);\n}\n')
        fn = [n for n in ir.nodes if n.type == "function_def"]
        assert len(fn) == 1
        assert fn[0].name == "greet"

    def test_for_loop(self):
        ir = self.parser.parse('for (let i = 0; i < 5; i++) {\n  console.log(i);\n}\n')
        loops = [n for n in ir.nodes if n.type == "for_range"]
        assert len(loops) == 1

    def test_if_else(self):
        ir = self.parser.parse('if (x > 0) {\n  console.log("pos");\n} else {\n  console.log("neg");\n}\n')
        ifs = [n for n in ir.nodes if n.type == "if"]
        assert len(ifs) == 1
        assert len(ifs[0].else_body) == 1

    def test_arrow_function(self):
        from itsconvert.ir import Lambda
        ir = self.parser.parse('const double = (x) => x * 2;\n')
        lambdas = [n for n in ir.nodes if n.type == "lambda"]
        assert len(lambdas) == 1

    def test_source_language_js(self):
        ir = self.parser.parse('const x = 1;\n')
        assert ir.source_language == "js"

    def test_import(self):
        ir = self.parser.parse("import fs from 'fs';\n")
        assert ir.nodes[0].type == "import"

    def test_try_catch(self):
        ir = self.parser.parse('try {\n  x();\n} catch (e) {\n  console.log(e);\n}\n')
        tc = [n for n in ir.nodes if n.type == "try_catch"]
        assert len(tc) == 1


class TestRubyParser:
    def setup_method(self):
        from itsconvert.translators.rb_parser import RubyParser
        self.parser = RubyParser()

    def test_assign(self):
        ir = self.parser.parse('x = 42\n')
        assert ir.nodes[0].type == "assign"
        assert ir.nodes[0].value.kind == "int"

    def test_puts(self):
        ir = self.parser.parse('puts "hello"\n')
        assert ir.nodes[0].type == "print"

    def test_string_interpolation(self):
        ir = self.parser.parse('puts "Hello, #{name}!"\n')
        val = ir.nodes[0].values[0]
        assert val.kind == "fstring"

    def test_def(self):
        ir = self.parser.parse('def greet(who)\n  puts who\nend\n')
        fns = [n for n in ir.nodes if n.type == "function_def"]
        assert len(fns) == 1
        assert fns[0].name == "greet"

    def test_times(self):
        ir = self.parser.parse('3.times do |i|\n  puts i\nend\n')
        loops = [n for n in ir.nodes if n.type == "for_range"]
        assert len(loops) == 1

    def test_if_elsif_else(self):
        ir = self.parser.parse('if x > 0\n  puts "pos"\nelsif x < 0\n  puts "neg"\nelse\n  puts "zero"\nend\n')
        ifs = [n for n in ir.nodes if n.type == "if"]
        assert len(ifs) == 1
        assert len(ifs[0].elif_branches) == 1
        assert len(ifs[0].else_body) == 1

    def test_source_language_rb(self):
        ir = self.parser.parse('x = 1\n')
        assert ir.source_language == "rb"


class TestGoParser:
    def setup_method(self):
        from itsconvert.translators.go_parser import GoParser
        self.parser = GoParser()

    def test_short_var_decl(self):
        ir = self.parser.parse('x := 42\n')
        assert ir.nodes[0].type == "assign"

    def test_fmt_println(self):
        ir = self.parser.parse('fmt.Println("hello")\n')
        assert ir.nodes[0].type == "print"

    def test_func(self):
        ir = self.parser.parse('func greet(name string) {\n    fmt.Println(name)\n}\n')
        fns = [n for n in ir.nodes if n.type == "function_def"]
        assert len(fns) == 1
        assert fns[0].name == "greet"

    def test_for_range_loop(self):
        ir = self.parser.parse('for i := 0; i < 5; i++ {\n    fmt.Println(i)\n}\n')
        loops = [n for n in ir.nodes if n.type == "for_range"]
        assert len(loops) == 1

    def test_switch(self):
        ir = self.parser.parse('switch x {\ncase 1:\n    fmt.Println("one")\ndefault:\n    fmt.Println("other")\n}\n')
        switches = [n for n in ir.nodes if n.type == "switch"]
        assert len(switches) == 1

    def test_source_language_go(self):
        ir = self.parser.parse('x := 1\n')
        assert ir.source_language == "go"


# --- Type inference and analyzer tests ---

class TestAnalyzer:
    def setup_method(self):
        self.parser = PythonParser()

    def test_infer_int(self):
        from itsconvert.analyzer import infer_types
        ir = self.parser.parse('x = 42\n')
        types = infer_types(ir)
        assert types["x"] == "int"

    def test_infer_float(self):
        from itsconvert.analyzer import infer_types
        ir = self.parser.parse('pi = 3.14\n')
        types = infer_types(ir)
        assert types["pi"] == "float"

    def test_infer_str(self):
        from itsconvert.analyzer import infer_types
        ir = self.parser.parse('name = "Alice"\n')
        types = infer_types(ir)
        assert types["name"] == "str"

    def test_infer_bool(self):
        from itsconvert.analyzer import infer_types
        ir = self.parser.parse('flag = True\n')
        types = infer_types(ir)
        assert types["flag"] == "bool"

    def test_summarize_includes_confidence(self):
        from itsconvert.analyzer import summarize_ir
        ir = self.parser.parse('x = 1\n')
        summary = summarize_ir(ir)
        assert "Confidence" in summary

    def test_summarize_includes_breakdown(self):
        from itsconvert.analyzer import summarize_ir
        ir = self.parser.parse('x = 1\nprint("hi")\n')
        summary = summarize_ir(ir)
        assert "assign" in summary
        assert "print" in summary


# --- CMD parser upgrade tests ---

class TestCMDParserUpgrade:
    def setup_method(self):
        from itsconvert.translators.cmd_parser import CMDParser
        self.parser = CMDParser()

    def test_if_exist(self):
        ir = self.parser.parse('if exist myfile.txt echo found\n')
        ifs = [n for n in ir.nodes if n.type == "if"]
        assert len(ifs) == 1

    def test_if_errorlevel(self):
        ir = self.parser.parse('if errorlevel 1 echo failed\n')
        ifs = [n for n in ir.nodes if n.type == "if"]
        assert len(ifs) == 1

    def test_for_l_loop(self):
        ir = self.parser.parse('for /l %%i in (1,1,5) do echo %%i\n')
        loops = [n for n in ir.nodes if n.type == "for_range"]
        assert len(loops) == 1

    def test_goto_becomes_command(self):
        ir = self.parser.parse('goto :done\n')
        cmds = [n for n in ir.nodes if n.type == "command"]
        assert len(cmds) == 1
        assert "goto" in cmds[0].command

    def test_subroutine(self):
        ir = self.parser.parse(':myFunc\necho hello\nexit /b\n')
        fns = [n for n in ir.nodes if n.type == "function_def"]
        assert len(fns) == 1
        assert fns[0].name == "myFunc"

    def test_if_defined(self):
        ir = self.parser.parse('if defined MYVAR echo defined\n')
        ifs = [n for n in ir.nodes if n.type == "if"]
        assert len(ifs) == 1

    def test_confidence_field(self):
        ir = self.parser.parse('echo hello\n')
        assert 0.0 <= ir.confidence <= 1.0
