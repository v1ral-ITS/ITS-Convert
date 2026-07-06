"""Emit Haskell from IR."""
from __future__ import annotations
from itsconvert.ir import (
    ScriptIR, IRNode, Value, Condition,
    Comment, Assign, AugAssign, Print, Input, Command, Exit,
    If, ElifBranch, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass, FunctionDef, Return, Import,
    StringOpNode, FileIONode, EnvVar, Argv, TryCatch, Raise,
    ListOp, DictOp, Assert, RawBlock,
)


class HaskellEmitter:
    """Emit Haskell source. Top-level statements are wrapped in main :: IO ()."""

    def emit(self, ir: ScriptIR) -> str:
        lines: list[str] = [
            "module Main where",
            "",
            "import System.Exit (exitWith, ExitCode(..))",
            "import System.Environment (getArgs, lookupEnv)",
            "import System.IO",
            "import Control.Exception (catch, SomeException, evaluate)",
            "import Data.List (intercalate, isPrefixOf, isSuffixOf, isInfixOf)",
            "import Data.Char (toUpper, toLower)",
            "",
        ]
        fns = [n for n in ir.nodes if isinstance(n, FunctionDef)]
        other = [n for n in ir.nodes if not isinstance(n, FunctionDef)]
        for fn in fns:
            lines.extend(self._fn(fn, 0))
            lines.append("")
        lines.append("main :: IO ()")
        lines.append("main = do")
        for node in other:
            lines.extend(self._n(node, 1))
        return "\n".join(lines) + "\n"

    def _n(self, node, i):
        p = "  " * i
        if isinstance(node, Comment): return [f"{p}-- {node.text}"]
        if isinstance(node, Assign): return [f"{p}let {node.name} = {self._v(node.value)}"]
        if isinstance(node, AugAssign): return [f"{p}let {node.name} = {node.name} {node.op} {self._v(node.value)}"]
        if isinstance(node, Print):
            if not node.values: return [f"{p}putStrLn \"\""]
            args = " ++ \" \" ++ ".join(f"show ({self._v(v)})" if v.kind not in ("string", "fstring", "var") else self._v(v) for v in node.values)
            fn = "putStr" if node.end == "" else "putStrLn"
            return [f"{p}{fn} ({args})"]
        if isinstance(node, Input):
            lines = []
            if node.prompt: lines.append(f'{p}putStr "{node.prompt}"')
            lines.append(f"{p}hFlush stdout")
            lines.append(f"{p}{node.name} <- getLine")
            return lines
        if isinstance(node, Command):
            cmd = f"{node.command} {self._args(node.args)}".strip()
            return [f"{p}-- shell: {cmd}"]
        if isinstance(node, Exit): return [f"{p}exitWith (if {node.code} == 0 then ExitSuccess else ExitFailure {node.code})"]
        if isinstance(node, If): return self._if(node, i)
        if isinstance(node, ForRange):
            s, e = self._v(node.start), self._v(node.stop)
            return [f"{p}mapM_ (\\ {node.var} -> do"] + self._body(node.body, i+1) + [f"{p}  ) [{s}..{e}-1]"]
        if isinstance(node, ForEnumerate):
            return [f"{p}mapM_ (\\ ({node.index_var}, {node.value_var}) -> do"] + self._body(node.body, i+1) + [f"{p}  ) (zip [0..] {self._v(node.iterable)})"]
        if isinstance(node, ForKeys):
            return [f"{p}mapM_ (\\ {node.var} -> do"] + self._body(node.body, i+1) + [f"{p}  ) (map fst (Data.Map.toList {self._v(node.dict_value)}))"]
        if isinstance(node, For):
            return [f"{p}mapM_ (\\ {node.var} -> do"] + self._body(node.body, i+1) + [f"{p}  ) {self._v(node.iterable)}"]
        if isinstance(node, While):
            return [f"{p}-- while {self._cond(node.condition)}:"] + self._body(node.body, i+1)
        if isinstance(node, Break): return [f"{p}-- break (not directly supported in do-notation)"]
        if isinstance(node, Continue): return [f"{p}-- continue (not directly supported in do-notation)"]
        if isinstance(node, Pass): return [f"{p}return ()"]
        if isinstance(node, Return): return [f"{p}return{(' (' + self._v(node.value) + ')') if node.value else ' ()'}"]
        if isinstance(node, Import): return [f"{p}-- import {node.module}"]
        if isinstance(node, EnvVar):
            if node.action == "get" and node.result_name:
                return [f'{p}{node.result_name} <- fmap (maybe "" id) (lookupEnv "{node.name}")']
            return [f"{p}-- env: {node.action}"]
        if isinstance(node, Argv):
            if node.action == "all" and node.name: return [f"{p}{node.name} <- getArgs"]
            return [f"{p}-- argv: {node.action}"]
        if isinstance(node, TryCatch):
            cv = node.catch_var or "_e"
            lines = [f"{p}result <- catch (evaluate (do"]
            lines.extend(self._body(node.try_body, i+1))
            lines.append(f"{p}  )) (\\ ({cv} :: SomeException) -> do")
            lines.extend(self._body(node.catch_body, i+1))
            lines.append(f"{p}  )")
            return lines
        if isinstance(node, Raise):
            msg = self._v(node.message) if node.message else '"Error"'
            return [f"{p}ioError (userError {msg})"]
        if isinstance(node, Assert): return [f"{p}if not ({self._cond(node.condition)}) then ioError (userError \"Assertion failed\") else return ()"]
        if isinstance(node, FileIONode): return self._file(node, p)
        if isinstance(node, ListOp): return self._list(node, p)
        if isinstance(node, RawBlock): return [f"{p}-- raw ({node.language})"] + [f"{p}-- {l}" for l in node.code.split("\n")]
        return [f"{p}-- FIXME: {node.type}"]

    def _if(self, n, i):
        p = "  " * i
        lines = [f"{p}if {self._cond(n.condition)}"]
        lines.append(f"{p}  then do")
        lines.extend(self._body(n.then_body, i+2))
        if n.elif_branches or n.else_body:
            lines.append(f"{p}  else do")
            for eb in n.elif_branches:
                lines.append(f"{p}    if {self._cond(eb.condition)}")
                lines.append(f"{p}      then do")
                lines.extend(self._body(eb.body, i+4))
                lines.append(f"{p}      else return ()")
            lines.extend(self._body(n.else_body, i+2))
        else:
            lines.append(f"{p}  else return ()")
        return lines

    def _fn(self, n, i):
        p = "  " * i
        params = " ".join(pp.name for pp in n.params if not pp.vararg and not pp.kwarg) or "()"
        lines = [f"{n.name} {params} = do"]
        lines.extend(self._body(n.body, i+1))
        return lines

    def _list(self, n, p):
        nm = n.name or "xs"
        if n.action == "create": return [f"{p}let {nm} = [{', '.join(self._v(x) for x in n.items)}]"]
        if n.action == "append": return [f"{p}let {nm} = {nm} ++ [{self._v(n.value)}]"]
        if n.action == "len" and n.result_name: return [f"{p}let {n.result_name} = length {nm}"]
        if n.action == "sort" and n.result_name: return [f"{p}let {n.result_name} = Data.List.sort {nm}"]
        if n.action == "contains" and n.value and n.result_name: return [f"{p}let {n.result_name} = {self._v(n.value)} `elem` {nm}"]
        if n.action == "join" and n.result_name and n.value: return [f"{p}let {n.result_name} = intercalate {self._v(n.value)} {nm}"]
        return [f"{p}-- list: {n.action}"]

    def _file(self, n, p):
        path = self._v(n.path)
        if n.op == "read" and n.name: return [f"{p}{n.name} <- readFile {path}"]
        if n.op == "write" and n.content: return [f"{p}writeFile {path} {self._v(n.content)}"]
        if n.op == "append" and n.content: return [f"{p}appendFile {path} {self._v(n.content)}"]
        return [f"{p}-- file: {n.op}"]

    def _body(self, nodes, i): return [l for n in nodes for l in self._n(n, i)]
    def _args(self, a): return " ".join(self._v(x) for x in a)

    def _v(self, v):
        if v.kind == "string": return repr(str(v.value))
        if v.kind == "int": return str(v.value)
        if v.kind == "float": return f"{v.value}" if "." in str(v.value) else f"{v.value}.0"
        if v.kind == "bool": return "True" if v.value else "False"
        if v.kind == "null": return "Nothing"
        if v.kind == "var": return str(v.value)
        if v.kind == "list": return "[" + ", ".join(self._v(p) for p in v.parts) + "]" if v.parts else "[]"
        if v.kind == "binop" and v.parts and len(v.parts) >= 3:
            l, o, r = v.parts; os = self._vs(o)
            m = {"and": "&&", "or": "||", "//": "`div`", "%": "`mod`", "**": "^"}
            return f"({self._v(l)} {m.get(os, os)} {self._v(r)})"
        if v.kind == "unaryop" and v.parts and len(v.parts) >= 2:
            o, x = v.parts; os = self._vs(o)
            m = {"not": "not", "-": "negate"}
            return f"({m.get(os, os)} {self._v(x)})"
        if v.kind == "fstring" and v.parts:
            parts = []
            for p in v.parts:
                if p.kind == "string":
                    parts.append(repr(str(p.value)))
                else:
                    parts.append(f"show ({self._v(p)})")
            return " ++ ".join(parts) if parts else '""'
        if v.kind == "call" and v.parts and len(v.parts) >= 2:
            fn = self._vs(v.parts[0])
            args = " ".join(self._v(a) for a in (v.parts[1].parts or [])) if v.parts[1].parts is not None else self._v(v.parts[1])
            return f"({fn} {args})"
        return repr(v.value)

    def _vs(self, v): s = self._v(v); return s.strip("'\"") if s.startswith(("'", '"')) else s

    def _cond(self, c):
        m = {"==": "==", "!=": "/=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
        return f"{self._v(c.left)} {m.get(c.op, c.op)} {self._v(c.right)}"


def emit_haskell(ir: ScriptIR) -> str: return HaskellEmitter().emit(ir)
