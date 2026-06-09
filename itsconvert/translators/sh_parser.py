"""Parse Bash/sh source into IR (line-based heuristic parser)."""
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


class BashParser(Parser):
    """Parse Bash/sh source into ScriptIR using line-based heuristics."""

    def parse(self, source: str) -> ScriptIR:
        lines = source.splitlines()
        nodes: list[IRNode] = []
        warnings: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line == "set -euo pipefail" or line.startswith("#!/"):
                i += 1
                continue
            if line.startswith("#"):
                nodes.append(Comment(text=line.lstrip("#").strip()))
                i += 1
                continue
            if line.startswith("echo ") or line == "echo":
                nodes.append(Print(values=[Value(kind="string", value=line[5:].strip().strip('"'))], end="\n"))
                i += 1
                continue
            if line.startswith("echo -n "):
                nodes.append(Print(values=[Value(kind="string", value=line[8:].strip().strip('"'))], end=""))
                i += 1
                continue
            if line.startswith("read "):
                m = re.match(r'read\s+(?:-r\s+)?(?:-p\s+"([^"]*)"\s+)?(\w+)', line)
                if m:
                    prompt = m.group(1) or ""
                    name = m.group(2)
                    nodes.append(Input(name=name, prompt=prompt))
                i += 1
                continue
            if line.startswith("exit "):
                code = int(line.split()[1]) if line.split()[1].isdigit() else 0
                nodes.append(Exit(code=code))
                i += 1
                continue
            if line.startswith("export "):
                m = re.match(r'export\s+(\w+)=(.*)', line)
                if m:
                    nodes.append(EnvVar(action="set", name=m.group(1), value=Value(kind="string", value=m.group(2).strip('"'))))
                i += 1
                continue
            if line.startswith("if "):
                # simplified: if [ ... ]; then
                cond_match = re.match(r'if\s+\[\[\s+(.+?)\s+\]\]\s*;\s*then', line) or \
                             re.match(r'if\s+\[\s+(.+?)\s+\]\s*;\s*then', line)
                if cond_match:
                    cond = self._parse_condition(cond_match.group(1))
                    then_body, elif_branches, else_body, end_i = self._parse_if_block(lines, i + 1)
                    nodes.append(If(condition=cond, then_body=then_body, elif_branches=elif_branches, else_body=else_body))
                    i = end_i + 1
                    continue
            if line.startswith("for "):
                for_match = re.match(r'for\s+\((\w+)\s*=\s*(\d+);\s*\1\s*<\s*(\d+);\s*\1\+\+\)\s*;\s*do', line) or \
                               re.match(r'for\s+\(\(\s*(\w+)=(\d+);\s*\1<(\d+);\s*\1\+\+\s*\)\)\s*;\s*do', line)
                if for_match:
                    var, start, stop = for_match.group(1), for_match.group(2), for_match.group(3)
                    body, end_i = self._parse_block(lines, i + 1, "done")
                    nodes.append(ForRange(var=var, start=Value(kind="int", value=int(start)),
                                         stop=Value(kind="int", value=int(stop)), body=body))
                    i = end_i + 1
                    continue
                foreach_match = re.match(r'for\s+(\w+)\s+in\s+(.+?)\s*;\s*do', line)
                if foreach_match:
                    var = foreach_match.group(1)
                    iterable = foreach_match.group(2).strip()
                    body, end_i = self._parse_block(lines, i + 1, "done")
                    nodes.append(For(var=var, iterable=Value(kind="string", value=iterable), body=body))
                    i = end_i + 1
                    continue
            if line.startswith("while "):
                cond_match = re.match(r'while\s+\[\[\s+(.+?)\s+\]\]\s*;\s*do', line) or \
                             re.match(r'while\s+\[\s+(.+?)\s+\]\s*;\s*do', line)
                if cond_match:
                    cond = self._parse_condition(cond_match.group(1))
                    body, end_i = self._parse_block(lines, i + 1, "done")
                    nodes.append(While(condition=cond, body=body))
                    i = end_i + 1
                    continue
            if line.endswith("() {"):
                fname = line.split("()")[0].strip()
                body, end_i = self._parse_block(lines, i + 1, "}")
                nodes.append(FunctionDef(name=fname, body=body))
                i = end_i + 1
                continue
            if line.startswith("break"):
                nodes.append(Break())
                i += 1
                continue
            if line.startswith("continue"):
                nodes.append(Continue())
                i += 1
                continue
            # variable assignment: VAR=value or VAR="value"
            assign_match = re.match(r'^(\w+)=(.*)', line)
            if assign_match:
                name = assign_match.group(1)
                raw_val = assign_match.group(2).strip('"').strip("'")
                nodes.append(Assign(name=name, value=Value(kind="string", value=raw_val)))
                i += 1
                continue
            # env var get: VAR=${OTHER}
            env_get = re.match(r'^(\w+)=\$\{(\w+)\}', line)
            if env_get:
                nodes.append(EnvVar(action="get", name=env_get.group(2), result_name=env_get.group(1)))
                i += 1
                continue
            # fallback: treat as command
            nodes.append(Command(command=line, args=[], capture=False, name=None))
            i += 1

        return ScriptIR(source_language="sh", nodes=nodes, warnings=warnings)

    def _parse_condition(self, cond_str: str) -> Condition:
        # simple: VAR op VALUE
        m = re.match(r'\"?(\w+)\"?\s+(-eq|-ne|-gt|-lt|-ge|-le|==|!=)\s+\"?(\w+)\"?', cond_str)
        if m:
            op_map = {"-eq": "==", "-ne": "!=", "-gt": ">", "-lt": "<", "-ge": ">=", "-le": "<="}
            op = op_map.get(m.group(2), m.group(2))
            return Condition(left=Value(kind="var", value=m.group(1)), op=op, right=Value(kind="string", value=m.group(3)))
        return Condition(left=Value(kind="string", value=cond_str), op="!=", right=Value(kind="null"))

    def _parse_block(self, lines: list[str], start: int, end_keyword: str) -> tuple[list[IRNode], int]:
        nodes: list[IRNode] = []
        i = start
        while i < len(lines):
            line = lines[i].strip()
            if line == end_keyword:
                return nodes, i
            if line and not line.startswith("#!/"):
                result = self._simple_line(line)
                if result:
                    nodes.append(result)
            i += 1
        return nodes, i

    def _parse_if_block(self, lines: list[str], start: int) -> tuple[list[IRNode], list[ElifBranch], list[IRNode], int]:
        then_body: list[IRNode] = []
        elif_branches: list[ElifBranch] = []
        else_body: list[IRNode] = []
        i = start
        section = "then"
        while i < len(lines):
            line = lines[i].strip()
            if line == "fi":
                return then_body, elif_branches, else_body, i
            if line.startswith("elif "):
                cond_match = re.match(r'elif\s+\[\[\s+(.+?)\s+\]\]\s*;\s*then', line) or \
                             re.match(r'elif\s+\[\s+(.+?)\s+\]\s*;\s*then', line)
                if cond_match:
                    cond = self._parse_condition(cond_match.group(1))
                    section = "elif"
                    elif_branches.append(ElifBranch(condition=cond, body=[]))
                i += 1
                continue
            if line == "else":
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
        if line.startswith("echo "):
            return Print(values=[Value(kind="string", value=line[5:].strip().strip('"'))], end="\n")
        if line == ":":
            return Pass()
        assign = re.match(r'^(\w+)=(.*)', line)
        if assign:
            return Assign(name=assign.group(1), value=Value(kind="string", value=assign.group(2).strip('"').strip("'")))
        return Command(command=line, args=[], capture=False, name=None)
