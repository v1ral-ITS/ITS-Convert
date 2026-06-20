"""Parse Python source into IR using the built-in ast module."""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from itsconvert.ir import (
    ScriptIR, Language, Value, Condition, ConditionExpr, CompoundCondition, IRNode,
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Param, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock, Switch, SwitchCase,
    ClassDef, ClassField, Lambda, WithBlock,
)
from itsconvert.errors import ParseError, UnsupportedConstructError


def _val(node: ast.expr | None) -> Value:
    """Convert an AST expression node to an IR Value."""
    if node is None:
        return Value(kind="null")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return Value(kind="bool", value=node.value)
        if isinstance(node.value, int):
            return Value(kind="int", value=node.value)
        if isinstance(node.value, float):
            return Value(kind="float", value=node.value)
        if isinstance(node.value, str):
            return Value(kind="string", value=node.value)
        if node.value is None:
            return Value(kind="null")
        return Value(kind="string", value=str(node.value))
    if isinstance(node, ast.Name):
        return Value(kind="var", value=node.id)
    if isinstance(node, ast.List):
        return Value(kind="list", parts=[_val(e) for e in node.elts])
    if isinstance(node, ast.Tuple):
        return Value(kind="list", parts=[_val(e) for e in node.elts])
    if isinstance(node, ast.Dict):
        return Value(kind="dict", parts=[
            Value(kind="list", parts=[_val(k) if k else Value(kind="null"), _val(v)])
            for k, v in zip(node.keys, node.values)
        ])
    if isinstance(node, ast.BinOp):
        op_map = {
            ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
            ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
            ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^",
            ast.LShift: "<<", ast.RShift: ">>",
        }
        op = op_map.get(type(node.op))
        if op is None:
            return Value(kind="binop", parts=[_val(node.left), Value(kind="string", value="+"), _val(node.right)])
        return Value(kind="binop", parts=[_val(node.left), Value(kind="string", value=op), _val(node.right)])
    if isinstance(node, ast.UnaryOp):
        op_map = {ast.UAdd: "+", ast.USub: "-", ast.Not: "not", ast.Invert: "~"}
        op = op_map.get(type(node.op), "not")
        return Value(kind="unaryop", parts=[Value(kind="string", value=op), _val(node.operand)])
    if isinstance(node, ast.BoolOp):
        op = "and" if isinstance(node.op, ast.And) else "or"
        return Value(kind="binop", parts=[_val(node.values[0]), Value(kind="string", value=op), _val(node.values[1])])
    if isinstance(node, ast.Compare):
        if len(node.ops) == 1:
            op_map = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
                       ast.Gt: ">", ast.GtE: ">=", ast.Is: "==", ast.IsNot: "!="}
            op = op_map.get(type(node.ops[0]), "==")
            return Value(kind="binop", parts=[_val(node.left), Value(kind="string", value=op), _val(node.comparators[0])])
        # chain: a < b < c  → flatten to (a < b) and (b < c)
        parts = []
        left = node.left
        for op_node, right in zip(node.ops, node.comparators):
            op_map = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
                       ast.Gt: ">", ast.GtE: ">=", ast.Is: "==", ast.IsNot: "!="}
            op = op_map.get(type(op_node), "==")
            parts.append(Value(kind="binop", parts=[_val(left), Value(kind="string", value=op), _val(right)]))
            left = right
        result = parts[0]
        for p in parts[1:]:
            result = Value(kind="binop", parts=[result, Value(kind="string", value="and"), p])
        return result
    if isinstance(node, ast.Call):
        func_name = _call_name(node)
        args = [_val(a) for a in node.args]
        return Value(kind="call", parts=[Value(kind="string", value=func_name), Value(kind="list", parts=args)])
    if isinstance(node, ast.Subscript):
        return Value(kind="subscript", parts=[_val(node.value), _val(node.slice)])
    if isinstance(node, ast.Attribute):
        return Value(kind="attr", parts=[_val(node.value), Value(kind="string", value=node.attr)])
    if isinstance(node, ast.Starred):
        return _val(node.value)  # flatten
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(Value(kind="string", value=str(v.value)))
            elif isinstance(v, ast.FormattedValue):
                parts.append(_val(v.value))
            else:
                parts.append(_val(v))
        return Value(kind="fstring", parts=parts)
    if isinstance(node, ast.IfExp):
        return Value(kind="binop", parts=[
            _val(node.body), Value(kind="string", value="if"), _val(node.test),
            Value(kind="string", value="else"), _val(node.orelse),
        ])
    # fallback: try to reconstruct source
    try:
        import ast as _ast
        src = _ast.unparse(node)
        return Value(kind="var", value=src)
    except Exception:
        return Value(kind="string", value="<unsupported-expr>")


