"""Parse PowerShell source into IR (line-based heuristic parser)."""
from __future__ import annotations

import re
from itsconvert.ir import (
    ScriptIR, Value, Condition, ConditionExpr, CompoundCondition, IRNode,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, While, Break, Continue, Pass,
    FunctionDef, Param, Return, Import, EnvVar, Argv, TryCatch, Raise,
)
from itsconvert.errors import ParseError
from itsconvert.translators import Parser

# Matches $var or ${var}
_PS1_VAR_RE = re.compile(r'\$\{(\w+)\}|\$(\w+)')


class PS1Parser(Parser):
    """Parse PowerShell source into ScriptIR."""

    def parse(self, source: str) -> ScriptIR:
        lines = source.splitlines()
        nodes: list[IRNode] = []
        warnings: list[str] = []
        fallbacks = 0
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

            # param() block at top of script
            if re.match(r'^param\s*\(', line, re.IGNORECASE):
                # collect multi-line param block
                param_block = line
                depth = line.count("(") - line.count(")")
                while depth > 0 and i + 1 < len(lines):
                    i += 1
                    param_block += "\n" + lines[i]
                    depth += lines[i].count("(") - lines[i].count(")")
                params = self._parse_param_block(param_block)
                # Emit argv nodes for each param
                for idx, p in enumerate(params):
                    nodes.append(Argv(action="nth", index=idx, name=p.name))
                i += 1
                continue

            # Write-Host / Write-Output / Write-Error / Write-Warning / Write-Verbose
            write_m = re.match(r'(Write-Host|Write-Output|Write-Error|Write-Warning|Write-Verbose|Write-Debug)\s*(.*)', line, re.IGNORECASE)
            if write_m:
                cmdlet = write_m.group(1).lower()
                content = write_m.group(2).strip()
                no_newline = "-NoNewline" in content
                content = content.replace("-NoNewline", "").strip()
                val = self._parse_ps1_value(content.strip('"').strip("'"))
                # Write-Error goes to stderr — note in warning
                if "error" in cmdlet:
                    warnings.append(f"Write-Error mapped to Print (stderr not distinguished)")
                nodes.append(Print(values=[val], end="" if no_newline else "\n"))
                i += 1
                continue

            if re.match(r'\$(\w+)\s*=\s*Read-Host', line):
                m = re.match(r'\$(\w+)\s*=\s*Read-Host\s*(?:-Prompt\s*)?"?([^"]*)"?', line, re.IGNORECASE)
                if m:
                    nodes.append(Input(name=m.group(1), prompt=m.group(2).strip()))
                else:
                    m2 = re.match(r'\$(\w+)\s*=\s*Read-Host', line)
                    if m2:
                        nodes.append(Input(name=m2.group(1), prompt=""))
                i += 1
                continue
            if re.match(r'Read-Host', line, re.IGNORECASE):
                i += 1
                continue

            if re.match(r'exit\s', line, re.IGNORECASE) or line.lower() == "exit":
                parts = line.split()
                code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                nodes.append(Exit(code=code))
                i += 1
                continue

            # Environment variable set: $env:VAR = value
            if re.match(r'\$env:\w+\s*=', line):
                m = re.match(r'\$env:(\w+)\s*=\s*(.*)', line)
                if m:
                    nodes.append(EnvVar(action="set", name=m.group(1), value=self._parse_ps1_value(m.group(2).strip('"').strip("'"))))
                i += 1
                continue
            # Environment variable get: $x = $env:VAR
            if re.match(r'\$(\w+)\s*=\s*\$env:(\w+)', line):
                m = re.match(r'\$(\w+)\s*=\s*\$env:(\w+)', line)
                if m:
                    nodes.append(EnvVar(action="get", name=m.group(2), result_name=m.group(1)))
                i += 1
                continue
            # $args usage
            if re.match(r'\$(\w+)\s*=\s*\$args\[(\d+)\]', line):
                m = re.match(r'\$(\w+)\s*=\s*\$args\[(\d+)\]', line)
                if m:
                    nodes.append(Argv(action="nth", index=int(m.group(2)), name=m.group(1)))
                i += 1
                continue

            if re.match(r'if\s*\(', line, re.IGNORECASE):
                m = re.match(r'if\s*\((.+?)\)\s*\{', line, re.IGNORECASE)
                if m:
                    cond = self._parse_condition(m.group(1))
                    then_body, elif_branches, else_body, end_i = self._parse_if_block(lines, i + 1)
                    nodes.append(If(condition=cond, then_body=then_body, elif_branches=elif_branches, else_body=else_body))
                    i = end_i + 1
                    continue

            if re.match(r'foreach\s*\(', line, re.IGNORECASE):
                m = re.match(r'foreach\s*\(\s*\$(\w+)\s+in\s+(.+?)\s*\)\s*\{', line, re.IGNORECASE)
                if m:
                    var = m.group(1)
                    iterable = m.group(2).strip()
                    body, end_i = self._parse_block(lines, i + 1)
                    nodes.append(For(var=var, iterable=self._parse_ps1_value(iterable), body=body))
                    i = end_i + 1
                    continue

            if re.match(r'for\s*\(', line, re.IGNORECASE):
                m = re.match(r'for\s*\(\s*\$(\w+)\s*=\s*(\d+);\s*\$\1\s*(-lt|-le)\s*(\d+);', line, re.IGNORECASE)
                if m:
                    var, start_v, op, stop_v = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
                    body, end_i = self._parse_block(lines, i + 1)
                    stop = stop_v if op == "-lt" else stop_v + 1
                    nodes.append(ForRange(var=var, start=Value(kind="int", value=start_v),
                                         stop=Value(kind="int", value=stop), body=body))
                    i = end_i + 1
                    continue

            if re.match(r'while\s*\(', line, re.IGNORECASE):
                m = re.match(r'while\s*\((.+?)\)\s*\{', line, re.IGNORECASE)
                if m:
                    cond = self._parse_condition(m.group(1))
                    body, end_i = self._parse_block(lines, i + 1)
                    nodes.append(While(condition=cond, body=body))
                    i = end_i + 1
                    continue

            if re.match(r'function\s+', line, re.IGNORECASE):
                m = re.match(r'function\s+(\w+)\s*(?:\(([^)]*)\))?\s*\{', line, re.IGNORECASE)
                if m:
                    fname = m.group(1)
                    raw_params = m.group(2) or ""
                    params = [Param(name=p.lstrip("$").strip()) for p in raw_params.split(",") if p.strip()] if raw_params.strip() else []
                    body, end_i = self._parse_block(lines, i + 1)
                    nodes.append(FunctionDef(name=fname, params=params, body=body))
                    i = end_i + 1
                    continue

            # try/catch/finally
            if line.lower() == "try {" or re.match(r'^try\s*\{', line, re.IGNORECASE):
                try_body, end_i = self._parse_block(lines, i + 1)
                i = end_i + 1
                catch_var = None
                catch_body: list[IRNode] = []
                finally_body: list[IRNode] = []
                while i < len(lines):
                    next_line = lines[i].strip()
                    catch_m = re.match(r'^\}\s*catch\s*(?:\[.*?\])?\s*(?:\{|\(\s*\$(\w+)\s*\)\s*\{)', next_line, re.IGNORECASE)
                    if catch_m:
                        catch_var = catch_m.group(1)
                        catch_body, end_i = self._parse_block(lines, i + 1)
                        i = end_i + 1
                    elif re.match(r'^\}\s*finally\s*\{', next_line, re.IGNORECASE):
                        finally_body, end_i = self._parse_block(lines, i + 1)
                        i = end_i + 1
                    else:
                        break
                nodes.append(TryCatch(try_body=try_body, catch_var=catch_var, catch_body=catch_body, finally_body=finally_body))
                continue

            if re.match(r'^throw\s', line, re.IGNORECASE):
                msg_str = line[6:].strip().strip('"').strip("'")
                nodes.append(Raise(message=Value(kind="string", value=msg_str)))
                i += 1
                continue

            if line.lower().startswith("break"):
                nodes.append(Break())
                i += 1
                continue
            if line.lower().startswith("continue"):
                nodes.append(Continue())
                i += 1
                continue
            if line.lower() == "return" or re.match(r'^return\s', line, re.IGNORECASE):
                val_str = line[7:].strip() if len(line) > 7 else None
                nodes.append(Return(value=self._parse_ps1_value(val_str.strip('"').strip("'")) if val_str else None))
                i += 1
                continue

            # Typed variable: [int]$x = 5
            typed_assign = re.match(r'^\[(\w+)\]\s*\$(\w+)\s*=\s*(.*)', line)
            if typed_assign:
                type_hint = typed_assign.group(1)
                name = typed_assign.group(2)
                raw_val = typed_assign.group(3).strip().strip('"').strip("'")
                nodes.append(Assign(name=name, value=self._parse_ps1_value(raw_val)))
                i += 1
                continue

            # variable assignment: $VAR = value
            assign_match = re.match(r'^\$(\w+)\s*=\s*(.*)', line)
            if assign_match:
                name = assign_match.group(1)
                raw_val = assign_match.group(2).strip()
                nodes.append(Assign(name=name, value=self._parse_ps1_value(raw_val.strip('"').strip("'"))))
                i += 1
                continue

            # augmented assignment: $x += 1, $x -= 1, etc.
            aug_m = re.match(r'^\$(\w+)\s*(\+=|-=|\*=|/=)\s*(.*)', line)
            if aug_m:
                op_map = {"+=": "+", "-=": "-", "*=": "*", "/=": "/"}
                nodes.append(AugAssign(name=aug_m.group(1), op=op_map[aug_m.group(2)], value=self._parse_ps1_value(aug_m.group(3).strip())))
                i += 1
                continue

            # pipeline: cmd | Out-String or similar
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                for part in parts:
                    nodes.append(Command(command=part, args=[], capture=False, name=None))
                i += 1
                continue

            # fallback: command
            nodes.append(Command(command=line, args=[], capture=False, name=None))
            fallbacks += 1
            i += 1

        total = len(nodes) or 1
        confidence = max(0.0, 1.0 - (fallbacks / total) * 0.5)
        return ScriptIR(source_language="ps1", nodes=nodes, warnings=warnings, confidence=round(confidence, 2))

    def _parse_param_block(self, block: str) -> list[Param]:
        params = []
        for m in re.finditer(r'\[([^\]]*)\]\s*\$(\w+)', block):
            params.append(Param(name=m.group(2), type_hint=m.group(1)))
        if not params:
            for m in re.finditer(r'\$(\w+)', block):
                if m.group(1) not in ("param",):
                    params.append(Param(name=m.group(1)))
        return params

    def _parse_ps1_value(self, raw: str) -> Value:
        """Parse a PowerShell value string into a Value."""
        raw = raw.strip()
        if not raw:
            return Value(kind="null")
        # Integer
        if re.match(r'^-?\d+$', raw):
            return Value(kind="int", value=int(raw))
        # Float
        if re.match(r'^-?\d+\.\d+$', raw):
            return Value(kind="float", value=float(raw))
        # Boolean
        if raw.lower() in ("$true", "true"):
            return Value(kind="bool", value=True)
        if raw.lower() in ("$false", "false"):
            return Value(kind="bool", value=False)
        if raw.lower() in ("$null", "null"):
            return Value(kind="null")
        # Variable reference
        if re.match(r'^\$(\w+)$', raw):
            return Value(kind="var", value=raw[1:])
        # String with interpolation
        if _PS1_VAR_RE.search(raw):
            parts: list[Value] = []
            pos = 0
            for m in _PS1_VAR_RE.finditer(raw):
                if m.start() > pos:
                    parts.append(Value(kind="string", value=raw[pos:m.start()]))
                var_name = m.group(1) or m.group(2)
                parts.append(Value(kind="var", value=var_name))
                pos = m.end()
            if pos < len(raw):
                parts.append(Value(kind="string", value=raw[pos:]))
            return Value(kind="fstring", parts=parts)
        return Value(kind="string", value=raw)

    def _parse_condition(self, cond_str: str) -> ConditionExpr:
        cond_str = cond_str.strip()
        # Compound: -and / -or / && / ||
        for sep, bool_op in [(" -and ", "and"), (" -or ", "or"), (" && ", "and"), (" || ", "or")]:
            if sep.lower() in cond_str.lower():
                idx = cond_str.lower().find(sep.lower())
                left = cond_str[:idx]
                right = cond_str[idx + len(sep):]
                return CompoundCondition(
                    left=self._parse_condition(left),
                    op=bool_op,
                    right=self._parse_condition(right),
                )
        m = re.match(r'(\$\w+)\s+(-eq|-ne|-gt|-lt|-ge|-le|==|!=|-like|-match)\s+(.+)', cond_str.strip())
        if m:
            op_map = {"-eq": "==", "-ne": "!=", "-gt": ">", "-lt": "<", "-ge": ">=", "-le": "<=",
                      "==": "==", "!=": "!=", "-like": "==", "-match": "=="}
            op = op_map.get(m.group(2).lower(), "==")
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
            if re.match(r'\}\s*elseif\s*\(', line, re.IGNORECASE):
                m = re.match(r'\}\s*elseif\s*\((.+?)\)\s*\{', line, re.IGNORECASE)
                if m:
                    cond = self._parse_condition(m.group(1))
                    section = "elif"
                    elif_branches.append(ElifBranch(condition=cond, body=[]))
                i += 1
                continue
            if re.match(r'\}\s*else\s*\{', line, re.IGNORECASE):
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
        write_m = re.match(r'(Write-Host|Write-Output|Write-Error|Write-Warning)\s*(.*)', line, re.IGNORECASE)
        if write_m:
            content = write_m.group(2).strip().strip('"').strip("'")
            return Print(values=[Value(kind="string", value=content)], end="\n")
        if line.lower().startswith("break"):
            return Break()
        if line.lower().startswith("continue"):
            return Continue()
        if line.lower() == "return" or re.match(r'^return\s', line, re.IGNORECASE):
            val = line[7:].strip() if len(line) > 7 else None
            return Return(value=Value(kind="string", value=val.strip('"').strip("'")) if val else None)
        assign = re.match(r'^\$(\w+)\s*=\s*(.*)', line)
        if assign:
            return Assign(name=assign.group(1), value=Value(kind="string", value=assign.group(2).strip().strip('"').strip("'")))
        return Command(command=line, args=[], capture=False, name=None)


