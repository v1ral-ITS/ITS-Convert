"""cx_Freeze packager for creating standalone executables."""
from __future__ import annotations

import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError

class CxFreezePackager:
    """
    Create standalone executables using cx_Freeze.

    cx_Freeze is a set of utilities for building executables for Python scripts.
    It supports Windows, Linux, and macOS.

    Requires:
    - cx_Freeze installed: pip install cx_Freeze
    """

    def build(self, source_file: Path, output_dir: Path) -> Path:
        """
        Build a standalone executable using cx_Freeze.

        Args:
            source_file: Path to the Python source script
            output_dir: Directory to place the resulting executable

        Returns:
            Path to the created executable
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import cx_Freeze
        except ImportError:
            raise PackagingError(
                "cx_Freeze not found. Please install with: pip install cx_Freeze"
            )

        setup_script = f"""from cx_Freeze import setup, Executable

build_exe_options = {{
    "packages": ["os"],
    "excludes": ["tkinter"],
}}

setup(
    name="{source_file.stem}",
    version="1.0",
    description="Packaged with ITS-Convert",
    options={{"build_exe": build_exe_options}},
    executables=[Executable(str(source_file.resolve()))]
)
"""

        setup_file = output_dir / "setup.py"
        setup_file.write_text(setup_script)

        cmd = [
            "python",
            str(setup_file),
            "build",
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
                f"cx_Freeze build failed: {result.stderr}\nstdout: {result.stdout}"
            )

        build_dir = output_dir / "build"
        if not build_dir.exists():
            raise PackagingError(f"Build directory not found: {build_dir}")

        exe_name = source_file.stem

        possible_paths = [
            build_dir / exe_name,
            build_dir / f"{exe_name}.exe",
        ]

        for subdir in build_dir.iterdir():
            if subdir.is_dir():
                possible_paths.append(subdir / exe_name)
                possible_paths.append(subdir / f"{exe_name}.exe")

        for path in possible_paths:
            if path.exists():
                return path

        raise PackagingError(
            f"Executable not found in {build_dir}. cx_Freeze output: {result.stdout}"
        )
