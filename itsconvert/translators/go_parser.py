"""Parse Go source into IR (heuristic line-based parser)."""
from __future__ import annotations

import re
from itsconvert.ir import (
    ScriptIR, Value, Condition, ConditionExpr, CompoundCondition, IRNode,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, While, Break, Continue,
    FunctionDef, Param, Return, Import, TryCatch, Raise,
    Switch, SwitchCase,
)
from itsconvert.translators import Parser


class GoParser(Parser):
    """Parse Go source into ScriptIR using heuristic line-based parsing."""

    def parse(self, source: str) -> ScriptIR:
        lines = source.splitlines()
        nodes: list[IRNode] = []
        warnings: list[str] = []
        fallbacks = 0
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()
            if not stripped:
                i += 1
                continue
            # Single-line comment
            if stripped.startswith("//"):
                nodes.append(Comment(text=stripped[2:].strip()))
                i += 1
                continue
            # Multi-line comment
            if stripped.startswith("/*"):
                while i < len(lines) and "*/" not in lines[i]:
                    i += 1
                i += 1
                continue
            # package / import declarations (skip)
            if stripped.startswith("package ") or stripped.startswith("import "):
                # Multi-line import block
                if stripped == "import (":
                    while i < len(lines) and ")" not in lines[i]:
                        i += 1
                i += 1
                continue
            # Skip top-level import block
            if stripped == "import (":
                while i < len(lines) and lines[i].strip() != ")":
                    i += 1
                i += 1
                continue
            # fmt.Println / fmt.Printf / fmt.Print / fmt.Fprintf
            m = re.match(r'fmt\.Print(?:ln|f|)?\s*\((.+)\)', stripped)
            if m:
                args = self._parse_call_args(m.group(1))
                nodes.append(Print(values=args))
                i += 1
                continue
            # fmt.Println(os.Stderr, ...) → treat as print
            m = re.match(r'fmt\.Fprintf\s*\(\s*os\.\w+\s*,\s*(.+)\)', stripped)
            if m:
                args = self._parse_call_args(m.group(1))
                nodes.append(Print(values=args))
                i += 1
                continue
            # os.Exit(code)
            m = re.match(r'os\.Exit\s*\(\s*(\d+)\s*\)', stripped)
            if m:
                nodes.append(Exit(code=int(m.group(1))))
                i += 1
                continue
            # panic(msg)
            m = re.match(r'panic\s*\((.+)\)', stripped)
            if m:
                nodes.append(Raise(message=self._parse_value(m.group(1).strip())))
                i += 1
                continue
            # func name(params) [return_type] {
            m = re.match(r'func\s+(\w+)\s*\(([^)]*)\)(?:\s+\w+)?\s*\{', stripped)
            if m:
                fname, raw_params = m.group(1), m.group(2)
                params = self._parse_params(raw_params)
                body_lines, end_i = self._collect_block(lines, i)
                nodes.append(FunctionDef(name=fname, params=params,
                                         body=self._parse_lines(body_lines, warnings)))
                i = end_i
                continue
            # if cond {
            if re.match(r'^if\b', stripped):
                node, end_i = self._parse_if(lines, i, warnings)
                if node:
                    nodes.append(node)
                    i = end_i
                    continue
            # switch expr {
            if re.match(r'^switch\b', stripped):
                node, end_i = self._parse_switch(lines, i, warnings)
                if node:
                    nodes.append(node)
                    i = end_i
                    continue
            # for i := 0; i < N; i++
            if re.match(r'^for\b', stripped):
                node, end_i = self._parse_for(lines, i, warnings)
                if node:
                    nodes.append(node)
                    i = end_i
                    continue
            # Short var decl: x := val
            m = re.match(r'^(\w+)\s*:=\s*(.+)', stripped)
            if m:
                name, val_str = m.group(1), m.group(2).rstrip("{").strip()
                nodes.append(Assign(name=name, value=self._parse_value(val_str)))
                i += 1
                continue
            # var x type = val  or  var x = val
            m = re.match(r'^var\s+(\w+)(?:\s+\w+)?\s*(?:=\s*(.+))?', stripped)
            if m:
                name, val_str = m.group(1), (m.group(2) or "").strip()
                nodes.append(Assign(name=name, value=self._parse_value(val_str) if val_str else Value(kind="null")))
                i += 1
                continue
            # x = val (reassignment)
            m = re.match(r'^(\w+)\s*=\s*(.+)', stripped)
            if m and not stripped.startswith("//"):
                nodes.append(Assign(name=m.group(1), value=self._parse_value(m.group(2).strip())))
                i += 1
                continue
            # augmented assignment: x += val
            m = re.match(r'^(\w+)\s*(\+=|-=|\*=|\/=|%=)\s*(.+)', stripped)
            if m:
                op_map = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%"}
                nodes.append(AugAssign(name=m.group(1), op=op_map[m.group(2)],
                                       value=self._parse_value(m.group(3).strip())))
                i += 1
                continue
            # return
            m = re.match(r'^return\s*(.*)', stripped)
            if m:
                ret_str = m.group(1).strip()
                nodes.append(Return(value=self._parse_value(ret_str) if ret_str else None))
                i += 1
                continue
            # break / continue
            if stripped == "break":
                nodes.append(Break()); i += 1; continue
            if stripped == "continue":
                nodes.append(Continue()); i += 1; continue
            # Closing brace
            if stripped in ("}", "{"):
                i += 1
                continue
            # Generic function call
            m = re.match(r'^([\w.]+)\s*\((.*)?\)', stripped)
            if m:
                nodes.append(Command(command=m.group(1), args=self._parse_call_args(m.group(2) or ""),
                                     capture=False, name=None))
                i += 1
                continue
            fallbacks += 1
            i += 1

        total = len(nodes) or 1
        confidence = max(0.0, 1.0 - (fallbacks / total) * 0.5)
        return ScriptIR(source_language="go", nodes=nodes, warnings=warnings, confidence=round(confidence, 2))

    def _parse_value(self, s: str) -> Value:
        s = s.strip().rstrip(";").strip()
        if not s:
            return Value(kind="null")
        if s == "nil":
            return Value(kind="null")
        if s == "true":
            return Value(kind="bool", value=True)
        if s == "false":
            return Value(kind="bool", value=False)
        if re.match(r'^-?\d+$', s):
            return Value(kind="int", value=int(s))
        if re.match(r'^-?\d+\.\d+$', s):
            return Value(kind="float", value=float(s))
        # fmt.Sprintf
        m = re.match(r'fmt\.Sprintf\s*\((.+)\)', s)
        if m:
            return Value(kind="var", value=s)
        # String with backtick
        if s.startswith("`") and s.endswith("`"):
            return Value(kind="string", value=s[1:-1])
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return Value(kind="string", value=s[1:-1])
        if re.match(r'^[a-zA-Z_]\w*$', s):
            return Value(kind="var", value=s)
        m = re.match(r'^(.+?)\s*(\+|-|\*|\/|%|&&|\|\||==|!=|>=|<=|>|<)\s*(.+)$', s)
        if m:
            return Value(kind="binop", parts=[
                self._parse_value(m.group(1).strip()),
                Value(kind="string", value=m.group(2)),
                self._parse_value(m.group(3).strip()),
            ])
        return Value(kind="var", value=s)

    def _parse_call_args(self, s: str) -> list[Value]:
        if not s.strip():
            return []
        parts: list[str] = []
        depth = 0
        current: list[str] = []
        for c in s:
            if c in "([{":
                depth += 1; current.append(c)
            elif c in ")]}":
                depth -= 1; current.append(c)
            elif c == "," and depth == 0:
                parts.append("".join(current).strip()); current = []
            else:
                current.append(c)
        if current:
            parts.append("".join(current).strip())
        return [self._parse_value(p) for p in parts if p]

    def _parse_params(self, raw: str) -> list[Param]:
        params: list[Param] = []
        for p in raw.split(","):
            p = p.strip()
            if not p:
                continue
            # name type
            parts = p.split()
            if len(parts) >= 2:
                params.append(Param(name=parts[0], type_hint=parts[-1]))
            elif parts:
                params.append(Param(name=parts[0]))
        return params

    def _parse_condition(self, s: str) -> ConditionExpr:
        s = s.strip().rstrip("{").strip()
        # Compound
        for sep, bool_op in [(" && ", "and"), (" || ", "or")]:
            if sep in s:
                idx = s.find(sep)
                return CompoundCondition(
                    left=self._parse_condition(s[:idx]),
                    op=bool_op,
                    right=self._parse_condition(s[idx + len(sep):]),
                )
        m = re.match(r'(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)', s)
        if m:
            return Condition(left=self._parse_value(m.group(1).strip()),
                             op=m.group(2),
                             right=self._parse_value(m.group(3).strip()))
        return Condition(left=self._parse_value(s), op="!=", right=Value(kind="bool", value=False))

    def _collect_block(self, lines: list[str], start: int) -> tuple[list[str], int]:
        """Collect brace-delimited block lines, return (body_lines, next_i)."""
        body: list[str] = []
        i = start
        depth = 0
        started = False
        while i < len(lines):
            opens = lines[i].count("{")
            closes = lines[i].count("}")
            if opens > 0 and not started:
                started = True
                depth += opens - closes
                if depth <= 0:
                    return body, i + 1
                i += 1
                continue
            if started:
                depth += opens - closes
                if depth <= 0:
                    return body, i + 1
                body.append(lines[i])
            i += 1
        return body, i

    def _parse_lines(self, lines: list[str], warnings: list[str]) -> list[IRNode]:
        return GoParser().parse("\n".join(lines)).nodes

    def _parse_if(self, lines: list[str], start: int, warnings: list[str]) -> tuple[If | None, int]:
        stripped = lines[start].strip()
        # if [init;] cond {
        m = re.match(r'^if\s+(?:.+;\s*)?(.+?)\s*\{', stripped)
        if not m:
            return None, start + 1
        cond = self._parse_condition(m.group(1))
        then_lines, i = self._collect_block(lines, start)
        then_body = self._parse_lines(then_lines, warnings)
        elif_branches: list[ElifBranch] = []
        else_body: list[IRNode] = []
        while i < len(lines):
            next_s = lines[i].strip()
            elif_m = re.match(r'(?:\}\s*)?else\s+if\s+(.+?)\s*\{', next_s)
            else_m = re.match(r'(?:\}\s*)?else\s*\{', next_s)
            if elif_m:
                elif_cond = self._parse_condition(elif_m.group(1))
                elif_lines, i = self._collect_block(lines, i)
                elif_branches.append(ElifBranch(condition=elif_cond,
                                                 body=self._parse_lines(elif_lines, warnings)))
            elif else_m:
                else_lines, i = self._collect_block(lines, i)
                else_body = self._parse_lines(else_lines, warnings)
                break
            else:
                break
        return If(condition=cond, then_body=then_body, elif_branches=elif_branches, else_body=else_body), i

    def _parse_for(self, lines: list[str], start: int, warnings: list[str]) -> tuple[IRNode | None, int]:
        stripped = lines[start].strip()
        # for i := 0; i < N; i++
        m = re.match(r'^for\s+(\w+)\s*:=\s*(.+?);\s*\1\s*([<>]=?)\s*(.+?);\s*\1\s*(\+\+|--|\+=\s*\d+)\s*\{', stripped)
        if m:
            var, start_v, op, stop_v = m.group(1), m.group(2), m.group(3), m.group(4)
            body_lines, end_i = self._collect_block(lines, start)
            return ForRange(var=var,
                            start=self._parse_value(start_v.strip()),
                            stop=self._parse_value(stop_v.strip()),
                            body=self._parse_lines(body_lines, warnings)), end_i
        # for _, v := range arr {  or  for k, v := range m {
        m = re.match(r'^for\s+(\w+)\s*,\s*(\w+)\s*:=\s*range\s+(\w+)\s*\{', stripped)
        if m:
            k_var, v_var, iterable = m.group(1), m.group(2), m.group(3)
            body_lines, end_i = self._collect_block(lines, start)
            body = self._parse_lines(body_lines, warnings)
            from itsconvert.ir import ForEnumerate
            return ForEnumerate(idx=k_var, var=v_var,
                                iterable=Value(kind="var", value=iterable), body=body), end_i
        # for v := range arr {
        m = re.match(r'^for\s+(\w+)\s*:=\s*range\s+(\w+)\s*\{', stripped)
        if m:
            var, iterable = m.group(1), m.group(2)
            body_lines, end_i = self._collect_block(lines, start)
            return For(var=var, iterable=Value(kind="var", value=iterable),
                       body=self._parse_lines(body_lines, warnings)), end_i
        # for cond { (while-style)
        m = re.match(r'^for\s+(.+?)\s*\{', stripped)
        if m:
            cond_str = m.group(1).strip()
            body_lines, end_i = self._collect_block(lines, start)
            return While(condition=self._parse_condition(cond_str),
                         body=self._parse_lines(body_lines, warnings)), end_i
        # for { (infinite loop)
        body_lines, end_i = self._collect_block(lines, start)
        return While(condition=Condition(left=Value(kind="bool", value=True), op="==",
                                         right=Value(kind="bool", value=True)),
                     body=self._parse_lines(body_lines, warnings)), end_i

    def _parse_switch(self, lines: list[str], start: int, warnings: list[str]) -> tuple[Switch | None, int]:
        stripped = lines[start].strip()
        m = re.match(r'^switch\s*(.*?)\s*\{', stripped)
        subject_str = m.group(1).strip() if m and m.group(1).strip() else "true"
        subject = self._parse_value(subject_str)
        body_lines, end_i = self._collect_block(lines, start)
        cases: list[SwitchCase] = []
        default_body: list[IRNode] = []
        j = 0
        while j < len(body_lines):
            case_s = body_lines[j].strip()
            cm = re.match(r'^case\s+(.+):', case_s)
            dm = re.match(r'^default:', case_s)
            if cm:
                pattern = self._parse_value(cm.group(1).strip())
                case_lines: list[str] = []
                j += 1
                while j < len(body_lines):
                    next_s = body_lines[j].strip()
                    if re.match(r'^case\s+', next_s) or re.match(r'^default:', next_s):
                        break
                    case_lines.append(body_lines[j])
                    j += 1
                cases.append(SwitchCase(pattern=pattern, body=self._parse_lines(case_lines, warnings)))
            elif dm:
                j += 1
                default_lines: list[str] = []
                while j < len(body_lines):
                    next_s = body_lines[j].strip()
                    if re.match(r'^case\s+', next_s):
                        break
                    default_lines.append(body_lines[j])
                    j += 1
                default_body = self._parse_lines(default_lines, warnings)
            else:
                j += 1
        return Switch(subject=subject, cases=cases, default_body=default_body), end_i
