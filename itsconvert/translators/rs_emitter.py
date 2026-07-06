"""Emit Rust from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class RustEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = ["fn main() {"]
        for node in ir.nodes:
            lines.extend(self._n(node, 1))
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign):
            t = self._type(node.value)
            mut = "let mut " if self._is_mutated(node.name, []) else "let "
            return [f"{p}{mut}{node.name}: {t} = {self._v(node.value)};"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)};"]
        if isinstance(node, Print):
            vals = ", ".join(self._v(v) for v in node.values) if node.values else ""
            if len(node.values) == 1: return [f"{p}println!({vals});"]
            fmt = " ".join("{}" for _ in node.values)
            return [f'{p}println!("{fmt}", {vals});']
        if isinstance(node, Input):
            return [f'{p}let mut {node.name} = String::new();',
                    f'{p}println!("{node.prompt}");',
                    f"{p}std::io::stdin().read_line(&mut {node.name}).unwrap();",
                    f"{p}{node.name} = {node.name}.trim().to_string();"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name:
                return [f"{p}let {node.name} = std::process::Command::new({repr(cmd)}).output().unwrap();"]
            return [f"{p}std::process::Command::new({repr(cmd)}).status().unwrap();"]
        if isinstance(node, Exit): return [f"{p}std::process::exit({node.code});"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, For):
            return [f"{p}for {node.var} in {self._v(node.iterable)}.iter() {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for {node.var} in {s}..{e} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for ({node.index_var}, {node.value_var}) in {self._v(node.iterable)}.iter().enumerate() {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for {node.var} in {self._v(node.dict_value)}.keys() {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}while {self._cond(node.condition)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break;"]
        if isinstance(node, Continue): return [f"{p}continue;"]
        if isinstance(node, Pass): return [f"{p}// pass"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''};"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}let {node.result_name} = std::env::var("{node.name}").unwrap_or_default();']
            if node.action == "set": return [f'{p}std::env::set_var("{node.name}", {self._v(node.value)});']
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}let {node.name} = std::env::args().nth({node.index + 1}).unwrap();"]
            if node.action == "count" and node.name: return [f"{p}let {node.name} = std::env::args().count();"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, TryCatch):
            cv = node.catch_var or "err"
            lines = [f"{p}match std::panic::catch_unwind(|| {{"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}}}) {{")
            lines.append(f"{p}    Ok(_) => {{}}")
            lines.append(f"{p}    Err({cv}) => {{")
            lines.extend(self._body(node.catch_body, i+2))
            lines.append(f"{p}    }}")
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, Raise): return [f"{p}panic!({self._v(node.message) if node.message else '\"Error\"'});"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, StringOpNode):
            if not node.operands: return [f"{p}// string_op: {node.op}"]
            base = self._v(node.operands[0])
            if node.op == "upper" and node.name: return [f'{p}let {node.name} = {base}.to_uppercase();']
            if node.op == "lower" and node.name: return [f'{p}let {node.name} = {base}.to_lowercase();']
            if node.op == "strip" and node.name: return [f'{p}let {node.name} = {base}.trim().to_string();']
            if node.op == "len" and node.name: return [f'{p}let {node.name} = {base}.len();']
            if node.op == "replace" and len(node.operands) >= 3 and node.name:
                return [f'{p}let {node.name} = {base}.replace({self._v(node.operands[1])}.as_str(), {self._v(node.operands[2])}.as_str());']
            if node.op == "split" and len(node.operands) >= 2 and node.name:
                return [f'{p}let {node.name}: Vec<&str> = {base}.split({self._v(node.operands[1])}.as_str()).collect();']
            if node.op == "contains" and len(node.operands) >= 2 and node.name:
                return [f'{p}let {node.name} = {base}.contains({self._v(node.operands[1])}.as_str());']
            if node.op == "startswith" and len(node.operands) >= 2 and node.name:
                return [f'{p}let {node.name} = {base}.starts_with({self._v(node.operands[1])}.as_str());']
            if node.op == "endswith" and len(node.operands) >= 2 and node.name:
                return [f'{p}let {node.name} = {base}.ends_with({self._v(node.operands[1])}.as_str());']
            return [f"{p}// string_op: {node.op}"]
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, Assert): return [f"{p}assert!({self._cond(node.condition)});"]
        if isinstance(node, RawBlock): return [f"{p}// raw ({node.language})"] + [f"{p}// {l}" for l in node.code.split("\n")]
        return [f"{p}// FIXME: {node.type}"]

    def _type(self, v): return {"int": "i32", "float": "f64", "string": "String", "bool": "bool", "null": "()", "var": "var"}.get(v.kind, "String")

    def _is_mutated(self, name, nodes): return True  # conservative: always mut for simplicity

    def _if(self, n, i):
        p = "    " * i
        lines = [f"{p}if {self._cond(n.condition)} {{"]
        lines.extend(self._body(n.then_body, i+1))
        for eb in n.elif_branches:
            lines.append(f"{p}}} else if {self._cond(eb.condition)} {{")
            lines.extend(self._body(eb.body, i+1))
        if n.else_body:
            lines.append(f"{p}}} else {{")
            lines.extend(self._body(n.else_body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _fn(self, n, i):
        p = "    " * i
        params = ", ".join(f"{pp.name}: &str" for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"{p}fn {n.name}({params}) -> String {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}let mut {nm} = vec![{', '.join(self._v(x) for x in n.items)}];"]
        if n.action == "append": return [f"{p}{nm}.push({self._v(n.value)});"]
        if n.action == "pop": return [f"{p}{nm}.pop();"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = {nm}.len();"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}let {n.result_name} = {nm}.join(&{self._v(n.value)});"]
        if n.action == "sort" and n.result_name: return [f"{p}let mut {n.result_name} = {nm}.clone(); {n.result_name}.sort();"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}let {n.result_name} = {nm}.contains(&{self._v(n.value)});"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "map"
        if n.action == "create":
            if not n.items: return [f'{p}let mut {nm} = std::collections::HashMap::new();']
            lines = [f'{p}let mut {nm} = std::collections::HashMap::new();']
            for k, v in n.items: lines.append(f"{p}{nm}.insert({self._v(k)}, {self._v(v)});")
            return lines
        if n.action == "get" and n.key and n.result_name: return [f"{p}let {n.result_name} = {nm}.get(&{self._v(n.key)});"]
        if n.action == "set" and n.key: return [f"{p}{nm}.insert({self._v(n.key)}, {self._v(n.value)});"]
        if n.action == "delete" and n.key: return [f"{p}{nm}.remove(&{self._v(n.key)});"]
        if n.action == "keys" and n.result_name: return [f"{p}let {n.result_name}: Vec<_> = {nm}.keys().collect();"]
        if n.action == "values" and n.result_name: return [f"{p}let {n.result_name}: Vec<_> = {nm}.values().collect();"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = {nm}.len();"]
        return [f"{p}// dict: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f'{p}let {n.name} = std::fs::read_to_string({path}).unwrap_or_default();']
        if n.op == "write" and n.content: return [f'{p}std::fs::write({path}, {self._v(n.content)}).unwrap();']
        if n.op == "append" and n.content:
            return [f'{p}use std::io::Write; let mut _f = std::fs::OpenOptions::new().append(true).open({path}).unwrap();',
                    f'{p}_f.write_all({self._v(n.content)}.as_bytes()).unwrap();']
        if n.op == "exists" and n.name: return [f'{p}let {n.name} = std::path::Path::new({path}).exists();']
        if n.op == "mkdir": return [f'{p}std::fs::create_dir_all({path}).unwrap();']
        if n.op == "delete": return [f'{p}std::fs::remove_file({path}).unwrap_or(());']
        return [f"{p}// file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return f'String::from({repr(str(v.value))})'
        if v.kind == "int": return str(v.value)
        if v.kind == "float": return f"{v.value}" if "." in str(v.value) else f"{v.value}.0"
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "()"
        if v.kind == "var": return str(v.value) + ".clone()"
        if v.kind == "list": return "vec![" + ", ".join(self._v(p) for p in v.parts) + "]" if v.parts else "vec![]"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "&&", "or": "||"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "!"}
            return f"({m.get(os, os)}{self._v(x)})"
        if v.kind == "fstring" and v.parts:
            fmt_str = ""
            args = []
            for p in v.parts:
                if p.kind == "string":
                    fmt_str += str(p.value).replace("{", "{{").replace("}", "}}")
                else:
                    fmt_str += "{}"
                    args.append(self._v(p))
            if args:
                return f'format!("{fmt_str}", {", ".join(args)})'
            return repr(fmt_str)
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_rs(ir: ScriptIR) -> str: return RustEmitter().emit(ir)
