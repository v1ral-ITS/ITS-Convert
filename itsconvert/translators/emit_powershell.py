from __future__ import annotations

from itsconvert.ir import Assign, Command, Exit, If, Input, Print, ScriptIR, Value


class PowerShellEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines = ["$ErrorActionPreference = 'Stop'"]
        for node in ir.nodes:
            lines.extend(self._emit_node(node, 0))
        return "\n".join(lines) + "\n"

    def _value(self, value: Value) -> str:
        if value.kind == "string":
            safe = str(value.value).replace("'", "''")
            return f"'{safe}'"
        if value.kind == "var":
            return f"${value.value}"
        if value.kind == "bool":
            return "$true" if value.value else "$false"
        if value.kind == "null":
            return "$null"
        return str(value.value)

    def _cond(self, condition) -> str:
        op_map = {"==": "-eq", "!=": "-ne", ">": "-gt", "<": "-lt", ">=": "-ge", "<=": "-le"}
        return f"{self._value(condition.left)} {op_map[condition.op]} {self._value(condition.right)}"

    def _emit_node(self, node, indent: int) -> list[str]:
        pad = "    " * indent
        if isinstance(node, Assign):
            return [f"{pad}${node.name} = {self._value(node.value)}"]
        if isinstance(node, Print):
            return [f"{pad}Write-Host {self._value(node.value)}"]
        if isinstance(node, Input):
            prompt = self._value(Value(kind='string', value=node.prompt))
            return [f"{pad}${node.name} = Read-Host {prompt}"]
        if isinstance(node, Command):
            cmd = self._value(Value(kind='string', value=node.command))
            return [f"{pad}Invoke-Expression {cmd}"]
        if isinstance(node, Exit):
            return [f"{pad}exit {node.code}"]
        if isinstance(node, If):
            lines = [f"{pad}if ({self._cond(node.condition)}) {{"]

            if node.then_body:
                for child in node.then_body:
                    lines.extend(self._emit_node(child, indent + 1))
            if node.else_body:
                lines.append(f"{pad}}} else {{")
                for child in node.else_body:
                    lines.extend(self._emit_node(child, indent + 1))
                lines.append(f"{pad}}}")
            else:
                lines.append(f"{pad}}}")
            return lines
        raise TypeError(f"Unsupported node: {type(node).__name__}")
