"""Translator registry — parsers and emitters for each language."""
from __future__ import annotations

from itsconvert.ir import ScriptIR, Language
from itsconvert.errors import ParseError, UnsupportedConstructError


class Parser:
    """Base class for source-language parsers."""
    def parse(self, source: str) -> ScriptIR:
        raise NotImplementedError


class Emitter:
    """Base class for target-language emitters."""
    def emit(self, ir: ScriptIR) -> str:
        raise NotImplementedError


# --- Parsers ---

_PARSERS = {
    "py": "itsconvert.translators.py_parser:PythonParser",
    "sh": "itsconvert.translators.sh_parser:BashParser",
    "ps1": "itsconvert.translators.ps1_parser:PS1Parser",
    "cmd": "itsconvert.translators.cmd_parser:CMDParser",
}


def get_parser(lang: Language | str) -> Parser:
    if lang in _PARSERS:
        mod_path, cls_name = _PARSERS[lang].rsplit(":", 1)
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, cls_name)()
    raise UnsupportedConstructError(f"No parser for language: {lang}")


# --- Emitters ---

_EMITTERS = {
    "py": "itsconvert.translators.py_emitter:PyEmitter",
    "sh": "itsconvert.translators.sh_emitter:BashEmitter",
    "ps1": "itsconvert.translators.ps1_emitter:PowerShellEmitter",
    "cmd": "itsconvert.translators.cmd_emitter:CMDEmitter",
    "js": "itsconvert.translators.js_emitter:JSEmitter",
    "ts": "itsconvert.translators.ts_emitter:TSEmitter",
    "rb": "itsconvert.translators.rb_emitter:RubyEmitter",
    "pl": "itsconvert.translators.pl_emitter:PerlEmitter",
    "lua": "itsconvert.translators.lua_emitter:LuaEmitter",
    "php": "itsconvert.translators.php_emitter:PHPEmitter",
    "go": "itsconvert.translators.go_emitter:GoEmitter",
    "rs": "itsconvert.translators.rs_emitter:RustEmitter",
    "java": "itsconvert.translators.java_emitter:JavaEmitter",
    "c": "itsconvert.translators.c_emitter:CEmitter",
    "cpp": "itsconvert.translators.cpp_emitter:CppEmitter",
    "cs": "itsconvert.translators.cs_emitter:CSharpEmitter",
    "swift": "itsconvert.translators.swift_emitter:SwiftEmitter",
    "kt": "itsconvert.translators.kt_emitter:KotlinEmitter",
    "dart": "itsconvert.translators.dart_emitter:DartEmitter",
    "r": "itsconvert.translators.r_emitter:REmitter",
    "scala": "itsconvert.translators.scala_emitter:ScalaEmitter",
    "nim": "itsconvert.translators.nim_emitter:NimEmitter",
    "zig": "itsconvert.translators.zig_emitter:ZigEmitter",
    "v": "itsconvert.translators.v_emitter:VLangEmitter",
}


def get_emitter(lang: Language | str) -> Emitter:
    if lang in _EMITTERS:
        mod_path, cls_name = _EMITTERS[lang].rsplit(":", 1)
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, cls_name)()
    raise UnsupportedConstructError(f"No emitter for language: {lang}")


def available_emitters() -> list[str]:
    return sorted(_EMITTERS.keys())


def available_parsers() -> list[str]:
    return sorted(_PARSERS.keys())


__all__ = ["Parser", "Emitter", "get_parser", "get_emitter", "available_emitters", "available_parsers"]
