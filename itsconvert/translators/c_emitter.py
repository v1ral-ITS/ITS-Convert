"""Emit C from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, AugAssign, Print, Input, Exit,
    If, ElifBranch, ForRange, While,
    Break, Continue, FunctionDef, Return, Import,
    StringOpNode, EnvVar, Argv, TryCatch, Raise,
    ListOp, Assert, RawBlock,
)


class CEmitter:
    def emit(self, ir: ScriptIR) -> str:
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        lines: list[str] = ["#include <stdio.h>", "#include <stdlib.h>", "#include <string.h>", ""]
        for fn in fns:
            lines.extend(self._fn(fn, 0))
            lines.append("")
        lines.append("int main(int argc, char *argv[]) {")
        for node in other:
            lines.extend(self._n(node, 1))
        lines.append("    return 0;")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}/* {node.text} */"]
        if isinstance(node, Assign):
            if node.value.kind == "int": return [f"{p}int {node.name} = {self._v(node.value)};"]
            if node.value.kind == "float": return [f"{p}double {node.name} = {self._v(node.value)};"]
            if node.value.kind == "bool": return [f"{p}int {node.name} = {self._v(node.value)};"]
            return [f"{p}const char* {node.name} = {self._v(node.value)};"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)};"]
        if isinstance(node, Print):
            if not node.values: return [f'{p}printf("\\n");']
            fmts = []
            args = []
            for v in node.values:
                if v.kind == "int": fmts.append("%d"); args.append(self._v(v))
                elif v.kind == "float": fmts.append("%f"); args.append(self._v(v))
                elif v.kind == "bool": fmts.append("%d"); args.append(self._v(v))
                elif v.kind == "string": fmts.append("%s"); args.append(self._v(v))
                else: fmts.append("%s"); args.append(self._v(v))
            fmt = " ".join(fmts) + "\\n"
            a = ", ".join(args)
            return [f'{p}printf("{fmt}"{", " + a if a else ""});']
        if isinstance(node, Input):
            return [f'{p}char {node.name}[256];',
                    f'{p}printf("{node.prompt}");',
                    f"{p}scanf(\"%255s\", {node.name});"]
        if isinstance(node, Exit): return [f"{p}exit({node.code});"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for (int {node.var} = {s}; {node.var} < {e}; {node.var}++) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break;"]
        if isinstance(node, Continue): return [f"{p}continue;"]
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''};"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}const char* {node.result_name} = getenv("{node.name}");']
            return [f"{p}/* env: {node.action} */"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}const char* {node.name} = argv[{node.index + 1}];"]
            if node.action == "count" and node.name: return [f"{p}int {node.name} = argc;"]
            return [f"{p}/* argv: {node.action} */"]
        if isinstance(node, Raise): return [f"{p}fprintf(stderr, {self._v(node.message) if node.message else '\"Error\"'}); exit(1);"]
        if isinstance(node, Assert): return [f"{p}assert({self._cond(node.condition)});"]
        if isinstance(node, RawBlock): return [f"{p}/* raw ({node.language}) */"] + [f"{p}/* {l} */" for l in node.code.split("\n")]
        return [f"{p}/* FIXME: {node.type} */"]

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
        params = ", ".join(f"const char* {pp.name}" for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"int {n.name}({params}) {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append("}")
        return lines

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind == "int": return str(v.value)
        if v.kind == "float": return f"{v.value}" if "." in str(v.value) else f"{v.value}.0"
        if v.kind == "bool": return "1" if v.value else "0"
        if v.kind == "null": return "NULL"
        if v.kind == "var": return str(v.value)
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "&&", "or": "||"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "fstring" and v.parts:
            parts = [f"\" %s \"" if p.kind != "string" else str(p.value) for p in v.parts]
            return repr("".join(parts))
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_c(ir: ScriptIR) -> str: return CEmitter().emit(ir)
