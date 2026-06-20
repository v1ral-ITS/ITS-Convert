"""Emit Perl from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class PerlEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ["#!/usr/bin/env perl", "use strict;", "use warnings;", ""]
        for node in ir.nodes:
            lines.extend(self._n(node, 0))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}# {node.text}"]
        if isinstance(node, Assign):
            sigil = "@" if node.value.kind == "list" else "%" if node.value.kind == "dict" else "$"
            return [f"{p}my {sigil}{node.name} = {self._v(node.value)};"]
        if isinstance(node, AugAssign): return [f"{p}${node.name} {node.op}= {self._v(node.value)};"]
        if isinstance(node, Print):
            vals = ", ".join(self._v(v) for v in node.values) if node.values else ""
            return [f"{p}print {vals}, \"\\n\";"]
        if isinstance(node, Input):
            if node.prompt: return [f'{p}my ${node.name} = <STDIN>; chomp ${node.name};  # {node.prompt}']
            return [f"{p}my ${node.name} = <STDIN>; chomp ${node.name};"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name: return [f"{p}my ${node.name} = `{cmd}`;"]
            return [f"{p}system({repr(cmd)});"]
        if isinstance(node, Exit): return [f"{p}exit({node.code});"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, For):
            return [f"{p}for my ${node.var} (@{{{self._v(node.iterable)}}}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for (my ${node.var} = {s}; ${node.var} < {e}; ${node.var}++) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for my ${node.index_var} (0 .. $#{{{self._v(node.iterable)}}}) {{", f"{p}    my ${node.value_var} = {self._v(node.iterable)}[$${node.index_var}];"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for my ${node.var} (keys %{{{self._v(node.dict_value)}}}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}last;"]
        if isinstance(node, Continue): return [f"{p}next;"]
        if isinstance(node, Pass): return [f"{p}# pass"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''};"]
        if isinstance(node, Import): return [f"{p}use {node.module};"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f"{p}my ${node.result_name} = $ENV{{{node.name}}};"]
            if node.action == "set": return [f"{p}$ENV{{{node.name}}} = {self._v(node.value)};"]
            if node.action == "delete": return [f"{p}delete $ENV{{{node.name}}};"]
            return [f"{p}# env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "script_name" and node.name: return [f"{p}my ${node.name} = $0;"]
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}my ${node.name} = $ARGV[{node.index}];"]
            if node.action == "count" and node.name: return [f"{p}my ${node.name} = scalar @ARGV;"]
            return [f"{p}# argv: {node.action}"]
        if isinstance(node, Switch):
            if not node.cases:
                return self._body(node.default_body, i)
            subj = self._v(node.subject)
            first = node.cases[0]
            lines = [f"{p}if ({subj} eq {self._v(first.pattern)}) {{"]
            lines.extend(self._body(first.body, i+1))
            lines.append(f"{p}}}")
            for case in node.cases[1:]:
                lines.append(f"{p}elsif ({subj} eq {self._v(case.pattern)}) {{")
                lines.extend(self._body(case.body, i+1))
                lines.append(f"{p}}}")
            if node.default_body:
                lines.append(f"{p}else {{")
                lines.extend(self._body(node.default_body, i+1))
                lines.append(f"{p}}}")
            return lines
        if isinstance(node, ClassDef):
            return [f"{p}# class {node.name} (not supported in this language)"]
        if isinstance(node, Lambda):
            return [f"{p}my ${node.name or '_fn'} = sub {{ {self._v(node.body)} }};"]
        if isinstance(node, WithBlock):
            lines = [f"{p}# with {self._v(node.expr)} as {node.var or '_ctx'}:"]
            lines.extend(self._body(node.body, i))
            return lines
        if isinstance(node, TryCatch):
            cv = node.catch_var or "err"
            lines = [f"{p}eval {{"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}}};")
            lines.append(f"{p}if (my ${cv} = $@) {{")
            lines.extend(self._body(node.catch_body, i+1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Raise): return [f"{p}die {self._v(node.message) if node.message else '\"Error\"'};"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, Assert): return [f"{p}die 'Assertion failed' unless {self._cond(node.condition)};"]
        if isinstance(node, RawBlock): return [f"{p}# raw ({node.language})"] + [f"{p}# {l}" for l in node.code.split("\n")]
        return [f"{p}# FIXME: {node.type}"]

    def _if(self, n, i):
        p = "    " * i
        lines = [f"{p}if ({self._cond(n.condition)}) {{"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}}} elsif ({self._cond(eb.condition)}) {{")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}}} else {{")
            lines.extend(self._body(n.else_body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _fn(self, n, i):
        p = "    " * i
        params = ", ".join(f"${p.name}" for p in n.params if not p.vararg and not p.kwarg)
        lines = [f"{p}sub {n.name} {{"]
        if params: lines.append(f"{p}    my ({params}) = @_;")
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}my @{nm} = ({', '.join(self._v(x) for x in n.items)});"]
        if n.action == "append": return [f"{p}push @{nm}, {self._v(n.value)};"]
        if n.action == "pop": return [f"{p}pop @{nm};"]
        if n.action == "len" and n.result_name: return [f"{p}my ${n.result_name} = scalar @{nm};"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}my ${n.result_name} = join({self._v(n.value)}, @{nm});"]
        if n.action == "sort" and n.result_name: return [f"{p}my @{n.result_name} = sort @{nm};"]
        return [f"{p}# list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "h"
        if n.action == "create":
            if not n.items: return [f"{p}my %{nm} = ();"]
            pairs = [f"{self._v(k)} => {self._v(v)}" for k, v in n.items]
            return [f"{p}my %{nm} = ({', '.join(pairs)});"]
        if n.action == "get" and n.key and n.result_name: return [f"{p}my ${n.result_name} = ${nm}{{{self._v(n.key)}}};"]
        if n.action == "set" and n.key: return [f"{p}${nm}{{{self._v(n.key)}}} = {self._v(n.value)};"]
        if n.action == "delete" and n.key: return [f"{p}delete ${nm}{{{self._v(n.key)}}};"]
        if n.action == "keys" and n.result_name: return [f"{p}my @{n.result_name} = keys %{nm};"]
        if n.action == "values" and n.result_name: return [f"{p}my @{n.result_name} = values %{nm};"]
        if n.action == "len" and n.result_name: return [f"{p}my ${n.result_name} = scalar keys %{nm};"]
        if n.action == "contains" and n.key and n.result_name: return [f"{p}my ${n.result_name} = exists ${nm}{{{self._v(n.key)}}};"]
        return [f"{p}# dict: {n.action}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return "1" if v.value else "0"
        if v.kind == "null": return "undef"
        if v.kind == "var": return f"${v.value}"
        if v.kind == "list": return "(" + ", ".join(self._v(p) for p in v.parts) + ")" if v.parts else "()"
        if v.kind == "dict": return "{}"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "and", "or": "or"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "not"}
            return f"({m.get(os, os)} {self._v(x)})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2: return f"${self._v(v.parts[0])}[{self._v(v.parts[1])}]"
        if v.kind == "attr" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}->{self._vs(v.parts[1])}"
        if v.kind == "fstring" and v.parts:
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    escaped = str(p.value).replace("\\", "\\\\").replace('"', '\\"').replace("@", "\\@")
                    parts.append(escaped)
                elif p.kind == "var":
                    parts.append(f"${p.value}")
                else:
                    inner = self._v(p)
                    parts.append("${" + inner + "}")
            return '"' + "".join(parts) + '"'

        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' && ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_pl(ir: ScriptIR) -> str: return PerlEmitter().emit(ir)
