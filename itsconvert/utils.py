from __future__ import annotations

from pathlib import Path

from itsconvert.ir import Language


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def infer_language(path: Path) -> Language:
    ext = path.suffix.lower()
    mapping: dict[str, Language] = {
        ".py": "py",
        ".sh": "sh",
        ".bash": "sh",
        ".ps1": "ps1",
        ".cmd": "cmd",
        ".bat": "cmd",
        ".js": "js",
        ".mjs": "js",
        ".ts": "ts",
        ".rb": "rb",
        ".pl": "pl",
        ".pm": "pl",
        ".lua": "lua",
        ".php": "php",
        ".go": "go",
        ".rs": "rs",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".cs": "cs",
        ".swift": "swift",
        ".kt": "kt",
        ".kts": "kt",
        ".dart": "dart",
        ".r": "r",
        ".R": "r",
        ".scala": "scala",
        ".nim": "nim",
        ".zig": "zig",
        ".v": "v",
        ".jl": "jl",
        ".hs": "hs",
        ".lhs": "hs",
        ".ex": "ex",
        ".exs": "ex",
        ".fs": "fs",
        ".fsx": "fs",
        ".fsi": "fs",
    }
    try:
        return mapping[ext]
    except KeyError as exc:
        raise ValueError(f"Unsupported extension: {ext}") from exc
