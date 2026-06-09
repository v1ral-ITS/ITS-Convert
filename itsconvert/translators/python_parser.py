from __future__ import annotations

import ast

from itsconvert.errors import UnsupportedConstructError
from itsconvert.ir import Assign, Command, Condition, Exit, If, Input, Print, ScriptIR, Value


class PythonParser:
    def parse(self, source: str) -> ScriptIR:
        tree = ast.parse(source)
        ir = ScriptIR(source_language="py")
        for node in tree.body:
            ir.nodes.append(self._convert_node(node, ir))
        return ir

    def _convert_node(self, node: ast.AST, ir: ScriptIR):
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise UnsupportedConstructError("Only simple assignments are supported")
            target = node.targets[0].id
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "input":
                prompt = ""
                if node.value.args:
                    prompt_val = self._value(node.value.args[0])
                    prompt = str(prompt_val.value)
                return Input(name=target, prompt=prompt)
            return Assign(name=target, value=self._value(node.value))

        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id == "print":
                first_arg = call.args[0] if call.args else ast.Constant(value="")
                return Print(value=self._value(first_arg))
            return Command(command=ast.unparse(call))

        if isinstance(node, ast.If):
            return If(
                condition=self._condition(node.test),
                then_body=[self._convert_node(n, ir) for n in node.body],
                else_body=[self._convert_node(n, ir) for n in node.orelse],
            )

        if isinstance(node, ast.Return):
            code = 0
            if node.value is not None:
                value = self._value(node.value)
                if value.kind != "int":
                    raise UnsupportedConstructError("Only integer return codes are supported")
                code = int(value.value)
            return Exit(code=code)

        if isinstance(node, ast.Raise):
            raise UnsupportedConstructError("raise is not supported in v1")

        raise UnsupportedConstructError(f"Unsupported Python construct: {type(node).__name__}")

    def _value(self, node: ast.AST) -> Value:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return Value(kind="bool", value=node.value)
            if isinstance(node.value, str):
                return Value(kind="string", value=node.value)
            if isinstance(node.value, int):
                return Value(kind="int", value=node.value)
            if isinstance(node.value, float):
                return Value(kind="float", value=node.value)
            if node.value is None:
                return Value(kind="null", value=None)

        if isinstance(node, ast.Name):
            return Value(kind="var", value=node.id)

        if isinstance(node, ast.JoinedStr):
            return Value(kind="string", value=ast.unparse(node))

        raise UnsupportedConstructError(f"Unsupported Python value: {type(node).__name__}")

    def _condition(self, node: ast.AST) -> Condition:
        if not isinstance(node, ast.Compare):
            raise UnsupportedConstructError("Only simple comparisons are supported")
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise UnsupportedConstructError("Only single comparisons are supported")

        op_map = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Gt: ">",
            ast.Lt: "<",
            ast.GtE: ">=",
            ast.LtE: "<=",
        }
        op_type = type(node.ops[0])
        if op_type not in op_map:
            raise UnsupportedConstructError("Unsupported comparison operator")

        return Condition(
            left=self._value(node.left),
            op=op_map[op_type],
            right=self._value(node.comparators[0]),
        )
