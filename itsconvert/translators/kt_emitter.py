"""Emit Kotlin from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class KotlinEmitter:
    def emit(self, ir: ScriptIR) -> str:
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        lines: list[str] = ["fun main(args: Array<String>) {"]
        for node in other:
            lines.extend(self._n(node, 1))
        lines.append("}")
        for fn in fns:
            lines.append("")
            lines.extend(self._fn(fn, 0))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign): return [f"{p}var {node.name} = {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)}"]
        if isinstance(node, Print): return [f"{p}println({', '.join(self._v(v) for v in node.values) if node.values else '\"\"'})"]
        if isinstance(node, Input):
            return [f'{p}print("{node.prompt}")',
                    f"{p}var {node.name} = readlnOrNull() ?: \"\""]
        if isinstance(node, Exit): return [f"{p}exitProcess({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for ({node.var} in {s} until {e}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, For):
            return [f"{p}for ({node.var} in {self._v(node.iterable)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for (({node.index_var}, {node.value_var}) in {self._v(node.iterable)}.withIndex()) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for ({node.var} in {self._v(node.dict_value)}.keys) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}continue"]
        if isinstance(node, Pass): return [f"{p}// pass"]
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''}"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}val {node.result_name} = System.getenv("{node.name}")']
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}val {node.name} = args[{node.index}]"]
            if node.action == "count" and node.name: return [f"{p}val {node.name} = args.size"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, Switch):
            lines = [f"{p}when ({self._v(node.subject)}) {{"]
            for case in node.cases:
                lines.append(f"{p}    {self._v(case.pattern)} -> {{")
                lines.extend(self._body(case.body, i+2))
                lines.append(f"{p}    }}")
            if node.default_body:
                lines.append(f"{p}    else -> {{")
                lines.extend(self._body(node.default_body, i+2))
                lines.append(f"{p}    }}")
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, ClassDef):
            bases = f"({node.bases[0]})" if node.bases else ""
            lines = [f"{p}class {node.name}{bases} {{"]
            for field in node.fields:
                val = f" = {self._v(field.value)}" if field.value else ""
                lines.append(f"{p}    var {field.name}: Any{val}")
            for method in node.methods:
                lines.extend(self._fn(method, i+1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Lambda):
            params = ", ".join(f"{pp.name}: Any" for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}val {node.name or '_fn'} = {{ {params} -> {self._v(node.body)} }}"]
        if isinstance(node, WithBlock):
            lines = [f"{p}# with {self._v(node.expr)} as {node.var or '_ctx'}:"]
            lines.extend(self._body(node.body, i))
            return lines
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}try {{"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}}} catch ({cv}: Exception) {{")
            lines.extend(self._body(node.catch_body, i+1))
            if node.finally_body:
                lines.append(f"{p}}} finally {{")
                lines.extend(self._body(node.finally_body, i+1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Raise): return [f"{p}throw Exception({self._v(node.message) if node.message else '\"Error\"'})"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, Assert): return [f"{p}check({self._cond(node.condition)})"]
        if isinstance(node, RawBlock): return [f"{p}// raw ({node.language})"] + [f"{p}// {l}" for l in node.code.split("\n")]
        return [f"{p}// FIXME: {node.type}"]

    def _if(self, n, i):
        p = "    " * i
        lines = [f"{p}if ({self._cond(n.condition)}) {{"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}}} else if ({self._cond(eb.condition)}) {{")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}}} else {{")
            lines.extend(self._body(n.else_body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _fn(self, n, i):
        p = "    " * i
        params = ", ".join(f"{pp.name}: String" + (f" = {self._v(pp.default)}" if pp.default else "") for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"fun {n.name}({params}): String {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append("}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}var {nm} = mutableListOf({', '.join(self._v(x) for x in n.items)})"]
        if n.action == "append": return [f"{p}{nm}.add({self._v(n.value)})"]
        if n.action == "pop": return [f"{p}{nm}.removeLast()"]
        if n.action == "len" and n.result_name: return [f"{p}val {n.result_name} = {nm}.size"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}val {n.result_name} = {nm}.joinToString({self._v(n.value)})"]
        if n.action == "sort" and n.result_name: return [f"{p}{nm}.sort(); val {n.result_name} = {nm}"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}val {n.result_name} = {nm}.contains({self._v(n.value)})"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "map"
        if n.action == "create":
            lines = [f"{p}var {nm} = mutableMapOf<String, Any>()"]
            for k, v in n.items: lines.append(f"{p}{nm}[{self._v(k)}] = {self._v(v)}")
            return lines
        if n.action == "get" and n.key and n.result_name: return [f"{p}val {n.result_name} = {nm}[{self._v(n.key)}]"]
        if n.action == "set" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = {self._v(n.value)}"]
        if n.action == "delete" and n.key: return [f"{p}{nm}.remove({self._v(n.key)})"]
        if n.action == "keys" and n.result_name: return [f"{p}val {n.result_name} = {nm}.keys"]
        if n.action == "values" and n.result_name: return [f"{p}val {n.result_name} = {nm}.values"]
        if n.action == "len" and n.result_name: return [f"{p}val {n.result_name} = {nm}.size"]
        if n.action == "contains" and n.key and n.result_name: return [f"{p}val {n.result_name} = {nm}.containsKey({self._v(n.key)})"]
        return [f"{p}// dict: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f"{p}val {node.name} = File({path}).readText()"]
        if n.op == "write" and n.content: return [f"{p}File({path}).writeText({self._v(n.content)})"]
        if n.op == "exists": return [f"{p}val {n.name or '_ex'} = File({path}).exists()"]
        return [f"{p}// file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return str(v.value).lower()
        if v.kind == "null": return "null"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "listOf(" + ", ".join(self._v(p) for p in v.parts) + ")" if v.parts else "listOf()"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "&&", "or": "||"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "!"}
            return f"({m.get(os, os)}{self._v(x)})"
        if v.kind == "fstring" and v.parts:
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    escaped = str(p.value).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
                    parts.append(escaped)
                elif p.kind == "var":
                    parts.append(f"${p.value}")
                else:
                    inner = self._v(p)
                    parts.append("${" + inner + "}")
            return '"' + "".join(parts) + '"'

        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' && ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_kt(ir: ScriptIR) -> str: return KotlinEmitter().emit(ir)
