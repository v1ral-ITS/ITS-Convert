from __future__ import annotations

import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError


class Ps2ExePackager:
    def build(self, source_file: Path, output_dir: Path) -> Path:
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        source_file = source_file.resolve(strict=True)
        output_file = output_dir / f"{source_file.stem}.exe"
        source_quoted = str(source_file).replace("'", "''")
        output_quoted = str(output_file).replace("'", "''")
        ps_command = (
            "$ErrorActionPreference = 'Stop'; Import-Module ps2exe; "
            f"Invoke-PS2EXE -InputFile '{source_quoted}' -OutputFile '{output_quoted}'"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PackagingError(result.stderr or result.stdout)
        if not output_file.is_file():
            raise PackagingError(f'PS2EXE did not create {output_file}')
        return output_file
