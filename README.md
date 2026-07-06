<div align="center">

# ITS-Convert

**Translate automation scripts across 25 languages.**

Parse once. Emit anywhere.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-56%20passing-brightgreen.svg)](tests/)

</div>

---

ITS-Convert is a cross-language script translator built on an Intermediate Representation (IR). Feed it a Python script (or Bash, PowerShell, CMD) and it emits idiomatic code in **25 target languages** -- from JavaScript to Rust, Go to Scala, Lua to Zig.

## How it works

```
  Source Script          IR (26+ node types)          Target Script
 ┌────────────┐       ┌──────────────────┐        ┌──────────────┐
 │  demo.py   │──────▶│  Assign          │───────▶│  demo.go     │
 │  demo.sh   │──────▶│  Print           │───────▶│  demo.rs     │
 │  demo.ps1  │──────▶│  If / For / While│───────▶│  demo.js     │
 │  demo.cmd  │──────▶│  FunctionDef     │───────▶│  demo.rb     │
 └────────────┘       │  TryCatch        │        └──────────────┘
                      │  EnvVar / Argv   │
                      │  FileIO / ListOp │
                      │  DictOp / Assert │
                      │  ...             │
                      └──────────────────┘
```

Every source file is parsed into a language-agnostic IR, then an emitter walks the IR and produces target-language code with idiomatic syntax -- `console.log()` for JS, `println!()` for Rust, `fmt.Println()` for Go, `cat()` for R, etc.

## Supported languages

### Parsers (source languages)

| Language | Extension | Parser |
|----------|-----------|--------|
| Python   | `.py`     | Full AST parser via `ast` module |
| Bash     | `.sh`     | Heuristic line-based parser |
| PowerShell | `.ps1` | Heuristic line-based parser |
| CMD / Batch | `.cmd`, `.bat` | Heuristic line-based parser |

### Emitters (target languages)

| | | | | |
|---|---|---|---|---|
| **Python** | **Bash** | **PowerShell** | **CMD** | **JavaScript** |
| **TypeScript** | **Ruby** | **Perl** | **Lua** | **PHP** |
| **Go** | **Rust** | **Java** | **C** | **C++** |
| **C#** | **Swift** | **Kotlin** | **Dart** | **R** |
| **Scala** | **Nim** | **Zig** | **V** | |

Each emitter handles: variables, print, input, if/elif/else, for/for-range/while, break/continue, functions, return, environment variables, CLI arguments, try/catch, lists, dicts, asserts, and file I/O (where the target language supports it).

## Install

### From npm

```bash
npm install -g itsconvert
node --version    # requires Node.js 18+
python --version  # requires Python 3.11+
python -m pip install pydantic rich typer  # same runtime deps as requirements.txt
itsconvert languages
```

The npm package is a thin launcher around the Python CLI in this repository, so you still need **Python 3.11+** and the Python runtime dependencies installed.

### From PyPI (when published)

```bash
pip install itsconvert
```

### From source

```bash
git clone https://github.com/v1ral-its/ITS-Convert.git
cd ITS-Convert
pip install -e .
```

### Requirements

- Python 3.11+
- Dependencies (auto-installed): `pydantic`, `rich`, `typer`

## Usage

### List available languages

```bash
itsconvert languages
```

### Inspect a script's IR

```bash
itsconvert inspect examples/demo.py
```

### Translate to any target language

```bash
itsconvert translate examples/demo.py --to go
itsconvert translate examples/demo.py --to rust
itsconvert translate examples/demo.py --to js
itsconvert translate examples/demo.py --to ruby -o build/demo.rb
```

### Package as executable

```bash
itsconvert build build/demo.py --builder pyinstaller
itsconvert build build/demo.sh --builder shc
itsconvert build build/demo.ps1 --builder wrapper
```

## Examples

Translate the bundled demo script into every language:

```bash
for lang in py sh ps1 cmd js ts rb pl lua php go rs java c cpp cs swift kt dart r scala nim zig v; do
  itsconvert translate examples/demo.py --to "$lang"
done
```

### Quick output comparison

**Python (source):**
```python
name = "World"
print(f"Hello, {name}!")
```

**Go:**
```go
package main

import "fmt"

func main() {
    name := "World"
    fmt.Println("Hello, " + name + "!")
}
```

**Rust:**
```rust
fn main() {
    let mut name = String::from("World");
    println!("Hello, {}!", name.clone());
}
```

**Ruby:**
```ruby
name = "World"
puts "Hello, #{name}!"
```

**Lua:**
```lua
local name = "World"
print("Hello, " .. tostring(name) .. "!")
```

## Architecture

