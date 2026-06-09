from __future__ import annotations

import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError


class NuitkaPackager:
    def build(self, source_file: Path, output_dir: Path) -> Path:
        cmd = ["python", "-m", "nuitka", "--onefile", f"--output-dir={output_dir}", str(source_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise PackagingError(result.stderr or result.stdout)
        return output_dir / source_file.stem
