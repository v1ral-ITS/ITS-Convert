"""Parse JavaScript/TypeScript source into IR (heuristic line-based parser)."""
from __future__ import annotations

import re
from itsconvert.ir import (
    ScriptIR, Value, Condition, ConditionExpr, CompoundCondition, IRNode,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, While, Break, Continue, Pass,
    FunctionDef, Param, Return, Import, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, Lambda,
)
from itsconvert.translators import Parser

# ${var} or ${expr} interpolation in template literals
_TMPL_VAR_RE = re.compile(r'\$\{([^}]+)\}')


class JSParser(Parser):
    """Parse JavaScript/TypeScript source into ScriptIR using heuristic line-based parsing."""

    def parse(self, source: str, lang: str = "js") -> ScriptIR:
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
            # import / require
            if stripped.startswith("import ") or re.match(r'(?:const|let|var)\s+\w+\s*=\s*require\(', stripped):
                imp = self._parse_import(stripped)
                if imp:
                    nodes.append(imp)
                i += 1
                continue
            # console.log
            m = re.match(r'console\.(log|warn|error|info)\s*\((.+)\)\s*;?$', stripped)
            if m:
                args_str = m.group(2)
                vals = self._parse_call_args(args_str)
                nodes.append(Print(values=vals))
                i += 1
                continue
            # process.exit
            m = re.match(r'process\.exit\s*\(\s*(\d*)\s*\)\s*;?$', stripped)
            if m:
                nodes.append(Exit(code=int(m.group(1)) if m.group(1) else 0))
                i += 1
                continue
            # throw new Error(...)
            m = re.match(r'throw\s+new\s+\w+\s*\((.+)\)\s*;?$', stripped)
            if m:
                nodes.append(Raise(message=self._parse_value(m.group(1).strip().strip('"').strip("'"))))
                i += 1
                continue
            # if (...) { ... } [else if (...) { }] [else { }]
            if re.match(r'if\s*\(', stripped):
                node, end_i = self._parse_if(lines, i, warnings)
                if node:
                    nodes.append(node)
                    i = end_i
                    continue
            # for (let/var/const i = 0; i < N; i++) or for...of / for...in
            if stripped.startswith("for ") or stripped.startswith("for("):
                node, end_i = self._parse_for(lines, i, warnings)
                if node:
                    nodes.append(node)
                    i = end_i
                    continue
            # while (...) {
            if re.match(r'while\s*\(', stripped):
                node, end_i = self._parse_while(lines, i, warnings)
                if node:
                    nodes.append(node)
                    i = end_i
                    continue
            # try { ... } catch (e) { ... } [finally { }]
            if re.match(r'^try\s*\{', stripped):
                node, end_i = self._parse_try(lines, i, warnings)
                nodes.append(node)
                i = end_i
                continue
            # function name(...) {
            m = re.match(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*\{', stripped)
            if m:
                fname, raw_params = m.group(1), m.group(2)
                params = self._parse_params(raw_params)
                body, end_i = self._collect_block(lines, i)
                nodes.append(FunctionDef(name=fname, params=params, body=self._parse_block_lines(body, warnings)))
                i = end_i
                continue
            # const/let/var with arrow function: const f = (x) => ...
            m = re.match(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>\s*(.+)', stripped)
            if not m:
                m = re.match(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(\w+)\s*=>\s*(.+)', stripped)
            if m:
                name, raw_params, body_str = m.group(1), m.group(2) if '(' in m.group(0) else m.group(2), m.group(3).rstrip(';')
                params = self._parse_params(raw_params)
                nodes.append(Lambda(name=name, params=params, body=self._parse_value(body_str.strip())))
                i += 1
                continue
            # const/let/var x = expr
            m = re.match(r'(?:const|let|var)\s+(\w+)\s*=\s*(.+?)(?:\s*;)?$', stripped)
            if m:
                name, val_str = m.group(1), m.group(2).rstrip(';')
                nodes.append(Assign(name=name, value=self._parse_value(val_str.strip())))
                i += 1
                continue
            # x = expr (reassignment)
            m = re.match(r'^(\w+)\s*=\s*(.+?)(?:\s*;)?$', stripped)
            if m and not stripped.startswith("//"):
                name, val_str = m.group(1), m.group(2).rstrip(';')
                nodes.append(Assign(name=name, value=self._parse_value(val_str.strip())))
                i += 1
                continue
            # x += expr
            m = re.match(r'^(\w+)\s*(\+=|-=|\*=|\/=|%=)\s*(.+?)(?:\s*;)?$', stripped)
            if m:
                op_map = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%"}
                nodes.append(AugAssign(name=m.group(1), op=op_map[m.group(2)], value=self._parse_value(m.group(3).rstrip(';'))))
                i += 1
                continue
            # return
            m = re.match(r'^return\s*(.*?)(?:\s*;)?$', stripped)
            if m:
                ret_str = m.group(1).strip()
                nodes.append(Return(value=self._parse_value(ret_str) if ret_str else None))
                i += 1
                continue
            # break / continue
            if stripped.rstrip(';') == "break":
                nodes.append(Break()); i += 1; continue
            if stripped.rstrip(';') == "continue":
                nodes.append(Continue()); i += 1; continue
            # process.env access
            m = re.match(r'(?:const|let|var)\s+(\w+)\s*=\s*process\.env\.(\w+)', stripped)
            if m:
                nodes.append(EnvVar(action="get", name=m.group(2), result_name=m.group(1)))
                i += 1
                continue
            # generic expression statement (function call, etc.)
            m = re.match(r'^(\w[\w.]*)\s*\((.*)?\)\s*;?$', stripped)
            if m:
                name_str = m.group(1)
                args = self._parse_call_args(m.group(2) or "")
                nodes.append(Command(command=name_str, args=args, capture=False, name=None))
                i += 1
                continue
            fallbacks += 1
            i += 1

        total = len(nodes) or 1
        confidence = max(0.0, 1.0 - (fallbacks / total) * 0.5)
        src_lang = "ts" if lang == "ts" else "js"
        return ScriptIR(source_language=src_lang, nodes=nodes, warnings=warnings, confidence=round(confidence, 2))

    def _parse_import(self, line: str) -> Import | None:
        # import { a, b } from 'mod'
        m = re.match(r"import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]", line)
        if m:
            names = [n.strip() for n in m.group(1).split(",")]
            return Import(module=m.group(2), names=names)
        # import mod from 'mod'
        m = re.match(r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]", line)
        if m:
            return Import(module=m.group(2), alias=m.group(1))
        # import 'mod'
        m = re.match(r"import\s+['\"]([^'\"]+)['\"]", line)
        if m:
            return Import(module=m.group(1))
        # const x = require('mod')
        m = re.match(r"(?:const|let|var)\s+(\w+)\s*=\s*require\(['\"]([^'\"]+)['\"]\)", line)
        if m:
            return Import(module=m.group(2), alias=m.group(1))
        return None

    def _parse_params(self, raw: str) -> list[Param]:
        params = []
        for p in raw.split(","):
            p = p.strip()
            if not p:
                continue
            # TypeScript typed: name: Type or name: Type = default
            m = re.match(r'(\w+)\s*:\s*\w+(?:\s*=\s*(.+))?', p)
            if m:
                default = self._parse_value(m.group(2).strip()) if m.group(2) else None
                params.append(Param(name=m.group(1), default=default))
            else:
                # Default value: name = default
                m2 = re.match(r'(\w+)\s*=\s*(.+)', p)
                if m2:
                    params.append(Param(name=m2.group(1), default=self._parse_value(m2.group(2).strip())))
                elif p.startswith("..."):
                    params.append(Param(name=p[3:], vararg=True))
                else:
                    params.append(Param(name=p))
        return params

    def _parse_value(self, s: str) -> Value:
        s = s.strip()
        if not s:
            return Value(kind="null")
        # null / undefined
        if s in ("null", "undefined"):
            return Value(kind="null")
        # boolean
        if s == "true":
            return Value(kind="bool", value=True)
        if s == "false":
            return Value(kind="bool", value=False)
        # integer
        if re.match(r'^-?\d+$', s):
            return Value(kind="int", value=int(s))
        # float
        if re.match(r'^-?\d+\.\d+$', s):
            return Value(kind="float", value=float(s))
        # template literal: `Hello, ${name}!`
        if s.startswith("`") and s.endswith("`"):
            inner = s[1:-1]
            if _TMPL_VAR_RE.search(inner):
                parts: list[Value] = []
                pos = 0
                for m in _TMPL_VAR_RE.finditer(inner):
                    if m.start() > pos:
                        parts.append(Value(kind="string", value=inner[pos:m.start()]))
                    parts.append(Value(kind="var", value=m.group(1).strip()))
                    pos = m.end()
                if pos < len(inner):
                    parts.append(Value(kind="string", value=inner[pos:]))
                return Value(kind="fstring", parts=parts)
            return Value(kind="string", value=inner)
        # string literal
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return Value(kind="string", value=s[1:-1])
        # array literal
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            if not inner:
                return Value(kind="list", parts=[])
            parts = [self._parse_value(a.strip()) for a in inner.split(",")]
            return Value(kind="list", parts=parts)
        # identifier (variable)
        if re.match(r'^[a-zA-Z_$][\w$]*$', s):
            return Value(kind="var", value=s)
        # binary expression (simple a op b)
        m = re.match(r'^(.+?)\s*(\+|-|\*|\/|%|&&|\|\||===|!==|==|!=|>=|<=|>|<)\s*(.+)$', s)
        if m:
            op = m.group(2)
            op_map = {"&&": "and", "||": "or", "===": "==", "!==": "!="}
            return Value(kind="binop", parts=[
                self._parse_value(m.group(1).strip()),
                Value(kind="string", value=op_map.get(op, op)),
                self._parse_value(m.group(3).strip()),
            ])
        return Value(kind="var", value=s)

    def _parse_call_args(self, args_str: str) -> list[Value]:
        if not args_str.strip():
            return []
        # String-aware split by comma (tracks quotes and brackets)
        parts: list[str] = []
        depth = 0
        in_str: str | None = None
        current: list[str] = []
        for c in args_str:
            if in_str:
                current.append(c)
                if c == in_str:
                    in_str = None
            elif c in ('"', "'", "`"):
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
        return [self._parse_value(p) for p in parts if p]

    def _parse_condition(self, cond_str: str) -> ConditionExpr:
        cond_str = cond_str.strip()
        # Remove outer parentheses
        if cond_str.startswith("(") and cond_str.endswith(")"):
            cond_str = cond_str[1:-1]
        # Compound: && / ||
        for sep, bool_op in [(" && ", "and"), (" || ", "or")]:
            if sep in cond_str:
                idx = cond_str.find(sep)
                return CompoundCondition(
                    left=self._parse_condition(cond_str[:idx]),
                    op=bool_op,
                    right=self._parse_condition(cond_str[idx + len(sep):]),
                )
        # Comparison
        m = re.match(r'(.+?)\s*(===|!==|==|!=|>=|<=|>|<)\s*(.+)', cond_str)
        if m:
            op_map = {"===": "==", "!==": "!=", "==": "==", "!=": "!=",
                      ">=": ">=", "<=": "<=", ">": ">", "<": "<"}
            return Condition(left=self._parse_value(m.group(1).strip()),
                             op=op_map.get(m.group(2), "=="),
                             right=self._parse_value(m.group(3).strip()))
        return Condition(left=self._parse_value(cond_str), op="!=", right=Value(kind="bool", value=False))

    def _collect_block(self, lines: list[str], start: int) -> tuple[list[str], int]:
        """Collect the body lines of a brace-delimited block, return (body_lines, next_i).

        If the closing brace line also contains an ``else`` clause (e.g. ``} else {``),
        ``next_i`` points *at* that line so the caller can process the else branch.
        """
        body: list[str] = []
        i = start
        depth = 0
        started = False
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            opens = line.count("{")
            closes = line.count("}")
            if opens > 0 and not started:
                started = True
                # If the start line begins with "}" it's a "} else {" - only count opens
                if stripped.startswith("}"):
                    depth = opens
                else:
                    depth += opens - closes
                if depth <= 0:
                    return body, i + 1
                i += 1
                continue
            if started:
                # "} else {" or "} else if (...) {" closes our block AND starts else
                if stripped.startswith("}") and re.search(r'\}\s*else\b', stripped):
                    return body, i
                depth += opens - closes
                if depth <= 0:
                    return body, i + 1
                body.append(line)
            i += 1
        return body, i

    def _parse_block_lines(self, lines: list[str], warnings: list[str]) -> list[IRNode]:
        sub_parser = JSParser()
        ir = sub_parser.parse("\n".join(lines))
        return ir.nodes

    def _parse_if(self, lines: list[str], start: int, warnings: list[str]) -> tuple[If | None, int]:
        line = lines[start].strip()
        m = re.match(r'if\s*\((.+?)\)\s*\{', line)
        if not m:
            return None, start + 1
        cond = self._parse_condition(m.group(1))
        then_lines, i = self._collect_block(lines, start)
        then_body = self._parse_block_lines(then_lines, warnings)
        elif_branches: list[ElifBranch] = []
        else_body: list[IRNode] = []
        # Check for else if / else
        while i < len(lines):
            next_stripped = lines[i].strip()
            elif_m = re.match(r'(?:\}\s*)?else\s+if\s*\((.+?)\)\s*\{', next_stripped)
            else_m = re.match(r'(?:\}\s*)?else\s*\{', next_stripped)
            if elif_m:
                elif_cond = self._parse_condition(elif_m.group(1))
                elif_lines, i = self._collect_block(lines, i)
                elif_body = self._parse_block_lines(elif_lines, warnings)
                elif_branches.append(ElifBranch(condition=elif_cond, body=elif_body))
            elif else_m:
                else_lines, i = self._collect_block(lines, i)
                else_body = self._parse_block_lines(else_lines, warnings)
                break
            else:
                break
        return If(condition=cond, then_body=then_body, elif_branches=elif_branches, else_body=else_body), i

    def _parse_for(self, lines: list[str], start: int, warnings: list[str]) -> tuple[IRNode | None, int]:
        line = lines[start].strip()
        # for (let i = 0; i < N; i++)
        m = re.match(r'for\s*\(\s*(?:let|const|var)?\s*(\w+)\s*=\s*(.+?);\s*\1\s*([<>]=?)\s*(.+?);\s*\1\s*(\+\+|--|\+=\s*\d+|-=\s*\d+)\s*\)\s*\{?', line)
        if m:
            var, start_v, op, stop_v = m.group(1), m.group(2), m.group(3), m.group(4)
            body_lines, end_i = self._collect_block(lines, start)
            body = self._parse_block_lines(body_lines, warnings)
            return ForRange(var=var,
                            start=self._parse_value(start_v.strip()),
                            stop=self._parse_value(stop_v.strip()),
                            body=body), end_i
        # for (let x of arr)
        m = re.match(r'for\s*\(\s*(?:let|const|var)\s+(\w+)\s+of\s+(.+?)\s*\)\s*\{?', line)
        if m:
            var, iterable = m.group(1), m.group(2)
            body_lines, end_i = self._collect_block(lines, start)
            body = self._parse_block_lines(body_lines, warnings)
            from itsconvert.ir import For
            return For(var=var, iterable=self._parse_value(iterable), body=body), end_i
        return None, start + 1

    def _parse_while(self, lines: list[str], start: int, warnings: list[str]) -> tuple[IRNode | None, int]:
        line = lines[start].strip()
        m = re.match(r'while\s*\((.+?)\)\s*\{?', line)
        if m:
            cond = self._parse_condition(m.group(1))
            body_lines, end_i = self._collect_block(lines, start)
            body = self._parse_block_lines(body_lines, warnings)
            return While(condition=cond, body=body), end_i
        return None, start + 1

    def _parse_try(self, lines: list[str], start: int, warnings: list[str]) -> tuple[TryCatch, int]:
        try_lines, i = self._collect_block(lines, start)
        try_body = self._parse_block_lines(try_lines, warnings)
        catch_var = None
        catch_body: list[IRNode] = []
        finally_body: list[IRNode] = []
        while i < len(lines):
            next_stripped = lines[i].strip()
            catch_m = re.match(r'(?:\}\s*)?catch\s*\(\s*(\w+)\s*\)\s*\{', next_stripped)
            finally_m = re.match(r'(?:\}\s*)?finally\s*\{', next_stripped)
            if catch_m:
                catch_var = catch_m.group(1)
                catch_lines, i = self._collect_block(lines, i)
                catch_body = self._parse_block_lines(catch_lines, warnings)
            elif finally_m:
                finally_lines, i = self._collect_block(lines, i)
                finally_body = self._parse_block_lines(finally_lines, warnings)
                break
            else:
                break
        return TryCatch(try_body=try_body, catch_var=catch_var, catch_body=catch_body, finally_body=finally_body), i


class TSParser(JSParser):
    """Parse TypeScript source into ScriptIR (extends JSParser with TS-specific patterns)."""

    def parse(self, source: str, lang: str = "ts") -> ScriptIR:  # type: ignore[override]
        ir = super().parse(source, lang="ts")
        return ir


def parse_js(source: str) -> ScriptIR:
    return JSParser().parse(source)


def parse_ts(source: str) -> ScriptIR:
    return TSParser().parse(source, lang="ts")
