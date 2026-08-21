"""Elixir target emitter for the common automation-script IR subset."""
import json
from itsconvert.ir import *


class ElixirEmitter:
    def emit(self, ir: ScriptIR) -> str:
        return "\n".join(line for node in ir.nodes for line in self._node(node, 0)) + "\n"

    def _node(self, node, depth):
        p = "  " * depth
        if isinstance(node, Comment): return [f"{p}# {node.text}"]
        if isinstance(node, Assign): return [f"{p}{node.name} = {self._value(node.value)}"]
        if isinstance(node, Print): return [f"{p}IO.puts({self._joined(node.values)})"]
        if isinstance(node, Input): return [f"{p}{node.name} = IO.gets({json.dumps(node.prompt)}) |> String.trim()"]
        if isinstance(node, If):
            lines = [f"{p}if {self._condition(node.condition)} do"] + self._body(node.then_body, depth + 1)
            if node.else_body: lines += [f"{p}else"] + self._body(node.else_body, depth + 1)
            return lines + [f"{p}end"]
        if isinstance(node, For): return [f"{p}for {node.var} <- {self._value(node.iterable)} do"] + self._body(node.body, depth + 1) + [f"{p}end"]
        if isinstance(node, ForRange): return [f"{p}for {node.var} <- {self._value(node.start)}..({self._value(node.stop)} - 1) do"] + self._body(node.body, depth + 1) + [f"{p}end"]
        if isinstance(node, FunctionDef):
            params = ", ".join(x.name for x in node.params)
            return [f"{p}def {node.name}({params}) do"] + self._body(node.body, depth + 1) + [f"{p}end"]
        if isinstance(node, Return): return [f"{p}{self._value(node.value) if node.value else ':ok'}"]
        if isinstance(node, Exit): return [f"{p}System.halt({node.code})"]
        if isinstance(node, Pass): return [f"{p}:ok"]
        if isinstance(node, Assert): return [f"{p}unless {self._condition(node.condition)}, do: raise(\"Assertion failed\")"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}{node.result_name} = System.get_env("{node.name}")']
            if node.action == "set": return [f'{p}System.put_env("{node.name}", to_string({self._value(node.value)}))']
        if isinstance(node, RawBlock): return [f"{p}# raw {node.language}: {line}" for line in node.code.splitlines()]
        return [f"{p}# Unsupported IR node: {node.type}"]

    def _body(self, nodes, depth): return [line for node in nodes for line in self._node(node, depth)]
    def _condition(self, c): return f"{self._value(c.left)} {c.op} {self._value(c.right)}"
    def _joined(self, values): return ' <> " " <> '.join(f"to_string({self._value(v)})" for v in values) or '""'
    def _value(self, value):
        if value.kind == "string": return json.dumps(str(value.value))
        if value.kind in ("int", "float", "var"): return str(value.value)
        if value.kind == "bool": return "true" if value.value else "false"
        if value.kind == "null": return "nil"
        if value.kind == "list": return "[" + ", ".join(self._value(v) for v in (value.parts or [])) + "]"
        if value.kind == "binop" and value.parts and len(value.parts) >= 3:
            left, op, right = value.parts[:3]
            operator = {"and": "and", "or": "or"}.get(str(op.value), str(op.value))
            return f"({self._value(left)} {operator} {self._value(right)})"
        return repr(value.value)
