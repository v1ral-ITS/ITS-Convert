from __future__ import annotations

from itsconvert.ir import Assign, Command, Exit, If, Input, Print, ScriptIR, Value


class CmdEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines = ["@echo off", "setlocal enabledelayedexpansion"]
        for node in ir.nodes:
            lines.extend(self._emit_node(node, 0))
        return "\n".join(lines) + "\n"

    def _value(self, value: Value) -> str:
        if value.kind == "var":
            return f"%{value.value}%"
        if value.kind == "null":
            return ""
        return str(value.value)

    def _emit_node(self, node, indent: int) -> list[str]:
        pad = "    " * indent
        if isinstance(node, Assign):
            return [f"{pad}set {node.name}={self._value(node.value)}"]
        if isinstance(node, Print):
            return [f"{pad}echo {self._value(node.value)}"]
        if isinstance(node, Input):
            return [f"{pad}set /p {node.name}={node.prompt}"]
        if isinstance(node, Command):
            return [f"{pad}{node.command}"]
        if isinstance(node, Exit):
            return [f"{pad}exit /b {node.code}"]
        if isinstance(node, If):
            return [
                f"{pad}rem complex IF lowering is not implemented for CMD yet",
                f"{pad}echo Unsupported IF block for CMD target",
                f"{pad}exit /b 1",
            ]
        raise TypeError(f"Unsupported node: {type(node).__name__}")
