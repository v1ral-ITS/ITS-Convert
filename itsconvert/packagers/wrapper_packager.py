from __future__ import annotations

from pathlib import Path

from itsconvert.utils import write_text


class WrapperPackager:
    def build(self, source_file: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = source_file.suffix.lower()
        stem = source_file.stem

        if suffix == ".py":
            output_file = output_dir / f"run_{stem}.cmd"
            content = f'@echo off\npython "%~dp0\\{source_file.name}" %*\n'
        elif suffix == ".ps1":
            output_file = output_dir / f"run_{stem}.cmd"
            content = f'@echo off\npowershell -ExecutionPolicy Bypass -File "%~dp0\\{source_file.name}" %*\n'
        elif suffix in {".sh", ".bash"}:
            output_file = output_dir / f"run_{stem}.sh"
            content = f'#!/usr/bin/env bash\nbash "$(dirname "$0")/{source_file.name}" "$@"\n'
        else:
            output_file = output_dir / f"run_{stem}.txt"
            content = f"Run: {source_file.name}\n"

        write_text(output_file, content)
        return output_file