```
itsconvert/
├── ir.py                  # 26+ IR node types (Pydantic models)
├── cli.py                 # Typer CLI (inspect, translate, languages, build)
├── analyzer.py            # IR summary/stats
├── errors.py              # Custom exceptions
├── utils.py               # File I/O, language inference (30+ extensions)
├── translators/
│   ├── __init__.py        # Registry (get_parser / get_emitter / available_*)
│   ├── py_parser.py       # Full Python AST parser
│   ├── sh_parser.py       # Bash heuristic parser
│   ├── ps1_parser.py      # PowerShell heuristic parser
│   ├── cmd_parser.py      # CMD heuristic parser
│   ├── py_emitter.py      # Python emitter (round-trip)
│   ├── sh_emitter.py      # Bash emitter
│   ├── ps1_emitter.py     # PowerShell emitter
│   ├── cmd_emitter.py     # CMD/batch emitter
│   ├── js_emitter.py      # JavaScript emitter
│   ├── ts_emitter.py      # TypeScript emitter
│   ├── rb_emitter.py      # Ruby emitter
│   ├── pl_emitter.py      # Perl emitter
│   ├── lua_emitter.py     # Lua emitter
│   ├── php_emitter.py     # PHP emitter
│   ├── go_emitter.py      # Go emitter (package main + auto-imports)
│   ├── rs_emitter.py      # Rust emitter (fn main + Vec/HashMap)
│   ├── java_emitter.py    # Java emitter (public class Main)
│   ├── c_emitter.py       # C emitter (#include + printf)
│   ├── cpp_emitter.py     # C++ emitter (iostream + auto)
│   ├── cs_emitter.py      # C# emitter (var + Dictionary)
│   ├── swift_emitter.py   # Swift emitter (import Foundation)
│   ├── kt_emitter.py      # Kotlin emitter (fun main)
│   ├── dart_emitter.py    # Dart emitter (dart:io)
│   ├── r_emitter.py       # R emitter (cat + <-)
│   ├── scala_emitter.py   # Scala emitter (object Main)
│   ├── nim_emitter.py     # Nim emitter (echo + for..in)
│   ├── zig_emitter.py     # Zig emitter (@import + pub fn main)
│   └── v_emitter.py       # V emitter (module main + <<)
├── packagers/
│   └── __init__.py        # PyInstaller, Nuitka, ps2exe, shc, wrapper
examples/
├── demo.py                # Full demo (imports, f-strings, try/catch, env)
├── demo.sh                # Bash demo
└── demo.ps1               # PowerShell demo
tests/
└── test_convert.py        # 56 tests (parsers, emitters, round-trip, utils)
```

## IR node types

| Category | Nodes |
|----------|-------|
| **Control flow** | `If`, `ElifBranch`, `For`, `ForRange`, `ForEnumerate`, `ForKeys`, `While`, `Break`, `Continue`, `Pass` |
| **Functions** | `FunctionDef` (params, defaults, type hints, varargs), `Return` |
| **Error handling** | `TryCatch`, `Raise`, `Assert` |
| **I/O** | `Print`, `Input`, `FileIONode` (read/write/append/exists/delete/mkdir), `Command` |
| **Data structures** | `ListOp` (create/append/pop/sort/join/contains/len), `DictOp` (create/get/set/keys/values/contains) |
| **Variables** | `Assign`, `MultiAssign`, `AugAssign`, `EnvVar`, `Argv` |
| **Strings** | `StringOpNode` (upper/lower/strip/replace/split/join/len/contains/startswith/endswith) |
| **Expressions** | `BinaryOp`, `UnaryOp`, f-strings, `Subscript`, `Attr`, `Call` |
| **Other** | `Comment`, `Import`, `RawBlock`, `Exit` |

## Design principles

- **Safe by default.** When the parser cannot prove a safe translation, it emits a comment or raises an error instead of guessing.
- **IR-first.** Every translation goes through the IR, making it easy to add new languages without touching existing code.
- **Idiomatic output.** Emitters produce language-native syntax (`Write-Host` for PowerShell, `puts` for Ruby, `echo` for Nim) rather than transliterating Python.
- **Extensible.** Add a new language by creating one file (`xxx_emitter.py`) and registering it in `__init__.py`.

## Development

```bash
# Clone and install with dev dependencies
git clone https://github.com/v1ral-its/ITS-Convert.git
cd ITS-Convert
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Add a new emitter
# 1. Create itsconvert/translators/xxx_emitter.py
# 2. Add the language code to the Language type in ir.py
# 3. Register in itsconvert/translators/__init__.py _EMITTERS dict
# 4. Add file extension to utils.py mapping
# 5. Add tests in tests/test_convert.py
```

## Publish to npm

```bash
# 1. Log into npm
npm login

# 2. Review the package contents
npm pack --dry-run

# 3. Publish the package
npm publish
```

If you also publish to PyPI, keep the version in `package.json` and `pyproject.toml` in sync.

## License

[MIT](LICENSE) -- use it however you want.

---

<div align="center">

*If ITS-Convert saved you time, consider giving it a star ⭐*

</div>
