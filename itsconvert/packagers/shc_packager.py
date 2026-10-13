from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError


class ShcPackager:
    def build(self, source_file: Path, output_dir: Path) -> Path:
        if shutil.which("shc") is None:
            raise PackagingError("shc is not installed")
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        source_file = source_file.resolve(strict=True)
        output_file = output_dir / source_file.stem
        result = subprocess.run(
            ["shc", "-f", str(source_file), "-o", str(output_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PackagingError(result.stderr or result.stdout)
        if not output_file.is_file():
            raise PackagingError(f'shc did not create {output_file}')
        return output_file
