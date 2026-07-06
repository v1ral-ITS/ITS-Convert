"""Emit Scala from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class ScalaEmitter:
    def emit(self, ir: ScriptIR) -> str:
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        lines: list[str] = ["object Main {", ""]
        for fn in fns:
            lines.extend(self._fn(fn, 1))
            lines.append("")
        lines.append("  def main(args: Array[String]): Unit = {")
        for node in other:
            lines.extend(self._n(node, 2))
        lines.append("  }")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign): return [f"{p}val {node.name} = {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} = {node.name} {node.op} {self._v(node.value)}"]
        if isinstance(node, Print): return [f"{p}println({', '.join(self._v(v) for v in node.values) if node.values else '\"\"'})"]
        if isinstance(node, Input):
            return [f"{p}val {node.name} = scala.io.StdIn.readLine(\"{node.prompt}\")"]
        if isinstance(node, Exit): return [f"{p}sys.exit({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for ({node.var} <- {s} until {e}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for (({node.index_var}, {node.value_var}) <- {self._v(node.iterable)}.zipWithIndex) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for ({node.var} <- {self._v(node.dict_value)}.keys) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, For):
            return [f"{p}for ({node.var} <- {self._v(node.iterable)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''}"]
        if isinstance(node, StringOpNode):
            if not node.operands: return [f"{p}// string_op: {node.op}"]
            base = self._v(node.operands[0])
            if node.op == "upper" and node.name: return [f'{p}val {node.name} = {base}.toUpperCase']
            if node.op == "lower" and node.name: return [f'{p}val {node.name} = {base}.toLowerCase']
            if node.op == "strip" and node.name: return [f'{p}val {node.name} = {base}.trim']
            if node.op == "len" and node.name: return [f'{p}val {node.name} = {base}.length']
            if node.op == "replace" and len(node.operands) >= 3 and node.name:
                return [f'{p}val {node.name} = {base}.replace({self._v(node.operands[1])}, {self._v(node.operands[2])})']
            if node.op == "contains" and len(node.operands) >= 2 and node.name:
                return [f'{p}val {node.name} = {base}.contains({self._v(node.operands[1])})']
            if node.op == "startswith" and len(node.operands) >= 2 and node.name:
                return [f'{p}val {node.name} = {base}.startsWith({self._v(node.operands[1])})']
            if node.op == "endswith" and len(node.operands) >= 2 and node.name:
                return [f'{p}val {node.name} = {base}.endsWith({self._v(node.operands[1])})']
            return [f"{p}// string_op: {node.op}"]
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}val {node.result_name} = sys.env("{node.name}")']
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}val {node.name} = args({node.index})"]
            if node.action == "count" and node.name: return [f"{p}val {node.name} = args.length"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}try {{"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}}} catch {{ case {cv}: Exception =>")
            lines.extend(self._body(node.catch_body, i+1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Raise): return [f"{p}throw new Exception({self._v(node.message) if node.message else '\"Error\"'})"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, Assert): return [f"{p}assert({self._cond(node.condition)})"]
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
        lines = [f"{p}def {n.name}({params}): String = {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}val {nm} = List({', '.join(self._v(x) for x in n.items)})"]
        if n.action == "append": return [f"{p}val {nm} = {nm} :+ {self._v(n.value)}"]
        if n.action == "len" and n.result_name: return [f"{p}val {n.result_name} = {nm}.length"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}val {n.result_name} = {nm}.mkString({self._v(n.value)})"]
        if n.action == "sort" and n.result_name: return [f"{p}val {n.result_name} = {nm}.sorted"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}val {n.result_name} = {nm}.contains({self._v(n.value)})"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "map"
        if n.action == "create":
            lines = [f"{p}val {nm} = scala.collection.mutable.Map[String, String]()"]
            for k, v in n.items: lines.append(f"{p}{nm}({self._v(k)}) = {self._v(v)}")
            return lines
        if n.action == "get" and n.key and n.result_name: return [f"{p}val {n.result_name} = {nm}({self._v(n.key)})"]
        if n.action == "set" and n.key: return [f"{p}{nm}({self._v(n.key)}) = {self._v(n.value)}"]
        if n.action == "keys" and n.result_name: return [f"{p}val {n.result_name} = {nm}.keys.toList"]
        if n.action == "len" and n.result_name: return [f"{p}val {n.result_name} = {nm}.size"]
        return [f"{p}// dict: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f'{p}val {n.name} = scala.io.Source.fromFile({path}).mkString']
        if n.op == "write" and n.content:
            return [f'{p}val _pw = new java.io.PrintWriter(new java.io.File({path}))',
                    f'{p}_pw.write({self._v(n.content)})',
                    f'{p}_pw.close()']
        if n.op == "exists" and n.name: return [f'{p}val {n.name} = new java.io.File({path}).exists()']
        if n.op == "mkdir": return [f'{p}new java.io.File({path}).mkdirs()']
        return [f"{p}// file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return str(v.value).capitalize()
        if v.kind == "null": return "null"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "List(" + ", ".join(self._v(p) for p in v.parts) + ")" if v.parts else "List()"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "&&", "or": "||"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "fstring" and v.parts:
            parts = [f"s\"${{{self._v(p)}}}\"" if p.kind != "string" else str(p.value) for p in v.parts]
            return "s\"" + "".join(parts) + "\""
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_scala(ir: ScriptIR) -> str: return ScalaEmitter().emit(ir)
