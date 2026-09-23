<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6366f1,100:a855f7&height=160&section=header&text=ITS-Convert&fontSize=52&fontColor=ffffff&fontAlignY=38&desc=Translate%2C%20Build%2C%20%26%20Package%20Scripts%20Across%2027%2B%20Languages&descAlignY=58&descSize=16" width="100%" />

<br/>

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-6366f1?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-a855f7?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-62%20passing-22c55e?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![Languages](https://img.shields.io/badge/target%20languages-27-f59e0b?style=for-the-badge)](#supported-languages)
[![PyPI](https://img.shields.io/badge/PyPI-itsconvert-3b82f6?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/itsconvert/)
[![Build Status](https://img.shields.io/badge/build%20system-10%20packagers-22c55e?style=for-the-badge)](#packagers)

<br/>

> **Translate. Build. Package. Deploy.**
> The ultimate cross-platform script toolchain: Translate between 27+ languages, then build to .exe, .app, AppImage, or standalone binaries with 10 different packagers.

<br/>

</div>
 <img src="https://i.ibb.co/TqtRRLxW/ITSolutions-LOGO.jpg" alt="ITSolutions-LOGO" border="0"> 
---

## Table of Contents

- [How it works](#how-it-works)
- [Full Capabilities](#full-capabilities)
- [Supported Languages](#supported-languages)
- [Supported Packagers](#packagers)
- [Install](#install)
- [Usage](#usage)
  - [Translation Commands](#translation-commands)
  - [Build Commands](#build-commands)
  - [Full Pipeline Examples](#full-pipeline-examples)
- [Architecture](#architecture)
- [Makefile Targets](#makefile-targets)
- [Docker Support](#docker-support)
- [GitHub Actions](#github-actions)
- [AI Code Review Integration](#ai-code-review-integration)
- [Development](#development)
- [License](#license)

---

## How it works

ITS-Convert is a **complete toolchain** with three superpowers:

```text
┌─────────────────────┐
│      TRANSLATE      │
├─────────────────────┤
│ Python → Go         │
│ Python → Rust       │
│ Bash   → Python     │
│ ...30+ combinations │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│       BUILD         │
├─────────────────────┤
│ PyInstaller         │
│ Nuitka              │
│ cx_Freeze           │
│ Briefcase           │
│ py2exe              │
│ py2app              │
│ shc                 │
│ wrapper             │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      PACKAGE        │
├─────────────────────┤
│ Windows .exe        │
│ Linux AppImage      │
│ macOS .app          │
│ Standalone Binary   │
│ Docker Image        │
└─────────────────────┘
```
