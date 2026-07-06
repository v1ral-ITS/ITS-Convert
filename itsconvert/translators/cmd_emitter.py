"""Emit CMD/batch script from IR."""
from __future__ import annotations

from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition, Language,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class CMDEmitter:
    """Emit CMD/batch from ScriptIR."""

    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ["@echo off", "setlocal enabledelayedexpansion", ""]
        for node in ir.nodes:
            lines.extend(self._emit_node(node, indent=0))
        lines.append("")
        lines.append("endlocal")
        return "\n".join(lines) + "\n"

    def _emit_node(self, node: IRNode, indent: int) -> list[str]:
        prefix = "    " * indent
        if isinstance(node, Comment):
            return [f"{prefix}REM {node.text}"]
        if isinstance(node, Assign):
            return [f"{prefix}set \"{node.name}={self._val(node.value)}\""]
        if isinstance(node, MultiAssign):
            vals = self._val(node.value)
            return [f"{prefix}REM Multi-assign"] + [f"{prefix}set \"{n}={vals}\"" for n in node.names]
        if isinstance(node, AugAssign):
            op = node.op
            if op in ("+",):
                return [f"{prefix}set /a \"{node.name}=!{node.name}!+{self._val(node.value)}\""]
            if op in ("-",):
                return [f"{prefix}set /a \"{node.name}=!{node.name}!-{self._val(node.value)}\""]
            return [f"{prefix}set /a \"{node.name}=!{node.name}!{op}{self._val(node.value)}\""]
        if isinstance(node, Print):
            if not node.values:
                return [f"{prefix}echo("]
            parts = [self._val(v) for v in node.values]
            joined = " ".join(parts)
            if node.end != "\n":
                return [f"{prefix}<nul set /p=\"{joined}\""]
            return [f"{prefix}echo {joined}"]
        if isinstance(node, Input):
            if node.prompt:
                return [f'{prefix}set /p "{node.name}=" /p:"{node.prompt} "']
            return [f'{prefix}set /p "{node.name}="']
        if isinstance(node, Command):
            args = self._emit_args(node.args)
            cmd = f"{node.command} {args}".strip()
            if node.capture and node.name:
                return [f"{prefix}for /f \"delims=\" %%a in ('{cmd}') do set \"{node.name}=%%a\""]
            return [f"{prefix}{cmd}"]
        if isinstance(node, Exit):
            return [f"{prefix}exit /b {node.code}"]
        if isinstance(node, If):
            return self._emit_if(node, indent)
        if isinstance(node, ForRange):
            return self._emit_for_range(node, indent)
        if isinstance(node, ForEnumerate):
            prefix = "    " * indent
            body = self._emit_body(node.body, indent + 1)
            return [f"{prefix}REM enumerate loop (index={node.index_var}, value={node.value_var})"] + body
        if isinstance(node, ForKeys):
            prefix = "    " * indent
            body = self._emit_body(node.body, indent + 1)
            return [f"{prefix}REM for keys in {self._val(node.dict_value)}: (CMD has no native dict iteration)"] + body
        if isinstance(node, For):
            return self._emit_for(node, indent)
        if isinstance(node, Break):
            return [f"{prefix}goto :eof"]
        if isinstance(node, Continue):
            return [f"{prefix}REM continue (not supported in CMD)"]
        if isinstance(node, Pass):
            return [f"{prefix}REM pass"]
        if isinstance(node, FunctionDef):
            return self._emit_function(node, indent)
        if isinstance(node, Return):
            if node.value:
                return [f"{prefix}echo {self._val(node.value)}", f"{prefix}exit /b"]
            return [f"{prefix}exit /b"]
        if isinstance(node, Import):
            return [f"{prefix}REM import {node.module}"]
        if isinstance(node, FileIONode):
            return self._emit_file_io(node, prefix)
        if isinstance(node, EnvVar):
            return self._emit_env_var(node, prefix)
        if isinstance(node, Argv):
            return self._emit_argv(node, prefix)
        if isinstance(node, Exit):
            return [f"{prefix}exit /b {node.code}"]
        # fallback for unsupported constructs
        return [f"{prefix}REM FIXME: unsupported: {node.type}"]

    def _emit_if(self, node: If, indent: int) -> list[str]:
        prefix = "    " * indent
        cond = self._condition(node.condition)
        lines = [f"{prefix}if {cond} ("]
        lines.extend(self._emit_body(node.then_body, indent + 1))
        if node.elif_branches:
            for elif_b in node.elif_branches:
                elif_cond = self._condition(elif_b.condition)
                lines.append(f"{prefix}) else if {elif_cond} (")
                lines.extend(self._emit_body(elif_b.body, indent + 1))
        if node.else_body:
            lines.append(f'{prefix}) else (')
            lines.extend(self._emit_body(node.else_body, indent + 1))
        lines.append(f"{prefix})")
        return lines

    def _emit_for_range(self, node: ForRange, indent: int) -> list[str]:
        prefix = "    " * indent
        start = self._val(node.start)
        stop = self._val(node.stop)
        step = self._val(node.step) if node.step else "1"
        lines = [f"{prefix}for /l %%{node.var} in ({start},{step},{stop}) do ("]
        lines.extend(self._emit_body(node.body, indent + 1))
        lines.append(f"{prefix})")
        return lines

    def _emit_for(self, node: For, indent: int) -> list[str]:
        prefix = "    " * indent
        lines = [f"{prefix}for %%{node.var} in ({self._val(node.iterable)}) do ("]
        lines.extend(self._emit_body(node.body, indent + 1))
        lines.append(f"{prefix})")
        return lines

    def _emit_function(self, node: FunctionDef, indent: int) -> list[str]:
        prefix = "    " * indent
        lines = [f"{prefix}:{node.name}"]
        if node.params:
            for p in node.params:
                lines.append(f"{prefix}set \"{p.name}=%~1\"")
                lines.append(f"{prefix}shift")
        lines.extend(self._emit_body(node.body, indent + 1))
        lines.append(f"{prefix}exit /b")
        lines.append("")
        return lines

    def _emit_file_io(self, node: FileIONode, prefix: str) -> list[str]:
        path = self._val(node.path)
        if node.op == "read" and node.name:
            return [f"{prefix}set /p \"{node.name}=\" <{path}"]
        if node.op == "write" and node.content:
            return [f"{prefix}echo {self._val(node.content)} >{path}"]
        if node.op == "append" and node.content:
            return [f"{prefix}echo {self._val(node.content)} >>{path}"]
        if node.op == "exists":
            name = node.name or "exists"
            return [f"{prefix}if exist {path} (set \"{name}=1\") else (set \"{name}=0\")"]
        if node.op == "delete":
            return [f"{prefix}del {path}"]
        if node.op == "mkdir":
            return [f"{prefix}mkdir {path}"]
        return [f"{prefix}REM file op: {node.op} {path}"]

    def _emit_env_var(self, node: EnvVar, prefix: str) -> list[str]:
        if node.action == "get":
            name = node.result_name or node.name.lower()
            return [f"{prefix}set \"{name}=!{node.name}!\""]
        if node.action == "set":
            return [f"{prefix}set \"{node.name}={self._val(node.value)}\""]
        if node.action == "delete":
            return [f"{prefix}set \"{node.name}=\""]
        return [f"{prefix}REM env: {node.action} {node.name}"]

    def _emit_argv(self, node: Argv, prefix: str) -> list[str]:
        if node.action == "script_name":
            name = node.name or "script"
            return [f"{prefix}set \"{name}=%~0\""]
        if node.action == "nth" and node.index is not None:
            name = node.name or f"arg{node.index}"
            return [f"{prefix}set \"{name}=%{node.index + 1}\""]
        if node.action == "count":
            return [f"{prefix}REM argc not directly available in CMD"]
        return [f"{prefix}REM argv: {node.action}"]

    def _emit_body(self, nodes: list[IRNode], indent: int) -> list[str]:
        lines: list[str] = []
        for node in nodes:
            lines.extend(self._emit_node(node, indent))
        return lines

    def _emit_args(self, args: list[Value]) -> str:
        return " ".join(self._val(a) for a in args)

    def _val(self, v: Value) -> str:
        if v.kind == "string":
            return str(v.value or "")
        if v.kind in ("int", "float"):
            return str(v.value)
        if v.kind == "bool":
            return "1" if v.value else "0"
        if v.kind == "null":
            return ""
        if v.kind == "var":
            return f"!{v.value}!"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            left, op, right = v.parts
            op_str = self._val_strip(op)
            if op_str in ("+", "-", "*", "/", "%"):
                return f"!{self._val_strip(left)}!{op_str}!{self._val_strip(right)}!"
            return f"!{self._val_strip(left)}!{op_str}!{self._val_strip(right)}!"
        return str(v.value or "")

    def _val_strip(self, v: Value) -> str:
        return self._val(v)

    def _condition(self, c: Condition) -> str:
        left = self._val(c.left)
        right = self._val(c.right)
        op = c.op
        if op == "==":
            return f"\"{left}\"==\"{right}\""
        if op == "!=":
            return f"NOT \"{left}\"==\"{right}\""
        return f"\"{left}\"{op}\"{right}\""


def emit_cmd(ir: ScriptIR) -> str:
    return CMDEmitter().emit(ir)
