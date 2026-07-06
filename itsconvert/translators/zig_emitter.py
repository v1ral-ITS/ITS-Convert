"""Emit Zig from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, AugAssign, Print, Input, Exit,
    If, ElifBranch, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, FunctionDef, Return, Import,
    EnvVar, Argv, TryCatch, Raise,
    Assert, RawBlock,
)


class ZigEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ['const std = @import("std");', ""]
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        for fn in fns:
            lines.extend(self._fn(fn, 0))
            lines.append("")
        lines.append("pub fn main() !void {")
        for node in other:
            lines.extend(self._n(node, 1))
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign):
            if node.value.kind == "int": return [f"{p}var {node.name}: i32 = {self._v(node.value)};"]
            if node.value.kind == "float": return [f"{p}var {node.name}: f64 = {self._v(node.value)};"]
            if node.value.kind == "bool": return [f"{p}var {node.name}: bool = {self._v(node.value)};"]
            return [f"{p}var {node.name} = {self._v(node.value)};"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)};"]
        if isinstance(node, Print):
            vals = " ".join(self._v(v) for v in node.values)
            return [f'{p}std.debug.print("{vals}\\n", .{{}});']
        if isinstance(node, Input): return [f"{p}// Zig: stdin not trivial; var {node.name}: [256]u8 = undefined;"]
        if isinstance(node, Exit): return [f"{p}std.process.exit({node.code});"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for ({s}..{e}) |{node.var}| {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}var {node.index_var}: usize = 0;",
                    f"{p}for ({self._v(node.iterable)}) |{node.value_var}| {{",
                    f"{p}    defer {node.index_var} += 1;"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}var iter_{node.var} = {self._v(node.dict_value)}.iterator();",
                    f"{p}while (iter_{node.var}.next()) |entry| {{",
                    f"{p}    const {node.var} = entry.key_ptr.*;"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break;"]
        if isinstance(node, Continue): return [f"{p}continue;"]
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''};"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}const {node.result_name} = std.process.getEnvVarOwned(allocator, "{node.name}") catch "";']
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}const {node.name} = std.process.args()[{node.index + 1}];"]
            if node.action == "count" and node.name: return [f"{p}const {node.name} = std.process.args().len;"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, Raise): return [f"{p}return error.Unexpected;"]
        if isinstance(node, Assert): return [f"{p}std.debug.assert({self._cond(node.condition)});"]
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
        params = ", ".join(f"{pp.name}: []const u8" for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"fn {n.name}({params}) !void {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append("}")
        return lines

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return str(v.value).lower()
        if v.kind == "null": return "null"
        if v.kind == "var": return str(v.value)
        if v.kind == "fstring" and v.parts:
            parts = [f"{{{self._v(p)}}}" if p.kind != "string" else str(p.value) for p in v.parts]
            return repr("".join(parts))
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_zig(ir: ScriptIR) -> str: return ZigEmitter().emit(ir)
