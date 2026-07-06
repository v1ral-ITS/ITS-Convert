"""Emit Nim from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class NimEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = []
        for node in ir.nodes:
            lines.extend(self._n(node, 0))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "  " * i
        if isinstance(node, Comment): return [f"{p}# {node.text}"]
        if isinstance(node, Assign): return [f"{p}let {node.name} = {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)}"]
        if isinstance(node, Print):
            return [f"{p}echo {', '.join(self._v(v) for v in node.values) if node.values else '\"\"'}"]
        if isinstance(node, Input):
            if node.prompt: return [f'{p}stdout.write("{node.prompt}")']
            return [f"{p}let {node.name} = readLine(stdin)"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name: return [f"{p}let {node.name} = execProcess({repr(cmd)})"]
            return [f"{p}discard execProcess({repr(cmd)})"]
        if isinstance(node, Exit): return [f"{p}quit({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, For):
            return [f"{p}for {node.var} in {self._v(node.iterable)}:"] + self._body(node.body, i+1)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for {node.var} in {s}..<{e}:"] + self._body(node.body, i+1)
        if isinstance(node, ForEnumerate):
            return [f"{p}for {node.index_var}, {node.value_var} in pairs({self._v(node.iterable)}):"] + self._body(node.body, i+1)
        if isinstance(node, ForKeys):
            return [f"{p}for {node.var} in {self._v(node.dict_value)}.keys:"] + self._body(node.body, i+1)
        if isinstance(node, While):
            return [f"{p}while {self._cond(node.condition)}:"] + self._body(node.body, i+1)
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}continue"]
        if isinstance(node, Pass): return [f"{p}discard"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''}"]
        if isinstance(node, Import): return [f"{p}import {node.module}"]
        if isinstance(node, StringOpNode):
            if not node.operands: return [f"{p}# string_op: {node.op}"]
            base = self._v(node.operands[0])
            if node.op == "upper" and node.name: return [f'{p}let {node.name} = {base}.toUpperAscii()']
            if node.op == "lower" and node.name: return [f'{p}let {node.name} = {base}.toLowerAscii()']
            if node.op == "strip" and node.name: return [f'{p}let {node.name} = {base}.strip()']
            if node.op == "len" and node.name: return [f'{p}let {node.name} = {base}.len']
            if node.op == "replace" and len(node.operands) >= 3 and node.name:
                return [f'{p}let {node.name} = {base}.replace({self._v(node.operands[1])}, {self._v(node.operands[2])})']
            if node.op == "contains" and len(node.operands) >= 2 and node.name:
                return [f'{p}let {node.name} = {base}.contains({self._v(node.operands[1])})']
            if node.op == "startswith" and len(node.operands) >= 2 and node.name:
                return [f'{p}let {node.name} = {base}.startsWith({self._v(node.operands[1])})']
            if node.op == "endswith" and len(node.operands) >= 2 and node.name:
                return [f'{p}let {node.name} = {base}.endsWith({self._v(node.operands[1])})']
            return [f"{p}# string_op: {node.op}"]
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f"{p}let {node.result_name} = getEnv(\"{node.name}\")"]
            return [f"{p}# env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}let {node.name} = args[{node.index}]"]
            if node.action == "count" and node.name: return [f"{p}let {node.name} = paramCount()"]
            return [f"{p}# argv: {node.action}"]
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}try:"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}except {cv}:")
            lines.extend(self._body(node.catch_body, i+1))
            return lines
        if isinstance(node, Raise): return [f"{p}raise newException(ValueError, {self._v(node.message) if node.message else '\"Error\"'})"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, Assert): return [f"{p}assert {self._cond(node.condition)}"]
        if isinstance(node, RawBlock): return [f"{p}# raw ({node.language})"] + [f"{p}# {l}" for l in node.code.split("\n")]
        return [f"{p}# FIXME: {node.type}"]

    def _augop(self, op):
        return {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod"}.get(op, f"aug_{op}")

    def _if(self, n, i):
        p = "  " * i
        lines = [f"{p}if {self._cond(n.condition)}:"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}elif {self._cond(eb.condition)}:")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}else:")
            lines.extend(self._body(n.else_body, i+1))
        return lines

    def _fn(self, n, i):
        p = "  " * i
        params = ", ".join(f"{pp.name}: string" + (f" = {self._v(pp.default)}" if pp.default else "") for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"{p}proc {n.name}({params}): string ="]
        lines.extend(self._body(n.body, i+1))
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}let {nm} = @[{', '.join(self._v(x) for x in n.items)}]"]
        if n.action == "append": return [f"{p}{nm}.add({self._v(n.value)})"]
        if n.action == "pop": return [f"{p}discard {nm}.pop()"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = {nm}.len"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}let {n.result_name} = {nm}.join({self._v(n.value)})"]
        if n.action == "sort" and n.result_name: return [f"{p}let {n.result_name} = sorted({nm})"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}let {n.result_name} = {nm}.contains({self._v(n.value)})"]
        return [f"{p}# list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "t"
        if n.action == "create":
            if not n.items: return [f"{p}let {nm} = initTable[string, string]()"]
            lines = [f"{p}let {nm} = {{", f"{p}  {', '.join(f'{self._v(k)}: {self._v(v)}' for k, v in n.items)}", f"{p}}}.toTable"]
            return lines
        if n.action == "get" and n.key and n.result_name: return [f"{p}let {n.result_name} = {nm}[{self._v(n.key)}]"]
        if n.action == "set" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = {self._v(n.value)}"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = {nm}.len"]
        return [f"{p}# dict: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f'{p}let {n.name} = readFile({path})']
        if n.op == "write" and n.content: return [f'{p}writeFile({path}, {self._v(n.content)})']
        if n.op == "append" and n.content: return [f'{p}let _f = open({path}, fmAppend)', f'{p}_f.write({self._v(n.content)})', f'{p}_f.close()']
        if n.op == "exists" and n.name: return [f'{p}let {n.name} = fileExists({path})']
        if n.op == "mkdir": return [f'{p}createDir({path})']
        if n.op == "delete": return [f'{p}removeFile({path})']
        return [f"{p}# file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return str(v.value).capitalize()
        if v.kind == "null": return "nil"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "@[" + ", ".join(self._v(p) for p in v.parts) + "]" if v.parts else "@[]"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "and", "or": "or"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "not"}
            return f"({m.get(os, os)} {self._v(x)})"
        if v.kind == "fstring" and v.parts:
            parts = ["$" + self._v(p) if p.kind != "string" else str(p.value) for p in v.parts]
            return repr("".join(parts))
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_nim(ir: ScriptIR) -> str: return NimEmitter().emit(ir)