def _call_name(node: ast.Call) -> str:
    """Extract the function name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        base = _call_name_recursive(node.func)
        return base
    return "<unknown>"


def _call_name_recursive(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name_recursive(node.value)}.{node.attr}"
    return "<unknown>"


def _condition(test: ast.expr) -> ConditionExpr:
    """Extract a ConditionExpr from an AST test expression."""
    # Compound: a and b, a or b
    if isinstance(test, ast.BoolOp):
        op: Condition | CompoundCondition
        bool_op = "and" if isinstance(test.op, ast.And) else "or"
        result: ConditionExpr = _condition(test.values[0])
        for v in test.values[1:]:
            result = CompoundCondition(left=result, op=bool_op, right=_condition(v))
        return result
    # not expr → flip the condition if simple
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        inner = _condition(test.operand)
        if isinstance(inner, Condition):
            flip = {"==": "!=", "!=": "==", ">": "<=", "<": ">=", ">=": "<", "<=": ">"}
            return Condition(left=inner.left, op=flip.get(inner.op, inner.op), right=inner.right)
        return inner
    # Single comparison
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        op_map = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
                   ast.Gt: ">", ast.GtE: ">=", ast.Is: "==", ast.IsNot: "!=",
                   ast.In: "==", ast.NotIn: "!="}
        op_str = op_map.get(type(test.ops[0]), "==")
        return Condition(left=_val(test.left), op=op_str, right=_val(test.comparators[0]))
    # Chained comparison: a < b < c → (a < b) and (b < c)
    if isinstance(test, ast.Compare):
        op_map = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
                   ast.Gt: ">", ast.GtE: ">=", ast.Is: "==", ast.IsNot: "!="}
        parts: list[ConditionExpr] = []
        left: ast.expr = test.left
        for op_node, right in zip(test.ops, test.comparators):
            op_str = op_map.get(type(op_node), "==")
            parts.append(Condition(left=_val(left), op=op_str, right=_val(right)))
            left = right
        chain: ConditionExpr = parts[0]
        for p in parts[1:]:
            chain = CompoundCondition(left=chain, op="and", right=p)
        return chain
    # fallback: treat as bool comparison
    return Condition(left=_val(test), op="!=", right=Value(kind="bool", value=False))


class PythonParser:
    """Parse Python source code into ScriptIR."""

    def parse(self, source: str) -> ScriptIR:
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise ParseError(f"Python syntax error: {e}") from e

        nodes: list[IRNode] = []
        warnings: list[str] = []

        for node in tree.body:
            result = self._translate_node(node, warnings)
            if isinstance(result, list):
                nodes.extend(result)
            elif result is not None:
                nodes.append(result)

        # Compute confidence: penalise for RawBlock/Command fallbacks
        total = len(nodes) or 1
        fallbacks = sum(1 for n in nodes if isinstance(n, (RawBlock, Command)))
        confidence = max(0.0, 1.0 - (fallbacks / total) * 0.5)
        return ScriptIR(source_language="py", nodes=nodes, warnings=warnings, confidence=round(confidence, 2))

    def _translate_node(self, node: ast.stmt, warnings: list[str]) -> IRNode | list[IRNode] | None:
        if isinstance(node, ast.Expr):
            return self._translate_expr_stmt(node, warnings)
        if isinstance(node, ast.Assign):
            return self._translate_assign(node)
        if isinstance(node, ast.AugAssign):
            return self._translate_aug_assign(node)
        if isinstance(node, ast.AnnAssign):
            if node.value:
                return Assign(name=node.target.id if isinstance(node.target, ast.Name) else str(node.target), value=_val(node.value))
            return None
        if isinstance(node, ast.If):
            return self._translate_if(node, warnings)
        if isinstance(node, ast.For):
            return self._translate_for(node, warnings)
        if isinstance(node, ast.While):
            return self._translate_while(node, warnings)
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            return self._translate_function(node, warnings)
        if isinstance(node, ast.Return):
            return Return(value=_val(node.value) if node.value else None)
        if isinstance(node, ast.Import):
            items = []
            for alias in node.names:
                items.append(Import(module=alias.name, alias=alias.asname))
            return items if len(items) > 1 else items[0] if items else None
        if isinstance(node, ast.ImportFrom):
            return Import(module=node.module or "", names=[a.name for a in node.names])
        if isinstance(node, ast.Break):
            return Break()
        if isinstance(node, ast.Continue):
            return Continue()
        if isinstance(node, ast.Pass):
            return Pass()
        if isinstance(node, ast.Try):
            return self._translate_try(node, warnings)
        if isinstance(node, ast.Raise):
            return self._translate_raise(node)
        if isinstance(node, ast.Assert):
            return self._translate_assert(node)
        if isinstance(node, ast.With) or isinstance(node, ast.AsyncWith):
            return self._translate_with(node, warnings)
        # Python 3.10+ match/case
        if hasattr(ast, "Match") and isinstance(node, ast.Match):
            return self._translate_match(node, warnings)
        if isinstance(node, ast.Global) or isinstance(node, ast.Nonlocal):
            warnings.append(f"Skipped {type(node).__name__} statement")
            return None
        if isinstance(node, ast.ClassDef):
            return self._translate_class(node, warnings)
        if isinstance(node, ast.Delete):
            warnings.append("del statement converted to None assignment")
            targets = []
            for t in node.targets:
                if isinstance(t, ast.Name):
                    targets.append(Assign(name=t.id, value=Value(kind="null")))
            return targets if targets else None

        warnings.append(f"Unsupported statement: {type(node).__name__}")
        return RawBlock(language="py", code=ast.unparse(node))

    def _translate_expr_stmt(self, node: ast.Expr, warnings: list[str]) -> IRNode | None:
        val = node.value
        # print()
        if isinstance(val, ast.Call) and isinstance(val.func, ast.Name) and val.func.id == "print":
            return self._translate_print(val)
        # input()
        if isinstance(val, ast.Call) and isinstance(val.func, ast.Name) and val.func.id == "input":
            return self._translate_input_call(val)
        # os.system / subprocess call patterns
        if isinstance(val, ast.Call):
            name = _call_name(val)
            if name in ("sys.exit", "exit", "quit"):
                code = 0
                if val.args:
                    v = _val(val.args[0])
                    code = int(v.value) if v.value is not None else 0
                return Exit(code=code)
            # env var patterns
            if name == "os.environ.get" and len(val.args) >= 1:
                return EnvVar(action="get", name=str(_val(val.args[0]).value or ""), result_name=None)
            if name == "os.getenv" and len(val.args) >= 1:
                return EnvVar(action="get", name=str(_val(val.args[0]).value or ""), result_name=None)
            if name == "os.environ.__setitem__" and len(val.args) >= 2:
                # os.environ["KEY"] = val — but this is actually Assign with Subscript target
                pass
            # string method calls
            if name in ("str.upper", "str.lower", "str.strip", "str.replace", "str.split", "str.join", "str.startswith", "str.endswith"):
                return self._translate_string_method(name, val)
            # file I/O patterns
            if name == "open":
                return self._translate_file_open(val, warnings)
            # general function call as command passthrough
            return Command(command=name, args=[_val(a) for a in val.args], capture=False, name=None)
        return None

    def _translate_print(self, call: ast.Call) -> Print:
        values = [_val(a) for a in call.args]
        end = "\n"
        file = None
        for kw in call.keywords:
            if kw.arg == "end":
                end = str(_val(kw.value).value or "\n")
            elif kw.arg == "file":
                file = _val(kw.value)
        return Print(values=values, end=end, file=file)

    def _translate_input_call(self, call: ast.Call) -> Input:
        prompt = ""
        if call.args:
            prompt = str(_val(call.args[0]).value or "")
        return Input(name="<input>", prompt=prompt)

    def _translate_assign(self, node: ast.Assign) -> IRNode | list[IRNode]:
        value = _val(node.value)
        if len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                # detect lambda assignment: x = lambda a, b: expr
                if isinstance(node.value, ast.Lambda):
                    return self._translate_lambda_assign(target.id, node.value)
                # detect input() assignment: x = input("prompt")
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "input":
                    prompt = str(_val(node.value.args[0]).value or "") if node.value.args else ""
                    return Input(name=target.id, prompt=prompt)
                # detect os.environ patterns
                if isinstance(node.value, ast.Call):
                    name = _call_name(node.value)
                    if name in ("os.getenv", "os.environ.get") and node.value.args:
                        return EnvVar(action="get", name=str(_val(node.value.args[0]).value or ""), result_name=target.id)
                    if name in ("len",) and node.value.args:
                        arg = _val(node.value.args[0])
                        if arg.kind == "var":
                            return Assign(name=target.id, value=Value(kind="call", parts=[
                                Value(kind="string", value="len"), Value(kind="list", parts=[arg])
                            ]))
                # detect os.environ["KEY"] = value
                if isinstance(target, ast.Subscript):
                    sub_parts = [_val(target.value), _val(target.slice)]
                    base_name = _call_name_recursive(target.value) if isinstance(target.value, ast.Attribute) else ""
                    if base_name == "os.environ" or (isinstance(target.value, ast.Attribute) and target.value.attr == "environ"):
                        key = str(_val(target.slice).value or "")
                        return EnvVar(action="set", name=key, value=value)
                # detect subprocess.run / os.system capture
                if isinstance(node.value, ast.Call):
                    call_name = _call_name(node.value)
                    if call_name in ("subprocess.run", "subprocess.call", "subprocess.check_output", "subprocess.check_call"):
                        cmd_args = []
                        if node.value.args:
                            cmd_args.append(_val(node.value.args[0]))
                        for kw in node.value.keywords:
                            if kw.arg == "args" and isinstance(kw.value, ast.List):
                                cmd_args = [_val(e) for e in kw.value.elts]
                        return Command(
                            command="subprocess",
                            args=cmd_args,
                            capture=call_name != "subprocess.run",
                            name=target.id,
                        )
                    if call_name == "os.system" and node.value.args:
                        return Command(command=str(_val(node.value.args[0]).value or ""), args=[], capture=False, name=target.id)
                # detect open() for file read
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "open":
                    # x = open("file").read() — complex pattern, simplified
                    pass
                return Assign(name=target.id, value=value)
            if isinstance(target, ast.Tuple):
                names = [elt.id for elt in target.elts if isinstance(elt, ast.Name)]
                if names:
                    return MultiAssign(names=names, value=value)
            if isinstance(target, ast.Subscript):
                # list/dict subscript assignment
                return Assign(name=ast.unparse(target), value=value)
        # multiple targets: a = b = c
        return Assign(name=node.targets[0].id if isinstance(node.targets[0], ast.Name) else ast.unparse(node.targets[0]), value=value)

    def _translate_aug_assign(self, node: ast.AugAssign) -> AugAssign:
        op_map = {
            ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
            ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
            ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^",
        }
        op = op_map.get(type(node.op), "+")
        name = node.target.id if isinstance(node.target, ast.Name) else ast.unparse(node.target)
        return AugAssign(name=name, op=op, value=_val(node.value))

    def _translate_if(self, node: ast.If, warnings: list[str]) -> If:
        condition = _condition(node.test)
        then_body = []
        for child in node.body:
            result = self._translate_node(child, warnings)
            if isinstance(result, list):
                then_body.extend(result)
            elif result is not None:
                then_body.append(result)

        elif_branches = []
        else_body = []

        current = node.orelse
        while current:
            if isinstance(current, list) and len(current) == 1 and isinstance(current[0], ast.If):
                elif_node = current[0]
                elif_body = []
                for child in elif_node.body:
                    result = self._translate_node(child, warnings)
                    if isinstance(result, list):
                        elif_body.extend(result)
                    elif result is not None:
                        elif_body.append(result)
                elif_branches.append(ElifBranch(condition=_condition(elif_node.test), body=elif_body))
                current = elif_node.orelse
            else:
                for child in current:
                    result = self._translate_node(child, warnings)
                    if isinstance(result, list):
                        else_body.extend(result)
                    elif result is not None:
                        else_body.append(result)
                break

        return If(condition=condition, then_body=then_body, elif_branches=elif_branches, else_body=else_body)

    def _translate_for(self, node: ast.For, warnings: list[str]) -> IRNode:
        body = self._translate_body(node.body, warnings)

        # for i in range(...)
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
            args = node.iter.args
            if len(args) == 1:
                return ForRange(var=node.target.id if isinstance(node.target, ast.Name) else "i",
                                start=Value(kind="int", value=0), stop=_val(args[0]), body=body)
            if len(args) == 2:
                return ForRange(var=node.target.id if isinstance(node.target, ast.Name) else "i",
                                start=_val(args[0]), stop=_val(args[1]), body=body)
            if len(args) == 3:
                return ForRange(var=node.target.id if isinstance(node.target, ast.Name) else "i",
                                start=_val(args[0]), stop=_val(args[1]), step=_val(args[2]), body=body)

        # for i, x in enumerate(...)
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "enumerate":
            if isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2:
                idx = node.target.elts[0].id if isinstance(node.target.elts[0], ast.Name) else "i"
                val = node.target.elts[1].id if isinstance(node.target.elts[1], ast.Name) else "x"
                return ForEnumerate(index_var=idx, value_var=val, iterable=_val(node.iter.args[0]) if node.iter.args else Value(kind="null"), body=body)

        # for k in dict: → for_keys
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute) and node.iter.func.attr == "keys":
            var = node.target.id if isinstance(node.target, ast.Name) else "k"
            return ForKeys(var=var, dict_value=_val(node.iter.func.value), body=body)

        return For(var=node.target.id if isinstance(node.target, ast.Name) else ast.unparse(node.target),
                   iterable=_val(node.iter), body=body)

    def _translate_while(self, node: ast.While, warnings: list[str]) -> While:
        return While(condition=_condition(node.test), body=self._translate_body(node.body, warnings))

    def _translate_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, warnings: list[str]) -> FunctionDef:
        params = []
        for arg in node.args.args:
            p = Param(name=arg.arg, type_hint=ast.unparse(arg.annotation) if arg.annotation else None)
            params.append(p)
        if node.args.vararg:
            params.append(Param(name=node.args.vararg.arg, vararg=True))
        if node.args.kwarg:
            params.append(Param(name=node.args.kwarg.arg, kwarg=True))
        # defaults (match from the end)
        defaults = node.args.defaults
        if defaults:
            offset = len(params) - len(defaults)
            for i, d in enumerate(defaults):
                params[offset + i].default = _val(d)

        body = self._translate_body(node.body, warnings)
        return_type = ast.unparse(node.returns) if node.returns else None
        return FunctionDef(name=node.name, params=params, body=body, return_type=return_type)

    def _translate_try(self, node: ast.Try, warnings: list[str]) -> TryCatch:
        try_body = self._translate_body(node.body, warnings)
        catch_var = None
        catch_body = []
        if node.handlers:
            handler = node.handlers[0]
            if isinstance(handler, ast.ExceptHandler):
                if handler.name:
                    catch_var = handler.name
                elif handler.type:
                    catch_var = "e"
                catch_body = self._translate_body(handler.body, warnings)
        finally_body = self._translate_body(node.finalbody, warnings) if node.finalbody else []
        return TryCatch(try_body=try_body, catch_var=catch_var, catch_body=catch_body, finally_body=finally_body)

    def _translate_raise(self, node: ast.Raise) -> Raise:
        exc_type = None
        message = None
        if node.exc:
            if isinstance(node.exc, ast.Call):
                exc_type = _call_name(node.exc)
                if node.exc.args:
                    message = _val(node.exc.args[0])
            elif isinstance(node.exc, ast.Name):
                exc_type = node.exc.id
        return Raise(message=message, exc_type=exc_type)

    def _translate_assert(self, node: ast.Assert) -> Assert:
        return Assert(condition=_condition(node.test), message=_val(node.msg) if node.msg else None)

    def _translate_with(self, node: ast.With, warnings: list[str]) -> IRNode | list[IRNode]:
        # Detect: with open("file") as f:  → FileIO
        if len(node.items) == 1:
            item = node.items[0]
            if isinstance(item.context_expr, ast.Call):
                call = item.context_expr
                name = _call_name(call)
                if name == "open" and call.args:
                    path = _val(call.args[0])
                    mode = "r"
                    encoding = "utf-8"
                    for kw in call.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode = kw.value.value
                        if kw.arg == "encoding" and isinstance(kw.value, ast.Constant):
                            encoding = kw.value.value
                    body = self._translate_body(node.body, warnings)
                    var_name = item.optional_vars.id if item.optional_vars and isinstance(item.optional_vars, ast.Name) else None
                    if "r" in mode:
                        return FileIONode(op="read", path=path, name=var_name, encoding=encoding)
                    if "w" in mode:
                        content = self._extract_write_content(body, var_name)
                        return FileIONode(op="write", path=path, content=content, encoding=encoding)
                    if "a" in mode:
                        content = self._extract_write_content(body, var_name)
                        return FileIONode(op="append", path=path, content=content, encoding=encoding)
                # Generic with-block for other context managers
                var_name = item.optional_vars.id if item.optional_vars and isinstance(item.optional_vars, ast.Name) else None
                body = self._translate_body(node.body, warnings)
                return WithBlock(expr=_val(item.context_expr), var=var_name, body=body)

        warnings.append("Complex with statement kept as raw block")
        return RawBlock(language="py", code=ast.unparse(node))

    def _extract_write_content(self, body: list[IRNode], file_var: str | None) -> Value | None:
        """Try to extract what's being written from a file write call in the body."""
        for n in body:
            if isinstance(n, Command) and n.command == f"{file_var}.write" and n.args:
                return n.args[0]
        return None

    def _translate_string_method(self, name: str, call: ast.Call) -> StringOpNode:
        op_map = {
            "str.upper": "upper", "str.lower": "lower", "str.strip": "strip",
            "str.replace": "replace", "str.split": "split", "str.join": "join",
            "str.startswith": "startswith", "str.endswith": "endswith",
        }
        op = op_map.get(name, "upper")
        operands = [_val(a) for a in call.args]
        return StringOpNode(op=op, operands=operands)

    def _translate_file_open(self, call: ast.Call, warnings: list[str]) -> IRNode:
        warnings.append("bare open() call — use 'with open()' for proper file I/O translation")
        return Command(command="open", args=[_val(a) for a in call.args], capture=True, name=None)

    def _translate_class(self, node: ast.ClassDef, warnings: list[str]) -> ClassDef:
        bases = []
        for base in node.bases:
            bases.append(ast.unparse(base))
        fields: list[ClassField] = []
        methods: list[FunctionDef] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = self._translate_function(item, warnings)
                methods.append(fn)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        val = _val(item.value)
                        type_hint = None
                        fields.append(ClassField(name=target.id, value=val, type_hint=type_hint))
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    type_hint = ast.unparse(item.annotation) if item.annotation else None
                    val = _val(item.value) if item.value else None
                    fields.append(ClassField(name=item.target.id, value=val, type_hint=type_hint))
            # skip pass, docstrings, etc.
        return ClassDef(name=node.name, bases=bases, fields=fields, methods=methods)

    def _translate_lambda_assign(self, name: str, node: ast.Lambda) -> Lambda:
        params = [Param(name=arg.arg) for arg in node.args.args]
        if node.args.vararg:
            params.append(Param(name=node.args.vararg.arg, vararg=True))
        body = _val(node.body)
        return Lambda(name=name, params=params, body=body)

    def _translate_match(self, node: "ast.Match", warnings: list[str]) -> Switch:
        subject = _val(node.subject)
        cases: list[SwitchCase] = []
        default_body: list[IRNode] = []
        for case in node.cases:
            body = self._translate_body(case.body, warnings)
            pattern = case.pattern
            # default: `case _:`
            if hasattr(ast, "MatchAs") and isinstance(pattern, ast.MatchAs) and pattern.pattern is None:
                default_body = body
            # literal value: `case 42:` or `case "hello":`
            elif hasattr(ast, "MatchValue") and isinstance(pattern, ast.MatchValue):
                cases.append(SwitchCase(pattern=_val(pattern.value), body=body))
            # singleton: `case None:` / `case True:`
            elif hasattr(ast, "MatchSingleton") and isinstance(pattern, ast.MatchSingleton):
                cases.append(SwitchCase(pattern=Value(kind="null" if pattern.value is None else "bool", value=pattern.value), body=body))
            else:
                # Complex pattern (MatchOr, MatchClass, etc.) — best-effort
                warnings.append(f"Complex match pattern converted with limited fidelity")
                cases.append(SwitchCase(pattern=Value(kind="string", value=ast.unparse(pattern)), body=body))
        return Switch(subject=subject, cases=cases, default_body=default_body)

    def _translate_body(self, stmts: list[ast.stmt], warnings: list[str]) -> list[IRNode]:
        nodes: list[IRNode] = []
        for stmt in stmts:
            result = self._translate_node(stmt, warnings)
            if isinstance(result, list):
                nodes.extend(result)
            elif result is not None:
                nodes.append(result)
        return nodes


def parse_python(source: str) -> ScriptIR:
    """Convenience function: parse Python source to IR."""
    return PythonParser().parse(source)
