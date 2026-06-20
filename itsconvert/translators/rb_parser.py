"""Parse Ruby source into IR (heuristic line-based parser)."""
from __future__ import annotations

import re
from itsconvert.ir import (
    ScriptIR, Value, Condition, ConditionExpr, CompoundCondition, IRNode,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, While, Break, Continue,
    FunctionDef, Param, Return, Import, TryCatch, Raise,
)
from itsconvert.translators import Parser

# String interpolation: #{expr}
_INTERP_RE = re.compile(r'#\{([^}]+)\}')


class RubyParser(Parser):
    """Parse Ruby source into ScriptIR using heuristic line-based parsing."""

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
            # Comment
            if stripped.startswith("#"):
                nodes.append(Comment(text=stripped[1:].strip()))
                i += 1
                continue
            # require / require_relative
            m = re.match(r'require(?:_relative)?\s+[\'"]([^\'"]+)[\'"]', stripped)
            if m:
                nodes.append(Import(module=m.group(1)))
                i += 1
                continue
            # puts / print / p
            m = re.match(r'(puts|print|p)\s+(.+)', stripped)
            if m:
                verb, rest = m.group(1), m.group(2).strip()
                end_nl = "\n" if verb in ("puts", "p") else ""
                vals = [self._parse_value(v.strip()) for v in self._split_args(rest)]
                nodes.append(Print(values=vals, end=end_nl))
                i += 1
                continue
            # gets.chomp assignment: name = gets.chomp
            m = re.match(r'(\w+)\s*=\s*(?:STDIN\.gets|gets)(?:\.chomp|\.strip)?', stripped)
            if m:
                from itsconvert.ir import Input
                nodes.append(Input(name=m.group(1), prompt=""))
                i += 1
                continue
            # def name ... end
            if re.match(r'^def\s+\w+', stripped):
                node, end_i = self._parse_def(lines, i, warnings)
                if node:
                    nodes.append(node)
                    i = end_i
                    continue
            # if ... [elsif ...] [else ...] end
            if re.match(r'^if\s+', stripped) or re.match(r'^unless\s+', stripped):
                node, end_i = self._parse_if(lines, i, warnings)
                if node:
                    nodes.append(node)
                    i = end_i
                    continue
            # LOOP_VAR.times do |var| ... end  or  N.times { |var| ... }
            m = re.match(r'(\w+|\d+)\.times\s+do\s+\|(\w+)\|\s*$', stripped)
            if m:
                count_s, var = m.group(1), m.group(2)
                body_lines, end_i = self._collect_do_block(lines, i + 1)
                body = self._parse_lines(body_lines, warnings)
                count_v = self._parse_value(count_s)
                nodes.append(ForRange(var=var, start=Value(kind="int", value=0),
                                      stop=count_v, body=body))
                i = end_i
                continue
            # arr.each do |var| ... end
            m = re.match(r'(\w+)\.each\s+do\s+\|(\w+)\|\s*$', stripped)
            if m:
                iterable, var = m.group(1), m.group(2)
                body_lines, end_i = self._collect_do_block(lines, i + 1)
                body = self._parse_lines(body_lines, warnings)
                nodes.append(For(var=var, iterable=Value(kind="var", value=iterable), body=body))
                i = end_i
                continue
            # (start..end).each do |var|
            m = re.match(r'\((\d+)\.\.(\d+)\)\.each\s+do\s+\|(\w+)\|\s*$', stripped)
            if m:
                start_v, stop_v, var = int(m.group(1)), int(m.group(2)), m.group(3)
                body_lines, end_i = self._collect_do_block(lines, i + 1)
                body = self._parse_lines(body_lines, warnings)
                nodes.append(ForRange(var=var, start=Value(kind="int", value=start_v),
                                      stop=Value(kind="int", value=stop_v + 1), body=body))
                i = end_i
                continue
            # while COND; ... end
            m = re.match(r'^while\s+(.+)', stripped)
            if m:
                cond = self._parse_condition(m.group(1).rstrip(" do").rstrip(";").strip())
                body_lines, end_i = self._collect_do_block(lines, i + 1)
                body = self._parse_lines(body_lines, warnings)
                nodes.append(While(condition=cond, body=body))
                i = end_i
                continue
            # begin / rescue / ensure / end (try/catch)
            if stripped == "begin":
                node, end_i = self._parse_begin(lines, i, warnings)
                nodes.append(node)
                i = end_i
                continue
            # raise / fail
            m = re.match(r'^(?:raise|fail)\s+(.*)', stripped)
            if m:
                nodes.append(Raise(message=self._parse_value(m.group(1).strip().strip('"').strip("'"))))
                i += 1
                continue
            # exit
            m = re.match(r'^exit(?:\s+(\d+))?\s*$', stripped)
            if m:
                nodes.append(Exit(code=int(m.group(1)) if m.group(1) else 0))
                i += 1
                continue
            # break / next (continue in Ruby)
            if stripped == "break":
                nodes.append(Break()); i += 1; continue
            if stripped == "next":
                nodes.append(Continue()); i += 1; continue
            # return
            m = re.match(r'^return\s*(.*)', stripped)
            if m:
                ret_str = m.group(1).strip()
                nodes.append(Return(value=self._parse_value(ret_str) if ret_str else None))
                i += 1
                continue
            # augmented assignment
            m = re.match(r'^(\w+)\s*(\+=|-=|\*=|\/=|%=)\s*(.+)', stripped)
            if m:
                op_map = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%"}
                nodes.append(AugAssign(name=m.group(1), op=op_map[m.group(2)], value=self._parse_value(m.group(3).strip())))
                i += 1
                continue
            # assignment: var = value (also @var, @@var, $var, CONSTANT)
            m = re.match(r'^(@{0,2}\$?\w+)\s*=\s*(.+)', stripped)
            if m and "==" not in stripped[:stripped.index("=")+1] and not re.match(r'.+=\s*$', stripped):
                nodes.append(Assign(name=m.group(1), value=self._parse_value(m.group(2).strip())))
                i += 1
                continue
            # command / method call (generic fallthrough)
            m = re.match(r'^([\w.]+)\s*\(?(.*?)\)?\s*$', stripped)
            if m:
                nodes.append(Command(command=m.group(1), args=[self._parse_value(a.strip()) for a in self._split_args(m.group(2)) if a.strip()], capture=False, name=None))
                i += 1
                continue
            fallbacks += 1
            i += 1

        total = len(nodes) or 1
        confidence = max(0.0, 1.0 - (fallbacks / total) * 0.5)
        return ScriptIR(source_language="rb", nodes=nodes, warnings=warnings, confidence=round(confidence, 2))

    def _parse_value(self, s: str) -> Value:
        s = s.strip().rstrip(";").strip()
        if not s:
            return Value(kind="null")
        if s in ("nil", "null"):
            return Value(kind="null")
        if s == "true":
            return Value(kind="bool", value=True)
        if s == "false":
            return Value(kind="bool", value=False)
        if re.match(r'^-?\d+$', s):
            return Value(kind="int", value=int(s))
        if re.match(r'^-?\d+\.\d+$', s):
            return Value(kind="float", value=float(s))
        # Double-quoted string (may have interpolation)
        if s.startswith('"') and s.endswith('"'):
            inner = s[1:-1]
            if _INTERP_RE.search(inner):
                parts: list[Value] = []
                pos = 0
                for m in _INTERP_RE.finditer(inner):
                    if m.start() > pos:
                        parts.append(Value(kind="string", value=inner[pos:m.start()]))
                    parts.append(Value(kind="var", value=m.group(1).strip()))
                    pos = m.end()
                if pos < len(inner):
                    parts.append(Value(kind="string", value=inner[pos:]))
                return Value(kind="fstring", parts=parts)
            return Value(kind="string", value=inner)
        if s.startswith("'") and s.endswith("'"):
            return Value(kind="string", value=s[1:-1])
        # Symbol
        if s.startswith(":") and re.match(r'^:\w+$', s):
            return Value(kind="string", value=s[1:])
        # Array literal
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            parts = [self._parse_value(a.strip()) for a in self._split_args(inner)] if inner else []
            return Value(kind="list", parts=parts)
        # Variable
        if re.match(r'^@{0,2}\$?\w+$', s):
            return Value(kind="var", value=s)
        return Value(kind="var", value=s)

    def _parse_condition(self, s: str) -> ConditionExpr:
        s = s.strip()
        # unless → negate
        # Remove trailing " do" or ";"
        s = re.sub(r'\s+(do|then)\s*$', '', s).rstrip(";").strip()
        # Compound: && / || / and / or
        for sep, bool_op in [(" && ", "and"), (" || ", "or"), (" and ", "and"), (" or ", "or")]:
            if sep in s:
                idx = s.find(sep)
                return CompoundCondition(
                    left=self._parse_condition(s[:idx]),
                    op=bool_op,
                    right=self._parse_condition(s[idx + len(sep):]),
                )
        # Comparison
        m = re.match(r'(.+?)\s*(==|!=|>=|<=|>|<|\.eql\?|\.equal\?)\s*(.+)', s)
        if m:
            return Condition(left=self._parse_value(m.group(1)), op="==", right=self._parse_value(m.group(3)))
        # Not / negation
        m = re.match(r'^!(.+)$', s)
        if m:
            return Condition(left=self._parse_value(m.group(1)), op="==", right=Value(kind="bool", value=False))
        return Condition(left=self._parse_value(s), op="!=", right=Value(kind="bool", value=False))

    def _split_args(self, s: str) -> list[str]:
        """Split on commas not inside brackets/parens/strings."""
        parts: list[str] = []
        depth = 0
        in_str: str | None = None
        current: list[str] = []
        for c in s:
            if in_str:
                current.append(c)
                if c == in_str:
                    in_str = None
            elif c in ('"', "'"):
                in_str = c
                current.append(c)
            elif c in "([{":
                depth += 1
                current.append(c)
            elif c in ")]}":
                depth -= 1
                current.append(c)
            elif c == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(c)
        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]

    def _collect_do_block(self, lines: list[str], start: int) -> tuple[list[str], int]:
        """Collect body lines until matching 'end' keyword."""
        body: list[str] = []
        depth = 1
        i = start
        while i < len(lines):
            stripped = lines[i].strip()
            if re.match(r'^(if|unless|while|def|do|begin|case)\b', stripped):
                depth += 1
            if stripped == "end" or re.match(r'^end\b', stripped):
                depth -= 1
                if depth <= 0:
                    return body, i + 1
            else:
                body.append(lines[i])
            i += 1
        return body, i

    def _parse_lines(self, lines: list[str], warnings: list[str]) -> list[IRNode]:
        return RubyParser().parse("\n".join(lines)).nodes

    def _parse_def(self, lines: list[str], start: int, warnings: list[str]) -> tuple[FunctionDef | None, int]:
        stripped = lines[start].strip()
        m = re.match(r'def\s+(\w+)(?:\s*\(([^)]*)\))?\s*$', stripped)
        if not m:
            return None, start + 1
        name, raw_params = m.group(1), m.group(2) or ""
        params = []
        for p in raw_params.split(","):
            p = p.strip()
            if not p:
                continue
            m2 = re.match(r'(\w+)\s*=\s*(.+)', p)
            if m2:
                params.append(Param(name=m2.group(1), default=self._parse_value(m2.group(2).strip())))
            elif p.startswith("*"):
                params.append(Param(name=p[1:], vararg=True))
            elif p:
                params.append(Param(name=p))
        body_lines, end_i = self._collect_do_block(lines, start + 1)
        body = self._parse_lines(body_lines, warnings)
        return FunctionDef(name=name, params=params, body=body), end_i

    def _parse_if(self, lines: list[str], start: int, warnings: list[str]) -> tuple[If | None, int]:
        stripped = lines[start].strip()
        is_unless = stripped.startswith("unless")
        m = re.match(r'^(?:if|unless)\s+(.+)', stripped)
        if not m:
            return None, start + 1
        cond_str = m.group(1).strip().rstrip(";").rstrip()
        cond = self._parse_condition(cond_str)
        if is_unless:
            # unless = if-not: negate by swapping condition
            cond = Condition(left=Value(kind="var", value=cond_str), op="==", right=Value(kind="bool", value=False))
        # Collect then_body up to elsif/else/end
        then_lines: list[str] = []
        elif_branches: list[ElifBranch] = []
        else_body: list[IRNode] = []
        i = start + 1
        depth = 1
        current_section = "then"
        current_elif_cond: ConditionExpr | None = None
        current_lines: list[str] = []
        while i < len(lines):
            stripped = lines[i].strip()
            if re.match(r'^(if|unless|while|def|do|begin|case)\b', stripped):
                depth += 1
            if depth == 1 and stripped.startswith("elsif "):
                if current_section == "then":
                    then_lines = current_lines[:]
                elif current_section == "elif" and current_elif_cond:
                    elif_branches.append(ElifBranch(condition=current_elif_cond,
                                                     body=self._parse_lines(current_lines, warnings)))
                em = re.match(r'^elsif\s+(.+)', stripped)
                current_elif_cond = self._parse_condition(em.group(1).strip()) if em else None
                current_lines = []
                current_section = "elif"
            elif depth == 1 and stripped == "else":
                if current_section == "then":
                    then_lines = current_lines[:]
                elif current_section == "elif" and current_elif_cond:
                    elif_branches.append(ElifBranch(condition=current_elif_cond,
                                                     body=self._parse_lines(current_lines, warnings)))
                current_lines = []
                current_section = "else"
            elif re.match(r'^end\b', stripped):
                depth -= 1
                if depth <= 0:
                    if current_section == "then":
                        then_lines = current_lines[:]
                    elif current_section == "elif" and current_elif_cond:
                        elif_branches.append(ElifBranch(condition=current_elif_cond,
                                                         body=self._parse_lines(current_lines, warnings)))
                    elif current_section == "else":
                        else_body = self._parse_lines(current_lines, warnings)
                    break
            else:
                current_lines.append(lines[i])
            i += 1
        then_body = self._parse_lines(then_lines, warnings)
        return If(condition=cond, then_body=then_body, elif_branches=elif_branches, else_body=else_body), i + 1

    def _parse_begin(self, lines: list[str], start: int, warnings: list[str]) -> tuple[TryCatch, int]:
        try_lines: list[str] = []
        rescue_lines: list[str] = []
        ensure_lines: list[str] = []
        rescue_var = None
        section = "try"
        i = start + 1
        depth = 1
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == "begin":
                depth += 1
            elif re.match(r'^rescue\b', stripped) and depth == 1:
                rescue_m = re.match(r'^rescue\s+\w+\s*(?:=>\s*(\w+))?', stripped)
                rescue_var = rescue_m.group(1) if rescue_m and rescue_m.group(1) else "e"
                section = "rescue"
            elif stripped == "ensure" and depth == 1:
                section = "ensure"
            elif re.match(r'^end\b', stripped):
                depth -= 1
                if depth <= 0:
                    break
            else:
                if section == "try":
                    try_lines.append(lines[i])
                elif section == "rescue":
                    rescue_lines.append(lines[i])
                elif section == "ensure":
                    ensure_lines.append(lines[i])
            i += 1
        return TryCatch(
            try_body=self._parse_lines(try_lines, warnings),
            catch_var=rescue_var,
            catch_body=self._parse_lines(rescue_lines, warnings),
            finally_body=self._parse_lines(ensure_lines, warnings),
        ), i + 1
