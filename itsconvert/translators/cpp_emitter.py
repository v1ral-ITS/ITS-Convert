"""Emit C++ from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class CppEmitter:
    def emit(self, ir: ScriptIR) -> str:
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        lines: list[str] = ["#include <iostream>", "#include <string>", "#include <vector>", "#include <map>",
                            "#include <cstdlib>", "#include <fstream>", "#include <algorithm>", ""]
        lines.append("using namespace std;")
        lines.append("")
        for fn in fns:
            lines.extend(self._fn(fn, 0))
            lines.append("")
        lines.append("int main(int argc, char* argv[]) {")
        for node in other:
            lines.extend(self._n(node, 1))
        lines.append("    return 0;")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign): return [f"{p}auto {node.name} = {self._v(node.value)};"]
        if isinstance(node, MultiAssign): return [f"{p}auto [{', '.join(node.names)}] = {self._v(node.value)};"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)};"]
        if isinstance(node, Print):
            vals = " << " + " << ".join(self._v(v) for v in node.values) if node.values else ""
            return [f"{p}cout{vals} << endl;"]
        if isinstance(node, Input):
            return [f"{p}string {node.name};",
                    f'{p}cout << "{node.prompt}";',
                    f"{p}cin >> {node.name};"]
        if isinstance(node, Exit): return [f"{p}exit({node.code});"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for (int {node.var} = {s}; {node.var} < {e}; {node.var}++) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, For):
            return [f"{p}for (auto& {node.var} : {self._v(node.iterable)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}int {node.index_var} = 0; for (auto& {node.value_var} : {self._v(node.iterable)}) {{",
                    f"{p}    {node.index_var}++;"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for (auto& [{node.var}, _v] : {self._v(node.dict_value)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break;"]
        if isinstance(node, Continue): return [f"{p}continue;"]
        if isinstance(node, Pass): return [f"{p}// pass"]
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
            lines = [f"{p}class {node.name} {{"]
            lines.append(f"{p}public:")
            for field in node.fields:
                lines.append(f"{p}    string {field.name};")
            for method in node.methods:
                params = ", ".join(f"const string& {pp.name}" for pp in method.params if not pp.vararg and not pp.kwarg and pp.name != "self")
                lines.append(f"{p}    string {method.name}({params}) {{")
                lines.extend(self._body(method.body, i + 2))
                lines.append(f"{p}    }}")
            lines.append(f"{p}}};")
            return lines
        if isinstance(node, Lambda):
            params = ", ".join(pp.name for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}// lambda: {node.name or '_fn'} = ({params}) => {self._v(node.body)}"]
        if isinstance(node, WithBlock):
            lines = [f"{p}// with {self._v(node.expr)} as {node.var or '_ctx'}:"]
            lines.extend(self._body(node.body, i))
            return lines
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''};"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}const char* {node.result_name} = getenv("{node.name}");']
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}string {node.name}(argv[{node.index + 1}]);"]
            if node.action == "count" and node.name: return [f"{p}int {node.name} = argc;"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}try {{"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}}} catch (exception& {cv}) {{")
            lines.extend(self._body(node.catch_body, i+1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Raise): return [f"{p}throw runtime_error({self._v(node.message) if node.message else '\"Error\"'});"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, Assert): return [f"{p}assert({self._cond(node.condition)});"]
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
        params = ", ".join(f"const string& {pp.name}" for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"string {n.name}({params}) {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append("}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}vector<string> {nm} = {{{', '.join(self._v(x) for x in n.items)}}};"]
        if n.action == "append": return [f"{p}{nm}.push_back({self._v(n.value)});"]
        if n.action == "pop": return [f"{p}{nm}.pop_back();"]
        if n.action == "len" and n.result_name: return [f"{p}int {n.result_name} = {nm}.size();"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}string {n.result_name}; for (auto& s : {nm}) {{ {n.result_name} += s; {n.result_name} += {self._v(n.value)}; }}"]
        if n.action == "sort" and n.result_name: return [f"{p}sort({nm}.begin(), {nm}.end()); auto {n.result_name} = {nm};"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "m"
        if n.action == "create":
            lines = [f"{p}map<string, string> {nm};"]
            for k, v in n.items: lines.append(f"{p}{nm}[{self._v(k)}] = {self._v(v)};")
            return lines
        if n.action == "get" and n.key and n.result_name: return [f"{p}auto {n.result_name} = {nm}[{self._v(n.key)}];"]
        if n.action == "set" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = {self._v(n.value)};"]
        if n.action == "delete" and n.key: return [f"{p}{nm}.erase({self._v(n.key)});"]
        if n.action == "len" and n.result_name: return [f"{p}int {n.result_name} = {nm}.size();"]
        return [f"{p}// dict: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name:
            return [f"{p}ifstream _f({path}); string {n.name}((istreambuf_iterator<char>(_f)), istreambuf_iterator<char>());"]
        if n.op == "write" and n.content:
            return [f"{p}ofstream _of({path}); _of << {self._v(n.content)};"]
        if n.op == "exists": return [f"{p}bool {n.name or '_exists'} = ifstream({path}).good();"]
        return [f"{p}// file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind == "int": return str(v.value)
        if v.kind == "float": return f"{v.value}" if "." in str(v.value) else f"{v.value}.0"
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "nullptr"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "{" + ", ".join(self._v(p) for p in v.parts) + "}" if v.parts else "{}"
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
                    escaped = str(p.value).replace("\\", "\\\\").replace('"', '\\"')
                    parts.append(f'"{escaped}"')
                elif p.kind in ("int", "float"):
                    parts.append(f"std::to_string({self._v(p)})")
                else:
                    parts.append(f"std::string({self._v(p)})")
            return " + ".join(parts) if parts else '""'
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' && ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_cpp(ir: ScriptIR) -> str: return CppEmitter().emit(ir)
