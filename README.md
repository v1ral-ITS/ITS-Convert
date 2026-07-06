<div align="center">

# ITS-Convert

**Translate automation scripts across 29 languages.**

Parse once. Emit anywhere.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
[![Languages](https://img.shields.io/badge/languages-29-orange.svg)](itsconvert/translators/)

**Built by [ImPerial TeK. Solutions](https://codepollisher.app)**

</div>

---

ITS-Convert is a cross-language script translator built on an Intermediate Representation (IR). Feed it a Python script (or Bash, PowerShell, CMD) and it emits idiomatic code in **29 target languages** — from JavaScript to Rust, Go to Haskell, Julia to Elixir, Lua to Zig.

> **Questions or support?**
> - 🌐 [codepollisher.app](https://codepollisher.app)
> - 📧 [support@codepollisher.app](mailto:support@codepollisher.app)
> - 📧 [ITSolutions_MGNT@pm.me](mailto:ITSolutions_MGNT@pm.me)

## How it works

```
  Source Script          IR (26+ node types)          Target Script
 ┌────────────┐       ┌──────────────────────┐       ┌──────────────┐
 │  demo.py   │──────▶│  Assign              │──────▶│  demo.go     │
 │  demo.sh   │──────▶│  Print               │──────▶│  demo.rs     │
 │  demo.ps1  │──────▶│  If / For / While    │──────▶│  demo.js     │
 │  demo.cmd  │──────▶│  FunctionDef         │──────▶│  demo.jl     │
 └────────────┘       │  TryCatch            │       │  demo.hs     │
                      │  EnvVar / Argv       │       │  demo.ex     │
                      │  FileIO / ListOp     │       │  demo.fs     │
                      │  DictOp / Assert     │       └──────────────┘
                      │  StringOpNode        │
                      │  ForEnumerate/Keys   │
                      │  ...                 │
                      └──────────────────────┘
```

Every source file is parsed into a language-agnostic IR, then an emitter walks the IR and produces target-language code with idiomatic syntax — `console.log()` for JS, `println!()` for Rust, `fmt.Println()` for Go, `IO.puts` for Elixir, `println` for Julia, `putStrLn` for Haskell, `printfn` for F#.

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
| **Scala** | **Nim** | **Zig** | **V** | **Julia** |
| **Haskell** | **Elixir** | **F#** | | |

Each emitter handles: variables, print, input, if/elif/else, for/for-range/for-enumerate/for-keys/while, break/continue, functions, return, environment variables, CLI arguments, try/catch, lists, dicts, string operations, asserts, and file I/O (where the target language supports it).

## Install

### From PyPI (when published)

```bash
pip install itsconvert
```

### From source

```bash
git clone https://github.com/v1ral-ITS/ITS-Convert.git
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
itsconvert translate examples/demo.py --to julia
itsconvert translate examples/demo.py --to hs
itsconvert translate examples/demo.py --to ex
itsconvert translate examples/demo.py --to fs
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
for lang in py sh ps1 cmd js ts rb pl lua php go rs java c cpp cs swift kt dart r scala nim zig v jl hs ex fs; do
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
    fmt.Println(fmt.Sprintf("Hello, %v!", name))
}
```

**Rust:**
```rust
fn main() {
    let mut name: String = String::from("World");
    println!(format!("Hello, {}!", name.clone()));
}
```

**Julia:**
```julia
name = "World"
println("Hello, $(name)!")
```

**Haskell:**
```haskell
module Main where

main :: IO ()
main = do
  let name = "World"
  putStrLn ("Hello, " ++ show (name) ++ "!")
```

**Elixir:**
```elixir
defmodule Main do
  def main(_args) do
    name = "World"
    IO.puts("Hello, #{to_string(name)}!")
  end
end

Main.main(System.argv())
```

**F#:**
```fsharp
open System
open System.IO

[<EntryPoint>]
let main argv =
    let name = "World"
    printfn "%A" $"Hello, {name}!"
    0
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
├── utils.py               # File I/O, language inference (34+ extensions)
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
│   ├── js_emitter.py      # JavaScript emitter (template literals)
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
│   ├── v_emitter.py       # V emitter (module main + <<)
│   ├── julia_emitter.py   # Julia emitter (function + println)
│   ├── haskell_emitter.py # Haskell emitter (module Main + IO ())
│   ├── elixir_emitter.py  # Elixir emitter (defmodule + IO.puts)
│   └── fsharp_emitter.py  # F# emitter ([<EntryPoint>] + printfn)
├── packagers/
│   └── __init__.py        # PyInstaller, Nuitka, ps2exe, shc, wrapper
examples/
├── demo.py                # Full demo (imports, f-strings, try/catch, env)
├── demo.sh                # Bash demo
└── demo.ps1               # PowerShell demo
tests/
├── test_convert.py        # Parser, emitter, round-trip, utility tests
├── test_ir.py             # IR model tests
└── test_translate.py      # Translation integration tests
```

## IR node types

| Category | Nodes |
|----------|-------|
| **Control flow** | `If`, `ElifBranch`, `For`, `ForRange`, `ForEnumerate`, `ForKeys`, `While`, `Break`, `Continue`, `Pass` |
| **Functions** | `FunctionDef` (params, defaults, type hints, varargs), `Return` |
| **Error handling** | `TryCatch`, `Raise`, `Assert` |
| **I/O** | `Print`, `Input`, `FileIONode` (read/write/append/exists/delete/mkdir/listdir/copy/move), `Command` |
| **Data structures** | `ListOp` (create/append/pop/sort/join/contains/len/extend/insert/remove/index/reverse/slice), `DictOp` (create/get/set/keys/values/contains/len/update/pop) |
| **Variables** | `Assign`, `MultiAssign`, `AugAssign`, `EnvVar`, `Argv` |
| **Strings** | `StringOpNode` (upper/lower/strip/replace/split/join/len/contains/startswith/endswith) |
| **Expressions** | `BinaryOp`, `UnaryOp`, f-strings / interpolated strings, `Subscript`, `Attr`, `Call` |
| **Other** | `Comment`, `Import`, `RawBlock`, `Exit` |

## Design principles

- **Safe by default.** When the parser cannot prove a safe translation, it emits a comment or raises an error instead of guessing.
- **IR-first.** Every translation goes through the IR, making it easy to add new languages without touching existing code.
- **Idiomatic output.** Emitters produce language-native syntax (`Write-Host` for PowerShell, `puts` for Ruby, `echo` for Nim, `IO.puts` for Elixir, `printfn` for F#) rather than transliterating Python.
- **Extensible.** Add a new language by creating one file (`xxx_emitter.py`) and registering it in `__init__.py`.

## Development

```bash
# Clone and install with dev dependencies
git clone https://github.com/v1ral-ITS/ITS-Convert.git
cd ITS-Convert
pip install -e ".[dev]"

# Run tests
PYTHONPATH=. python -m pytest -q

# Add a new emitter
# 1. Create itsconvert/translators/xxx_emitter.py
# 2. Add the language code to the Language type in ir.py
# 3. Register in itsconvert/translators/__init__.py _EMITTERS dict
# 4. Add file extension to utils.py mapping
# 5. Add suffix to cli.py _SUFFIX_MAP
# 6. Add tests in tests/test_convert.py
```

## License

[MIT](LICENSE) — use it however you want.

---

<div align="center">

Developed and maintained by **[ImPerial TeK. Solutions](https://codepollisher.app)**

🌐 [codepollisher.app](https://codepollisher.app) &nbsp;|&nbsp; 📧 [support@codepollisher.app](mailto:support@codepollisher.app) &nbsp;|&nbsp; 📧 [ITSolutions_MGNT@pm.me](mailto:ITSolutions_MGNT@pm.me)

*If ITS-Convert saved you time, consider giving it a star ⭐*

</div>
