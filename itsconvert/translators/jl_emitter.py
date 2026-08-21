"""Julia target emitter."""
import json
from itsconvert.ir import *


class JuliaEmitter:
    def emit(self, ir: ScriptIR) -> str:
        return "\n".join(line for node in ir.nodes for line in self._node(node, 0)) + "\n"

    def _node(self, node, depth):
        p = "    " * depth
        if isinstance(node, Comment): return [f"{p}# {node.text}"]
        if isinstance(node, Assign): return [f"{p}{node.name} = {self._value(node.value)}"]
        if isinstance(node, MultiAssign): return [f"{p}{', '.join(node.names)} = {self._value(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}{node.name} {node.op}= {self._value(node.value)}"]
        if isinstance(node, Print): return [f"{p}println({', '.join(self._value(v) for v in node.values)})"]
        if isinstance(node, Input): return [f"{p}print({json.dumps(node.prompt)})", f"{p}{node.name} = readline()"]
        if isinstance(node, If):
            lines = [f"{p}if {self._condition(node.condition)}"] + self._body(node.then_body, depth + 1)
            for branch in node.elif_branches:
                lines += [f"{p}elseif {self._condition(branch.condition)}"] + self._body(branch.body, depth + 1)
            if node.else_body: lines += [f"{p}else"] + self._body(node.else_body, depth + 1)
            return lines + [f"{p}end"]
        if isinstance(node, For): return [f"{p}for {node.var} in {self._value(node.iterable)}"] + self._body(node.body, depth + 1) + [f"{p}end"]
        if isinstance(node, ForRange):
            step = self._value(node.step) if node.step else "1"
            return [f"{p}for {node.var} in {self._value(node.start)}:{step}:({self._value(node.stop)} - 1)"] + self._body(node.body, depth + 1) + [f"{p}end"]
        if isinstance(node, While): return [f"{p}while {self._condition(node.condition)}"] + self._body(node.body, depth + 1) + [f"{p}end"]
        if isinstance(node, FunctionDef):
            params = ", ".join(x.name + ("=" + self._value(x.default) if x.default else "") for x in node.params)
            return [f"{p}function {node.name}({params})"] + self._body(node.body, depth + 1) + [f"{p}end"]
        if isinstance(node, Return): return [f"{p}return" + (f" {self._value(node.value)}" if node.value else "")]
        if isinstance(node, Break): return [f"{p}break"]
        if isinstance(node, Continue): return [f"{p}continue"]
        if isinstance(node, Pass): return [f"{p}nothing"]
        if isinstance(node, Exit): return [f"{p}exit({node.code})"]
        if isinstance(node, Assert): return [f"{p}@assert {self._condition(node.condition)}"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name: return [f'{p}{node.result_name} = get(ENV, "{node.name}", nothing)']
            if node.action == "set": return [f'{p}ENV["{node.name}"] = {self._value(node.value)}']
        if isinstance(node, RawBlock): return [f"{p}# raw {node.language}: {line}" for line in node.code.splitlines()]
        return [f"{p}# Unsupported IR node: {node.type}"]

    def _body(self, nodes, depth): return [line for node in nodes for line in self._node(node, depth)]
    def _condition(self, c): return f"{self._value(c.left)} {c.op} {self._value(c.right)}"
    def _value(self, value):
        if value.kind == "string": return json.dumps(str(value.value))
        if value.kind in ("int", "float", "var"): return str(value.value)
        if value.kind == "bool": return "true" if value.value else "false"
        if value.kind == "null": return "nothing"
        if value.kind == "list": return "[" + ", ".join(self._value(v) for v in (value.parts or [])) + "]"
        if value.kind == "binop" and value.parts and len(value.parts) >= 3:
            left, op, right = value.parts[:3]; operator = str(op.value).replace("and", "&&").replace("or", "||")
            return f"({self._value(left)} {operator} {self._value(right)})"
        return repr(value.value)
