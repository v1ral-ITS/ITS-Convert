"""Emit R from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class REmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = []
        for node in ir.nodes:
            lines.extend(self._n(node, 0))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "  " * i
        if isinstance(node, Comment): return [f"{p}# {node.text}"]
        if isinstance(node, Assign): return [f"{p}{node.name} <- {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} <- {node.name} {node.op} {self._v(node.value)}"]
        if isinstance(node, Print):
            return [f"{p}cat({', '.join(self._v(v) for v in node.values) if node.values else '\"\"'}, '\\n')"]
        if isinstance(node, Input):
            if node.prompt: return [f'{p}{node.name} <- readline(prompt = "{node.prompt}")']
            return [f"{p}{node.name} <- readline()"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name: return [f"{p}{node.name} <- system({repr(cmd)}, intern = TRUE)"]
            return [f"{p}system({repr(cmd)})"]
        if isinstance(node, Exit): return [f"{p}quit(save = 'no', status = {node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, For):
            return [f"{p}for ({node.var} in {self._v(node.iterable)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for ({node.var} in {s}:{e}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for ({node.index_var} in seq_along({self._v(node.iterable)})) {{", f"{p}  {node.value_var} <- {self._v(node.iterable)}[[{node.index_var}]]"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for ({node.var} in names({self._v(node.dict_value)})) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}next"]
        if isinstance(node, Pass): return [f"{p}# pass"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return({self._v(node.value)})" if node.value else f"{p}return()"]
        if isinstance(node, Import): return [f"{p}library({node.module})"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f"{p}{node.result_name} <- Sys.getenv('{node.name}')"]
            if node.action == "set": return [f"{p}Sys.setenv('{node.name}' = {self._v(node.value)})"]
            return [f"{p}# env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}{node.name} <- commandArgs(trailingOnly = TRUE)[{node.index + 1}]"]
            if node.action == "count" and node.name: return [f"{p}{node.name} <- length(commandArgs(trailingOnly = TRUE))"]
            return [f"{p}# argv: {node.action}"]
        if isinstance(node, Switch):
            lines = [f"{p}switch({self._v(node.subject)},"]
            for case in node.cases:
                lines.append(f"{p}  {self._v(case.pattern)} = {{")
                lines.extend(self._body(case.body, i+1))
                lines.append(f"{p}  }},")
            if node.default_body:
                lines.append(f"{p}  {{")
                lines.extend(self._body(node.default_body, i+1))
                lines.append(f"{p}  }}")
            lines.append(f"{p})")
            return lines
        if isinstance(node, ClassDef):
            return [f"{p}# class {node.name} (not supported in this language)"]
        if isinstance(node, Lambda):
            params = ", ".join(pp.name for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}{node.name or '_fn'} <- function({params}) {self._v(node.body)}"]
        if isinstance(node, WithBlock):
            lines = [f"{p}# with {self._v(node.expr)} as {node.var or '_ctx'}:"]
            lines.extend(self._body(node.body, i))
            return lines
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}tryCatch({{"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}}}, error = function({cv}) {{")
            lines.extend(self._body(node.catch_body, i+1))
            lines.append(f"{p}}})")
            return lines
        if isinstance(node, Raise): return [f"{p}stop({self._v(node.message) if node.message else '\"Error\"'})"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, Assert): return [f"{p}stopifnot({self._cond(node.condition)})"]
        if isinstance(node, RawBlock): return [f"{p}# raw ({node.language})"] + [f"{p}# {l}" for l in node.code.split("\n")]
        return [f"{p}# FIXME: {node.type}"]

    def _if(self, n, i):
        p = "  " * i
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
        p = "  " * i
        params = ", ".join(pp.name + (f" = {self._v(pp.default)}" if pp.default else "") for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"{p}{n.name} <- function({params}) {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}{nm} <- c({', '.join(self._v(x) for x in n.items)})"]
        if n.action == "append": return [f"{p}{nm} <- c({nm}, {self._v(n.value)})"]
        if n.action == "pop": return [f"{p}{nm} <- head({nm}, -1)"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} <- length({nm})"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}{n.result_name} <- paste({nm}, collapse = {self._v(n.value)})"]
        if n.action == "sort" and n.result_name: return [f"{p}{n.result_name} <- sort({nm})"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}{n.result_name} <- {self._v(n.value)} %in% {nm}"]
        return [f"{p}# list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "lst"
        if n.action == "create":
            if not n.items: return [f"{p}{nm} <- list()"]
            pairs = [f"{self._vs(k)} = {self._v(v)}" for k, v in n.items]
            return [f"{p}{nm} <- list({', '.join(pairs)})"]
        if n.action == "get" and n.key and n.result_name: return [f"{p}{n.result_name} <- {nm}[[{self._v(n.key)}]]"]
        if n.action == "set" and n.key: return [f"{p}{nm}[[{self._v(n.key)}]] <- {self._v(n.value)}"]
        if n.action == "keys" and n.result_name: return [f"{p}{n.result_name} <- names({nm})"]
        if n.action == "values" and n.result_name: return [f"{p}{n.result_name} <- unlist({nm})"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} <- length({nm})"]
        return [f"{p}# dict: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f"{p}{n.name} <- readLines({path})"]
        if n.op == "write" and n.content: return [f"{p}writeLines({self._v(n.content)}, {path})"]
        if n.op == "exists": return [f"{p}{n.name or '_ex'} <- file.exists({path})"]
        if n.op == "delete": return [f"{p}file.remove({path})"]
        if n.op == "mkdir": return [f"{p}dir.create({path}, recursive = TRUE)"]
        return [f"{p}# file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind == "int": return str(v.value) + "L"
        if v.kind == "float": return str(v.value)
        if v.kind == "bool": return "TRUE" if v.value else "FALSE"
        if v.kind == "null": return "NULL"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "c(" + ", ".join(self._v(p) for p in v.parts) + ")" if v.parts else "c()"
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
                else:
                    parts.append(self._v(p))
            return f'paste0({", ".join(parts)})'

        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " & ", "or": " | "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' & ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_r(ir: ScriptIR) -> str: return REmitter().emit(ir)
