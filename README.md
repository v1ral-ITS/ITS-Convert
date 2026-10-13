<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6366f1,100:a855f7&height=180&section=header&text=ITS-Convert&fontSize=52&fontColor=ffffff&fontAlignY=35&desc=ImPerial%20TeK.%20Solutions%20%7C%20Translate.%20Build.%20Package.&descAlignY=58&descSize=16" width="100%" alt="ITS-Convert — ImPerial TeK. Solutions" />

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-6366f1?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-a855f7?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/v1ral-ITS/ITS-Convert/test.yaml?style=for-the-badge&label=tests&logo=githubactions&logoColor=white)](https://github.com/v1ral-ITS/ITS-Convert/actions/workflows/test.yaml)
[![Source languages](https://img.shields.io/badge/source%20languages-4-3b82f6?style=for-the-badge)](#supported-languages)
[![Target languages](https://img.shields.io/badge/target%20languages-26-f59e0b?style=for-the-badge)](#supported-languages)
[![Packaging adapters](https://img.shields.io/badge/packaging%20adapters-10-22c55e?style=for-the-badge)](#packagers)

**Write automation once. Inspect its structure. Generate another language. Package for your platform.**

Built by **Bear Carrington · ImPerial TeK. Solutions**

[GitHub](https://github.com/v1ral-ITS) · [CodePolisher CLI](https://github.com/v1ral-ITS/codepolisher-cli) · [Issues](https://github.com/v1ral-ITS/ITS-Convert/issues)

<img src="https://i.ibb.co/TqtRRLxW/ITSolutions-LOGO.jpg" alt="ITSolutions company logo" width="180" />

</div>

---

## What ITS-Convert does

ITS-Convert is a Python CLI and library for **structured automation-script translation and packaging**. It parses supported source scripts into a typed, language-neutral intermediate representation (IR), then generates source in a selected target language. A separate build step invokes a packaging tool or creates a launcher.

It includes **4 source parsers, 26 target emitters, 10 registered packaging adapters, IR inspection, and multi-target batch generation**. The translation engine runs locally and does not require an AI model, API key, or hosted service.

```text
 Python ──────┐
 Bash ────────┤       Typed IR          26 target emitters
 PowerShell ──┼──────► inspect ────────► generated source
 CMD / BAT ───┘       analyze                 │
                                             ▼
 Native or generated script ─────────► packaging adapter
                                             │
                          .exe / native binary / .app / AppImage / launcher
```

**Translation coverage varies by construct and target.** The language count describes registered emitters, not complete compatibility with every language or arbitrary application. Native packaging depends on installed tools and the host OS. See [limitations](#translation-boundaries) and the [validation record](#validation).

## Contents

- [Capabilities](#capabilities)
- [Supported languages](#supported-languages)
- [Install](#install)
- [Usage](#usage)
- [Packagers](#packagers)
- [Configuration](#configuration)
- [Translation boundaries](#translation-boundaries)
- [Python API](#python-api)
- [CodePolisher integration](#codepolisher-integration)
- [Architecture](#architecture)
- [Development and CI](#development-and-ci)
- [Validation](#validation)
- [License](#license)

## Capabilities

| Capability | What is implemented |
|---|---|
| Source parsing | Python AST parsing plus Bash, PowerShell, and CMD/BAT parsers |
| Typed IR | Pydantic models for values, statements, control flow, functions, and automation operations |
| Inspection | Human-readable summary and JSON representation through `inspect` |
| Translation | Generate one selected target with `translate` |
| Batch generation | Parse once and emit several targets with repeated `--to` flags |
| Output protection | Keep the source intact; refuse existing output unless `--force` is supplied |
| Strict checking | Reject parser warnings and detected unsupported/raw output markers with `--strict` |
| Builder discovery | List registered adapters with `builders` |
| Executable packaging | Invoke a separately installed packager on native or generated source |
| Launcher packaging | Copy the script and generate a launcher; an interpreter is still required |
| Configurable operation | CLI arguments, environment overrides, and prompts for missing target/builder selections |
| Optional code review | A separate Python wrapper around the company's CodePolisher CLI |

The IR represents assignments, augmented and tuple assignments, printing, input, commands, exit codes, comparisons, conditionals, loops, function definitions and returns, imports, string operations, file operations, environment variables, arguments, exceptions, lists, dictionaries, assertions, and raw blocks. **Representation in the IR does not mean every parser recognizes every operation or every emitter implements it.**

## Supported languages

### Source languages

| Language | ID | Recognized source extensions |
|---|---|---|
| Python | `py` | `.py` |
| Bash | `sh` | `.sh`, `.bash` |
| PowerShell | `ps1` | `.ps1` |
| Windows command scripts | `cmd` | `.cmd`, `.bat` |

### Target languages

| Language | ID | Default extension | Language | ID | Default extension |
|---|---|---|---|---|---|
| Python | `py` | `.py` | Bash | `sh` | `.sh` |
| PowerShell | `ps1` | `.ps1` | CMD | `cmd` | `.cmd` |
| JavaScript | `js` | `.js` | TypeScript | `ts` | `.ts` |
| Ruby | `rb` | `.rb` | Perl | `pl` | `.pl` |
| Lua | `lua` | `.lua` | PHP | `php` | `.php` |
| Go | `go` | `.go` | Rust | `rs` | `.rs` |
| Java | `java` | `.java` | C | `c` | `.c` |
| C++ | `cpp` | `.cpp` | C# | `cs` | `.cs` |
| Swift | `swift` | `.swift` | Kotlin | `kt` | `.kt` |
| Dart | `dart` | `.dart` | R | `r` | `.R` |
| Scala | `scala` | `.scala` | Nim | `nim` | `.nim` |
| Zig | `zig` | `.zig` | V | `v` | `.v` |
| Julia | `jl` | `.jl` | Elixir | `ex` | `.exs` |

Julia and Elixir currently implement a smaller subset than the main emitters. Inspect their generated output for unsupported-node comments. Extensions recognized by the utility layer do not imply that a source parser exists for that language: Go-to-Python, for example, is not currently implemented.

## Install

Requires **Python 3.11+**. Node.js is only needed for the optional npm launcher or JavaScript execution tests.

```bash
git clone https://github.com/v1ral-ITS/ITS-Convert.git
cd ITS-Convert
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux, WSL, or macOS
source .venv/bin/activate
```

```bash
python -m pip install -e .
itsconvert --help
itsconvert languages
itsconvert builders
```

Core dependencies are Pydantic, Rich, and Typer. Packaging engines are optional dependencies installed separately into the same Python environment, for example:

```bash
python -m pip install pyinstaller
```

### Optional npm launcher

The npm package is a Node launcher for the Python implementation; it does not replace Python or install Python dependencies automatically. From this checkout, after installing the Python project:

```bash
npm link
itsconvert --help
```

Set `ITSCONVERT_PYTHON` to the environment's Python executable when using the npm launcher. Do not assume a registry release includes the latest GitHub changes; source installation is the reproducible path for this revision.

## Usage

### Inspect a script

```bash
itsconvert inspect examples/demo.py
```

Displays its IR summary and serialized JSON, including parser warnings.

### Translate one target

```bash
itsconvert translate examples/demo.py --to js --output build/demo.js
itsconvert translate examples/demo.sh --to py --output build/from_bash.py
```

Omit `--to` in an interactive terminal to be prompted, or set `ITSCONVERT_TARGET`. Use the short language IDs from `languages`.

Without `--output`, the target extension determines the destination next to the source. Same-language translation uses a `.converted` name, such as `demo.converted.py`. An explicit output equal to the source is always rejected. Use `--force` to replace another existing destination deliberately.

```bash
itsconvert translate examples/demo.py --to js --output build/demo.js --force
itsconvert translate examples/demo.py --to js --output build/demo.js --strict --force
```

Strict mode catches known warning markers; it does not compile the output or prove behavioral equivalence.

### Generate several targets

```bash
itsconvert batch examples/demo.py --to py --to js --to go --to rs --output-dir build/translated
```

Repeated targets are deduplicated. Unknown targets are rejected before parsing. All selected outputs are rendered and checked for collisions before files are written. Add `--strict` or `--force` as needed.

### Build a Windows executable

Run this on Windows with PyInstaller installed in the active environment:

```powershell
itsconvert build examples/hello.py --builder pyinstaller --output-dir dist
.\dist\hello.exe
```

### Translate, review, then build

```bash
itsconvert translate examples/demo.sh --to py --output build/demo.py
# Review and test build/demo.py before packaging it.
itsconvert build build/demo.py --builder pyinstaller --output-dir dist
```

### Create a launcher bundle

```bash
itsconvert build examples/hello.py --builder wrapper --output-dir dist/hello
```

The directory includes the source script and a launcher. Python launchers use `.cmd` on Windows and `.sh` on Unix; PowerShell uses `.cmd`; Bash uses `.sh`. This is a convenient launch bundle, not a standalone executable or source-code protection mechanism.

### Build an AppImage

On Linux/WSL with the required AppImage tool installed:

```bash
itsconvert build examples/hello.py --builder appimage --use-linuxdeploy --output-dir dist
# Alternative backend:
itsconvert build examples/hello.py --builder appimage --use-appimagetool --output-dir dist
```

The linuxdeploy Python path requires its Python plugin. The appimagetool Python path invokes host `python3`; it does not bundle Python. The adapter currently targets x86_64 and keeps a separate staging directory for each build. The appimagetool backend was built and executed successfully in Ubuntu WSL during this audit. The linuxdeploy/plugin route still needs end-to-end validation.

## Packagers

Ten adapters are registered in one canonical registry. **Registered** means selectable through the CLI, not certified on every supported platform.

| Builder ID | Input | Host / requirements | Output and validation status |
|---|---|---|---|
| `pyinstaller` | Python | Target OS; `pip install pyinstaller` | One-file native executable; Windows build/run smoke tested |
| `nuitka` | Python | Target OS; Nuitka and compatible compiler | One-file native executable; command/output regression checked, full compilation not validated in this audit |
| `wrapper` | Python, Bash, PowerShell | Matching interpreter on the destination | Copied source plus launcher; bundle regression tested |
| `ps2exe` | PowerShell | Windows PowerShell and ps2exe module | `.exe`; target-host validation pending |
| `shc` | Bash | Unix host, shc and compiler | Native shell-script wrapper; target-host validation pending |
| `appimage` | Python or executable | Linux x86_64; linuxdeploy + plugin or appimagetool | `.AppImage`; staging regression tested; appimagetool demo built and run in Ubuntu WSL; linuxdeploy validation pending |
| `cx_freeze` | Python | Target OS; cx_Freeze | Executable directory; target-host validation pending |
| `py2exe` | Python | Windows; py2exe | Console executable directory; target-host validation pending |
| `py2app` | Python | macOS; py2app | `.app` bundle; target-host validation pending |
| `briefcase` | Python | Briefcase and platform dependencies | Native app project/package; experimental, target-host validation pending |

Build on the intended target OS. Installing this tool in WSL does not make Windows `.exe` cross-compilation automatic. Likewise, a wrapper does not bundle third-party dependencies. Native binaries generated from Go/Rust/C/etc. must be compiled with those languages' own toolchains; the CLI does not currently expose Go or Rust compiler builders.

## Configuration

| Setting | Purpose |
|---|---|
| `--to` / `ITSCONVERT_TARGET` | Translation target; prompts if neither is supplied |
| `--builder` / `ITSCONVERT_BUILDER` | Build adapter; prompts if neither is supplied |
| Build `--output-dir` / `ITSCONVERT_OUTPUT_DIR` | Artifact directory; defaults to `dist` |
| Translate `--output` / `-o` | Explicit translated output path |
| Batch `--output-dir` / `-d` | Batch destination; defaults to `build` |
| `--force` | Allow replacing existing translated outputs, never the source |
| `--strict` | Reject detected translation warnings before writing |
| `--use-linuxdeploy` / `--use-appimagetool` | Select AppImage backend |
| `ITSCONVERT_PYTHON` | Python executable used by the npm launcher |
| `ITSCONVERT_WRAPPER_PYTHON` | Interpreter command/path embedded in generated Python launchers |
| `AUDIT_NODE` | Optional Node executable override for JavaScript regression tests |

Explicit flags take precedence over their environment settings. Supply target/builder flags in unattended jobs to avoid prompts. Core translation does not read or require secrets.

## Translation boundaries

The engine is designed around automation constructs. It is not a general-purpose application transpiler, dependency migrator, or compatibility layer for arbitrary Python libraries.

- Python class definitions, framework behavior, async semantics, advanced expressions, and target-specific APIs are not fully translated.
- Membership comparisons (`in`, `not in`) are explicitly rejected rather than silently converted to equality. Multiple exception handlers and `try/else` are also rejected by the current Python parser.
- Exception representation is simplified. Typed exception matching, library imports, argument conventions, file behavior, and data types can differ between languages.
- Unsupported nodes may become comments/raw markers. Parser warnings are shown by the CLI; use `--strict` to reject detected cases. Detection is conservative and does not catch every semantic mismatch.
- Basic control-flow generation does not establish full target-language correctness. Compiled targets need their own compiler checks; generated Java, for example, may require a filename matching its class.
- GUI applications, assets, dynamically loaded modules, and extra data files can require manual packager configuration. The current build command does not expose every backend-specific option.

Inspect generated source and execute representative tests before distributing it. Packaging a native script directly avoids translation changes when another language is unnecessary.

## Python API

```python
from pathlib import Path
from itsconvert.translators import get_parser, get_emitter
from itsconvert.packagers import available_packagers, get_packager

ir = get_parser("py").parse('name = "ITS"\nprint(name)\n')
javascript = get_emitter("js").emit(ir)
print(ir.model_dump_json(indent=2))
print(javascript)
print(available_packagers())

# With a matching packaging engine installed:
# artifact = get_packager("pyinstaller").build(Path("tool.py"), Path("dist"))
```

The canonical registries are `itsconvert.translators` and `itsconvert.packagers`. Older parser/emitter modules remain in the tree for compatibility; their presence does not add CLI language support.

## CodePolisher integration

[CodePolisher CLI](https://github.com/v1ral-ITS/codepolisher-cli) is a separate ImPerial TeK. Solutions project. Configure its provider/model in CodePolisher, then review generated source explicitly:

```bash
codepolisher review build/demo.py --output json
```

`itsconvert.code_review.CodeReviewer` offers a Python subprocess wrapper with batch review and save-as helpers. It requires `codepolisher` on PATH. Review is optional and is not automatically invoked by `translate` or `build`. AI review does not replace execution tests.

## Architecture

```text
itsconvert/
  cli.py             Typer commands and output checks
  ir.py              Typed intermediate representation
  analyzer.py        IR summaries
  utils.py           UTF-8 files and extension inference
  translators/       Source parsers, target emitters, registry
  packagers/         Canonical builder registry and adapters
  code_review.py     Optional CodePolisher subprocess integration
bin/itsconvert.js    npm-to-Python launcher
examples/           Public example scripts
tests/              Unit, CLI, and behavioral regression tests
.github/workflows/  Test and packaging jobs
```

The public `hello.py` example provides a neutral packaging smoke test. A ready-built [demo AppImage, checksum, and provenance](examples/artifacts/README.md) are committed under `examples/artifacts/` and included in the npm tarball and Python distributions. Python wheels install that data under `share/itsconvert/examples/artifacts` in the environment prefix. The demo requires x86_64 Linux and host `python3`; it is never executed during installation.

## Development and CI

```bash
python -m pip install -e ".[dev]"
python -m compileall -q itsconvert
python -m pytest
python -m pytest --cov=itsconvert --cov-report=term-missing
```

Node.js enables the JavaScript execution regressions. Without Node, those tests skip; CI installs Node explicitly. Tests include Python behavioral comparisons, JavaScript execution, CLI output protection, builder discovery, wrapper bundling, Nuitka argument validation, and AppImage entrypoint staging.

The test workflow checks multiple Python versions on Windows and Linux. Packaging workflows exercise selected backends on compatible hosts; a workflow definition alone is not evidence of a successful release. The Dockerfile provides a Debian-based translation runtime; build it with `docker build -t itsconvert .` and run `docker run --rm itsconvert languages`. Docker was not available for local validation and is not a CLI packaging adapter. The Makefile provides configurable developer helpers for Unix/Git Bash; it builds on the current host rather than cross-compiling for all platforms.

## Validation

The October 2026 audit found a malformed CLI file, disconnected packager registries, silent Python logic changes, invalid JavaScript, and broken wrapper/build paths. This revision repairs those confirmed defects and adds behavioral regressions.

The pre-repair full suite failed during collection; 56 tests passed only when the CLI-dependent module was excluded. After repair, the full suite is run with the added regressions. CI badges above report live workflow status rather than a hardcoded passing-test claim.

Local validation: **86 tests passed on Windows (Python 3.13)**; **86 tests passed in WSL (Python 3.14, Node 24)**. The Windows PyInstaller executable and Linux appimagetool AppImage both ran and printed the expected message. macOS packaging, linuxdeploy/plugin bundling, Nuitka compilation, and all 26 target compilers are **not** certified by this audit. The adapter table deliberately distinguishes implementation from end-to-end validation.

## License

MIT — see [LICENSE](LICENSE).

<div align="center">

**ImPerial TeK. Solutions · Tools that keep your workflow under your control.**

[Explore our GitHub](https://github.com/v1ral-ITS) · [CodePolisher CLI](https://github.com/v1ral-ITS/codepolisher-cli)

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6366f1,100:a855f7&height=100&section=footer" width="100%" alt="ImPerial TeK. Solutions footer" />

</div>
