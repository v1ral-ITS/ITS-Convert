from __future__ import annotations

from typing import Literal, Union
from pydantic import BaseModel, Field

Language = Literal["py", "sh", "ps1", "cmd", "js", "rb", "pl", "go", "rs", "lua", "ts", "php", "java", "c", "cpp", "cs", "swift", "kt", "dart", "pyi", "r", "scala", "nim", "zig", "v"]

ValueType = Literal["string", "int", "float", "bool", "null", "var", "list", "dict", "binop", "unaryop", "call", "subscript", "attr", "slice", "fstring"]
CompareOp = Literal["==", "!=", ">", "<", ">=", "<="]
BinaryOp = Literal["+", "-", "*", "/", "//", "%", "**", "&", "|", "^", "<<", ">>", "and", "or"]
UnaryOp = Literal["-", "not", "~"]
StringOp = Literal["concat", "format", "split", "join", "replace", "strip", "upper", "lower", "len", "contains", "startswith", "endswith"]
FileOp = Literal["read", "write", "append", "exists", "delete", "mkdir", "listdir", "basename", "dirname", "copy", "move"]
BoolOp = Literal["and", "or"]


class Value(BaseModel):
    kind: ValueType
    value: str | int | float | bool | None = None
    parts: list["Value"] | None = None  # for fstring, list, dict, binop, unaryop, call, subscript, attr, slice


class Condition(BaseModel):
    left: Value
    op: CompareOp
    right: Value


class CompoundCondition(BaseModel):
    """Compound boolean condition: `left and/or right` where each side can be a Condition or another CompoundCondition."""
    left: "ConditionExpr"
    op: BoolOp
    right: "ConditionExpr"


ConditionExpr = Union[Condition, CompoundCondition]


class Node(BaseModel):
    type: str


class Comment(Node):
    type: Literal["comment"] = "comment"
    text: str


class Assign(Node):
    type: Literal["assign"] = "assign"
    name: str
    value: Value


class MultiAssign(Node):
    type: Literal["multi_assign"] = "multi_assign"
    names: list[str]
    value: Value


class AugAssign(Node):
    type: Literal["aug_assign"] = "aug_assign"
    name: str
    op: BinaryOp
    value: Value


class Print(Node):
    type: Literal["print"] = "print"
    values: list[Value] = Field(default_factory=list)
    end: str = "\n"
    file: Value | None = None


class Input(Node):
    type: Literal["input"] = "input"
    name: str
    prompt: str = ""


class Command(Node):
    type: Literal["command"] = "command"
    command: str
    args: list[Value] = Field(default_factory=list)
    capture: bool = False
    name: str | None = None  # variable to capture output into


class Exit(Node):
    type: Literal["exit"] = "exit"
    code: int = 0


class If(Node):
    type: Literal["if"] = "if"
    condition: ConditionExpr
    then_body: list["IRNode"] = Field(default_factory=list)
    elif_branches: list["ElifBranch"] = Field(default_factory=list)
    else_body: list["IRNode"] = Field(default_factory=list)


class ElifBranch(BaseModel):
    condition: ConditionExpr
    body: list["IRNode"] = Field(default_factory=list)


class For(Node):
    type: Literal["for"] = "for"
    var: str
    iterable: Value
    body: list["IRNode"] = Field(default_factory=list)


class ForRange(Node):
    type: Literal["for_range"] = "for_range"
    var: str
    start: Value
    stop: Value
    step: Value | None = None
    body: list["IRNode"] = Field(default_factory=list)


class ForEnumerate(Node):
    type: Literal["for_enumerate"] = "for_enumerate"
    index_var: str
    value_var: str
    iterable: Value
    body: list["IRNode"] = Field(default_factory=list)


class ForKeys(Node):
    type: Literal["for_keys"] = "for_keys"
    var: str
    dict_value: Value
    body: list["IRNode"] = Field(default_factory=list)


class While(Node):
    type: Literal["while"] = "while"
    condition: ConditionExpr
    body: list["IRNode"] = Field(default_factory=list)


class Break(Node):
    type: Literal["break"] = "break"


class Continue(Node):
    type: Literal["continue"] = "continue"


class Pass(Node):
    type: Literal["pass"] = "pass"


class FunctionDef(Node):
    type: Literal["function_def"] = "function_def"
    name: str
    params: list["Param"] = Field(default_factory=list)
    body: list["IRNode"] = Field(default_factory=list)
    return_type: str | None = None


