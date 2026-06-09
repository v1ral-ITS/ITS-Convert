"""Parse PowerShell source into IR (line-based heuristic parser)."""
from __future__ import annotations

import re
from itsconvert.ir import (
    ScriptIR, Value, Condition, IRNode,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, While, Break, Continue, Pass,
    FunctionDef, Return, Import, EnvVar, Argv,
)
from itsconvert.errors import ParseError
from itsconvert.translators import Parser


class PS1Parser(Parser):
    """Parse PowerShell source into ScriptIR."""

    def parse(self, source: str) -> ScriptIR:
        lines = source.splitlines()
        nodes: list[IRNode] = []
        warnings: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("#"):
                nodes.append(Comment(text=line.lstrip("#").strip()))
                i += 1
                continue
            if line.startswith("Write-Host"):
                content = line[len("Write-Host"):].strip()
                no_newline = "-NoNewline" in content
                content = content.replace("-NoNewline", "").strip()
                val = content.strip('"').strip("'")
                nodes.append(Print(values=[Value(kind="string", value=val)], end="" if no_newline else "\n"))
                i += 1
                continue
            if line.startswith("Read-Host"):
                m = re.match(r'Read-Host\s+"([^"]*)"', line)
                prompt = m.group(1) if m else ""
                i += 1
                continue  # input is usually part of assignment, handled below
            if re.match(r'\$\w+\s*=\s*Read-Host', line):
                m = re.match(r'\$(\w+)\s*=\s*Read-Host\s+"([^"]*)"', line)
                if m:
                    nodes.append(Input(name=m.group(1), prompt=m.group(2)))
                else:
                    m2 = re.match(r'\$(\w+)\s*=\s*Read-Host', line)
                    if m2:
                        nodes.append(Input(name=m2.group(1), prompt=""))
                i += 1
                continue
            if line.startswith("exit "):
                code = int(line.split()[1]) if line.split()[1].isdigit() else 0
                nodes.append(Exit(code=code))
                i += 1
                continue
            if re.match(r'\$env:\w+\s*=', line):
                m = re.match(r'\$env:(\w+)\s*=\s*(.*)', line)
                if m:
                    nodes.append(EnvVar(action="set", name=m.group(1), value=Value(kind="string", value=m.group(2).strip('"').strip("'"))))
                i += 1
                continue
            if line.startswith("if "):
                m = re.match(r'if\s+\((.+?)\)\s*\{', line)
                if m:
                    cond = self._parse_condition(m.group(1))
                    then_body, elif_branches, else_body, end_i = self._parse_if_block(lines, i + 1)
                    nodes.append(If(condition=cond, then_body=then_body, elif_branches=elif_branches, else_body=else_body))
                    i = end_i + 1
                    continue
            if line.startswith("foreach "):
                m = re.match(r'foreach\s+\$(\w+)\s+in\s+(.+?)\s*\{', line)
                if m:
                    var = m.group(1)
                    iterable = m.group(2).strip()
                    body, end_i = self._parse_block(lines, i + 1)
                    nodes.append(For(var=var, iterable=Value(kind="string", value=iterable), body=body))
                    i = end_i + 1
                    continue
            if line.startswith("for ("):
                m = re.match(r'for\s+\(\s*\$(\w+)\s*=\s*(\d+);\s*\$\1\s*(-lt|-le)\s*(\d+);', line)
                if m:
                    var, start, op, stop = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
                    body, end_i = self._parse_block(lines, i + 1)
                    nodes.append(ForRange(var=var, start=Value(kind="int", value=start),
                                         stop=Value(kind="int", value=stop), body=body))
                    i = end_i + 1
                    continue
            if line.startswith("while "):
                m = re.match(r'while\s+\((.+?)\)\s*\{', line)
                if m:
                    cond = self._parse_condition(m.group(1))
                    body, end_i = self._parse_block(lines, i + 1)
                    nodes.append(While(condition=cond, body=body))
                    i = end_i + 1
                    continue
            if line.startswith("function "):
                m = re.match(r'function\s+(\w+)\s*\{', line)
                if m:
                    fname = m.group(1)
                    body, end_i = self._parse_block(lines, i + 1)
                    nodes.append(FunctionDef(name=fname, body=body))
                    i = end_i + 1
                    continue
            # variable assignment: $VAR = value
            assign_match = re.match(r'^\$(\w+)\s*=\s*(.*)', line)
            if assign_match:
                name = assign_match.group(1)
                raw_val = assign_match.group(2).strip().strip('"').strip("'")
                nodes.append(Assign(name=name, value=Value(kind="string", value=raw_val)))
                i += 1
                continue
            # fallback: command
            nodes.append(Command(command=line, args=[], capture=False, name=None))
            i += 1

        return ScriptIR(source_language="ps1", nodes=nodes, warnings=warnings)

    def _parse_condition(self, cond_str: str) -> Condition:
        m = re.match(r'(\$\w+)\s+(-eq|-ne|-gt|-lt|-ge|-le)\s+(.+)', cond_str.strip())
        if m:
            op_map = {"-eq": "==", "-ne": "!=", "-gt": ">", "-lt": "<", "-ge": ">=", "-le": "<="}
            op = op_map.get(m.group(2), "==")
            right = m.group(3).strip().strip('"').strip("'")
            return Condition(left=Value(kind="var", value=m.group(1).lstrip("$")), op=op, right=Value(kind="string", value=right))
        return Condition(left=Value(kind="string", value=cond_str), op="!=", right=Value(kind="null"))

    def _parse_block(self, lines: list[str], start: int) -> tuple[list[IRNode], int]:
        nodes: list[IRNode] = []
        depth = 1
        i = start
        while i < len(lines):
            line = lines[i].strip()
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                return nodes, i
            result = self._simple_line(line)
            if result:
                nodes.append(result)
            i += 1
        return nodes, i

    def _parse_if_block(self, lines: list[str], start: int) -> tuple[list[IRNode], list[ElifBranch], list[IRNode], int]:
        then_body: list[IRNode] = []
        elif_branches: list[ElifBranch] = []
        else_body: list[IRNode] = []
        section = "then"
        depth = 1
        i = start
        while i < len(lines):
            line = lines[i].strip()
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                return then_body, elif_branches, else_body, i
            if re.match(r'\}\s*elseif\s+\(', line):
                m = re.match(r'\}\s*elseif\s+\((.+?)\)\s*\{', line)
                if m:
                    cond = self._parse_condition(m.group(1))
                    section = "elif"
                    elif_branches.append(ElifBranch(condition=cond, body=[]))
                i += 1
                continue
            if re.match(r'\}\s*else\s*\{', line):
                section = "else"
                i += 1
                continue
            result = self._simple_line(line)
            if result:
                if section == "then":
                    then_body.append(result)
                elif section == "elif" and elif_branches:
                    elif_branches[-1].body.append(result)
                elif section == "else":
                    else_body.append(result)
            i += 1
        return then_body, elif_branches, else_body, i

    def _simple_line(self, line: str) -> IRNode | None:
        if not line:
            return None
        if line.startswith("#"):
            return Comment(text=line.lstrip("#").strip())
        if line.startswith("Write-Host"):
            content = line[len("Write-Host"):].strip().strip('"').strip("'")
            return Print(values=[Value(kind="string", value=content)], end="\n")
        if line.startswith("break"):
            return Break()
        if line.startswith("continue"):
            return Continue()
        if line == "return" or line.startswith("return "):
            val = line[7:].strip() if line.startswith("return ") else None
            return Return(value=Value(kind="string", value=val.strip('"').strip("'")) if val else None)
        assign = re.match(r'^\$(\w+)\s*=\s*(.*)', line)
        if assign:
            return Assign(name=assign.group(1), value=Value(kind="string", value=assign.group(2).strip().strip('"').strip("'")))
        return Command(command=line, args=[], capture=False, name=None)
