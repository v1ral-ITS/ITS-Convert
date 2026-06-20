"""Emit PHP from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,    Switch, SwitchCase, ClassDef, ClassField, Lambda, WithBlock, CompoundCondition,
)


class PHPEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ["<?php", ""]
        for node in ir.nodes:
            lines.extend(self._n(node, 0))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign): return [f"{p}${node.name} = {self._v(node.value)};"]
        if isinstance(node, MultiAssign): return [f"{p}list({', '.join('$'+n for n in node.names)}) = {self._v(node.value)};"]
        if isinstance(node, AugAssign): return [f"{p}${node.name} {node.op}= {self._v(node.value)};"]
        if isinstance(node, Print):
            args = ', '.join(self._v(v) for v in node.values) if node.values else "''"
            return [f"{p}echo {args} . PHP_EOL;"]
        if isinstance(node, Input):
            if node.prompt: return [f'{p}${node.name} = readline("{node.prompt}");']
            return [f"{p}${node.name} = readline();"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name: return [f"{p}${node.name} = shell_exec({repr(cmd)});"]
            return [f"{p}system({repr(cmd)});"]
        if isinstance(node, Exit): return [f"{p}exit({node.code});"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, For):
            return [f"{p}foreach ({self._v(node.iterable)} as ${node.var}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            st = f", {self._v(node.step)}" if node.step else ""
            return [f"{p}for (${node.var} = {s}; ${node.var} < {e}; ${node.var} += {st or '1'}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}foreach ({self._v(node.iterable)} as ${node.index_var} => ${node.value_var}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}foreach (array_keys({self._v(node.dict_value)}) as ${node.var}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while ({self._cond(node.condition)}) {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break;"]
        if isinstance(node, Continue): return [f"{p}continue;"]
        if isinstance(node, Pass): return [f"{p}// pass"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''};"]
        if isinstance(node, Import): return [f"{p}require '{node.module}';"]
        if isinstance(node, StringOpNode): return self._strop(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f"{p}${node.result_name} = getenv('{node.name}');"]
            if node.action == "set": return [f"{p}putenv('{node.name}=' . {self._v(node.value)});"]
            if node.action == "delete": return [f"{p}putenv('{node.name}');"]
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "script_name" and node.name: return [f"{p}${node.name} = $argv[0];"]
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}${node.name} = $argv[{node.index + 1}];"]
            if node.action == "count" and node.name: return [f"{p}${node.name} = $argc;"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, Switch):
            lines = [f"{p}switch ({self._v(node.subject)}) {{"]
            for case in node.cases:
                lines.append(f"{p}    case {self._v(case.pattern)}:")
                lines.extend(self._body(case.body, i+2))
                lines.append(f"{p}        break;")
            if node.default_body:
                lines.append(f"{p}    default:")
                lines.extend(self._body(node.default_body, i+2))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, ClassDef):
            return [f"{p}// class {node.name} (not supported in this language)"]
        if isinstance(node, Lambda):
            params = ", ".join(f"${pp.name}" for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}${node.name or '_fn'} = fn({params}) => {self._v(node.body)};"]
        if isinstance(node, WithBlock):
            lines = [f"{p}// with {self._v(node.expr)} as {node.var or '_ctx'}:"]
            lines.extend(self._body(node.body, i))
            return lines
        if isinstance(node, TryCatch):
            cv = node.catch_var or "e"
            lines = [f"{p}try {{"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}}} catch (Exception ${cv}) {{")
            lines.extend(self._body(node.catch_body, i+1))
            if node.finally_body:
                lines.append(f"{p}}} finally {{")
                lines.extend(self._body(node.finally_body, i+1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Raise): return [f"{p}throw new Exception({self._v(node.message) if node.message else '\"Error\"'});"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, Assert): return [f"{p}assert({self._cond(node.condition)});"]
        if isinstance(node, RawBlock): return [f"{p}// raw ({node.language})"] + [f"{p}// {l}" for l in node.code.split("\n")]
        return [f"{p}// FIXME: {node.type}"]

    def _if(self, n, i):
        p = "    " * i
        lines = [f"{p}if ({self._cond(n.condition)}) {{"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}}} elseif ({self._cond(eb.condition)}) {{")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}}} else {{")
            lines.extend(self._body(n.else_body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _fn(self, n, i):
        p = "    " * i
        params = ", ".join(f"${pp.name}" + (f" = {self._v(pp.default)}" if pp.default else "") for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"{p}function {n.name}({params}) {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _strop(self, n, p):
        base = self._v(n.operands[0]) if n.operands else "$s"
        ops = {"upper": f"strtoupper({base})", "lower": f"strtolower({base})", "strip": f"trim({base})",
               "len": f"strlen({base})",
               "replace": f"str_replace({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'}, {self._v(n.operands[2]) if len(n.operands)>2 else '\"\"'}, {base})",
               "split": f"explode({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'}, {base})",
               "join": f"implode({self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'}, {base})",
               "startswith": f"str_starts_with({base}, {self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
               "endswith": f"str_ends_with({base}, {self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})",
               "contains": f"str_contains({base}, {self._v(n.operands[1]) if len(n.operands)>1 else '\"\"'})"}
        expr = ops.get(n.op, f"/* {n.op} */")
        if n.name: return [f"{p}${n.name} = {expr};"]
        return [f"{p}{expr};"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f"{p}${n.name} = file_get_contents({path});"]
        if n.op == "write" and n.content: return [f"{p}file_put_contents({path}, {self._v(n.content)});"]
        if n.op == "append" and n.content: return [f"{p}file_put_contents({path}, {self._v(n.content)}, FILE_APPEND);"]
        if n.op == "exists": return [f"{p}${n.name or 'exists'} = file_exists({path});"]
        if n.op == "delete": return [f"{p}unlink({path});"]
        if n.op == "mkdir": return [f"{p}mkdir({path}, 0755, true);"]
        if n.op == "listdir" and n.name: return [f"{p}${n.name} = scandir({path});"]
        return [f"{p}// file: {n.op}"]

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}${nm} = [{', '.join(self._v(x) for x in n.items)}];"]
        if n.action == "append": return [f"{p}${nm}[] = {self._v(n.value)};"]
        if n.action == "pop": return [f"{p}array_pop(${nm});"]
        if n.action == "len" and n.result_name: return [f"{p}${n.result_name} = count(${nm});"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}${n.result_name} = implode({self._v(n.value)}, ${nm});"]
        if n.action == "sort" and n.result_name: return [f"{p}${n.result_name} = ${nm}; sort(${n.result_name});"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}${n.result_name} = in_array({self._v(n.value)}, ${nm});"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "dict"
        if n.action == "create":
            if not n.items: return [f"{p}${nm} = [];"]
            pairs = [f"{self._v(k)} => {self._v(v)}" for k, v in n.items]
            return [f"{p}${nm} = [{', '.join(pairs)}];"]
        if n.action == "get" and n.key and n.result_name: return [f"{p}${n.result_name} = ${nm}[{self._v(n.key)}];"]
        if n.action == "set" and n.key: return [f"{p}${nm}[{self._v(n.key)}] = {self._v(n.value)};"]
        if n.action == "delete" and n.key: return [f"{p}unset(${nm}[{self._v(n.key)}]);"]
        if n.action == "keys" and n.result_name: return [f"{p}${n.result_name} = array_keys(${nm});"]
        if n.action == "values" and n.result_name: return [f"{p}${n.result_name} = array_values(${nm});"]
        if n.action == "len" and n.result_name: return [f"{p}${n.result_name} = count(${nm});"]
        if n.action == "contains" and n.key and n.result_name: return [f"{p}${n.result_name} = array_key_exists({self._v(n.key)}, ${nm});"]
        return [f"{p}// dict: {n.action}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind in ("int", "float"): return str(v.value)
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "null"
        if v.kind == "var": return f"${v.value}"
        if v.kind == "list": return "[" + ", ".join(self._v(p) for p in v.parts) + "]" if v.parts else "[]"
        if v.kind == "dict": return "[]"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "&&", "or": "||"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "!"}
            return f"({m.get(os, os)}{self._v(x)})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2: return f"${self._vs(v.parts[0])}[{self._v(v.parts[1])}]"
        if v.kind == "attr" and v.parts and len(v.parts) >= 2: return f"${self._vs(v.parts[0])}->{self._vs(v.parts[1])}"
        if v.kind == "fstring" and v.parts:
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    escaped = str(p.value).replace("\\", "\\\\").replace('"', '\\"')
                    parts.append(escaped)
                elif p.kind == "var":
                    parts.append(f"${{{p.value}}}")
                else:
                    inner = self._v(p)
                    parts.append("{" + inner + "}")
            return '"' + "".join(parts) + '"'

        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' && ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_php(ir: ScriptIR) -> str: return PHPEmitter().emit(ir)
