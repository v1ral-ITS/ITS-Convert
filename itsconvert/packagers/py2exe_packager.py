"""py2exe packager for creating Windows executables."""
from __future__ import annotations

import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError

class Py2ExePackager:
    """
    Create Windows executables using py2exe.

    py2exe is a Python Distutils extension that converts Python scripts into
    standalone Windows executables.

    Requires:
    - py2exe installed: pip install py2exe
    - Windows platform
    """

    def build(self, source_file: Path, output_dir: Path) -> Path:
        """
        Build a Windows executable using py2exe.

        Args:
            source_file: Path to the Python source script
            output_dir: Directory to place the resulting executable

        Returns:
            Path to the created .exe file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import py2exe
        except ImportError:
            raise PackagingError(
                "py2exe not found. Please install with: pip install py2exe"
            )

        setup_script = f"""from distutils.core import setup
import py2exe

setup(
    name="{source_file.stem}",
    version="1.0",
    description="Packaged with ITS-Convert",
    author="ImPerial TeK. Solutions",
    windows=[{{
        "script": "{source_file.name}",
        "icon_resources": [(0, "icon.ico")],
    }}],
    options={{
        "py2exe": {{
            "bundle_files": 1,
            "compressed": 1,
            "optimize": 2,
            "excludes": ["_tkinter", "tkinter"],
        }}
    }},
    zipfile=None,
)
"""

        setup_file = output_dir / "setup.py"
        setup_file.write_text(setup_script)

        import shutil
        shutil.copy2(source_file, output_dir / source_file.name)

        cmd = [
            "python",
            str(setup_file),
            "py2exe",
            "-d", str(output_dir / "dist"),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=output_dir,
        )

        if result.returncode != 0:
            raise PackagingError(
                f"py2exe build failed: {result.stderr}\nstdout: {result.stdout}"
            )

        dist_dir = output_dir / "dist"
        exe_files = list(dist_dir.glob("*.exe"))

        if exe_files:
            return exe_files[0]

        raise PackagingError(f"Windows .exe not found in {dist_dir}")
