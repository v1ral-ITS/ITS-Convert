from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from itsconvert.errors import PackagingError


class PyInstallerPackager:
    def build(self, source_file: Path, output_dir: Path) -> Path:
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--distpath", str(output_dir), "--workpath", str(output_dir / "work"), "--specpath", str(output_dir), str(source_file.resolve())]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise PackagingError(result.stderr or result.stdout)
        output = output_dir / (source_file.stem + ('.exe' if sys.platform == 'win32' else ''))
        if not output.is_file():
            raise PackagingError(f'pyinstaller did not create {output}')
        return output
