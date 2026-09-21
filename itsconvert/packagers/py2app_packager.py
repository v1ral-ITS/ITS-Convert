"""py2app packager for creating macOS applications."""
from __future__ import annotations

import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError

class Py2AppPackager:
    """
    Create macOS applications using py2app.

    py2app is a Python setuptools command to create standalone Mac OS X applications.

    Requires:
    - py2app installed: pip install py2app
    - macOS platform
    """

    def build(self, source_file: Path, output_dir: Path) -> Path:
        """
        Build a macOS application using py2app.

        Args:
            source_file: Path to the Python source script
            output_dir: Directory to place the resulting application

        Returns:
            Path to the created .app bundle
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import py2app
        except ImportError:
            raise PackagingError(
                "py2app not found. Please install with: pip install py2app"
            )

        setup_script = f"""from setuptools import setup

APP = ["{source_file.name}"]

OPTIONS = {{
    "argv_emulation": True,
    "iconfile": None,
    "plist": {{
        "CFBundleName": "{source_file.stem}",
        "CFBundleDisplayName": "{source_file.stem}",
        "CFBundleIdentifier": "com.example.{source_file.stem}",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSHumanReadableCopyright": "Copyright 2024 ImPerial TeK. Solutions",
    }},
}}

setup(
    app=APP,
    name="{source_file.stem}",
    version="1.0",
    description="Packaged with ITS-Convert",
    options={{"py2app": OPTIONS}},
    setup_requires=["py2app"],
)
"""

        setup_file = output_dir / "setup.py"
        setup_file.write_text(setup_script)

        import shutil
        shutil.copy2(source_file, output_dir / source_file.name)

        cmd = [
            "python",
            str(setup_file),
            "py2app",
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
                f"py2app build failed: {result.stderr}\nstdout: {result.stdout}"
            )

        dist_dir = output_dir / "dist"
        app_bundles = list(dist_dir.glob("*.app"))

        if app_bundles:
            return app_bundles[0]

        raise PackagingError(f"macOS .app bundle not found in {dist_dir}")
