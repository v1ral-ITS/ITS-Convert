"""Emit PowerShell script from IR."""
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


class PowerShellEmitter:
    """Emit PowerShell from ScriptIR."""

    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = []
        for node in ir.nodes:
            lines.extend(self._emit_node(node, indent=0))
        return "\n".join(lines) + "\n"

    def _emit_node(self, node: IRNode, indent: int) -> list[str]:
        prefix = "    " * indent
        if isinstance(node, Comment):
            return [f"{prefix}# {node.text}"]
        if isinstance(node, Assign):
            return [f"{prefix}${node.name} = {self._val(node.value)}"]
        if isinstance(node, MultiAssign):
            vals = self._val(node.value)
            return [f"{prefix}# Multi-assign"] + [f"{prefix}${n} = {vals}" for n in node.names]
        if isinstance(node, AugAssign):
            op_map = {"and": "-and", "or": "-or"}
            ps_op = op_map.get(node.op, node.op)
            return [f"{prefix}${node.name} {ps_op}= {self._val(node.value)}"]
        if isinstance(node, Print):
            if not node.values:
                return [f"{prefix}Write-Host"]
            parts = [self._val(v) for v in node.values]
            joined = ", ".join(parts)
            if node.end != "\n":
                return [f"{prefix}Write-Host -NoNewline {joined}"]
            return [f"{prefix}Write-Host {joined}"]
        if isinstance(node, Input):
            if node.prompt:
                return [f'{prefix}${node.name} = Read-Host "{node.prompt}"']
            return [f"{prefix}${node.name} = Read-Host"]
        if isinstance(node, Command):
            args = self._emit_args(node.args)
            cmd = f"{node.command} {args}".strip()
            if node.capture and node.name:
                return [f"{prefix}${node.name} = {cmd}"]
            return [f"{prefix}{cmd}"]
        if isinstance(node, Exit):
            return [f"{prefix}exit {node.code}"]
        if isinstance(node, If):
            return self._emit_if(node, indent)
        if isinstance(node, For):
            return self._emit_for(node, indent)
        if isinstance(node, ForRange):
            return self._emit_for_range(node, indent)
        if isinstance(node, ForEnumerate):
            lines = [f"{prefix}${node.index_var} = 0"]
            lines.append(f"{prefix}foreach (${node.value_var} in {self._val(node.iterable)}) {{")
            for child in node.body:
                lines.extend(self._emit_node(child, indent + 1))
            lines.append(f"{prefix}    ${node.index_var}++")
            lines.append(f"{prefix}}}")
            return lines
        if isinstance(node, ForKeys):
            return [f"{prefix}foreach (${node.var} in {self._val(node.dict_value)}.Keys) {{"] + \
                   self._emit_body(node.body, indent + 1) + [f"{prefix}}}"]
        if isinstance(node, While):
            cond = self._condition(node.condition)
            return [f"{prefix}while ({cond}) {{"] + self._emit_body(node.body, indent + 1) + [f"{prefix}}}"]
        if isinstance(node, Break):
            return [f"{prefix}break"]
        if isinstance(node, Continue):
            return [f"{prefix}continue"]
        if isinstance(node, Pass):
            return [f"{prefix}# pass"]
        if isinstance(node, FunctionDef):
            return self._emit_function(node, indent)
        if isinstance(node, Return):
            if node.value:
                return [f"{prefix}return {self._val(node.value)}"]
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
            prefix = "    " * indent
            lines = [f"{prefix}switch ({self._val(node.subject)}) {{"]
            for case in node.cases:
                lines.append(f"{prefix}  {self._val(case.pattern)} {{")
                lines.extend(self._emit_body(case.body, indent + 2))
                lines.append(f"{prefix}  }}")
            if node.default_body:
                lines.append(f"{prefix}  default {{")
                lines.extend(self._emit_body(node.default_body, indent + 2))
                lines.append(f"{prefix}  }}")
            lines.append(f"{prefix}}}")
            return lines
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
            return [f"{prefix}Write-Error {msg}", f"{prefix}exit 1"]
        if isinstance(node, ListOp):
            return self._emit_list_op(node, prefix)
        if isinstance(node, DictOp):
            return self._emit_dict_op(node, prefix)
        if isinstance(node, Assert):
            cond = self._condition(node.condition)
            msg = f' -Message {self._val(node.message)}' if node.message else ""
            return [f"{prefix}if (-not ({cond})) {{ Write-Error{msg}; exit 1 }}"]
        if isinstance(node, RawBlock):
            return [f"{prefix}# --- raw ({node.language}) ---"] + [f"{prefix}# {l}" for l in node.code.split("\n")]
        return [f"{prefix}# FIXME: unsupported node type: {node.type}"]

    def _emit_if(self, node: If, indent: int) -> list[str]:
        prefix = "    " * indent
        cond = self._condition(node.condition)
        lines = [f"{prefix}if ({cond}) {{"]
        lines.extend(self._emit_body(node.then_body, indent + 1))
        for elif_b in node.elif_branches:
            elif_cond = self._condition(elif_b.condition)
            lines.append(f"{prefix}}} elseif ({elif_cond}) {{")
            lines.extend(self._emit_body(elif_b.body, indent + 1))
        if node.else_body:
            lines.append(f"{prefix}else {{")
            lines.extend(self._emit_body(node.else_body, indent + 1))
        lines.append(f"{prefix}}}")
        return lines

    def _emit_for(self, node: For, indent: int) -> list[str]:
        prefix = "    " * indent
        lines = [f"{prefix}foreach (${node.var} in {self._val(node.iterable)}) {{"]
        lines.extend(self._emit_body(node.body, indent + 1))
        lines.append(f"{prefix}}}")
        return lines

    def _emit_for_range(self, node: ForRange, indent: int) -> list[str]:
        prefix = "    " * indent
        start = self._val(node.start)
        stop = self._val(node.stop)
        step = self._val(node.step) if node.step else "1"
        lines = [f"{prefix}for (${node.var} = {start}; ${node.var} -lt {stop}; ${node.var} += {step}) {{"]
        lines.extend(self._emit_body(node.body, indent + 1))
        lines.append(f"{prefix}}}")
        return lines

    def _emit_function(self, node: FunctionDef, indent: int) -> list[str]:
        prefix = "    " * indent
        params = []
        for p in node.params:
            s = f"[string]${p.name}"
            if p.default:
                s += f" = {self._val(p.default)}"
            params.append(s)
        param_block = ""
        if params:
            param_block = f"\n{prefix}    param(\n" + f",\n".join(f"{prefix}        {p}" for p in params) + f"\n{prefix}    )"
        lines = [f"{prefix}function {node.name} {{{param_block}"]
        lines.extend(self._emit_body(node.body, indent + 1))
        lines.append(f"{prefix}}}")
        return lines

    def _emit_string_op(self, node: StringOpNode, prefix: str) -> list[str]:
        op = node.op
        if op == "len" and node.operands:
            return [f"{prefix}$({self._val(node.operands[0])}).Length"]
        if op == "upper" and node.operands:
            return [f"{prefix}$({self._val(node.operands[0])}).ToUpper()"]
        if op == "lower" and node.operands:
            return [f"{prefix}$({self._val(node.operands[0])}).ToLower()"]
        if op == "strip" and node.operands:
            return [f"{prefix}$({self._val(node.operands[0])}).Trim()"]
        if op == "replace" and len(node.operands) >= 3:
            return [f"{prefix}$({self._val(node.operands[0])}).Replace({self._val(node.operands[1])}, {self._val(node.operands[2])})"]
        if op == "split" and len(node.operands) >= 2:
            return [f"{prefix}$({self._val(node.operands[0])}).Split({self._val(node.operands[1])})"]
        if op == "join" and len(node.operands) >= 2:
            return [f"{prefix}{self._val(node.operands[0])} -join {self._val(node.operands[1])}"]
        if op == "startswith" and len(node.operands) >= 2:
            return [f"{prefix}$({self._val(node.operands[0])}).StartsWith({self._val(node.operands[1])})"]
        if op == "endswith" and len(node.operands) >= 2:
            return [f"{prefix}$({self._val(node.operands[0])}).EndsWith({self._val(node.operands[1])})"]
        if op == "contains" and len(node.operands) >= 2:
            return [f"{prefix}$({self._val(node.operands[0])}).Contains({self._val(node.operands[1])})"]
        return [f"{prefix}# string op: {op}"]

    def _emit_file_io(self, node: FileIONode, prefix: str) -> list[str]:
        path = self._val(node.path)
        if node.op == "read" and node.name:
            return [f"{prefix}${node.name} = Get-Content {path}"]
        if node.op == "read":
            return [f"{prefix}Get-Content {path}"]
        if node.op == "write" and node.content:
            return [f"{prefix}Set-Content -Path {path} -Value {self._val(node.content)}"]
        if node.op == "append" and node.content:
            return [f"{prefix}Add-Content -Path {path} -Value {self._val(node.content)}"]
        if node.op == "exists":
            name = node.name or "exists"
            return [f"{prefix}${name} = Test-Path {path}"]
        if node.op == "delete":
            return [f"{prefix}Remove-Item {path}"]
        if node.op == "mkdir":
            return [f"{prefix}New-Item -ItemType Directory -Path {path}"]
        if node.op == "listdir" and node.name:
            return [f"{prefix}${node.name} = Get-ChildItem {path}"]
        if node.op == "basename" and node.name:
            return [f"{prefix}${node.name} = Split-Path {path} -Leaf"]
        if node.op == "dirname" and node.name:
            return [f"{prefix}${node.name} = Split-Path {path} -Parent"]
        return [f"{prefix}# file op: {node.op} {path}"]

    def _emit_env_var(self, node: EnvVar, prefix: str) -> list[str]:
        if node.action == "get":
            name = node.result_name or node.name.lower()
            return [f"{prefix}${name} = $env:{node.name}"]
        if node.action == "set":
            return [f"{prefix}$env:{node.name} = {self._val(node.value)}"]
        if node.action == "delete":
            return [f"{prefix}Remove-Item Env:{node.name}"]
        if node.action == "list":
            return [f"{prefix}Get-ChildItem Env:"]
        return [f"{prefix}# env: {node.action} {node.name}"]

    def _emit_argv(self, node: Argv, prefix: str) -> list[str]:
        if node.action == "script_name":
            name = node.name or "script"
            return [f"{prefix}${name} = $PSCommandPath"]
        if node.action == "all":
            name = node.name or "args"
            return [f"{prefix}${name} = $args"]
        if node.action == "nth" and node.index is not None:
            name = node.name or f"arg{node.index}"
            return [f"{prefix}${name} = $args[{node.index}]"]
        if node.action == "count":
            name = node.name or "argc"
            return [f"{prefix}${name} = $args.Count"]
        return [f"{prefix}# argv: {node.action}"]

    def _emit_try(self, node: TryCatch, indent: int) -> list[str]:
        prefix = "    " * indent
        lines = [f"{prefix}try {{"]
        lines.extend(self._emit_body(node.try_body, indent + 1))
        catch_var = node.catch_var or "_"
        lines.append(f"{prefix}}} catch [{catch_var}] {{")
        lines.extend(self._emit_body(node.catch_body, indent + 1))
        if node.finally_body:
            lines.append(f"{prefix}}} finally {{")
            lines.extend(self._emit_body(node.finally_body, indent + 1))
        lines.append(f"{prefix}}}")
        return lines

    def _emit_list_op(self, node: ListOp, prefix: str) -> list[str]:
        name = f"${node.name}" if node.name else "$list"
        if node.action == "create":
            items = ", ".join(self._val(i) for i in node.items)
            return [f"{prefix}{name} = @({items})"]
        if node.action == "append":
            return [f"{prefix}{name} += {self._val(node.value)}"]
        if node.action == "pop":
            return [f"{prefix}{name} = {name}[0..({name}.Count-2)]"]
        if node.action == "len" and node.result_name:
            return [f"{prefix}${node.result_name} = {name}.Count"]
        if node.action == "sort" and node.result_name:
            return [f"{prefix}${node.result_name} = {name} | Sort-Object"]
        if node.action == "join" and node.result_name and node.value:
            return [f"{prefix}${node.result_name} = {name} -join {self._val(node.value)}"]
        if node.action == "contains" and node.value and node.result_name:
            return [f"{prefix}${node.result_name} = {node.value} -in {name}"]
        return [f"{prefix}# list op: {node.action} on {name}"]

    def _emit_dict_op(self, node: DictOp, prefix: str) -> list[str]:
        name = f"${node.name}" if node.name else "$dict"
        if node.action == "create":
            if not node.items:
                return [f"{prefix}{name} = @{{}}"]
            pairs = [f"{self._val(k)} = {self._val(v)}" for k, v in node.items]
            return [f"{prefix}{name} = @{{{'; '.join(pairs)}}}"]
        if node.action == "get" and node.key and node.result_name:
            return [f"{prefix}${node.result_name} = {name}[{self._val(node.key)}]"]
        if node.action == "set" and node.key:
            return [f"{prefix}{name}[{self._val(node.key)}] = {self._val(node.value)}"]
        if node.action == "delete" and node.key:
            return [f"{prefix}{name}.Remove({self._val(node.key)})"]
        if node.action == "keys" and node.result_name:
            return [f"{prefix}${node.result_name} = {name}.Keys"]
        if node.action == "values" and node.result_name:
            return [f"{prefix}${node.result_name} = {name}.Values"]
        if node.action == "len" and node.result_name:
            return [f"{prefix}${node.result_name} = {name}.Count"]
        if node.action == "contains" and node.key and node.result_name:
            return [f"{prefix}${node.result_name} = {name}.ContainsKey({self._val(node.key)})"]
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
            return "$true" if v.value else "$false"
        if v.kind == "null":
            return "$null"
        if v.kind == "var":
            return f"${v.value}"
        if v.kind == "list":
            if v.parts:
                items = ", ".join(self._val(p) for p in v.parts)
                return f"@({items})"
            return "@()"
        if v.kind == "dict":
            return "@{}"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            left, op, right = v.parts
            ps_op = {"and": "-and", "or": "-or", "//": "/", "**": "*",
                      "+": "+", "-": "-", "*": "*", "/": "/", "%": "%",
                      "==": "-eq", "!=": "-ne", "<": "-lt", "<=": "-le",
                      ">": "-gt", ">=": "-ge"}.get(self._val_strip(op), self._val(op))
            return f"({self._val(left)} {ps_op} {self._val(right)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            op, operand = v.parts
            ps_op = {"not": "-not", "-": "-"}.get(self._val_strip(op), self._val(op))
            return f"({ps_op} {self._val(operand)})"
        if v.kind == "call" and v.parts and len(v.parts) >= 2:
            func, args = v.parts
            return f"{self._val(func)} {self._val(args)}"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2:
            base, key = v.parts
            return f"{self._val(base)}[{self._val(key)}]"
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
        s = self._val(v)
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        return s

    def _condition(self, c: Condition) -> str:
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " -and ", "or": " -or "}
            return f"({self._condition(c.left)}{bool_map.get(c.op, ' -and ')}{self._condition(c.right)})"
        op_map = {"==": "-eq", "!=": "-ne", ">": "-gt", "<": "-lt", ">=": "-ge", "<=": "-le"}
        ps_op = op_map.get(c.op, c.op)
        if c.right.kind == "null":
            if c.op == "==" or c.op == "is":
                return f"-not ${self._val_strip(c.left)}"
            return f"[bool]${self._val_strip(c.left)}"
        return f"{self._val(c.left)} {ps_op} {self._val(c.right)}"


def emit_ps1(ir: ScriptIR) -> str:
    return PowerShellEmitter().emit(ir)
