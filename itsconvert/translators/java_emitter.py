"""Emit Java from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class JavaEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ["import java.util.*;", "import java.io.*;", "", "public class Main {", ""]
        # First pass: collect top-level functions as static methods
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        for fn in fns:
            lines.extend(self._fn(fn, 1))
            lines.append("")
        lines.append("    public static void main(String[] args) {")
        for node in other:
            lines.extend(self._n(node, 2))
        lines.append("    }")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign):
            t, init = self._decl(node.value)
            return [f"{p}{t} {node.name} = {init};"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)};"]
        if isinstance(node, Print):
            vals = " + " + " + ".join(self._v(v) for v in node.values) if node.values else ""
            return [f"{p}System.out.println({', '.join(self._v(v) for v in node.values) if node.values else '\"\"'});"]
        if isinstance(node, Input):
            return [f"{p}java.util.Scanner scanner = new java.util.Scanner(System.in);",
                    f'{p}System.out.print("{node.prompt}");',
                    f"{p}String {node.name} = scanner.nextLine();"]
        if isinstance(node, Exit): return [f"{p}System.exit({node.code});"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for (int {node.var} = {s}; {node.var} < {e}; {node.var}++) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, For):
            return [f"{p}for (var {node.var} : {self._v(node.iterable)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break;"]
        if isinstance(node, Continue): return [f"{p}continue;"]
        if isinstance(node, Pass): return [f"{p}// pass"]
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''};"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}String {node.result_name} = System.getenv("{node.name}");']
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}String {node.name} = args[{node.index}];"]
            if node.action == "count" and node.name: return [f"{p}int {node.name} = args.length;"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}try {{"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}}} catch (Exception {cv}) {{")
            lines.extend(self._body(node.catch_body, i+1))
            if node.finally_body:
                lines.append(f"{p}}} finally {{")
                lines.extend(self._body(node.finally_body, i+1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Raise): return [f"{p}throw new RuntimeException({self._v(node.message) if node.message else '\"Error\"'});"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, Assert): return [f"{p}assert {self._cond(node.condition)} : \"Assertion failed\";"]
        if isinstance(node, RawBlock): return [f"{p}// raw ({node.language})"] + [f"{p}// {l}" for l in node.code.split("\n")]
        return [f"{p}// FIXME: {node.type}"]

    def _decl(self, v):
        m = {"int": ("int", self._v(v)), "float": ("double", self._v(v)),
             "string": ("String", self._v(v)), "bool": ("boolean", self._v(v)),
             "null": ("Object", "null"), "var": ("var", self._v(v))}
        return m.get(v.kind, ("var", self._v(v)))

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
        params = ", ".join(f"String {pp.name}" for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"{p}public static String {n.name}({params}) {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}var {nm} = new ArrayList<>(List.of({', '.join(self._v(x) for x in n.items)}));"]
        if n.action == "append": return [f"{p}{nm}.add({self._v(n.value)});"]
        if n.action == "pop": return [f"{p}{nm}.remove({nm}.size() - 1);"]
        if n.action == "len" and n.result_name: return [f"{p}int {n.result_name} = {nm}.size();"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}String {n.result_name} = String.join({self._v(n.value)}, {nm});"]
        if n.action == "sort" and n.result_name: return [f"{p}Collections.sort({nm}); var {n.result_name} = {nm};"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}boolean {n.result_name} = {nm}.contains({self._v(n.value)});"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "map"
        if n.action == "create":
            lines = [f"{p}var {nm} = new HashMap<String, Object>();"]
            for k, v in n.items: lines.append(f"{p}{nm}.put({self._v(k)}, {self._v(v)});")
            return lines
        if n.action == "get" and n.key and n.result_name: return [f"{p}var {n.result_name} = {nm}.get({self._v(n.key)});"]
        if n.action == "set" and n.key: return [f"{p}{nm}.put({self._v(n.key)}, {self._v(n.value)});"]
        if n.action == "delete" and n.key: return [f"{p}{nm}.remove({self._v(n.key)});"]
        if n.action == "keys" and n.result_name: return [f"{p}var {n.result_name} = {nm}.keySet();"]
        if n.action == "values" and n.result_name: return [f"{p}var {n.result_name} = {nm}.values();"]
        if n.action == "len" and n.result_name: return [f"{p}int {n.result_name} = {nm}.size();"]
        return [f"{p}// dict: {n.action}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind == "int": return str(v.value)
        if v.kind == "float": return f"{v.value}" if "." in str(v.value) else f"{v.value}.0"
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "null"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "List.of(" + ", ".join(self._v(p) for p in v.parts) + ")" if v.parts else "List.of()"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "&&", "or": "||"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "!"}
            return f"({m.get(os, os)}{self._v(x)})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}.get({self._v(v.parts[1])})"
        if v.kind == "fstring" and v.parts:
            parts = [f"\" + {self._v(p)} + \"" if p.kind != "string" else str(p.value) for p in v.parts]
            return repr("".join(parts))
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_java(ir: ScriptIR) -> str: return JavaEmitter().emit(ir)
