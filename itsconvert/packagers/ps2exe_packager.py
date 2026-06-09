from __future__ import annotations

import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError


class Ps2ExePackager:
    def build(self, source_file: Path, output_dir: Path) -> Path:
        output_file = output_dir / f"{source_file.stem}.exe"
        ps_command = (
            "Import-Module ps2exe; "
            f"Invoke-PS2EXE -InputFile '{source_file}' -OutputFile '{output_file}'"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PackagingError(result.stderr or result.stdout)
        return output_file
