"""Emit Lua from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class LuaEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = []
        for node in ir.nodes:
            lines.extend(self._n(node, 0))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}-- {node.text}"]
        if isinstance(node, Assign): return [f"{p}local {node.name} = {self._v(node.value)}"]
        if isinstance(node, MultiAssign): return [f"{p}local {', '.join(node.names)} = {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} = {node.name} {node.op} {self._v(node.value)}"]
        if isinstance(node, Print):
            args = ', '.join(self._v(v) for v in node.values) if node.values else "''"
            return [f"{p}print({args})"]
        if isinstance(node, Input):
            if node.prompt: return [f'{p}local {node.name} = io.read()  -- {node.prompt}']
            return [f"{p}local {node.name} = io.read()"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name: return [f"{p}local {node.name} = io.popen({repr(cmd)}):read('*a')"]
            return [f"{p}os.execute({repr(cmd)})"]
        if isinstance(node, Exit): return [f"{p}os.exit({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, For):
            return [f"{p}for _, {node.var} in ipairs({self._v(node.iterable)}) do"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            st = f", {self._v(node.step)}" if node.step else ""
            return [f"{p}for {node.var} = {s}, {e} - 1{st} do"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for {node.index_var}, {node.value_var} in ipairs({self._v(node.iterable)}) do"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, ForKeys):
            return [f"{p}for {node.var}, _ in pairs({self._v(node.dict_value)}) do"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, While):
            return [f"{p}while {self._cond(node.condition)} do"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}goto continue  -- Lua 5.2+"]
        if isinstance(node, Pass): return [f"{p}-- pass"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''}"]
        if isinstance(node, Import): return [f"{p}local {node.alias or node.module} = require('{node.module}')"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f"{p}local {node.result_name} = os.getenv('{node.name}')"]
            if node.action == "set": return [f"{p}os.setenv('{node.name}', {self._v(node.value)})"]
            return [f"{p}-- env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}local {node.name} = arg[{node.index}]"]
            if node.action == "count" and node.name: return [f"{p}local {node.name} = #arg"]
            return [f"{p}-- argv: {node.action}"]
        if isinstance(node, Switch):
            if not node.cases:
                return self._body(node.default_body, i)
            subj = self._v(node.subject)
            first = node.cases[0]
            lines = [f"{p}if {subj} == {self._v(first.pattern)} then"]
            lines.extend(self._body(first.body, i+1))
            for case in node.cases[1:]:
                lines.append(f"{p}elseif {subj} == {self._v(case.pattern)} then")
                lines.extend(self._body(case.body, i+1))
            if node.default_body:
                lines.append(f"{p}else")
                lines.extend(self._body(node.default_body, i+1))
            lines.append(f"{p}end")
            return lines
        if isinstance(node, ClassDef):
            return [f"{p}-- class {node.name} (not supported in this language)"]
        if isinstance(node, Lambda):
            params = ", ".join(pp.name for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}local {node.name or '_fn'} = function({params}) return {self._v(node.body)} end"]
        if isinstance(node, WithBlock):
            lines = [f"{p}-- with {self._v(node.expr)} as {node.var or '_ctx'}:"]
            lines.extend(self._body(node.body, i))
            return lines
        if isinstance(node, TryCatch):
            cv = node.catch_var or "err"
            lines = [f"{p}local ok, {cv} = pcall(function()"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}end)")
            lines.append(f"{p}if not ok then")
            lines.extend(self._body(node.catch_body, i+1))
            lines.append(f"{p}end")
            return lines
        if isinstance(node, Raise): return [f"{p}error({self._v(node.message) if node.message else '\"Error\"'})"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, Assert): return [f"{p}assert({self._cond(node.condition)}, {self._v(node.message) if node.message else '\"Assertion failed\"'})"]
        if isinstance(node, RawBlock): return [f"{p}-- raw ({node.language})"] + [f"{p}-- {l}" for l in node.code.split("\n")]
        return [f"{p}-- FIXME: {node.type}"]

    def _if(self, n, i):
        p = "    " * i
        lines = [f"{p}if {self._cond(n.condition)} then"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}elseif {self._cond(eb.condition)} then")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}else")
            lines.extend(self._body(n.else_body, i+1))
        lines.append(f"{p}end")
        return lines

    def _fn(self, n, i):
        p = "    " * i
        params = ", ".join(p.name for p in n.params if not p.vararg and not p.kwarg)
        lines = [f"{p}local function {n.name}({params})"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}end")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}local {nm} = {{{', '.join(self._v(x) for x in n.items)}}}"]
        if n.action == "append": return [f"{p}table.insert({nm}, {self._v(n.value)})"]
        if n.action == "pop": return [f"{p}table.remove({nm})"]
        if n.action == "len" and n.result_name: return [f"{p}local {n.result_name} = #{nm}"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}local {n.result_name} = table.concat({nm}, {self._v(n.value)})"]
        if n.action == "sort" and n.result_name: return [f"{p}local {n.result_name} = {{table.unpack({nm})}}; table.sort({n.result_name})"]
        if n.action == "contains" and n.value and n.result_name:
            return [f"{p}local {n.result_name} = false; for _,v in ipairs({nm}) do if v == {self._v(n.value)} then {n.result_name} = true; break end end"]
        return [f"{p}-- list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "t"
        if n.action == "create":
            if not n.items: return [f"{p}local {nm} = {{}}"]
            pairs = [f"[{self._v(k)}] = {self._v(v)}" for k, v in n.items]
            return [f"{p}local {nm} = {{{', '.join(pairs)}}}"]
        if n.action == "get" and n.key and n.result_name: return [f"{p}local {n.result_name} = {nm}[{self._v(n.key)}]"]
        if n.action == "set" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = {self._v(n.value)}"]
        if n.action == "delete" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = nil"]
        if n.action == "keys" and n.result_name: return [f"{p}local {n.result_name} = {{}}; for k in pairs({nm}) do table.insert({n.result_name}, k) end"]
        if n.action == "values" and n.result_name: return [f"{p}local {n.result_name} = {{}}; for _,v in pairs({nm}) do table.insert({n.result_name}, v) end"]
        if n.action == "len" and n.result_name: return [f"{p}local {n.result_name} = 0; for _ in pairs({nm}) do {n.result_name} = {n.result_name} + 1 end"]
        return [f"{p}-- dict: {n.action}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "nil"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "{" + ", ".join(self._v(p) for p in v.parts) + "}" if v.parts else "{}"
        if v.kind == "dict": return "{}"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "and", "or": "or", "//": "/"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "not"}
            return f"({m.get(os, os)} {self._v(x)})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}[{self._v(v.parts[1])}]"
        if v.kind == "fstring" and v.parts:
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    escaped = str(p.value).replace("\\", "\\\\").replace('"', '\\"')
                    parts.append(f'"{escaped}"')
                else:
                    parts.append(f"tostring({self._v(p)})")
            return " .. ".join(parts) if parts else '""'

        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " and ", "or": " or "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' and ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_lua(ir: ScriptIR) -> str: return LuaEmitter().emit(ir)
