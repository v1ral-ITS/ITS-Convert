"""Emit V from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class VLangEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ["module main", ""]
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        for fn in fns:
            lines.extend(self._fn(fn, 0))
            lines.append("")
        lines.append("fn main() {")
        for node in other:
            lines.extend(self._n(node, 1))
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "\t" * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign): return [f"{p}mut {node.name} := {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)}"]
        if isinstance(node, Print): return [f"{p}println({', '.join(self._v(v) for v in node.values) if node.values else '\"\"'})"]
        if isinstance(node, Input):
            if node.prompt: return [f'{p}print("{node.prompt}")']
            return [f"{p}{node.name} := input()"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name: return [f"{p}{node.name} := exec({repr(cmd)})"]
            return [f"{p}system({repr(cmd)})"]
        if isinstance(node, Exit): return [f"{p}exit({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for {node.var} in {s}..{e} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for {node.index_var}, {node.value_var} in {self._v(node.iterable)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for {node.var}, _ in {self._v(node.dict_value)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, For):
            return [f"{p}for {node.var} in {self._v(node.iterable)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}for {self._cond(node.condition)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}continue"]
        if isinstance(node, Pass): return [f"{p}// pass"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''}"]
        if isinstance(node, Import): return [f"{p}import {node.module}"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}{node.result_name} := os.getenv("{node.name}")']
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}{node.name} := os.args[{node.index + 1}]"]
            if node.action == "count" and node.name: return [f"{p}{node.name} := os.args.len"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, TryCatch):
            lines = [f"{p}/* V: no try-catch */"]
            lines.extend(self._body(node.try_body, i))
            return lines
        if isinstance(node, Raise): return [f"{p}panic({self._v(node.message) if node.message else '\"Error\"'})"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, Assert): return [f"{p}assert {self._cond(node.condition)}"]
        if isinstance(node, RawBlock): return [f"{p}// raw ({node.language})"] + [f"{p}// {l}" for l in node.code.split("\n")]
        return [f"{p}// FIXME: {node.type}"]

    def _if(self, n, i):
        p = "\t" * i
        lines = [f"{p}if {self._cond(n.condition)} {{"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}}} else if {self._cond(eb.condition)} {{")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}}} else {{")
            lines.extend(self._body(n.else_body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _fn(self, n, i):
        p = "\t" * i
        params = ", ".join(f"{pp.name} string" + (f" = {self._v(pp.default)}" if pp.default else "") for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"fn {n.name}({params}) string {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append("}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}mut {nm} := [{', '.join(self._v(x) for x in n.items)}]"]
        if n.action == "append": return [f"{p}{nm} << {self._v(n.value)}"]
        if n.action == "pop": return [f"{p}{nm}.pop()"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} := {nm}.len"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}{n.result_name} := {nm}.join({self._v(n.value)})"]
        if n.action == "sort" and n.result_name: return [f"{p}mut {n.result_name} := {nm}.clone(); {n.result_name}.sort()"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}{n.result_name} := {self._v(n.value)} in {nm}"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "m"
        if n.action == "create":
            lines = [f"{p}mut {nm} := map[string]string{{}}"]
            for k, v in n.items: lines.append(f"{p}{nm}[{self._v(k)}] = {self._v(v)}")
            return lines
        if n.action == "get" and n.key and n.result_name: return [f"{p}{n.result_name} := {nm}[{self._v(n.key)}]"]
        if n.action == "set" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = {self._v(n.value)}"]
        if n.action == "delete" and n.key: return [f"{p}{nm}.delete({self._v(n.key)})"]
        if n.action == "keys" and n.result_name: return [f"{p}{n.result_name} := {nm}.keys()"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} := {nm}.len"]
        return [f"{p}// dict: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f'{p}{n.name} := os.read_file({path}) or {{ "" }}']
        if n.op == "write" and n.content: return [f'{p}os.write_file({path}, {self._v(n.content)}) or {{ }}']
        if n.op == "exists" and n.name: return [f'{p}{n.name} := os.exists({path})']
        if n.op == "mkdir": return [f'{p}os.mkdir_all({path}) or {{ }}']
        return [f"{p}// file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return str(v.value).capitalize()
        if v.kind == "null": return "none"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "[" + ", ".join(self._v(p) for p in v.parts) + "]" if v.parts else "[]"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "&&", "or": "||"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "fstring" and v.parts:
            parts = [f"${{{self._v(p)}}}" if p.kind != "string" else str(p.value) for p in v.parts]
            return repr("".join(parts))
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_v(ir: ScriptIR) -> str: return VLangEmitter().emit(ir)
