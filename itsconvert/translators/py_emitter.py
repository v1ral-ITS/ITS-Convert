"""Emit Python source from IR."""
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


class PyEmitter:
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
            return [f"{prefix}{node.name} = {self._val(node.value)}"]
        if isinstance(node, MultiAssign):
            return [f"{prefix}{', '.join(node.names)} = {self._val(node.value)}"]
        if isinstance(node, AugAssign):
            return [f"{prefix}{node.name} {node.op}= {self._val(node.value)}"]
        if isinstance(node, Print):
            vals = ", ".join(self._val(v) for v in node.values)
            if node.end != "\n":
                return [f"{prefix}print({vals}, end={repr(node.end)})"]
            return [f"{prefix}print({vals})"]
        if isinstance(node, Input):
            return [f'{prefix}{node.name} = input("{node.prompt}")']
        if isinstance(node, Command):
            cmd = f"{node.command} {self._emit_args(node.args)}".strip()
            if node.capture and node.name:
                return [f"{prefix}{node.name} = subprocess.run({repr(cmd)}, shell=True, capture_output=True, text=True)"]
            return [f"{prefix}subprocess.run({repr(cmd)}, shell=True)"]
        if isinstance(node, Exit):
            return [f"{prefix}sys.exit({node.code})"]
        if isinstance(node, If):
            return self._emit_if(node, indent)
        if isinstance(node, For):
            return [f"{prefix}for {node.var} in {self._val(node.iterable)}:"] + self._emit_body(node.body, indent + 1)
        if isinstance(node, ForRange):
            args = [self._val(node.start), self._val(node.stop)]
            if node.step:
                args.append(self._val(node.step))
            return [f"{prefix}for {node.var} in range({', '.join(args)}):"] + self._emit_body(node.body, indent + 1)
        if isinstance(node, ForEnumerate):
            return [f"{prefix}for {node.index_var}, {node.value_var} in enumerate({self._val(node.iterable)}):"] + self._emit_body(node.body, indent + 1)
        if isinstance(node, ForKeys):
            return [f"{prefix}for {node.var} in {self._val(node.dict_value)}:"] + self._emit_body(node.body, indent + 1)
        if isinstance(node, While):
            return [f"{prefix}while {self._condition(node.condition)}:"] + self._emit_body(node.body, indent + 1)
        if isinstance(node, Break):
            return [f"{prefix}break"]
        if isinstance(node, Continue):
            return [f"{prefix}continue"]
        if isinstance(node, Pass):
            return [f"{prefix}pass"]
        if isinstance(node, FunctionDef):
            return self._emit_function(node, indent)
        if isinstance(node, Return):
            if node.value:
                return [f"{prefix}return {self._val(node.value)}"]
            return [f"{prefix}return"]
        if isinstance(node, Import):
            if node.names:
                return [f"{prefix}from {node.module} import {', '.join(node.names)}"]
            if node.alias:
                return [f"{prefix}import {node.module} as {node.alias}"]
            return [f"{prefix}import {node.module}"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name:
                return [f"{prefix}{node.result_name} = os.environ.get({repr(node.name)})"]
            if node.action == "set":
                return [f"{prefix}os.environ[{repr(node.name)}] = {self._val(node.value)}"]
            if node.action == "delete":
                return [f"{prefix}del os.environ[{repr(node.name)}]"]
            return [f"{prefix}# env: {node.action} {node.name}"]
        if isinstance(node, Argv):
            if node.action == "script_name" and node.name:
                return [f"{prefix}{node.name} = sys.argv[0]"]
            if node.action == "nth" and node.index is not None and node.name:
                return [f"{prefix}{node.name} = sys.argv[{node.index + 1}]"]
            if node.action == "count" and node.name:
                return [f"{prefix}{node.name} = len(sys.argv)"]
            return [f"{prefix}# argv: {node.action}"]
        if isinstance(node, Switch):
            prefix = "    " * indent
            lines = [f"{prefix}match {self._val(node.subject)}:"]
            for case in node.cases:
                lines.append(f"{prefix}    case {self._val(case.pattern)}:")
                lines.extend(self._emit_body(case.body, indent + 2))
            if node.default_body:
                lines.append(f"{prefix}    case _:")
                lines.extend(self._emit_body(node.default_body, indent + 2))
            return lines
        if isinstance(node, ClassDef):
            prefix = "    " * indent
            bases = f"({', '.join(node.bases)})" if node.bases else ""
            lines = [f"{prefix}class {node.name}{bases}:"]
            if not node.fields and not node.methods:
                lines.append(f"{prefix}    pass")
                return lines
            for field in node.fields:
                val = f" = {self._val(field.value)}" if field.value else ""
                lines.append(f"{prefix}    {field.name}{val}")
            for method in node.methods:
                lines.extend(self._emit_function(method, indent + 1))
            return lines
        if isinstance(node, Lambda):
            prefix = "    " * indent
            params = ", ".join(pp.name for pp in node.params)
            return [f"{prefix}{node.name or '_fn'} = lambda {params}: {self._val(node.body)}"]
        if isinstance(node, WithBlock):
            prefix = "    " * indent
            as_clause = f" as {node.var}" if node.var else ""
            lines = [f"{prefix}with {self._val(node.expr)}{as_clause}:"]
            lines.extend(self._emit_body(node.body, indent + 1))
            return lines
        if isinstance(node, TryCatch):
            lines = [f"{prefix}try:"]
            lines.extend(self._emit_body(node.try_body, indent + 1))
            exc = f" as {node.catch_var}" if node.catch_var else ""
            lines.append(f"{prefix}except{exc}:")
            lines.extend(self._emit_body(node.catch_body, indent + 1))
            if node.finally_body:
                lines.append(f"{prefix}finally:")
                lines.extend(self._emit_body(node.finally_body, indent + 1))
            return lines
        if isinstance(node, Raise):
            if node.exc_type and node.message:
                return [f"{prefix}raise {node.exc_type}({self._val(node.message)})"]
            if node.message:
                return [f"{prefix}raise RuntimeError({self._val(node.message)})"]
            return [f"{prefix}raise"]
        if isinstance(node, FileIONode):
            path = self._val(node.path)
            if node.op == "read" and node.name:
                return [f"{prefix}{node.name} = Path({path}).read_text()"]
            if node.op == "write" and node.content:
                return [f"{prefix}Path({path}).write_text({self._val(node.content)})"]
            if node.op == "append" and node.content:
                return [f"{prefix}Path({path}).write_text({self._val(node.content)}, append=True)"]
            if node.op == "exists":
                name = node.name or "exists"
                return [f"{prefix}{name} = Path({path}).exists()"]
            return [f"{prefix}# file: {node.op} {path}"]
        if isinstance(node, ListOp):
            name = node.name or "lst"
            if node.action == "create":
                items = ", ".join(self._val(i) for i in node.items)
                return [f"{prefix}{name} = [{items}]"]
            if node.action == "append":
                return [f"{prefix}{name}.append({self._val(node.value)})"]
            if node.action == "len" and node.result_name:
                return [f"{prefix}{node.result_name} = len({name})"]
            return [f"{prefix}# list: {node.action} {name}"]
        if isinstance(node, DictOp):
            name = node.name or "d"
            if node.action == "create":
                pairs = [f"{self._val(k)}: {self._val(v)}" for k, v in node.items]
                return [f"{prefix}{name} = {{{', '.join(pairs)}}}"]
            return [f"{prefix}# dict: {node.action} {name}"]
        if isinstance(node, Assert):
            msg = f", {self._val(node.message)}" if node.message else ""
            return [f"{prefix}assert {self._condition(node.condition)}{msg}"]
        if isinstance(node, RawBlock):
            return [f"{prefix}# --- raw ({node.language}) ---"] + [f"{prefix}# {l}" for l in node.code.split("\n")]
        return [f"{prefix}# FIXME: {node.type}"]

    def _emit_if(self, node: If, indent: int) -> list[str]:
        prefix = "    " * indent
        lines = [f"{prefix}if {self._condition(node.condition)}:"]
        lines.extend(self._emit_body(node.then_body, indent + 1))
        for elif_b in node.elif_branches:
            lines.append(f"{prefix}elif {self._condition(elif_b.condition)}:")
            lines.extend(self._emit_body(elif_b.body, indent + 1))
        if node.else_body:
            lines.append(f"{prefix}else:")
            lines.extend(self._emit_body(node.else_body, indent + 1))
        return lines

    def _emit_function(self, node: FunctionDef, indent: int) -> list[str]:
        prefix = "    " * indent
        params = []
        for p in node.params:
            s = p.name
            if p.type_hint:
                s += f": {p.type_hint}"
            if p.default:
                s += f"={self._val(p.default)}"
            if p.vararg:
                s = f"*{s}"
            if p.kwarg:
                s = f"**{s}"
            params.append(s)
        lines = [f"{prefix}def {node.name}({', '.join(params)}):"]
        lines.extend(self._emit_body(node.body, indent + 1))
        return lines

    def _emit_body(self, nodes: list[IRNode], indent: int) -> list[str]:
        lines: list[str] = []
        for node in nodes:
            lines.extend(self._emit_node(node, indent))
        if not lines:
            lines.append("    " * indent + "pass")
        return lines

    def _emit_args(self, args: list[Value]) -> str:
        return " ".join(self._val(a) for a in args)

    def _val(self, v: Value) -> str:
        if v.kind == "string":
            return repr(str(v.value))
        if v.kind in ("int", "float"):
            return str(v.value)
        if v.kind == "bool":
            return str(v.value)
        if v.kind == "null":
            return "None"
        if v.kind == "var":
            return str(v.value)
        if v.kind == "list":
            if v.parts:
                return "[" + ", ".join(self._val(p) for p in v.parts) + "]"
            return "[]"
        if v.kind == "dict":
            return "{}"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            left, op, right = v.parts
            return f"{self._val(left)} {self._val_strip(op)} {self._val(right)}"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            op, operand = v.parts
            return f"{self._val_strip(op)} {self._val(operand)}"
        if v.kind == "call" and v.parts and len(v.parts) >= 2:
            func, args = v.parts
            return f"{self._val(func)}({self._val(args)})"
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
                    parts.append(str(p.value).replace("\\", "\\\\").replace('"', '\\"').replace('{', '{{').replace('}', '}}'))
                else:
                    parts.append("{" + self._val(p) + "}")
            return 'f"' + "".join(parts) + '"'
        return repr(v.value)

    def _val_strip(self, v: Value) -> str:
        s = self._val(v)
        if s.startswith("'") and s.endswith("'"):
            return s[1:-1]
        return s

    def _condition(self, c: Condition) -> str:
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " and ", "or": " or "}
            return f"({self._condition(c.left)}{bool_map.get(c.op, ' and ')}{self._condition(c.right)})"
        op_map = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._val(c.left)} {op_map.get(c.op, c.op)} {self._val(c.right)}"


def emit_py(ir: ScriptIR) -> str:
    return PyEmitter().emit(ir)
