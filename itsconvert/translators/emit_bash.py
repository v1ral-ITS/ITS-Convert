from __future__ import annotations

from itsconvert.ir import Assign, Command, Exit, If, Input, Print, ScriptIR, Value


class BashEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines = ["#!/usr/bin/env bash", "set -u"]
        for node in ir.nodes:
            lines.extend(self._emit_node(node, 0))
        return "\n".join(lines) + "\n"

    def _value(self, value: Value) -> str:
        if value.kind == "string":
            safe = str(value.value).replace('"', r'\"')
            return f'"{safe}"'
        if value.kind == "var":
            return f'"${value.value}"'
        if value.kind == "null":
            return '""'
        return str(value.value)

    def _cond(self, condition) -> str:
        left = self._value(condition.left)
        right = self._value(condition.right)
        if condition.op == "==":
            return f"[ {left} = {right} ]"
        if condition.op == "!=":
            return f"[ {left} != {right} ]"
        if condition.op == ">":
            return f"[ {left} -gt {right} ]"
        if condition.op == "<":
            return f"[ {left} -lt {right} ]"
        if condition.op == ">=":
            return f"[ {left} -ge {right} ]"
        return f"[ {left} -le {right} ]"

    def _emit_node(self, node, indent: int) -> list[str]:
        pad = "    " * indent
        if isinstance(node, Assign):
            return [f"{pad}{node.name}={self._value(node.value)}"]
        if isinstance(node, Print):
            return [f"{pad}echo {self._value(node.value)}"]
        if isinstance(node, Input):
            return [f"{pad}read -p {node.prompt!r} {node.name}"]
        if isinstance(node, Command):
            return [f"{pad}{node.command}"]
        if isinstance(node, Exit):
            return [f"{pad}exit {node.code}"]
        if isinstance(node, If):
            lines = [f"{pad}if {self._cond(node.condition)}; then"]
            if node.then_body:
                for child in node.then_body:
                    lines.extend(self._emit_node(child, indent + 1))
            else:
                lines.append(f"{pad}    :")
            if node.else_body:
                lines.append(f"{pad}else")
                for child in node.else_body:
                    lines.extend(self._emit_node(child, indent + 1))
            lines.append(f"{pad}fi")
            return lines
        raise TypeError(f"Unsupported node: {type(node).__name__}")
