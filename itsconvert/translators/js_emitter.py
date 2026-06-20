"""Emit JavaScript from IR."""
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


class JSEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ['"use strict";', ""]
        for node in ir.nodes:
            lines.extend(self._emit_node(node, indent=0))
        return "\n".join(lines) + "\n"

    def _emit_node(self, node: IRNode, indent: int) -> list[str]:
        p = "  " * indent
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign): return [f"{p}let {node.name} = {self._v(node.value)};"]
        if isinstance(node, MultiAssign): return [f"{p}let [{', '.join(node.names)}] = {self._v(node.value)};"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)};"]
        if isinstance(node, Print):
            args = ', '.join(self._v(v) for v in node.values) if node.values else "''"
            return [f"{p}console.log({args});"]
        if isinstance(node, Input):
            if node.prompt:
                return [f'{p}let {node.name} = prompt("{node.prompt}");']
            return [f"{p}let {node.name} = prompt();"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name:
                return [f"{p}let {node.name} = exec({self._s(cmd)});"]
            return [f"{p}// shell: {cmd}"]
        if isinstance(node, Exit): return [f"{p}process.exit({node.code});"]
        if isinstance(node, If): return self._if(node, indent)
        if isinstance(node, For): return [f"{p}for (let {node.var} of {self._v(node.iterable)}) {{"] + self._body(node.body, indent+1) + [f"{p}}}"]
        if isinstance(node, ForRange):
            s = self._v(node.start); e = self._v(node.stop); st = f", {self._v(node.step)}" if node.step else ""
            return [f"{p}for (let {node.var} = {s}; {node.var} < {e}; {node.var} += {st or '1'}) {{"] + self._body(node.body, indent+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for (let [{node.index_var}, {node.value_var}] of {self._v(node.iterable)}.entries()) {{"] + self._body(node.body, indent+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for (let {node.var} of Object.keys({self._v(node.dict_value)})) {{"] + self._body(node.body, indent+1) + [f"{p}}}"]
        if isinstance(node, While): return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, indent+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break;"]
        if isinstance(node, Continue): return [f"{p}continue;"]
        if isinstance(node, Pass): return [f"{p}// pass"]
        if isinstance(node, FunctionDef): return self._fn(node, indent)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''};"]
        if isinstance(node, Import):
            if node.names: return [f"{p}// import {{{', '.join(node.names)}}} from '{node.module}'"]
            return [f"{p}// import '{node.module}'"]
        if isinstance(node, StringOpNode): return self._strop(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f"{p}let {node.result_name} = process.env.{node.name};"]
            if node.action == "set": return [f"{p}process.env.{node.name} = {self._v(node.value)};"]
            if node.action == "delete": return [f"{p}delete process.env.{node.name};"]
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "script_name" and node.name: return [f"{p}let {node.name} = process.argv[1];"]
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}let {node.name} = process.argv[{node.index + 2}];"]
            if node.action == "count" and node.name: return [f"{p}let {node.name} = process.argv.length;"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, Switch):
            lines = [f"{p}switch ({self._v(node.subject)}) {{"]
            for case in node.cases:
                lines.append(f"{p}  case {self._v(case.pattern)}:")
                lines.extend(self._body(case.body, indent + 2))
                lines.append(f"{p}    break;")
            if node.default_body:
                lines.append(f"{p}  default:")
                lines.extend(self._body(node.default_body, indent + 2))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, ClassDef):
            bases = f" extends {node.bases[0]}" if node.bases else ""
            lines = [f"{p}class {node.name}{bases} {{"]
            for field in node.fields:
                val = f" = {self._v(field.value)}" if field.value else ""
                lines.append(f"{p}  {field.name}{val};")
            for method in node.methods:
                lines.extend(self._fn(method, indent + 1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Lambda):
            params = ", ".join(pp.name for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}let {node.name or '_fn'} = ({params}) => {self._v(node.body)};"]
        if isinstance(node, WithBlock):
            var = node.var or "_ctx"
            lines = [f"{p}const {var} = {self._v(node.expr)};"]
            lines.append(f"{p}try {{")
            lines.extend(self._body(node.body, indent + 1))
            lines.append(f"{p}}} finally {{")
            lines.append(f"{p}  if ({var}.close) {var}.close();")
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, TryCatch):
            cv = node.catch_var or "err"
            lines = [f"{p}try {{"]
            lines.extend(self._body(node.try_body, indent+1))
            lines.append(f"{p}}} catch ({cv}) {{")
            lines.extend(self._body(node.catch_body, indent+1))
            if node.finally_body:
                lines.append(f"{p}}} finally {{")
                lines.extend(self._body(node.finally_body, indent+1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Raise): return [f"{p}throw new Error({self._v(node.message) if node.message else '\"Error\"'});"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, Assert): return [f"{p}if (!({self._cond(node.condition)})) {{ throw new Error({self._v(node.message) if node.message else '\"Assertion failed\"'}); }}"]
        if isinstance(node, RawBlock): return [f"{p}// raw ({node.language})"] + [f"{p}// {l}" for l in node.code.split("\n")]
        return [f"{p}// FIXME: {node.type}"]

    def _if(self, n: If, ind: int) -> list[str]:
        p = "  " * ind
        lines = [f"{p}if ({self._cond(n.condition)}) {{"]
        lines.extend(self._body(n.then_body, ind+1))
        for eb in n.elif_branches:
            lines.append(f"{p}}} else if ({self._cond(eb.condition)}) {{")
            lines.extend(self._body(eb.body, ind+1))
        if n.else_body:
            lines.append(f"{p}}} else {{")
            lines.extend(self._body(n.else_body, ind+1))
        lines.append(f"{p}}}")
        return lines

    def _fn(self, n: FunctionDef, ind: int) -> list[str]:
        p = "  " * ind
        params = ", ".join(p.name + (f"={self._v(p.default)}" if p.default else "") for p in n.params if not p.vararg and not p.kwarg)
        lines = [f"{p}function {n.name}({params}) {{"]
        lines.extend(self._body(n.body, ind+1))
        lines.append(f"{p}}}")
        return lines

    def _strop(self, n: StringOpNode, p: str) -> list[str]:
        op_map = {"upper": "toUpperCase()", "lower": "toLowerCase()", "strip": "trim()", "len": ".length",
                   "replace": f".replace({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'}, {self._v(n.operands[2]) if len(n.operands)>2 else '\"\"'})",
                   "split": f".split({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
                   "join": f".join({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
                   "startswith": f".startsWith({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
                   "endswith": f".endsWith({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
                   "contains": f".includes({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})"}
        expr = f"{self._v(n.operands[0])}{op_map.get(n.op, '')}" if n.operands else f"/* {n.op} */"
        if n.name: return [f"{p}let {n.name} = {expr};"]
        return [f"{p}{expr};"]

    def _file(self, n: FileIONode, p: str) -> list[str]:
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f"{p}let {n.name} = require('fs').readFileSync({path}, 'utf-8');"]
        if n.op == "write" and n.content: return [f"{p}require('fs').writeFileSync({path}, {self._v(n.content)});"]
        if n.op == "append" and n.content: return [f"{p}require('fs').appendFileSync({path}, {self._v(n.content)});"]
        if n.op == "exists": return [f"{p}let {n.name or 'exists'} = require('fs').existsSync({path});"]
        if n.op == "delete": return [f"{p}require('fs').unlinkSync({path});"]
        if n.op == "mkdir": return [f"{p}require('fs').mkdirSync({path}, {{recursive: true}});"]
        if n.op == "listdir" and n.name: return [f"{p}let {n.name} = require('fs').readdirSync({path});"]
        return [f"{p}// file: {n.op}"]

    def _list(self, n: ListOp, p: str) -> list[str]:
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}let {nm} = [{', '.join(self._v(i) for i in n.items)}];"]
        if n.action == "append": return [f"{p}{nm}.push({self._v(n.value)});"]
        if n.action == "pop": return [f"{p}{nm}.pop();"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = {nm}.length;"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}let {n.result_name} = {nm}.join({self._v(n.value)});"]
        if n.action == "sort" and n.result_name: return [f"{p}let {n.result_name} = [...{nm}].sort();"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}let {n.result_name} = {nm}.includes({self._v(n.value)});"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n: DictOp, p: str) -> list[str]:
        nm = n.name or "obj"
        if n.action == "create":
            if not n.items: return [f"{p}let {nm} = {{}};"]
            pairs = [f"{self._v(k)}: {self._v(v)}" for k, v in n.items]
            return [f"{p}let {nm} = {{{', '.join(pairs)}}};"]
        if n.action == "get" and n.key and n.result_name: return [f"{p}let {n.result_name} = {nm}[{self._v(n.key)}];"]
        if n.action == "set" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = {self._v(n.value)};"]
        if n.action == "delete" and n.key: return [f"{p}delete {nm}[{self._v(n.key)}];"]
        if n.action == "keys" and n.result_name: return [f"{p}let {n.result_name} = Object.keys({nm});"]
        if n.action == "values" and n.result_name: return [f"{p}let {n.result_name} = Object.values({nm});"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = Object.keys({nm}).length;"]
        if n.action == "contains" and n.key and n.result_name: return [f"{p}let {n.result_name} = {self._v(n.key)} in {nm};"]
        return [f"{p}// dict: {n.action}"]

    def _body(self, nodes: list[IRNode], ind: int) -> list[str]:
        r: list[str] = []
        for n in nodes: r.extend(self._emit_node(n, ind))
        return r
    def _args(self, a: list[Value]) -> str: return " ".join(self._v(x) for x in a)

    def _v(self, v: Value) -> str:
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "null"
        if v.kind == "var": return str(v.value)
        if v.kind == "list":
            return "[" + ", ".join(self._v(p) for p in v.parts) + "]" if v.parts else "[]"
        if v.kind == "dict": return "{}"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o)
            m = {"and": "&&", "or": "||", "//": "/"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o)
            m = {"not": "!"}
            return f"({m.get(os, os)}{self._v(x)})"
        if v.kind == "call" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}({self._v(v.parts[1])})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}[{self._v(v.parts[1])}]"
        if v.kind == "attr" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}.{self._vs(v.parts[1])}"
        if v.kind == "fstring" and v.parts:
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    escaped = str(p.value).replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                    parts.append(escaped)
                else:
                    parts.append(f"${{{self._v(p)}}}")
            return "`" + "".join(parts) + "`"
        return repr(v.value)

    def _s(self, s: str) -> str: return repr(s)
    def _vs(self, v: Value) -> str: s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s

    def _cond(self, c: Condition) -> str:
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' && ')}{self._cond(c.right)})"
        m = {"==": "===", "!=": "!===", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        o = m.get(c.op, c.op)
        if c.right.kind == "null": return f"{self._v(c.left)} === null"
        return f"{self._v(c.left)} {o} {self._v(c.right)}"

def emit_js(ir: ScriptIR) -> str: return JSEmitter().emit(ir)
