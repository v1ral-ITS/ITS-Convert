"""Emit Ruby from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class RubyEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = []
        for node in ir.nodes:
            lines.extend(self._n(node, 0))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "  " * i
        if isinstance(node, Comment): return [f"{p}# {node.text}"]
        if isinstance(node, Assign): return [f"{p}{node.name} = {self._v(node.value)}"]
        if isinstance(node, MultiAssign): return [f"{p}{', '.join(node.names)} = {self._v(node.value)}"]
        if isinstance(node, AugAssign):
            op = node.op
            if op == "**": op = "**"
            return [f"{p}{node.name} {op}= {self._v(node.value)}"]
        if isinstance(node, Print):
            vals = ", ".join(self._v(v) for v in node.values) if node.values else ""
            return [f"{p}puts {vals}"]
        if isinstance(node, Input):
            if node.prompt: return [f'{p}{node.name} = readline.chomp  # {node.prompt}']
            return [f"{p}{node.name} = gets.chomp"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name: return [f"{p}{node.name} = `#{cmd}`"]
            return [f"{p}system({repr(cmd)})"]
        if isinstance(node, Exit): return [f"{p}exit({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, For):
            return [f"{p}{node.var} = {self._v(node.iterable)}"] + [f"{p}{self._v(node.iterable)}.each do |{node.var}|"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            st = f", {self._v(node.step)}" if node.step else ""
            return [f"{p}({s}...{e}).step({st or '1'}).each do |{node.var}|"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, ForEnumerate):
            return [f"{p}{self._v(node.iterable)}.each_with_index do |{node.value_var}, {node.index_var}|"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, ForKeys):
            return [f"{p}{self._v(node.dict_value)}.keys.each do |{node.var}|"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, While):
            return [f"{p}while {self._cond(node.condition)}"] + self._body(node.body, i+1) + [f"{p}end"]
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}next"]
        if isinstance(node, Pass): return [f"{p}# pass"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''}"]
        if isinstance(node, Import): return [f"{p}require '{node.module}'"]
        if isinstance(node, StringOpNode): return self._strop(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f"{p}{node.result_name} = ENV['{node.name}']"]
            if node.action == "set": return [f"{p}ENV['{node.name}'] = {self._v(node.value)}"]
            if node.action == "delete": return [f"{p}ENV.delete('{node.name}')"]
            return [f"{p}# env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "script_name" and node.name: return [f"{p}{node.name} = $0"]
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}{node.name} = ARGV[{node.index}]"]
            if node.action == "count" and node.name: return [f"{p}{node.name} = ARGV.length"]
            return [f"{p}# argv: {node.action}"]
        if isinstance(node, Switch):
            lines = [f"{p}case {self._v(node.subject)}"]
            for case in node.cases:
                lines.append(f"{p}when {self._v(case.pattern)}")
                lines.extend(self._body(case.body, i+1))
            if node.default_body:
                lines.append(f"{p}else")
                lines.extend(self._body(node.default_body, i+1))
            lines.append(f"{p}end")
            return lines
        if isinstance(node, ClassDef):
            bases = f" < {node.bases[0]}" if node.bases else ""
            lines = [f"{p}class {node.name}{bases}"]
            for field in node.fields:
                val = f" = {self._v(field.value)}" if field.value else " = nil"
                lines.append(f"{p}  @{field.name}{val}")
            for method in node.methods:
                lines.extend(self._fn(method, i+1))
            lines.append(f"{p}end")
            return lines
        if isinstance(node, Lambda):
            params = ", ".join(pp.name for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}{node.name or '_fn'} = lambda {{ |{params}| {self._v(node.body)} }}"]
        if isinstance(node, WithBlock):
            var = node.var or "_ctx"
            lines = [f"{p}begin", f"{p}  {var} = {self._v(node.expr)}"]
            lines.extend(self._body(node.body, i+1))
            lines.append(f"{p}ensure")
            lines.append(f"{p}  {var}.close if {var}.respond_to?(:close)")
            lines.append(f"{p}end")
            return lines
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}begin"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}rescue {cv}")
            lines.extend(self._body(node.catch_body, i+1))
            if node.finally_body:
                lines.append(f"{p}ensure")
                lines.extend(self._body(node.finally_body, i+1))
            lines.append(f"{p}end")
            return lines
        if isinstance(node, Raise): return [f"{p}raise {self._v(node.message) if node.message else 'RuntimeError, \"Error\"'}"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, Assert): return [f"{p}raise 'Assertion failed' unless {self._cond(node.condition)}"]
        if isinstance(node, RawBlock): return [f"{p}# raw ({node.language})"] + [f"{p}# {l}" for l in node.code.split("\n")]
        return [f"{p}# FIXME: {node.type}"]

    def _if(self, n, i):
        p = "  " * i
        lines = [f"{p}if {self._cond(n.condition)}"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}elsif {self._cond(eb.condition)}")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}else")
            lines.extend(self._body(n.else_body, i+1))
        lines.append(f"{p}end")
        return lines

    def _fn(self, n, i):
        p = "  " * i
        params = ", ".join(p.name + ("=" + self._v(p.default) if p.default else "") for p in n.params if not p.vararg and not p.kwarg)
        lines = [f"{p}def {n.name}({params})"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}end")
        return lines

    def _strop(self, n, p):
        base = self._v(n.operands[0]) if n.operands else "s"
        ops = {"upper": f"{base}.upcase", "lower": f"{base}.downcase", "strip": f"{base}.strip",
               "len": f"{base}.length",
               "replace": f"{base}.gsub({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'}, {self._v(n.operands[2]) if len(n.operands)>2 else '\"\"'})",
               "split": f"{base}.split({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
               "join": f"{self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'}.join({base})" if len(n.operands)>1 else f"{base}.join",
               "startswith": f"{base}.start_with?({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
               "endswith": f"{base}.end_with?({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
               "contains": f"{base}.include?({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})"}
        expr = ops.get(n.op, f"# {n.op}")
        if n.name: return [f"{p}{n.name} = {expr}"]
        return [f"{p}{expr}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f"{p}{n.name} = File.read({path})"]
        if n.op == "write" and n.content: return [f"{p}File.write({path}, {self._v(n.content)})"]
        if n.op == "append" and n.content: return [f"{p}File.write({path}, {self._v(n.content)}, mode: 'a')"]
        if n.op == "exists": return [f"{p}{n.name or 'exists'} = File.exist?({path})"]
        if n.op == "delete": return [f"{p}File.delete({path})"]
        if n.op == "mkdir": return [f"{p}Dir.mkdir({path})"]
        if n.op == "listdir" and n.name: return [f"{p}{n.name} = Dir.children({path})"]
        return [f"{p}# file: {n.op}"]

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}{nm} = [{', '.join(self._v(x) for x in n.items)}]"]
        if n.action == "append": return [f"{p}{nm} << {self._v(n.value)}"]
        if n.action == "pop": return [f"{p}{nm}.pop"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} = {nm}.length"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}{n.result_name} = {nm}.join({self._v(n.value)})"]
        if n.action == "sort" and n.result_name: return [f"{p}{n.result_name} = {nm}.sort"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}{n.result_name} = {nm}.include?({self._v(n.value)})"]
        return [f"{p}# list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "h"
        if n.action == "create":
            if not n.items: return [f"{p}{nm} = {{}}"]
            pairs = [f"{self._v(k)} => {self._v(v)}" for k, v in n.items]
            return [f"{p}{nm} = {{{', '.join(pairs)}}}"]
        if n.action == "get" and n.key and n.result_name: return [f"{p}{n.result_name} = {nm}[{self._v(n.key)}]"]
        if n.action == "set" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = {self._v(n.value)}"]
        if n.action == "delete" and n.key: return [f"{p}{nm}.delete({self._v(n.key)})"]
        if n.action == "keys" and n.result_name: return [f"{p}{n.result_name} = {nm}.keys"]
        if n.action == "values" and n.result_name: return [f"{p}{n.result_name} = {nm}.values"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} = {nm}.length"]
        if n.action == "contains" and n.key and n.result_name: return [f"{p}{n.result_name} = {nm}.key?({self._v(n.key)})"]
        return [f"{p}# dict: {n.action}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return str(v.value).lower()
        if v.kind == "null": return "nil"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "[" + ", ".join(self._v(p) for p in v.parts) + "]" if v.parts else "[]"
        if v.kind == "dict": return "{}"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "and", "or": "or"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "not"}
            return f"({m.get(os, os)} {self._v(x)})"
        if v.kind == "call" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}({self._v(v.parts[1])})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}[{self._v(v.parts[1])}]"
        if v.kind == "attr" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}.{self._vs(v.parts[1])}"
        if v.kind == "fstring" and v.parts:
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    escaped = str(p.value).replace("\\", "\\\\").replace('"', '\\"').replace("#{", "\\#{")
                    parts.append(escaped)
                else:
                    inner = self._v(p)
                    parts.append("#{" + inner + "}")
            return '"' + "".join(parts) + '"'

        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' && ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_rb(ir: ScriptIR) -> str: return RubyEmitter().emit(ir)
