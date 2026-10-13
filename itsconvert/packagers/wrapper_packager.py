"""Create launchers with their source script; interpreters remain required."""
from pathlib import Path
import os
import shlex
import shutil
import sys
from itsconvert.errors import PackagingError

class WrapperPackager:
    def build(self, source_file: Path, output_dir: Path) -> Path:
        source_file = source_file.resolve(strict=True)
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = source_file.suffix.lower()
        if suffix not in {'.py', '.ps1', '.sh', '.bash'}:
            raise PackagingError(f'Cannot wrap {suffix} files')
        copied = output_dir / source_file.name
        if copied != source_file:
            shutil.copy2(source_file, copied)
        interpreter = os.environ.get('ITSCONVERT_WRAPPER_PYTHON', 'python' if sys.platform == 'win32' else 'python3')
        if suffix == '.ps1' or (suffix == '.py' and sys.platform == 'win32'):
            wrapper = output_dir / f'run_{source_file.stem}.cmd'
            command = f'"{interpreter}"' if suffix == '.py' else 'powershell -NoProfile -File'
            content = f'@echo off\n{command} "%~dp0{source_file.name}" %*\n'
        else:
            wrapper = output_dir / f'run_{source_file.stem}.sh'
            command = shlex.quote(interpreter) if suffix == '.py' else 'bash'
            content = f'#!/usr/bin/env bash\nexec {command} "$(dirname "$0")/{source_file.name}" "$@"\n'
        wrapper.write_text(content, encoding='utf-8', newline='\n')
        wrapper.chmod(0o755)
        return wrapper
