"""Emit Go from IR."""
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


class GoEmitter:
    def emit(self, ir: ScriptIR) -> str:
        imports = set()
        for node in ir.nodes:
            self._collect_imports(node, imports)
        lines: list[str] = ["package main", ""]
        if imports:
            lines.append("import (")
            for imp in sorted(imports):
                lines.append(f'    "{imp}"')
            lines.append(")")
            lines.append("")
        lines.append("func main() {")
        for node in ir.nodes:
            lines.extend(self._n(node, 1))
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _collect_imports(self, node, imports):
        if self._has_fstring_node(node): imports.add("fmt")
        if isinstance(node, Print): imports.add("fmt")
        if isinstance(node, Input): imports.add("bufio"); imports.add("os"); imports.add("fmt")
        if isinstance(node, Command): imports.add("os/exec")
        if isinstance(node, EnvVar): imports.add("os")
        if isinstance(node, FileIONode): imports.add("os")
        if isinstance(node, Assert): imports.add("fmt")
        if isinstance(node, Argv): imports.add("os")
        if isinstance(node, FunctionDef):
            for n in node.body: self._collect_imports(n, imports)
        if isinstance(node, If):
            for n in node.then_body: self._collect_imports(n, imports)
            for eb in node.elif_branches:
                for n in eb.body: self._collect_imports(n, imports)
            for n in node.else_body: self._collect_imports(n, imports)
        if isinstance(node, (For, ForRange, ForEnumerate, ForKeys, While)):
            for n in node.body: self._collect_imports(n, imports)
        if isinstance(node, Switch):
            for case in node.cases:
                for n in case.body: self._collect_imports(n, imports)
            for n in node.default_body: self._collect_imports(n, imports)
        if isinstance(node, ClassDef):
            for method in node.methods:
                self._collect_imports(method, imports)
        if isinstance(node, WithBlock):
            for n in node.body: self._collect_imports(n, imports)

    def _has_fstring_value(self, value):
        if getattr(value, "kind", None) == "fstring":
            return True
        for part in getattr(value, "parts", []) or []:
            if self._has_fstring_value(part):
                return True
        return False

    def _has_fstring_node(self, node):
        for attr in ("value", "path", "content", "message", "expr", "subject", "iterable", "dict_value", "start", "stop", "step", "body"):
            value = getattr(node, attr, None)
            if isinstance(value, list):
                if any(self._has_fstring_node(x) for x in value):
                    return True
            elif hasattr(value, "kind") and self._has_fstring_value(value):
                return True
        if isinstance(node, Switch):
            return any(self._has_fstring_value(c.pattern) or any(self._has_fstring_node(x) for x in c.body) for c in node.cases)
        if isinstance(node, ClassDef):
            return any((field.value and self._has_fstring_value(field.value)) for field in node.fields) or any(self._has_fstring_node(m) for m in node.methods)
        if isinstance(node, Lambda):
            return self._has_fstring_value(node.body)
        return False

    def _n(self, node, i):
        p = "    " * i
        if isinstance(node, Comment): return [f"{p}// {node.text}"]
        if isinstance(node, Assign):
            if node.value.kind in ("int", "float"):
                t = "int" if node.value.kind == "int" else "float64"
                return [f"{p}{node.name} := {self._v(node.value)}"]
            return [f"{p}{node.name} := {self._v(node.value)}"]
        if isinstance(node, MultiAssign): return [f"{p}{', '.join(node.names)} := {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._v(node.value)}"]
        if isinstance(node, Print):
            if not node.values: return [f"{p}fmt.Println()"]
            fmts = " ".join("%v" for _ in node.values)
            args = ", ".join(self._v(v) for v in node.values)
            if len(node.values) == 1: return [f"{p}fmt.Println({args})"]
            return [f'{p}fmt.Printf("{fmts}\\n", {args})']
        if isinstance(node, Input):
            return [f"{p}scanner := bufio.NewScanner(os.Stdin)",
                    f'{p}fmt.Print("{node.prompt}")',
                    f"{p}scanner.Scan()",
                    f"{p}{node.name} := scanner.Text()"]
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            if node.capture and node.name:
                return [f"{p}cmd := exec.Command({repr(cmd)})",
                        f"{p}out, _ := cmd.Output()",
                        f"{p}{node.name} := string(out)"]
            return [f"{p}exec.Command({repr(cmd)}).Run()"]
        if isinstance(node, Exit): return [f"{p}os.Exit({node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, For):
            return [f"{p}for _, {node.var} := range {self._v(node.iterable)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}for {node.var} := {s}; {node.var} < {e}; {node.var}++ {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForEnumerate):
            return [f"{p}for {node.index_var}, {node.value_var} := range {self._v(node.iterable)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, ForKeys):
            return [f"{p}for {node.var} := range {self._v(node.dict_value)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, While):
            return [f"{p}for {self._cond(node.condition)} {{"] + self._body(node.body, i+1) + [f"{p}}}"]
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}continue"]
        if isinstance(node, Pass): return [f"{p}// pass"]
        if isinstance(node, FunctionDef): return self._fn(node, i)
        if isinstance(node, Return): return [f"{p}return{(' ' + self._v(node.value)) if node.value else ''}"]
        if isinstance(node, Import): return [f"{p}// import \"{node.module}\""]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f"{p}{node.result_name} := os.Getenv(\"{node.name}\")"]
            if node.action == "set": return [f"{p}os.Setenv(\"{node.name}\", {self._v(node.value)})"]
            if node.action == "delete": return [f"{p}os.Unsetenv(\"{node.name}\")"]
            return [f"{p}// env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "script_name" and node.name: return [f"{p}{node.name} := os.Args[0]"]
            if node.action == "nth" and node.index is not None and node.name: return [f"{p}{node.name} := os.Args[{node.index + 1}]"]
            if node.action == "count" and node.name: return [f"{p}{node.name} := len(os.Args)"]
            return [f"{p}// argv: {node.action}"]
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, DictOp): return self._dict(node, p)
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, Switch):
            lines = [f"{p}switch {self._v(node.subject)} {{"]
            for case in node.cases:
                lines.append(f"{p}case {self._v(case.pattern)}:")
                lines.extend(self._body(case.body, i + 1))
            if node.default_body:
                lines.append(f"{p}default:")
                lines.extend(self._body(node.default_body, i + 1))
            lines.append(f"{p}}}")
            return lines
        if isinstance(node, ClassDef):
            lines = [f"{p}type {node.name} struct {{"]
            for field in node.fields:
                lines.append(f"{p}    {field.name} interface{{}}")
            lines.append(f"{p}}}")
            lines.append("")
            for method in node.methods:
                recv = f"(self *{node.name})"
                params = ", ".join(f"{pp.name} interface{{}}" for pp in method.params if not pp.vararg and not pp.kwarg and pp.name != "self")
                lines.append(f"{p}func {recv} {method.name}({params}) interface{{}} {{")
                lines.extend(self._body(method.body, i + 1))
                lines.append(f"{p}}}")
            return lines
        if isinstance(node, Lambda):
            params = ", ".join(f"{pp.name} interface{{}}" for pp in node.params if not pp.vararg and not pp.kwarg)
            return [f"{p}{node.name or '_fn'} := func({params}) interface{{}} {{ return {self._v(node.body)} }}"]
        if isinstance(node, WithBlock):
            var = node.var or "_f"
            lines = [f"{p}{var}, _ := {self._v(node.expr)}"]
            lines.append(f"{p}defer {var}.Close()")
            lines.extend(self._body(node.body, i))
            return lines
        if isinstance(node, TryCatch):
            cv = node.catch_var or "err"
            lines = [f"{p}var {cv} interface{{}}"]
            lines.append(f"{p}func() {{")
            lines.append(f"{p}    defer func() {{")
            lines.append(f"{p}        if r := recover(); r != nil {{")
            lines.append(f"{p}            {cv} = r")
            if node.catch_body:
                lines.extend(self._body(node.catch_body, i + 3))
            lines.append(f"{p}        }}")
            lines.append(f"{p}    }}()")
            lines.extend(self._body(node.try_body, i + 1))
            lines.append(f"{p}}}()")
            if node.finally_body:
                lines.extend(self._body(node.finally_body, i))
            return lines
        if isinstance(node, Raise): return [f"{p}panic({self._v(node.message) if node.message else '\"Error\"'})"]
        if isinstance(node, Assert): return [f"{p}if !({self._cond(node.condition)}) {{ fmt.Println(\"assertion failed\"); os.Exit(1) }}"]
        if isinstance(node, RawBlock): return [f"{p}// raw ({node.language})"] + [f"{p}// {l}" for l in node.code.split("\n")]
        return [f"{p}// FIXME: {node.type}"]

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
        params = ", ".join(f"{pp.name} any" for pp in n.params if not pp.vararg and not pp.kwarg)
        lines = [f"{p}func {n.name}({params}) any {{"]
        lines.extend(self._body(n.body, i+1))
        lines.append(f"{p}}}")
        return lines

    def _list(self, n, p):
        nm = n.name or "arr"
        if n.action == "create": return [f"{p}{nm} := []any{{{', '.join(self._v(x) for x in n.items)}}}"]
        if n.action == "append": return [f"{p}{nm} = append({nm}, {self._v(n.value)})"]
        if n.action == "pop": return [f"{p}{nm} = {nm}[:len({nm})-1]"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} := len({nm})"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}{n.result_name} := strings.Join({nm}, {self._v(n.value)})"]
        if n.action == "sort" and n.result_name: return [f"{p}sort.Slice({nm}, func(i, j int) bool {{ return fmt.Sprint({nm}[i]) < fmt.Sprint({nm}[j]) }})"]
        if n.action == "contains" and n.value and n.result_name:
            return [f"{p}{n.result_name} := false; for _, v := range {nm} {{ if v == {self._v(n.value)} {{ {n.result_name} = true; break }} }}"]
        return [f"{p}// list: {n.action}"]

    def _dict(self, n, p):
        nm = n.name or "m"
        if n.action == "create":
            if not n.items: return [f"{p}{nm} := make(map[string]any)"]
            pairs = [f"{self._v(k)}: {self._v(v)}" for k, v in n.items]
            return [f"{p}{nm} := map[string]any{{{', '.join(pairs)}}}"]
        if n.action == "get" and n.key and n.result_name: return [f"{p}{n.result_name}, _ := {nm}[{self._v(n.key)}]"]
        if n.action == "set" and n.key: return [f"{p}{nm}[{self._v(n.key)}] = {self._v(n.value)}"]
        if n.action == "delete" and n.key: return [f"{p}delete({nm}, {self._v(n.key)})"]
        if n.action == "keys" and n.result_name: return [f"{p}{n.result_name} := make([]string, 0); for k := range {nm} {{ {n.result_name} = append({n.result_name}, k) }}"]
        if n.action == "values" and n.result_name: return [f"{p}{n.result_name} := make([]any, 0); for _, v := range {nm} {{ {n.result_name} = append({n.result_name}, v) }}"]
        if n.action == "len" and n.result_name: return [f"{p}{n.result_name} := len({nm})"]
        if n.action == "contains" and n.key and n.result_name: return [f"{p}_, {n.result_name} := {nm}[{self._v(n.key)}]"]
        return [f"{p}// dict: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f"{p}data, _ := os.ReadFile({path})", f"{p}{n.name} := string(data)"]
        if n.op == "write" and n.content: return [f"{p}os.WriteFile({path}, []byte({self._v(n.content)}), 0644)"]
        if n.op == "exists": return [f"{p}_, {n.name or '_err'} := os.Stat({path}); {n.name or '_exists'} := !os.IsNotExist(_err)"]
        if n.op == "mkdir": return [f"{p}os.MkdirAll({path}, 0755)"]
        return [f"{p}// file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)
    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind == "int": return str(v.value)
        if v.kind == "float": return f"{v.value}" if "." in str(v.value) else f"{v.value}.0"
        if v.kind == "bool": return "true" if v.value else "false"
        if v.kind == "null": return "nil"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "[]any{" + ", ".join(self._v(p) for p in v.parts) + "}" if v.parts else "[]any{}"
        if v.kind == "dict": return "map[string]any{}"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o); m = {"and": "&&", "or": "||"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o); m = {"not": "!"}
            return f"({m.get(os, os)}{self._v(x)})"
        if v.kind == "subscript" and v.parts and len(v.parts) >= 2: return f"{self._v(v.parts[0])}[{self._v(v.parts[1])}]"
        if v.kind == "fstring" and v.parts:
            fmt_str = ""
            args = []
            for p in v.parts:
                if p.kind == "string":
                    fmt_str += str(p.value).replace("%", "%%")
                else:
                    fmt_str += "%v"
                    args.append(self._v(p))
            if args:
                return f'fmt.Sprintf("{fmt_str}", {", ".join(args)})'
            return f'"{fmt_str}"'
        return repr(v.value)
    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'",'"')) else s
    def _cond(self, c):
        if isinstance(c, CompoundCondition):
            bool_map = {"and": " && ", "or": " || "}
            return f"({self._cond(c.left)}{bool_map.get(c.op, ' && ')}{self._cond(c.right)})"
        m = {"==": "==", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"

def emit_go(ir: ScriptIR) -> str: return GoEmitter().emit(ir)