class Param(BaseModel):
    name: str
    default: Value | None = None
    type_hint: str | None = None
    vararg: bool = False
    kwarg: bool = False


class Return(Node):
    type: Literal["return"] = "return"
    value: Value | None = None


class Import(Node):
    type: Literal["import"] = "import"
    module: str
    names: list[str] = Field(default_factory=list)  # from X import Y, Z
    alias: str | None = None


class StringOpNode(Node):
    type: Literal["string_op"] = "string_op"
    op: StringOp
    operands: list[Value] = Field(default_factory=list)
    name: str | None = None  # result variable


class FileIONode(Node):
    type: Literal["file_io"] = "file_io"
    op: FileOp
    path: Value
    content: Value | None = None
    name: str | None = None  # result variable
    encoding: str = "utf-8"


class EnvVar(Node):
    type: Literal["env_var"] = "env_var"
    action: Literal["get", "set", "delete", "list"]
    name: str
    value: Value | None = None
    result_name: str | None = None


class Argv(Node):
    type: Literal["argv"] = "argv"
    action: Literal["script_name", "all", "nth", "count"]
    index: int | None = None
    name: str | None = None


class TryCatch(Node):
    type: Literal["try_catch"] = "try_catch"
    try_body: list["IRNode"] = Field(default_factory=list)
    catch_var: str | None = None
    catch_body: list["IRNode"] = Field(default_factory=list)
    finally_body: list["IRNode"] = Field(default_factory=list)


class Raise(Node):
    type: Literal["raise"] = "raise"
    message: Value | None = None
    exc_type: str | None = None


class ListOp(Node):
    type: Literal["list_op"] = "list_op"
    action: Literal["create", "append", "extend", "pop", "insert", "remove", "index", "len", "sort", "reverse", "join", "slice", "contains"]
    name: str | None = None
    value: Value | None = None
    index: Value | None = None
    items: list[Value] = Field(default_factory=list)
    result_name: str | None = None


class DictOp(Node):
    type: Literal["dict_op"] = "dict_op"
    action: Literal["create", "get", "set", "delete", "keys", "values", "items", "contains", "len", "update", "pop"]
    name: str | None = None
    key: Value | None = None
    value: Value | None = None
    items: list[tuple[Value, Value]] = Field(default_factory=list)
    result_name: str | None = None


class Assert(Node):
    type: Literal["assert"] = "assert"
    condition: ConditionExpr
    message: Value | None = None


class RawBlock(Node):
    type: Literal["raw_block"] = "raw_block"
    language: Language
    code: str


class SwitchCase(BaseModel):
    """One case/when arm in a Switch/Match node."""
    pattern: Value
    body: list["IRNode"] = Field(default_factory=list)


class Switch(Node):
    """Switch/match statement: switch subject { case p: ... default: ... }"""
    type: Literal["switch"] = "switch"
    subject: Value
    cases: list[SwitchCase] = Field(default_factory=list)
    default_body: list["IRNode"] = Field(default_factory=list)


class ClassField(BaseModel):
    name: str
    value: Value | None = None
    type_hint: str | None = None


class ClassDef(Node):
    """Class definition with fields and methods."""
    type: Literal["class_def"] = "class_def"
    name: str
    bases: list[str] = Field(default_factory=list)
    fields: list[ClassField] = Field(default_factory=list)
    methods: list[FunctionDef] = Field(default_factory=list)


class Lambda(Node):
    """Anonymous function / lambda expression stored as a variable assignment."""
    type: Literal["lambda"] = "lambda"
    name: str | None = None  # variable name the lambda is bound to
    params: list[Param] = Field(default_factory=list)
    body: Value  # single-expression body


class WithBlock(Node):
    """Context manager / resource acquisition: `with expr as var:`."""
    type: Literal["with_block"] = "with_block"
    expr: Value
    var: str | None = None
    body: list["IRNode"] = Field(default_factory=list)


IRNode = Union[
    Comment, Assign, MultiAssign, AugAssign, Print, Input, Command, Exit,
    If, For, ForRange, ForEnumerate, ForKeys, While,
    Break, Continue, Pass,
    FunctionDef, Return, Import, StringOpNode, FileIONode, EnvVar, Argv,
    TryCatch, Raise, ListOp, DictOp, Assert, RawBlock,
    Switch, ClassDef, Lambda, WithBlock,
]


class ScriptIR(BaseModel):
    source_language: Language
    nodes: list[IRNode] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    """Parser confidence (0.0–1.0). Drops when constructs fall back to Command/RawBlock."""
