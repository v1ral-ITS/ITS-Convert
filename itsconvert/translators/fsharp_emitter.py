"""Emit F# from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class FSharpEmitter:
    def emit(self, ir: ScriptIR) -> str:
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        lines: list[str] = ["open System", "open System.IO", ""]
        for fn in fns:
            lines.extend(self._fn(fn, 0))
            lines.append("")
        lines.append("[<EntryPoint>]")
        lines.append("let main argv =")
        for node in other:
            lines.extend(self._n(node, 1))
        lines.append("    0")
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign): return [f"{p}let {node.name} = {self._v(node.value)}"]
        if isinstance(node, MultiAssign): return [f"{p}let {', '.join(node.names)} = {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}let {node.name} = {node.name} {node.op} {self._v(node.value)}"]
        if isinstance(node, Print):
            if not node.values: return [f"{p}printfn \"\""]
            args = ", ".join(self._v(v) for v in node.values)
            fn = "printf" if node.end == "" else "printfn"
            if len(node.values) == 1: return [f'{p}{fn} "%A" {args}']
            fmt = " ".join("%A" for _ in node.values)
            return [f'{p}{fn} "{fmt}" {args}']
        if isinstance(node, Input):
            if node.prompt: return [f'{p}printf "{node.prompt}"', f"{p}let {node.name} = Console.ReadLine()"]
            return [f"{p}let {node.name} = Console.ReadLine()"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            return [f"{p}// shell: {cmd}"]
        if isinstance(node, Exit): return [f"{p}Environment.Exit({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for {node.var} in {s} .. {e} - 1 do"] + self._body(node.body, i+1)
        if isinstance(node, ForEnumerate):
            return [f"{p}for ({node.index_var}, {node.value_var}) in Seq.indexed {self._v(node.iterable)} do"] + self._body(node.body, i+1)
        if isinstance(node, ForKeys):
            return [f"{p}for {node.var} in {self._v(node.dict_value)} |> Map.toSeq |> Seq.map fst do"] + self._body(node.body, i+1)
        if isinstance(node, For):
            return [f"{p}for {node.var} in {self._v(node.iterable)} do"] + self._body(node.body, i+1)
        if isinstance(node, While):
            return [f"{p}while {self._cond(node.condition)} do"] + self._body(node.body, i+1)
        if isinstance(node, Break): return [f"{p}// break (not directly supported in F# for-loops)"]
        if isinstance(node, Continue): return [f"{p}()  // continue"]
        if isinstance(node, Pass): return [f"{p}()"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}{self._v(node.value) if node.value else '()'}"]
        if isinstance(node, Import): return [f"{p}open {node.module}"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}let {node.result_name} = Environment.GetEnvironmentVariable("{node.name}") |> Option.ofObj |> Option.defaultValue ""']
            if node.action == "set": return [f'{p}Environment.SetEnvironmentVariable("{node.name}", {self._v(node.value)})']
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}let {node.name} = argv.[{node.index}]"]
            if node.action == "count" and node.name: return [f"{p}let {node.name} = argv.Length"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, TryCatch):
            cv = node.catch_var or "ex"
            lines = [f"{p}try"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}with")
            lines.append(f"{p}| :? Exception as {cv} ->")
            lines.extend(self._body(node.catch_body, i+1))
            return lines
        if isinstance(node, Raise):
            msg = self._v(node.message) if node.message else '"Error"'
            return [f"{p}raise (Exception({msg}))"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, StringOpNode): return self._strop(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, Assert): return [f"{p}if not ({self._cond(node.condition)}) then failwith \"Assertion failed\""]
        if isinstance(node, RawBlock): return [f"{p}// raw ({node.language})"] + [f"{p}// {l}" for l in node.code.split("\n")]
        return [f"{p}// FIXME: {node.type}"]

    def _if(self, n, i):
        p = "    " * i
        lines = [f"{p}if {self._cond(n.condition)} then"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}elif {self._cond(eb.condition)} then")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}else")
            lines.extend(self._body(n.else_body, i+1))
        return lines

    def _fn(self, n, i):
        p = "    " * i
        params = " ".join(
            pp.name + (f": {pp.type_hint or 'obj'}" if pp.type_hint else "")
            for pp in n.params if not pp.vararg and not pp.kwarg
        ) or "()"
        lines = [f"{p}let {n.name} {params} ="]
        lines.extend(self._body(n.body, i+1))
        return lines

    def _list(self, n, p):
        nm = n.name or "lst"
        if n.action == "create": return [f"{p}let {nm} = [{'; '.join(self._v(x) for x in n.items)}]"]
        if n.action == "append": return [f"{p}let {nm} = {nm} @ [{self._v(n.value)}]"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = List.length {nm}"]
        if n.action == "sort" and n.result_name: return [f"{p}let {n.result_name} = List.sort {nm}"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}let {n.result_name} = List.contains {self._v(n.value)} {nm}"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}let {n.result_name} = String.concat {self._v(n.value)} {nm}"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "m"
        if n.action == "create":
            if not n.items: return [f"{p}let {nm} = Map.empty"]
            pairs = [f"({self._v(k)}, {self._v(v)})" for k, v in n.items]
            return [f"{p}let {nm} = Map.ofList [{'; '.join(pairs)}]"]
        if n.action == "get" and n.key and n.result_name: return [f"{p}let {n.result_name} = Map.find {self._v(n.key)} {nm}"]
        if n.action == "set" and n.key: return [f"{p}let {nm} = Map.add {self._v(n.key)} {self._v(n.value)} {nm}"]
        if n.action == "delete" and n.key: return [f"{p}let {nm} = Map.remove {self._v(n.key)} {nm}"]
        if n.action == "keys" and n.result_name: return [f"{p}let {n.result_name} = Map.toSeq {nm} |> Seq.map fst |> Seq.toList"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = Map.count {nm}"]
        return [f"{p}// dict: {n.action}"]

    def _strop(self, n, p):
        if not n.operands: return [f"{p}// string_op: {n.op}"]
        base = self._v(n.operands[0])
        if n.op == "upper" and n.name: return [f'{p}let {n.name} = {base}.ToUpper()']
        if n.op == "lower" and n.name: return [f'{p}let {n.name} = {base}.ToLower()']
        if n.op == "strip" and n.name: return [f'{p}let {n.name} = {base}.Trim()']
        if n.op == "len" and n.name: return [f'{p}let {n.name} = {base}.Length']
        if n.op == "replace" and len(n.operands) >= 3 and n.name:
            return [f'{p}let {n.name} = {base}.Replace({self._v(n.operands[1])}, {self._v(n.operands[2])})']
        if n.op == "contains" and len(n.operands) >= 2 and n.name:
            return [f'{p}let {n.name} = {base}.Contains({self._v(n.operands[1])})']
        if n.op == "startswith" and len(n.operands) >= 2 and n.name:
            return [f'{p}let {n.name} = {base}.StartsWith({self._v(n.operands[1])})']
        if n.op == "endswith" and len(n.operands) >= 2 and n.name:
            return [f'{p}let {n.name} = {base}.EndsWith({self._v(n.operands[1])})']
        return [f"{p}// string_op: {n.op}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f"{p}let {n.name} = File.ReadAllText({path})"]
        if n.op == "write" and n.content: return [f"{p}File.WriteAllText({path}, {self._v(n.content)})"]
        if n.op == "append" and n.content: return [f"{p}File.AppendAllText({path}, {self._v(n.content)})"]
        if n.op == "exists" and n.name: return [f"{p}let {n.name} = File.Exists({path})"]
        if n.op == "mkdir": return [f"{p}Directory.CreateDirectory({path}) |> ignore"]
        if n.op == "delete": return [f"{p}File.Delete({path})"]
        return [f"{p}// file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)

    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind == "int": return str(v.value)
        if v.kind == "float": return f"{v.value}" if "." in str(v.value) else f"{v.value}.0"
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "None"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "[" + "; ".join(self._v(p) for p in v.parts) + "]" if v.parts else "[]"
        if v.kind == "dict": return "Map.empty"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o)
            m = {"and": "&&", "or": "||", "//": "/", "**": "**"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o)
            m = {"not": "not"}
            return f"({m.get(os, os)} {self._v(x)})"
        if v.kind == "fstring" and v.parts:
            parts = [f"{{{self._v(p)}}}" if p.kind != "string" else str(p.value) for p in v.parts]
            return f'$"{"".join(parts)}"'
        if v.kind == "call" and v.parts and len(v.parts) >= 2:
            fn = self._vs(v.parts[0])
            args = " ".join(self._v(a) for a in (v.parts[1].parts or [])) if v.parts[1].parts is not None else self._v(v.parts[1])
            return f"({fn} {args})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2:
            return f"{self._v(v.parts[0])}.[{self._v(v.parts[1])}]"
        return repr(v.value)

    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'", '"')) else s

    def _cond(self, c):
        m = {"==": "=", "!=": "<>", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"


def emit_fsharp(ir: ScriptIR) -> str: return FSharpEmitter().emit(ir)
