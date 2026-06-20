"""Emit C from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, AugAssign, Print, Input, Exit,
    If, ElifBranch, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, FunctionDef, Return, Import,
    StringOpNode, EnvVar, Argv, TryCatch, Raise,
    ListOp, Assert, RawBlock,
    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class CEmitter:
    def emit(self, ir: ScriptIR) -> str:
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        lines: list[str] = ["#include <stdio.h>", "#include <stdlib.h>", "#include <string.h>", "#include <assert.h>", ""]
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
                f, a = self._printf_parts(v)
                fmts.append(f)
                args.extend(a)
            fmt_str = " ".join(fmts) + "\\n"
            a_str = ", ".join(args)
            return [f'{p}printf("{fmt_str}"{", " + a_str if a_str else ""});']
        if isinstance(node, Input):
            return [f'{p}char {node.name}[256];',
                    f'{p}printf("{node.prompt}");',
                    f"{p}scanf(\"%255s\", {node.name});"]
        if isinstance(node, Exit): return [f"{p}exit({node.code});"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for (int {node.var} = {s}; {node.var} < {e}; {node.var}++) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}/* for enumerate: use index manually */",
                    f"{p}int {node.index_var} = 0;",
                    f"{p}/* {node.value_var} = item */"] + self._body(node.body, i) + [f"{p}{node.index_var}++;"]
        if isinstance(node, ForKeys):
            return [f"{p}/* ForKeys not directly supported in C */"] + self._body(node.body, i)
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break;"]
        if isinstance(node, Continue): return [f"{p}continue;"]
        if isinstance(node, Switch):
            lines = [f"{p}switch ({self._v(node.subject)}) {{"]
            for case in node.cases:
                lines.append(f"{p}    case {self._v(case.pattern)}:")
                lines.extend(self._body(case.body, i + 2))
                lines.append(f"{p}        break;")
            if node.default_body:
                lines.append(f"{p}    default:")
                lines.extend(self._body(node.default_body, i + 2))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, ClassDef):
            lines = [f"{p}/* class {node.name} */", f"{p}typedef struct {{"]
            for field in node.fields:
                lines.append(f"{p}    const char* {field.name};")
            lines.append(f"{p}}} {node.name};")
            for method in node.methods:
                params = f"{node.name}* self"
                extra = ", ".join(f"const char* {pp.name}" for pp in method.params if not pp.vararg and not pp.kwarg and pp.name != "self")
                if extra:
                    params += ", " + extra
                lines.append(f"{p}void {node.name}_{method.name}({params}) {{")
                lines.extend(self._body(method.body, i + 1))
                lines.append(f"{p}}}")
            return lines
        if isinstance(node, Lambda):
            params = ", ".join(pp.name for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}/* lambda: {node.name or '_fn'} = ({params}) => {self._v(node.body)} */"]
        if isinstance(node, WithBlock):
            lines = [f"{p}/* with {self._v(node.expr)} as {node.var or '_ctx'}: */"]
            lines.extend(self._body(node.body, i))
            return lines
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

    def _printf_parts(self, v) -> tuple[str, list[str]]:
        if v.kind == "int": return ("%d", [self._v(v)])
        if v.kind == "float": return ("%f", [self._v(v)])
        if v.kind == "bool": return ("%d", [self._v(v)])
        if v.kind == "string": return (str(v.value).replace('"', '\\"').replace("%", "%%"), [])
        if v.kind == "fstring" and v.parts:
            fmt = ""
            args = []
            for p in v.parts:
                if p.kind == "string":
                    fmt += str(p.value).replace('"', '\\"').replace("%", "%%")
                elif p.kind == "int":
                    fmt += "%d"
                    args.append(self._v(p))
                elif p.kind == "float":
                    fmt += "%f"
                    args.append(self._v(p))
                else:
                    fmt += "%s"
                    args.append(self._v(p))
            return (fmt, args)
        return ("%s", [self._v(v)])

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
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    parts.append(str(p.value).replace('"', '\\"'))
                else:
                    parts.append("%s")
            return '"' + "".join(parts) + '"'
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' && ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_c(ir: ScriptIR) -> str: return CEmitter().emit(ir)
