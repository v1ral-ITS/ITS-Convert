"""Parse CMD/batch source into IR (line-based heuristic parser)."""
from __future__ import annotations

import re
from itsconvert.ir import (
    ScriptIR, Value, Condition, ConditionExpr, CompoundCondition, IRNode,
    Comment, Assign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, EnvVar, FunctionDef, Return, Break, Continue,
)
from itsconvert.errors import ParseError
from itsconvert.translators import Parser


class CMDParser(Parser):
    def parse(self, source: str) -> ScriptIR:
        lines = source.splitlines()
        nodes: list[IRNode] = []
        warnings: list[str] = []
        fallbacks = 0
        i = 0
        # First pass: collect subroutine labels as FunctionDef
        subroutines: dict[str, int] = {}
        for idx, line in enumerate(lines):
            if re.match(r'^:(\w+)', line.strip()):
                label = re.match(r'^:(\w+)', line.strip()).group(1)
                subroutines[label] = idx

        while i < len(lines):
            line = lines[i].strip()
            if not line or line.lower() in ("@echo off", "@echo on", "setlocal enabledelayedexpansion",
                                             "setlocal enableextensions", "endlocal", "@cls"):
                i += 1
                continue
            if line.startswith("::") or line.upper().startswith("REM ") or line.upper() == "REM":
                text = line[2:].strip() if line.startswith("::") else line[4:].strip()
                nodes.append(Comment(text=text))
                i += 1
                continue
            # :label (subroutine definition) — collect body until next label or exit /b
            if re.match(r'^:(\w+)', line):
                m = re.match(r'^:(\w+)', line)
                label = m.group(1)
                body, end_i = self._parse_sub_body(lines, i + 1)
                nodes.append(FunctionDef(name=label, body=body))
                i = end_i
                continue
            # echo
            if line.lower().startswith("echo(") or line.lower() == "echo":
                nodes.append(Print(values=[], end="\n"))
                i += 1
                continue
            if re.match(r'^@?echo\s', line, re.IGNORECASE):
                rest = re.sub(r'^@?echo\s+', '', line, flags=re.IGNORECASE).strip()
                nodes.append(Print(values=[Value(kind="string", value=rest)], end="\n"))
                i += 1
                continue
            # set /p for input
            if re.match(r'^set\s+/p', line, re.IGNORECASE):
                m = re.match(r'^set\s+/p\s+"?(\w+)"?=\s*"?([^"]*)"?', line, re.IGNORECASE)
                if m:
                    nodes.append(Input(name=m.group(1), prompt=m.group(2)))
                else:
                    m2 = re.match(r'^set\s+/p\s+(\w+)=', line, re.IGNORECASE)
                    if m2:
                        nodes.append(Input(name=m2.group(1), prompt=""))
                i += 1
                continue
            # exit /b or exit
            if re.match(r'^exit\s*/b', line, re.IGNORECASE) or re.match(r'^exit\b', line, re.IGNORECASE):
                parts = line.split()
                code_str = parts[-1] if len(parts) > 1 and parts[-1].isdigit() else "0"
                nodes.append(Exit(code=int(code_str)))
                i += 1
                continue
            # set VAR=value
            if re.match(r'^set\s+', line, re.IGNORECASE):
                # set /a for arithmetic
                if re.match(r'^set\s+/a', line, re.IGNORECASE):
                    m = re.match(r'^set\s+/a\s+(\w+)\s*=\s*(.+)', line, re.IGNORECASE)
                    if m:
                        nodes.append(Assign(name=m.group(1), value=Value(kind="var", value=m.group(2).strip())))
                    i += 1
                    continue
                m = re.match(r'^set\s+"?(\w+)=([^"]*)"?', line, re.IGNORECASE)
                if m:
                    nodes.append(Assign(name=m.group(1), value=Value(kind="string", value=m.group(2))))
                i += 1
                continue
            # if /i, if exist, if errorlevel, if defined
            if re.match(r'^if\b', line, re.IGNORECASE):
                cond, then_line, skip = self._parse_if_line(line)
                if cond and then_line:
                    then_node = self._simple_line(then_line)
                    then_body = [then_node] if then_node else []
                    nodes.append(If(condition=cond, then_body=then_body))
                elif cond:
                    # multi-line if (parenthesized block - less common in CMD but handle it)
                    nodes.append(If(condition=cond, then_body=[]))
                i += 1
                continue
            # for /l loop: FOR /L %%var IN (start,step,end) DO cmd
            if re.match(r'^for\s+/l', line, re.IGNORECASE):
                m = re.match(r'^for\s+/l\s+%%(\w+)\s+in\s+\((\d+),(\d+),(\d+)\)\s+do\s+(.+)', line, re.IGNORECASE)
                if m:
                    var, start_v, step_v, stop_v, cmd_str = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
                    cmd_node = self._simple_line(cmd_str.strip())
                    body = [cmd_node] if cmd_node else []
                    nodes.append(ForRange(var=var, start=Value(kind="int", value=start_v),
                                         stop=Value(kind="int", value=stop_v + 1),
                                         step=Value(kind="int", value=step_v), body=body))
                i += 1
                continue
            # for /f loop: FOR /F %%var IN (...) DO cmd
            if re.match(r'^for\s+/[fd]', line, re.IGNORECASE):
                m = re.match(r'^for\s+/[fd]\s+(?:"[^"]*"\s+)?%%(\w+)\s+in\s+\((.+?)\)\s+do\s+(.+)', line, re.IGNORECASE)
                if m:
                    var, iterable_str, cmd_str = m.group(1), m.group(2), m.group(3)
                    cmd_node = self._simple_line(cmd_str.strip())
                    body = [cmd_node] if cmd_node else []
                    from itsconvert.ir import For
                    nodes.append(For(var=var, iterable=Value(kind="string", value=iterable_str), body=body))
                i += 1
                continue
            # goto :label
            if re.match(r'^goto\s+', line, re.IGNORECASE):
                m = re.match(r'^goto\s+:?(\w+)', line, re.IGNORECASE)
                if m:
                    label = m.group(1)
                    warnings.append(f"goto :{label} converted to command")
                    nodes.append(Command(command=f"goto:{label}", args=[], capture=False, name=None))
                i += 1
                continue
            # call :subroutine
            if re.match(r'^call\s+:', line, re.IGNORECASE):
                m = re.match(r'^call\s+:(\w+)\s*(.*)', line, re.IGNORECASE)
                if m:
                    fn_name = m.group(1)
                    args_str = m.group(2).strip()
                    args = [Value(kind="string", value=a) for a in args_str.split() if a] if args_str else []
                    nodes.append(Command(command=f"call:{fn_name}", args=args, capture=False, name=None))
                i += 1
                continue
            # generic command
            node = self._simple_line(line)
            if node:
                nodes.append(node)
            else:
                fallbacks += 1
            i += 1

        total = len(nodes) or 1
        confidence = max(0.0, 1.0 - (fallbacks / total) * 0.5)
        return ScriptIR(source_language="cmd", nodes=nodes, warnings=warnings, confidence=round(confidence, 2))

    def _parse_if_line(self, line: str) -> tuple[ConditionExpr | None, str | None, int]:
        """Parse a CMD if line and return (condition, then_clause, skip_count)."""
        # if /i "a" == "b" cmd
        m = re.match(r'^if\s+(?:/i\s+)?"?([^"=]+)"?\s+(==|neq|lss|gtr|leq|geq|equ|not\s+==)\s+"?([^"]+)"?\s+(.+)', line, re.IGNORECASE)
        if m:
            left, op_str, right, then_clause = m.group(1).strip(), m.group(2).strip().lower(), m.group(3).strip(), m.group(4).strip()
            op_map = {"==": "==", "neq": "!=", "lss": "<", "gtr": ">", "leq": "<=", "geq": ">=", "equ": "==", "not ==": "!="}
            op = op_map.get(op_str, "==")
            cond = Condition(left=Value(kind="string", value=left), op=op, right=Value(kind="string", value=right))
            return cond, then_clause, 0
        # if exist FILE cmd
        m = re.match(r'^if\s+exist\s+(\S+)\s+(.+)', line, re.IGNORECASE)
        if m:
            cond = Condition(left=Value(kind="var", value=m.group(1)), op="!=", right=Value(kind="null"))
            return cond, m.group(2).strip(), 0
        # if not exist FILE cmd
        m = re.match(r'^if\s+not\s+exist\s+(\S+)\s+(.+)', line, re.IGNORECASE)
        if m:
            cond = Condition(left=Value(kind="var", value=m.group(1)), op="==", right=Value(kind="null"))
            return cond, m.group(2).strip(), 0
        # if errorlevel N cmd
        m = re.match(r'^if\s+errorlevel\s+(\d+)\s+(.+)', line, re.IGNORECASE)
        if m:
            cond = Condition(left=Value(kind="var", value="ERRORLEVEL"), op=">=", right=Value(kind="int", value=int(m.group(1))))
            return cond, m.group(2).strip(), 0
        # if defined VAR cmd
        m = re.match(r'^if\s+defined\s+(\w+)\s+(.+)', line, re.IGNORECASE)
        if m:
            cond = Condition(left=Value(kind="var", value=m.group(1)), op="!=", right=Value(kind="null"))
            return cond, m.group(2).strip(), 0
        return None, None, 0

    def _parse_sub_body(self, lines: list[str], start: int) -> tuple[list[IRNode], int]:
        """Parse lines until next :label or end of file, collecting subroutine body."""
        body: list[IRNode] = []
        i = start
        while i < len(lines):
            line = lines[i].strip()
            # Stop at next label or end of script
            if re.match(r'^:\w+', line):
                return body, i
            if re.match(r'^exit\s*/b', line, re.IGNORECASE):
                body.append(Return(value=None))
                return body, i + 1
            n = self._simple_line(line)
            if n:
                body.append(n)
            i += 1
        return body, i

    def _simple_line(self, line: str) -> IRNode | None:
        if not line:
            return None
        if line.startswith("::") or line.upper().startswith("REM "):
            return Comment(text=line[2:].strip() if line.startswith("::") else line[4:].strip())
        if re.match(r'^@?echo\s', line, re.IGNORECASE):
            rest = re.sub(r'^@?echo\s+', '', line, flags=re.IGNORECASE).strip()
            return Print(values=[Value(kind="string", value=rest)], end="\n")
        if re.match(r'^set\s+"?(\w+)=', line, re.IGNORECASE):
            m = re.match(r'^set\s+"?(\w+)=([^"]*)"?', line, re.IGNORECASE)
            if m:
                return Assign(name=m.group(1), value=Value(kind="string", value=m.group(2)))
        return Command(command=line, args=[], capture=False, name=None)


