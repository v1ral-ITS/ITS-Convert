from __future__ import annotations

from itsconvert.ir import Assign, Command, Exit, If, Input, Print, ScriptIR, Value


class PythonEmitter:
    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = []
        imports_added = False
        for node in ir.nodes:
            node_lines, uses_subprocess = self._emit_node(node, 0)
            if uses_subprocess and not imports_added:
                lines.append("import subprocess")
                imports_added = True
            lines.extend(node_lines)
        return "\n".join(lines) + "\n"

    def _value(self, value: Value) -> str:
        if value.kind == "string":
            return repr(value.value)
        if value.kind == "var":
            return str(value.value)
        if value.kind == "null":
            return "None"
        if value.kind == "bool":
            return "True" if value.value else "False"
        return str(value.value)

    def _cond(self, condition) -> str:
        return f"{self._value(condition.left)} {condition.op} {self._value(condition.right)}"

    def _emit_node(self, node, indent: int) -> tuple[list[str], bool]:
        pad = "    " * indent
        if isinstance(node, Assign):
            return ([f"{pad}{node.name} = {self._value(node.value)}"], False)
        if isinstance(node, Print):
            return ([f"{pad}print({self._value(node.value)})"], False)
        if isinstance(node, Input):
            return ([f"{pad}{node.name} = input({node.prompt!r})"], False)
        if isinstance(node, Command):
            return ([f"{pad}subprocess.run({node.command!r}, shell=True, check=False)"], True)
        if isinstance(node, Exit):
            return ([f"{pad}raise SystemExit({node.code})"], False)
        if isinstance(node, If):
            lines = [f"{pad}if {self._cond(node.condition)}:"]
            uses = False
            if node.then_body:
                for child in node.then_body:
                    child_lines, child_uses = self._emit_node(child, indent + 1)
                    uses = uses or child_uses
                    lines.extend(child_lines)
            else:
                lines.append(f"{pad}    pass")
            if node.else_body:
                lines.append(f"{pad}else:")
                for child in node.else_body:
                    child_lines, child_uses = self._emit_node(child, indent + 1)
                    uses = uses or child_uses
                    lines.extend(child_lines)
            return (lines, uses)
        raise TypeError(f"Unsupported node: {type(node).__name__}")
