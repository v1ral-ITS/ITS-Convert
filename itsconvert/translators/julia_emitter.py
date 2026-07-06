"""Emit Julia from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class JuliaEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = []
        for node in ir.nodes:
            lines.extend(self._n(node, 0))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}# {node.text}"]
        if isinstance(node, Assign): return [f"{p}{node.name} = {self._v(node.value)}"]
        if isinstance(node, MultiAssign): return [f"{p}{', '.join(node.names)} = {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)}"]
        if isinstance(node, Print):
            if not node.values: return [f"{p}println()"]
            args = ", ".join(self._v(v) for v in node.values)
            if node.end == "":
                return [f"{p}print({args})"]
            return [f"{p}println({args})"]
        if isinstance(node, Input):
            if node.prompt: return [f'{p}print("{node.prompt}")', f"{p}{node.name} = readline()"]
            return [f"{p}{node.name} = readline()"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name: return [f"{p}{node.name} = read(`{cmd}`, String)"]
            return [f"{p}run(`{cmd}`)"]
        if isinstance(node, Exit): return [f"{p}exit({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            step = f":{self._v(node.step)}" if node.step else ""
            return [f"{p}for {node.var} in {s}{step}:{e}-1"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for ({node.index_var}, {node.value_var}) in enumerate({self._v(node.iterable)})"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, ForKeys):
            return [f"{p}for {node.var} in keys({self._v(node.dict_value)})"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, For):
            return [f"{p}for {node.var} in {self._v(node.iterable)}"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, While):
            return [f"{p}while {self._cond(node.condition)}"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}continue"]
        if isinstance(node, Pass): return [f"{p}nothing"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''}"]
        if isinstance(node, Import): return [f"{p}using {node.module}"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}{node.result_name} = get(ENV, "{node.name}", "")']
            if node.action == "set": return [f'{p}ENV["{node.name}"] = {self._v(node.value)}']
            if node.action == "delete": return [f'{p}delete!(ENV, "{node.name}")']
            return [f"{p}# env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}{node.name} = ARGS[{node.index + 1}]"]
            if node.action == "count" and node.name: return [f"{p}{node.name} = length(ARGS)"]
            return [f"{p}# argv: {node.action}"]
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}try"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}catch {cv}")
            lines.extend(self._body(node.catch_body, i+1))
            if node.finally_body:
                lines.append(f"{p}finally")
                lines.extend(self._body(node.finally_body, i+1))
            lines.append(f"{p}end")
            return lines
        if isinstance(node, Raise):
            msg = self._v(node.message) if node.message else '"Error"'
            return [f"{p}throw(ErrorException({msg}))"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, StringOpNode): return self._strop(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, Assert): return [f"{p}@assert {self._cond(node.condition)}"]
        if isinstance(node, RawBlock): return [f"{p}# raw ({node.language})"] + [f"{p}# {l}" for l in node.code.split("\n")]
        return [f"{p}# FIXME: {node.type}"]

    def _if(self, n, i):
        p = "    " * i
        lines = [f"{p}if {self._cond(n.condition)}"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}elseif {self._cond(eb.condition)}")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}else")
            lines.extend(self._body(n.else_body, i+1))
        lines.append(f"{p}end")
        return lines

    def _fn(self, n, i):
        p = "    " * i
        params = ", ".join(
            pp.name + (f"={self._v(pp.default)}" if pp.default else "")
            for pp in n.params if not pp.vararg and not pp.kwarg
        )
        lines = [f"{p}function {n.name}({params})"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}end")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}{nm} = [{', '.join(self._v(x) for x in n.items)}]"]
        if n.action == "append": return [f"{p}push!({nm}, {self._v(n.value)})"]
        if n.action == "pop": return [f"{p}pop!({nm})"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} = length({nm})"]
        if n.action == "sort" and n.result_name: return [f"{p}{n.result_name} = sort({nm})"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}{n.result_name} = {self._v(n.value)} in {nm}"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}{n.result_name} = join({nm}, {self._v(n.value)})"]
        return [f"{p}# list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "d"
        if n.action == "create":
            if not n.items: return [f'{p}{nm} = Dict{{String, Any}}()']
            pairs = [f"{self._v(k)} => {self._v(v)}" for k, v in n.items]
            return [f'{p}{nm} = Dict({", ".join(pairs)})']
        if n.action == "get" and n.key and n.result_name: return [f'{p}{n.result_name} = get({nm}, {self._v(n.key)}, nothing)']
        if n.action == "set" and n.key: return [f'{p}{nm}[{self._v(n.key)}] = {self._v(n.value)}']
        if n.action == "delete" and n.key: return [f'{p}delete!({nm}, {self._v(n.key)})']
        if n.action == "keys" and n.result_name: return [f'{p}{n.result_name} = collect(keys({nm}))']
        if n.action == "values" and n.result_name: return [f'{p}{n.result_name} = collect(values({nm}))']
        if n.action == "len" and n.result_name: return [f'{p}{n.result_name} = length({nm})']
        return [f"{p}# dict: {n.action}"]

    def _strop(self, n, p):
        if not n.operands: return [f"{p}# string_op: {n.op}"]
        base = self._v(n.operands[0])
        if n.op == "upper" and n.name: return [f'{p}{n.name} = uppercase({base})']
        if n.op == "lower" and n.name: return [f'{p}{n.name} = lowercase({base})']
        if n.op == "strip" and n.name: return [f'{p}{n.name} = strip({base})']
        if n.op == "len" and n.name: return [f'{p}{n.name} = length({base})']
        if n.op == "replace" and len(n.operands) >= 3 and n.name:
            return [f'{p}{n.name} = replace({base}, {self._v(n.operands[1])} => {self._v(n.operands[2])})']
        if n.op == "split" and len(n.operands) >= 2 and n.name:
            return [f'{p}{n.name} = split({base}, {self._v(n.operands[1])})']
        if n.op == "contains" and len(n.operands) >= 2 and n.name:
            return [f'{p}{n.name} = occursin({self._v(n.operands[1])}, {base})']
        return [f"{p}# string_op: {n.op}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f'{p}{n.name} = read({path}, String)']
        if n.op == "write" and n.content: return [f'{p}write({path}, {self._v(n.content)})']
        if n.op == "append" and n.content:
            return [f'{p}open({path}, "a") do _f', f'{p}    write(_f, {self._v(n.content)})', f'{p}end']
        if n.op == "exists" and n.name: return [f'{p}{n.name} = isfile({path})']
        if n.op == "mkdir": return [f'{p}mkpath({path})']
        if n.op == "delete": return [f'{p}rm({path})']
        return [f"{p}# file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)

    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind == "int": return str(v.value)
        if v.kind == "float": return f"{v.value}" if "." in str(v.value) else f"{v.value}.0"
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "nothing"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "[" + ", ".join(self._v(p) for p in v.parts) + "]" if v.parts else "[]"
        if v.kind == "dict": return "Dict()"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o)
            m = {"and": "&&", "or": "||", "//": "div"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o)
            m = {"not": "!"}
            return f"({m.get(os, os)}{self._v(x)})"
        if v.kind == "call" and v.parts and len(v.parts) >= 2:
            fn = self._vs(v.parts[0])
            args = ", ".join(self._v(a) for a in (v.parts[1].parts or [])) if v.parts[1].parts is not None else self._v(v.parts[1])
            return f"{fn}({args})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2:
            return f"{self._v(v.parts[0])}[{self._v(v.parts[1])}]"
        if v.kind == "fstring" and v.parts:
            parts = [f"$({self._v(p)})" if p.kind != "string" else str(p.value) for p in v.parts]
            return '"' + "".join(parts) + '"'
        return repr(v.value)

    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'", '"')) else s

    def _cond(self, c):
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"


def emit_julia(ir: ScriptIR) -> str: return JuliaEmitter().emit(ir)
