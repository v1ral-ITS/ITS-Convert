"""Parse Bash/sh source into IR (line-based heuristic parser)."""
from __future__ import annotations

import re
from itsconvert.ir import (
    ScriptIR, Value, Condition, ConditionExpr, CompoundCondition, IRNode,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, While, Break, Continue, Pass,
    FunctionDef, Return, Import, EnvVar, Argv, TryCatch,
    ListOp, RawBlock,
)
from itsconvert.errors import ParseError
from itsconvert.translators import Parser

# Matches ${var} or $var (not followed by another word char)
_BASH_VAR_RE = re.compile(r'\$\{(\w+)\}|\$(\w+)')


class BashParser(Parser):
    """Parse Bash/sh source into ScriptIR using line-based heuristics."""

    def parse(self, source: str) -> ScriptIR:
        lines = source.splitlines()
        nodes: list[IRNode] = []
        warnings: list[str] = []
        fallbacks = 0
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

            # heredoc: VAR=$(cat <<EOF ... EOF) or just <<EOF ... EOF
            heredoc_m = re.match(r'(\w+)=\$\(cat\s+<<[-]?(\w+)', line) or \
                        re.match(r'<<[-]?(\w+)', line)
            if heredoc_m:
                marker = heredoc_m.group(2) if heredoc_m.lastindex == 2 else heredoc_m.group(1)
                var_name = heredoc_m.group(1) if re.match(r'(\w+)=', line) else None
                content_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() != marker:
                    content_lines.append(lines[i])
                    i += 1
                content = "\n".join(content_lines)
                if var_name:
                    nodes.append(Assign(name=var_name, value=Value(kind="string", value=content)))
                i += 1
                continue

            # Command substitution assignment: VAR=$(cmd)
            cmd_sub_assign = re.match(r'^(\w+)=\$\((.+)\)$', line)
            if cmd_sub_assign:
                var_name = cmd_sub_assign.group(1)
                cmd_str = cmd_sub_assign.group(2).strip()
                tokens = self._split_command_line(cmd_str)
                cmd = tokens[0] if tokens else cmd_str
                args = [self._parse_bash_value(t) for t in tokens[1:]] if len(tokens) > 1 else []
                nodes.append(Command(command=cmd, args=args, capture=True, name=var_name))
                i += 1
                continue

            # Array assignment: arr=(a b c)
            arr_m = re.match(r'^(\w+)=\((.+)\)$', line)
            if arr_m:
                arr_name = arr_m.group(1)
                items_str = arr_m.group(2).strip()
                items = [self._parse_bash_value(t) for t in self._split_command_line(items_str)]
                nodes.append(ListOp(action="create", name=arr_name, items=items))
                i += 1
                continue

            if line.startswith("echo ") or line == "echo":
                rest = line[5:].strip() if len(line) > 5 else ""
                nodes.append(Print(values=[self._parse_bash_value(rest.strip('"'))], end="\n"))
                i += 1
                continue
            if line.startswith("echo -n "):
                rest = line[8:].strip()
                nodes.append(Print(values=[self._parse_bash_value(rest.strip('"'))], end=""))
                i += 1
                continue
            if line.startswith("printf "):
                rest = line[7:].strip()
                nodes.append(Print(values=[self._parse_bash_value(rest.strip('"'))], end=""))
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
                parts = line.split()
                code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                nodes.append(Exit(code=code))
                i += 1
                continue
            if line == "exit":
                nodes.append(Exit(code=0))
                i += 1
                continue
            if line.startswith("export "):
                m = re.match(r'export\s+(\w+)=(.*)', line)
                if m:
                    nodes.append(EnvVar(action="set", name=m.group(1), value=Value(kind="string", value=m.group(2).strip('"'))))
                i += 1
                continue
            if line.startswith("unset "):
                m = re.match(r'unset\s+(\w+)', line)
                if m:
                    nodes.append(EnvVar(action="delete", name=m.group(1)))
                i += 1
                continue

            # if [ ... ] ; then  /  if [[ ... ]] ; then
            if line.startswith("if "):
                cond_match = (re.match(r'if\s+\[\[\s+(.+?)\s+\]\]\s*;?\s*then', line) or
                              re.match(r'if\s+\[\s+(.+?)\s+\]\s*;?\s*then', line) or
                              re.match(r'if\s+\(\s*(.+?)\s*\)\s*;?\s*then', line))
                if cond_match:
                    cond = self._parse_condition(cond_match.group(1))
                    then_body, elif_branches, else_body, end_i = self._parse_if_block(lines, i + 1)
                    nodes.append(If(condition=cond, then_body=then_body, elif_branches=elif_branches, else_body=else_body))
                    i = end_i + 1
                    continue

            # for (( i=0; i<N; i++ ))  or  for ((i=0; i<N; i++))
            if line.startswith("for "):
                arith_m = re.match(r'for\s+\(\(\s*(\w+)\s*=\s*(.+?);\s*\1\s*([<>]=?)\s*(.+?);\s*\1(\+\+|--|\+=.+?|-=.+?)\s*\)\)\s*;?\s*do', line)
                if arith_m:
                    var = arith_m.group(1)
                    start = arith_m.group(2).strip()
                    stop = arith_m.group(4).strip()
                    body, end_i = self._parse_block(lines, i + 1, "done")
                    nodes.append(ForRange(
                        var=var,
                        start=Value(kind="int", value=int(start)) if start.isdigit() else Value(kind="var", value=start),
                        stop=Value(kind="int", value=int(stop)) if stop.isdigit() else Value(kind="var", value=stop),
                        body=body,
                    ))
                    i = end_i + 1
                    continue
                # for var in list; do
                foreach_m = re.match(r'for\s+(\w+)\s+in\s+(.+?)\s*;?\s*do', line)
                if foreach_m:
                    var = foreach_m.group(1)
                    iterable = foreach_m.group(2).strip()
                    body, end_i = self._parse_block(lines, i + 1, "done")
                    # seq-based: for i in $(seq 0 N)
                    seq_m = re.match(r'\$\(seq\s+(\d+)\s+(\d+)\)', iterable)
                    if seq_m:
                        nodes.append(ForRange(
                            var=var,
                            start=Value(kind="int", value=int(seq_m.group(1))),
                            stop=Value(kind="int", value=int(seq_m.group(2)) + 1),
                            body=body,
                        ))
                    else:
                        nodes.append(For(var=var, iterable=Value(kind="string", value=iterable), body=body))
                    i = end_i + 1
                    continue
            if line.startswith("while "):
                cond_match = (re.match(r'while\s+\[\[\s+(.+?)\s+\]\]\s*;?\s*do', line) or
                              re.match(r'while\s+\[\s+(.+?)\s+\]\s*;?\s*do', line) or
                              re.match(r'while\s+(.+?)\s*;?\s*do', line))
                if cond_match:
                    cond = self._parse_condition(cond_match.group(1))
                    body, end_i = self._parse_block(lines, i + 1, "done")
                    nodes.append(While(condition=cond, body=body))
                    i = end_i + 1
                    continue

            # function declaration: fname() { or function fname {
            fn_m = (re.match(r'^(\w+)\s*\(\s*\)\s*\{', line) or
                    re.match(r'^function\s+(\w+)\s*(?:\(\s*\))?\s*\{', line))
            if fn_m:
                fname = fn_m.group(1)
                body, end_i = self._parse_block_recursive(lines, i + 1)
                nodes.append(FunctionDef(name=fname, body=body))
                i = end_i + 1
                continue

            if line.startswith("return"):
                parts = line.split()
                val = None
                if len(parts) > 1:
                    val = Value(kind="int", value=int(parts[1])) if parts[1].isdigit() else Value(kind="var", value=parts[1])
                nodes.append(Return(value=val))
                i += 1
                continue
            if line.startswith("break"):
                nodes.append(Break())
                i += 1
                continue
            if line.startswith("continue"):
                nodes.append(Continue())
                i += 1
                continue
            if line == ":":
                nodes.append(Pass())
                i += 1
                continue

            # env var get: VAR=${OTHER} or VAR=$OTHER
            env_get = re.match(r'^(\w+)=\$\{(\w+)\}$', line) or re.match(r'^(\w+)=\$(\w+)$', line)
            if env_get:
                nodes.append(EnvVar(action="get", name=env_get.group(2), result_name=env_get.group(1)))
                i += 1
                continue

            # arithmetic: (( var op= val ))
            arith_stmt = re.match(r'^\(\(\s*(\w+)\s*(\+\+|--|(\+|-|\*|/)=\s*\d+)\s*\)\)', line)
            if arith_stmt:
                var = arith_stmt.group(1)
                op_str = arith_stmt.group(2)
                if op_str == "++" :
                    nodes.append(AugAssign(name=var, op="+", value=Value(kind="int", value=1)))
                elif op_str == "--":
                    nodes.append(AugAssign(name=var, op="-", value=Value(kind="int", value=1)))
                else:
                    raw_op = op_str.rstrip("=").strip()
                    val_m = re.search(r'[+\-*/]?=\s*(\d+)', op_str)
                    val = int(val_m.group(1)) if val_m else 1
                    nodes.append(AugAssign(name=var, op=raw_op, value=Value(kind="int", value=val)))
                i += 1
                continue

            # variable assignment: VAR=value or VAR="value"
            assign_match = re.match(r'^(\w+)=(.*)', line)
            if assign_match:
                name = assign_match.group(1)
                raw_val = assign_match.group(2)
                nodes.append(Assign(name=name, value=self._parse_bash_value(raw_val.strip('"').strip("'"))))
                i += 1
                continue

            # piped command: cmd1 | cmd2 → nested Command nodes
            if "|" in line and not line.startswith("#"):
                pipe_parts = [p.strip() for p in line.split("|")]
                prev: Command | None = None
                for part in pipe_parts:
                    tokens = self._split_command_line(part)
                    if tokens:
                        cmd = Command(command=tokens[0], args=[self._parse_bash_value(t) for t in tokens[1:]], capture=prev is not None, name=None)
                        if prev is not None:
                            # Represent piped as sequential commands
                            nodes.append(prev)
                        prev = cmd
                if prev:
                    nodes.append(prev)
                else:
                    fallbacks += 1
                i += 1
                continue

            # fallback: treat as command
            tokens = self._split_command_line(line)
            if tokens:
                cmd = tokens[0]
                args = [self._parse_bash_value(t) for t in tokens[1:]]
                nodes.append(Command(command=cmd, args=args, capture=False, name=None))
            else:
                fallbacks += 1
            i += 1

        total = len(nodes) or 1
        confidence = max(0.0, 1.0 - (fallbacks / total) * 0.5)
        return ScriptIR(source_language="sh", nodes=nodes, warnings=warnings, confidence=round(confidence, 2))

    def _parse_condition(self, cond_str: str) -> ConditionExpr:
        cond_str = cond_str.strip()
        # Compound: expr1 && expr2 / expr1 || expr2
        for sep, bool_op in [(" && ", "and"), (" || ", "or")]:
            if sep in cond_str:
                parts = cond_str.split(sep, 1)
                return CompoundCondition(
                    left=self._parse_condition(parts[0]),
                    op=bool_op,
                    right=self._parse_condition(parts[1]),
                )
        # file tests: -f, -d, -e, -z, -n
        file_m = re.match(r'(-[fdeznFDEZN])\s+"?(.+?)"?$', cond_str)
        if file_m:
            flag = file_m.group(1)
            operand = file_m.group(2)
            op_map = {"-f": "!=", "-d": "!=", "-e": "!=", "-n": "!=", "-z": "=="}
            return Condition(
                left=Value(kind="var", value=operand),
                op=op_map.get(flag, "!="),
                right=Value(kind="null"),
            )
        # numeric / string: VAR op VALUE
        m = re.match(r'\"?(\$\{?\w+\}?|[\w.]+)\"?\s+(-eq|-ne|-gt|-lt|-ge|-le|==|!=|=~)\s+\"?(\S+)\"?', cond_str)
        if m:
            op_map = {"-eq": "==", "-ne": "!=", "-gt": ">", "-lt": "<", "-ge": ">=", "-le": "<=",
                      "==": "==", "!=": "!=", "=~": "=="}
            left_raw = m.group(1).lstrip("$").strip("{}")
            op = op_map.get(m.group(2), m.group(2))
            right_raw = m.group(3)
            return Condition(
                left=Value(kind="var", value=left_raw),
                op=op,
                right=Value(kind="string", value=right_raw),
            )
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

    def _parse_block_recursive(self, lines: list[str], start: int) -> tuple[list[IRNode], int]:
        """Parse a brace-delimited block recursively (for function bodies)."""
        nodes: list[IRNode] = []
        depth = 1
        i = start
        while i < len(lines):
            line = lines[i].strip()
            depth += line.count("{") - line.count("}")
            if depth <= 0:
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
                cond_match = (re.match(r'elif\s+\[\[\s+(.+?)\s+\]\]\s*;?\s*then', line) or
                              re.match(r'elif\s+\[\s+(.+?)\s+\]\s*;?\s*then', line))
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
            rest = line[5:].strip()
            return Print(values=[self._parse_bash_value(rest.strip('"'))], end="\n")
        if line == "echo":
            return Print(values=[], end="\n")
        if line == ":":
            return Pass()
        if line.startswith("return"):
            parts = line.split()
            val = None
            if len(parts) > 1:
                val = Value(kind="int", value=int(parts[1])) if parts[1].isdigit() else Value(kind="var", value=parts[1])
            return Return(value=val)
        if line.startswith("break"):
            return Break()
        if line.startswith("continue"):
            return Continue()
        assign = re.match(r'^(\w+)=(.*)', line)
        if assign:
            return Assign(name=assign.group(1), value=self._parse_bash_value(assign.group(2).strip('"').strip("'")))
        tokens = self._split_command_line(line)
        if tokens:
            return Command(command=tokens[0], args=[self._parse_bash_value(t) for t in tokens[1:]], capture=False, name=None)
        return None

    def _split_command_line(self, line: str) -> list[str]:
        """Split a bash command line into tokens, respecting single and double quotes."""
        tokens: list[str] = []
        current: list[str] = []
        in_single = False
        in_double = False
        i = 0
        while i < len(line):
            c = line[i]
            if c == "'" and not in_double:
                in_single = not in_single
            elif c == '"' and not in_single:
                in_double = not in_double
            elif c == ' ' and not in_single and not in_double:
                if current:
                    tokens.append(''.join(current))
                    current = []
            else:
                current.append(c)
            i += 1
        if current:
            tokens.append(''.join(current))
        return tokens

    def _parse_bash_value(self, word: str) -> Value:
        """Parse a single bash word (possibly with ${var} interpolation) into a Value."""
        word = word.strip()
        if not word:
            return Value(kind="string", value="")
        # Pure ${var} reference
        m = re.match(r'^\$\{(\w+)\}$', word)
        if m:
            return Value(kind="var", value=m.group(1))
        # Pure $var reference
        m = re.match(r'^\$(\w+)$', word)
        if m:
            return Value(kind="var", value=m.group(1))
        # Arithmetic: $(( expr ))
        m = re.match(r'^\$\(\((.+)\)\)$', word)
        if m:
            expr = m.group(1).strip()
            # parse simple a op b
            arith_m = re.match(r'(\w+)\s*([+\-*/%])\s*(\w+)', expr)
            if arith_m:
                left_v = Value(kind="var", value=arith_m.group(1)) if not arith_m.group(1).isdigit() else Value(kind="int", value=int(arith_m.group(1)))
                right_v = Value(kind="var", value=arith_m.group(3)) if not arith_m.group(3).isdigit() else Value(kind="int", value=int(arith_m.group(3)))
                return Value(kind="binop", parts=[left_v, Value(kind="string", value=arith_m.group(2)), right_v])
            return Value(kind="var", value=expr)
        # Command substitution: $(cmd)
        m = re.match(r'^\$\((.+)\)$', word)
        if m:
            return Value(kind="call", parts=[Value(kind="string", value=m.group(1)), Value(kind="list", parts=[])])
        # Mixed: text with embedded ${var} / $var interpolation → fstring
        if _BASH_VAR_RE.search(word):
            parts: list[Value] = []
            pos = 0
            for m in _BASH_VAR_RE.finditer(word):
                if m.start() > pos:
                    parts.append(Value(kind="string", value=word[pos:m.start()]))
                var_name = m.group(1) or m.group(2)
                parts.append(Value(kind="var", value=var_name))
                pos = m.end()
            if pos < len(word):
                parts.append(Value(kind="string", value=word[pos:]))
            return Value(kind="fstring", parts=parts)
        # Plain literal — strip one matching pair of surrounding quotes if present
        if (word.startswith('"') and word.endswith('"') and len(word) >= 2) or \
           (word.startswith("'") and word.endswith("'") and len(word) >= 2):
            stripped = word[1:-1]
        else:
            stripped = word
        # Integer literal
        if stripped.lstrip("-").isdigit():
            return Value(kind="int", value=int(stripped))
        return Value(kind="string", value=stripped)

