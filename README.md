<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6366f1,100:a855f7&height=160&section=header&text=ITS-Convert&fontSize=52&fontColor=ffffff&fontAlignY=38&desc=Translate%20automation%20scripts%20across%2025%20languages&descAlignY=58&descSize=16" width="100%" />

<br/>

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-6366f1?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-a855f7?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-56%20passing-22c55e?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![Languages](https://img.shields.io/badge/target%20languages-25-f59e0b?style=for-the-badge)](#supported-languages)
[![PyPI](https://img.shields.io/badge/PyPI-itsconvert-3b82f6?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/itsconvert/)

<br/>

> **Parse once. Emit anywhere.**
> Feed it a Python, Bash, PowerShell, or CMD script — get back idiomatic code in any of 25 languages.

<br/>

</div>

---

## Table of Contents

- [How it works](#how-it-works)
- [Supported Languages](#supported-languages)
- [Install](#install)
- [Usage](#usage)
- [Examples](#examples)
- [Architecture](#architecture)
- [IR Node Types](#ir-node-types)
- [Development](#development)

---

## How it works

Every source file is parsed into a **language-agnostic IR**, then an emitter walks the IR and produces idiomatic target-language syntax.

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

`console.log()` for JS, `println!()` for Rust, `fmt.Println()` for Go, `cat()` for R — each emitter produces **language-native** output, not transliterated Python.

---

## Supported Languages

### 📥 Parsers (source)

| Language | Extension | Parser |
|----------|-----------|--------|
| Python | `.py` | Full AST parser via `ast` module |
| Bash | `.sh` | Heuristic line-based parser |
| PowerShell | `.ps1` | Heuristic line-based parser |
| CMD / Batch | `.cmd`, `.bat` | Heuristic line-based parser |

### 📤 Emitters (targets)

<table>
  <tr>
    <td align="center">🐍<br/><b>Python</b></td>
    <td align="center">🐚<br/><b>Bash</b></td>
    <td align="center">🪟<br/><b>PowerShell</b></td>
    <td align="center">⬛<br/><b>CMD</b></td>
    <td align="center">🟨<br/><b>JavaScript</b></td>
  </tr>
  <tr>
    <td align="center">🔷<br/><b>TypeScript</b></td>
    <td align="center">💎<br/><b>Ruby</b></td>
    <td align="center">🐪<br/><b>Perl</b></td>
    <td align="center">🌙<br/><b>Lua</b></td>
    <td align="center">🐘<br/><b>PHP</b></td>
  </tr>
  <tr>
    <td align="center">🐹<br/><b>Go</b></td>
    <td align="center">🦀<br/><b>Rust</b></td>
    <td align="center">☕<br/><b>Java</b></td>
    <td align="center">⚙️<br/><b>C</b></td>
    <td align="center">⚙️<br/><b>C++</b></td>
  </tr>
  <tr>
    <td align="center">🔷<br/><b>C#</b></td>
    <td align="center">🍎<br/><b>Swift</b></td>
    <td align="center">🎯<br/><b>Kotlin</b></td>
    <td align="center">🎯<br/><b>Dart</b></td>
    <td align="center">📊<br/><b>R</b></td>
  </tr>
  <tr>
    <td align="center">♠️<br/><b>Scala</b></td>
    <td align="center">👑<br/><b>Nim</b></td>
    <td align="center">⚡<br/><b>Zig</b></td>
    <td align="center">✅<br/><b>V</b></td>
    <td></td>
  </tr>
</table>

Each emitter handles: variables, print, input, if/elif/else, for/for-range/while, break/continue, functions, return, environment variables, CLI arguments, try/catch, lists, dicts, asserts, and file I/O.

---

## Install

### From PyPI

```bash
pip install itsconvert
```

### From source

```bash
git clone https://github.com/v1ral-its/ITS-Convert.git
cd ITS-Convert
pip install -e .
```

> **Requires:** Python 3.11+ · Dependencies auto-installed: `pydantic`, `rich`, `typer`

---

## Usage

```bash
# List all supported target languages
itsconvert languages

# Inspect the IR of any script
itsconvert inspect examples/demo.py

# Translate to any target language
itsconvert translate examples/demo.py --to go
itsconvert translate examples/demo.py --to rust
itsconvert translate examples/demo.py --to js
itsconvert translate examples/demo.py --to ruby -o build/demo.rb

# Package as executable
itsconvert build build/demo.py --builder pyinstaller
itsconvert build build/demo.sh --builder shc
itsconvert build build/demo.ps1 --builder wrapper
```

---

## Examples

Translate into every language at once:

```bash
for lang in py sh ps1 cmd js ts rb pl lua php go rs java c cpp cs swift kt dart r scala nim zig v; do
  itsconvert translate examples/demo.py --to "$lang"
done
```

### Output comparison

<table>
<tr><th>Python (source)</th><th>Go</th><th>Rust</th></tr>
<tr>
<td>

```python
name = "World"
print(f"Hello, {name}!")
```

</td>
<td>

```go
package main

import "fmt"

func main() {
    name := "World"
    fmt.Println("Hello, " + name + "!")
}
```

</td>
<td>

```rust
fn main() {
    let mut name = String::from("World");
    println!("Hello, {}!", name.clone());
}
```

</td>
</tr>
</table>

<details>
<summary>See Ruby, Lua, and TypeScript output</summary>

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

**TypeScript:**
```typescript
let name: string = "World";
console.log(`Hello, ${name}!`);
```

</details>

---

## Architecture

<details>
<summary>View full project structure</summary>

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
│   └── [lang]_emitter.py  # One emitter per target language (25 total)
├── packagers/
│   └── __init__.py        # PyInstaller, Nuitka, ps2exe, shc, wrapper
examples/
├── demo.py
├── demo.sh
└── demo.ps1
tests/
└── test_convert.py        # 56 tests
```

</details>

---

## IR Node Types

| Category | Nodes |
|----------|-------|
| **Control flow** | `If`, `ElifBranch`, `For`, `ForRange`, `ForEnumerate`, `ForKeys`, `While`, `Break`, `Continue`, `Pass` |
| **Functions** | `FunctionDef` (params, defaults, type hints, varargs), `Return` |
| **Error handling** | `TryCatch`, `Raise`, `Assert` |
| **I/O** | `Print`, `Input`, `FileIONode`, `Command` |
| **Data structures** | `ListOp`, `DictOp` |
| **Variables** | `Assign`, `MultiAssign`, `AugAssign`, `EnvVar`, `Argv` |
| **Strings** | `StringOpNode` (upper/lower/strip/replace/split/join/len/contains…) |
| **Expressions** | `BinaryOp`, `UnaryOp`, f-strings, `Subscript`, `Attr`, `Call` |
| **Other** | `Comment`, `Import`, `RawBlock`, `Exit` |

---

## Design Principles

- 🛡️ **Safe by default** — emits a comment or raises an error rather than guessing on unsafe translations
- 🔀 **IR-first** — all translations go through the IR; adding a new language never touches existing code
- ✨ **Idiomatic output** — `Write-Host` for PowerShell, `puts` for Ruby, `echo` for Nim
- 🔌 **Extensible** — one file per language: create `xxx_emitter.py`, register it, done

---

## Development

```bash
# Install with dev dependencies
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

---

## License

[MIT](LICENSE) — use it however you want.

---

<div align="center">

<br/>

<img src="https://i.ibb.co/gFJwwVL4/ITSolutions-LOGO.jpg" alt="ImPerial TeK. Solutions" width="120" />

<br/>

**Bear Carrington**

*Founder | ImPerial TeK. Solutions (ITSolutions)*

📧 [ITSolutions_MGNT@proton.me](mailto:ITSolutions_MGNT@proton.me) &nbsp;·&nbsp; 🌐 [codepolisher.app](https://codepolisher.app)

<br/>

*Innovating technology with precision and integrity.*

© ImPerial TeK. Solutions — All Rights Reserved

<br/>

*If ITS-Convert saved you time, consider giving it a star ⭐*

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:a855f7,100:6366f1&height=80&section=footer" width="100%" />

</div>
