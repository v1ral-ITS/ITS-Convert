"""Parse CMD/batch source into IR (line-based heuristic parser)."""
from __future__ import annotations

import re
from itsconvert.ir import (
    ScriptIR, Value, Condition, IRNode,
    Comment, Assign, Print, Input, Command, Exit,
    If, ForRange, EnvVar,
)
from itsconvert.errors import ParseError
from itsconvert.translators import Parser


class CMDParser(Parser):
    def parse(self, source: str) -> ScriptIR:
        lines = source.splitlines()
        nodes: list[IRNode] = []
        warnings: list[str] = []
        for line in lines:
            line = line.strip()
            if not line or line in ("@echo off", "setlocal enabledelayedexpansion", "endlocal"):
                continue
            if line.startswith("REM "):
                nodes.append(Comment(text=line[4:].strip()))
                continue
            if line.startswith("echo(") or line == "echo":
                nodes.append(Print(values=[], end="\n"))
                continue
            if line.startswith("echo "):
                nodes.append(Print(values=[Value(kind="string", value=line[5:].strip())], end="\n"))
                continue
            if line.startswith("set /p "):
                m = re.match(r'set\s+/p\s+"?(\w+)"?=', line)
                if m:
                    nodes.append(Input(name=m.group(1), prompt=""))
                continue
            if line.startswith("exit /b"):
                code = int(line.split()[-1]) if line.split()[-1].isdigit() else 0
                nodes.append(Exit(code=code))
                continue
            if line.startswith("set "):
                m = re.match(r'set\s+"?(\w+)=(.*)"?', line)
                if m:
                    nodes.append(Assign(name=m.group(1), value=Value(kind="string", value=m.group(2).strip('"'))))
                continue
            nodes.append(Command(command=line, args=[], capture=False, name=None))
        return ScriptIR(source_language="cmd", nodes=nodes, warnings=warnings)
