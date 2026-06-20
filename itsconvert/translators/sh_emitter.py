"""Emit Bash/sh script from IR."""
from __future__ import annotations

from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition, Language,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class BashEmitter:
    """Emit Bash/sh from ScriptIR."""

    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
        for node in ir.nodes:
            lines.extend(self._emit_node(node, indent=0))
            if not isinstance(node, (Comment, Pass)):
                pass
        # remove trailing blank lines
        while lines and lines[-1].strip() == "":
            lines.pop()
        return "\n".join(lines) + "\n"

    def _emit_node(self, node: IRNode, indent: int) -> list[str]:
        prefix = "    " * indent
        if isinstance(node, Comment):
            return [f"{prefix}# {node.text}"]
        if isinstance(node, Assign):
            return [f"{prefix}{node.name}={self._val(node.value)}"]
        if isinstance(node, MultiAssign):
            # bash: read arr <<< "..."; a=${arr[0]} b=${arr[1]}
            vals = self._val(node.value)
            return [f"{prefix}# Multi-assign: {' '.join(node.names)} = {vals}"] + \
                   [f"{prefix}{n}={vals}" for n in node.names]
        if isinstance(node, AugAssign):
            op = node.op
            if op == "+":
                if node.name.startswith(("arr", "list")) or True:
                    return [f'{prefix}{node.name}+="{self._val_strip(node.value)}"']
                return [f"{prefix}{node.name}=$(( {node.name} + {self._val(node.value)} ))"]
            if op == "-":
                return [f"{prefix}{node.name}=$(( {node.name} - {self._val(node.value)} ))"]
            if op == "*":
                return [f"{prefix}{node.name}=$(( {node.name} * {self._val(node.value)} ))"]
            if op == "/":
                return [f"{prefix}{node.name}=$(( {node.name} / {self._val(node.value)} ))"]
            return [f"{prefix}{node.name}=$(( {node.name} {op} {self._val(node.value)} ))"]
        if isinstance(node, Print):
            return self._emit_print(node, prefix)
        if isinstance(node, Input):
            if node.prompt:
                return [f'{prefix}read -r -p "{node.prompt} " {node.name}']
            return [f"{prefix}read -r {node.name}"]
        if isinstance(node, Command):
            args_str = self._emit_args(node.args)
            full = f"{node.command} {args_str}".strip() if args_str else node.command
            if node.capture and node.name:
                return [f"{prefix}{node.name}=$({full})"]
            return [f"{prefix}{full}"]
        if isinstance(node, Exit):
            return [f"{prefix}exit {node.code}"]
        if isinstance(node, If):
            return self._emit_if(node, indent)
        if isinstance(node, For):
            return self._emit_for(node, indent)
        if isinstance(node, ForRange):
            return self._emit_for_range(node, indent)
        if isinstance(node, ForEnumerate):
            lines = [f"{prefix}{node.index_var}=0"]
            lines.append(f"{prefix}for {node.value_var} in {self._val(node.iterable)}; do")
            for child in node.body:
                lines.extend(self._emit_node(child, indent + 1))
            lines.append(f"{prefix}    {node.index_var}=$(( {node.index_var} + 1 ))")
            lines.append(f"{prefix}done")
            return lines
        if isinstance(node, ForKeys):
            return [f"{prefix}for {node.var} in \"${{{self._val(node.dict_value)}[@]}}\"; do"] + \
                   self._emit_body(node.body, indent + 1) + [f"{prefix}done"]
        if isinstance(node, While):
            cond = self._condition(node.condition)
            return [f"{prefix}while {cond}; do"] + self._emit_body(node.body, indent + 1) + [f"{prefix}done"]
        if isinstance(node, Break):
            return [f"{prefix}break"]
        if isinstance(node, Continue):
            return [f"{prefix}continue"]
        if isinstance(node, Pass):
            return [f"{prefix}:"]
        if isinstance(node, FunctionDef):
            return self._emit_function(node, indent)
        if isinstance(node, Return):
            if node.value:
                return [f"{prefix}echo {self._val(node.value)}", f"{prefix}return"]
            return [f"{prefix}return"]
        if isinstance(node, Import):
            if node.names:
                return [f"{prefix}# from {node.module} import {', '.join(node.names)}"]
            return [f"{prefix}# import {node.module}"]
        if isinstance(node, StringOpNode):
            return self._emit_string_op(node, prefix)
        if isinstance(node, FileIONode):
            return self._emit_file_io(node, prefix)
        if isinstance(node, EnvVar):
            return self._emit_env_var(node, prefix)
        if isinstance(node, Argv):
            return self._emit_argv(node, prefix)
        if isinstance(node, Switch):
            return self._emit_switch(node, indent)
        if isinstance(node, ClassDef):
            return [f"{prefix}# class {node.name} (not supported in this language)"]
        if isinstance(node, Lambda):
            params = ", ".join(pp.name for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{prefix}# lambda: {node.name or '_fn'} = {params} => {self._val(node.body)}"]
        if isinstance(node, WithBlock):
            lines = [f"{prefix}# with {self._val(node.expr)} as {node.var or '_ctx'}:"]
            lines.extend(self._emit_body(node.body, indent))
            return lines
        if isinstance(node, TryCatch):
            return self._emit_try(node, indent)
        if isinstance(node, Raise):
            msg = self._val(node.message) if node.message else '"Error"'
            return [f"{prefix}echo {msg} >&2", f"{prefix}exit 1"]
        if isinstance(node, ListOp):
            return self._emit_list_op(node, prefix)
        if isinstance(node, DictOp):
            return self._emit_dict_op(node, prefix)
        if isinstance(node, Assert):
            cond = self._condition(node.condition)
            msg = f' "{self._val_strip(node.message)}"' if node.message else ""
            return [f"{prefix}[[ {cond} ]] || {{ echo {msg} >&2; exit 1; }}"]
        if isinstance(node, RawBlock):
            return [f"{prefix}# --- raw (py) ---"] + [f"{prefix}# {line}" for line in node.code.split("\n")]
        return [f"{prefix}# FIXME: unsupported node type: {node.type}"]

    def _emit_print(self, node: Print, prefix: str) -> list[str]:
        if not node.values:
            return [f"{prefix}echo" if node.end == "\n" else f"{prefix}echo -n"]
        parts = [self._val(v) for v in node.values]
        joined = " ".join(parts)
        if node.end == "\n":
            return [f"{prefix}echo {joined}"]
        return [f'{prefix}echo -n {joined}']

    def _emit_if(self, node: If, indent: int) -> list[str]:
        prefix = "    " * indent
        cond = self._condition(node.condition)
        lines = [f"{prefix}if {cond}; then"]
        lines.extend(self._emit_body(node.then_body, indent + 1))
        for elif_b in node.elif_branches:
            elif_cond = self._condition(elif_b.condition)
            lines.append(f"{prefix}elif {elif_cond}; then")
            lines.extend(self._emit_body(elif_b.body, indent + 1))
        if node.else_body:
            lines.append(f"{prefix}else")
            lines.extend(self._emit_body(node.else_body, indent + 1))
        lines.append(f"{prefix}fi")
        return lines

    def _emit_for(self, node: For, indent: int) -> list[str]:
        prefix = "    " * indent
        lines = [f"{prefix}for {node.var} in {self._val(node.iterable)}; do"]
        lines.extend(self._emit_body(node.body, indent + 1))
        lines.append(f"{prefix}done")
        return lines

    def _emit_for_range(self, node: ForRange, indent: int) -> list[str]:
        prefix = "    " * indent
        start = self._val(node.start)
        stop = self._val(node.stop)
        step = self._val(node.step) if node.step else ""
        if step:
            # seq START STEP STOP or (( i=START; i<STOP; i+=STEP ))
            lines = [f"{prefix}for (( i={start}; i<{stop}; i+={step} )); do"]
            lines.extend(self._emit_body(node.body, indent + 1))
            lines.append(f"{prefix}done")
            # also alias the loop var
            if node.var != "i":
                lines.insert(1, f"{prefix}    {node.var}=$i")
        else:
            lines = [f"{prefix}for (( i={start}; i<{stop}; i++ )); do"]
            body = self._emit_body(node.body, indent + 1)
            if node.var != "i":
                body.insert(0, f"{prefix}    {node.var}=$i")
            lines.extend(body)
            lines.append(f"{prefix}done")
        return lines

    def _emit_function(self, node: FunctionDef, indent: int) -> list[str]:
        prefix = "    " * indent
        params = " ".join(p.name for p in node.params if not p.vararg and not p.kwarg)
        vararg = ""
        for p in node.params:
            if p.vararg:
                vararg = p.name
        lines = [f"{prefix}{node.name}() {{"]
        if params:
            lines.append(f"{prefix}    local {' '.join(params.split())}")
        if vararg:
            lines.append(f"{prefix}    local {vararg}=(\"$@\")")
        lines.extend(self._emit_body(node.body, indent + 1))
        lines.append(f"{prefix}}}")
        return lines

    def _emit_string_op(self, node: StringOpNode, prefix: str) -> list[str]:
        op = node.op
        if op == "len" and node.operands:
            return [f"{prefix}# len: ${{# {self._val(node.operands[0])} }}"]
        if op == "upper" and node.operands:
            return [f"{prefix}# upper: ${{{self._val(node.operands[0])}^^}}"]
        if op == "lower" and node.operands:
            return [f"{prefix}# lower: ${{{self._val(node.operands[0])},,}}"]
        if op == "strip" and node.operands:
            return [f"{prefix}# strip: ${{{self._val(node.operands[0])}#${{lstrip}}}}"]
        if op == "replace" and len(node.operands) >= 3:
            return [f"{prefix}# replace: ${{{self._val(node.operands[0])}//{self._val(node.operands[1])}/{self._val(node.operands[2])}}}"]
        if op == "split" and len(node.operands) >= 2:
            return [f"{prefix}# split: IFS={self._val(node.operands[1])} read -ra <<< \"{self._val(node.operands[0])}\""]
        if op == "join" and len(node.operands) >= 2:
            return [f"{prefix}# join: IFS={self._val(node.operands[0])} echo \"${{{self._val(node.operands[1])}[*]}}\""]
        return [f"{prefix}# string op: {op}({', '.join(self._val(o) for o in node.operands)})"]

    def _emit_file_io(self, node: FileIONode, prefix: str) -> list[str]:
        path = self._val(node.path)
        if node.op == "read" and node.name:
            return [f"{prefix}{node.name}=$(cat {path})"]
        if node.op == "read":
            return [f"{prefix}cat {path}"]
        if node.op == "write" and node.content:
            content = self._val(node.content)
            return [f"{prefix}echo {content} > {path}"]
        if node.op == "append" and node.content:
            content = self._val(node.content)
            return [f"{prefix}echo {content} >> {path}"]
        if node.op == "exists":
            name = node.name or "exists"
            return [f"{prefix}{name}=[[ -f {path} ]] && echo yes || echo no"]
        if node.op == "delete":
            return [f"{prefix}rm -f {path}"]
        if node.op == "mkdir":
            return [f"{prefix}mkdir -p {path}"]
        if node.op == "listdir" and node.name:
            return [f"{prefix}{node.name}=($(ls {path}))"]
        if node.op == "basename" and node.name:
            return [f"{prefix}{node.name}=$(basename {path})"]
        if node.op == "dirname" and node.name:
            return [f"{prefix}{node.name}=$(dirname {path})"]
        return [f"{prefix}# file op: {node.op} {path}"]

    def _emit_env_var(self, node: EnvVar, prefix: str) -> list[str]:
        if node.action == "get":
            name = node.result_name or node.name.lower()
            return [f"{prefix}{name}=${{{node.name}}}"]
        if node.action == "set":
            return [f"{prefix}export {node.name}={self._val(node.value)}"]
        if node.action == "delete":
            return [f"{prefix}unset {node.name}"]
        if node.action == "list":
            return [f"{prefix}env"]
        return [f"{prefix}# env: {node.action} {node.name}"]

    def _emit_argv(self, node: Argv, prefix: str) -> list[str]:
        if node.action == "script_name":
            name = node.name or "script"
            return [f"{prefix}{name}=$0"]
        if node.action == "all":
            name = node.name or "args"
            return [f"{prefix}{name}=(\"$@\")"]
        if node.action == "nth" and node.index is not None:
            name = node.name or f"arg{node.index}"
            return [f"{prefix}{name}=${{{node.index + 1}}}"]
        if node.action == "count":
            name = node.name or "argc"
            return [f"{prefix}{name}=$#"]
        return [f"{prefix}# argv: {node.action}"]

    def _emit_switch(self, node: Switch, indent: int) -> list[str]:
        prefix = "    " * indent
        lines = [f"{prefix}case {self._val(node.subject)} in"]
        for case in node.cases:
            lines.append(f"{prefix}  {self._val(case.pattern)})")
            lines.extend(self._emit_body(case.body, indent + 2))
            lines.append(f"{prefix}    ;;")
        if node.default_body:
            lines.append(f"{prefix}  *)")
            lines.extend(self._emit_body(node.default_body, indent + 2))
            lines.append(f"{prefix}    ;;")
        lines.append(f"{prefix}esac")
        return lines

    def _emit_try(self, node: TryCatch, indent: int) -> list[str]:
        prefix = "    " * indent
        catch_var = node.catch_var or "err"
        lines = [f"{prefix}({{"]
        lines.extend(self._emit_body(node.try_body, indent + 1))
        lines.append(f"{prefix}}}) || {{")
        if node.catch_body:
            lines.append(f"{prefix}    {catch_var}=$?")
            lines.extend(self._emit_body(node.catch_body, indent + 1))
        else:
            lines.append(f"{prefix}    {catch_var}=$?")
        lines.append(f"{prefix}}}")
        if node.finally_body:
            lines.extend(self._emit_body(node.finally_body, indent))
        return lines

    def _emit_list_op(self, node: ListOp, prefix: str) -> list[str]:
        name = node.name or "list"
        if node.action == "create":
            items = " ".join(self._val(i) for i in node.items)
            return [f"{prefix}{name}=({items})"]
        if node.action == "append":
            return [f"{prefix}{name}+=({self._val(node.value)})"]
        if node.action == "pop" and node.index:
            return [f"{prefix}unset '{name}[{self._val(node.index)}]'"]
        if node.action == "pop":
            return [f"{prefix}unset '{name}[-1]'"]
        if node.action == "len" and node.result_name:
            return [f"{prefix}{node.result_name}=${{#{name}[@]}}"]
        if node.action == "join" and node.result_name and node.value:
            return [f"{prefix}{node.result_name}=$(IFS={self._val(node.value)}; echo \"${{{name}[*]}}\")"]
        if node.action == "sort" and node.result_name:
            return [f"{prefix}{node.result_name}=($(echo \"${{{name}[@]}}\" | tr ' ' '\\n' | sort))"]
        if node.action == "contains" and node.value and node.result_name:
            return [f"{prefix}{node.result_name}=$(echo \"${{{name}[@]}}\" | grep -qw {self._val(node.value)} && echo yes || echo no)"]
        return [f"{prefix}# list op: {node.action} on {name}"]

    def _emit_dict_op(self, node: DictOp, prefix: str) -> list[str]:
        name = node.name or "dict"
        if node.action == "create":
            lines = [f"{prefix}declare -A {name}"]
            for k, v in node.items:
                lines.append(f"{prefix}{name}[{self._val(k)}]={self._val(v)}")
            return lines
        if node.action == "get" and node.key and node.result_name:
            return [f"{prefix}{node.result_name}=${{{name}[{self._val(node.key)}]}}"]
        if node.action == "set" and node.key:
            return [f"{prefix}{name}[{self._val(node.key)}]={self._val(node.value)}"]
        if node.action == "delete" and node.key:
            return [f"{prefix}unset '{name}[{self._val(node.key)}]'"]
        if node.action == "keys" and node.result_name:
            return [f"{prefix}{node.result_name}=\"${{!{name}[@]}}\""]
        if node.action == "values" and node.result_name:
            return [f"{prefix}{node.result_name}=\"${{{name}[@]}}\""]
        if node.action == "len" and node.result_name:
            return [f"{prefix}{node.result_name}=${{#{name}[@]}}"]
        if node.action == "contains" and node.key and node.result_name:
            return [f"{prefix}{node.result_name}=[[ -v {name}[{self._val(node.key)}] ]] && echo yes || echo no"]
        return [f"{prefix}# dict op: {node.action} on {name}"]

    def _emit_body(self, nodes: list[IRNode], indent: int) -> list[str]:
        lines: list[str] = []
        for node in nodes:
            lines.extend(self._emit_node(node, indent))
        return lines

    def _emit_args(self, args: list[Value]) -> str:
        return " ".join(self._val(a) for a in args)

    def _val(self, v: Value) -> str:
        if v.kind == "string":
            return f'"{v.value}"'
        if v.kind in ("int", "float"):
            return str(v.value)
        if v.kind == "bool":
            return "1" if v.value else "0"
        if v.kind == "null":
            return '""'
        if v.kind == "var":
            val_str = str(v.value)
            if val_str.startswith("$"):
                return val_str
            return f"${{{val_str}}}"
        if v.kind == "list":
            if v.parts:
                items = " ".join(self._val(p) for p in v.parts)
                return f"({items})"
            return "()"
        if v.kind == "dict":
            return '"<dict>"'
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            left, op, right = v.parts
            op_str = self._val(op).strip('"')
            if op_str in ("and", "or"):
                return f"[[ {self._val(left)} ]] {op_str} [[ {self._val(right)} ]]"
            if op_str in ("+", "-", "*", "/", "%"):
                return f"$(( {self._val(left)} {op_str} {self._val(right)} ))"
            if op_str == "//":
                return f"$(( {self._val(left)} / {self._val(right)} ))"
            if op_str == "**":
                return f"$(( {self._val(left)} ** {self._val(right)} ))"
            return f"{self._val(left)} {op_str} {self._val(right)}"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            op, operand = v.parts
            op_str = self._val(op).strip('"')
            if op_str == "not":
                return f"! {self._val(operand)}"
            return f"{op_str}{self._val(operand)}"
        if v.kind == "call" and v.parts and len(v.parts) >= 2:
            func, args = v.parts
            return f"{self._val(func)} {self._val(args)}"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2:
            base, key = v.parts
            return f"${{{self._val(base)}[{self._val(key)}]}}"
        if v.kind == "attr" and v.parts and len(v.parts) >= 2:
            base, attr = v.parts
            return f"{self._val(base)}.{self._val(attr)}"
        if v.kind == "fstring" and v.parts:
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    parts.append(str(p.value))
                elif p.kind == "var":
                    parts.append(f"${{{p.value}}}")
                else:
                    inner = self._val(p)
                    if inner.startswith('"') and inner.endswith('"'):
                        inner = inner[1:-1]
                    parts.append(inner)
            return f'"{"".join(parts)}"'
        return f'"{v.value or ""}"'

    def _val_strip(self, v: Value) -> str:
        """Value without surrounding quotes."""
        s = self._val(v)
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        return s

    def _condition(self, c: Condition) -> str:
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._condition(c.left)}{bool_map.get(c.op, ' && ')}{self._condition(c.right)})"
        left = self._val(c.left)
        right = self._val(c.right)
        op = c.op
        if op == "==" and c.right.kind == "null":
            return f"[ -z {left} ]"
        if op == "!=" and c.right.kind == "null":
            return f"[ -n {left} ]"
        if c.left.kind == "string" or c.right.kind == "string":
            return f'[ "{left}" {op} "{right}" ]'
        return f"[ {left} {op} {right} ]"


def emit_bash(ir: ScriptIR) -> str:
    return BashEmitter().emit(ir)
