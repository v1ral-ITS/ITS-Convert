"""Briefcase packager for creating native applications."""
from __future__ import annotations

import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError

class BriefcasePackager:
    """
    Create native applications using Briefcase.

    Briefcase is a tool for packaging Python projects as native applications.
    It supports Windows, macOS, Linux, iOS, and Android.

    Requires:
    - Briefcase installed: pip install briefcase
    - Platform-specific dependencies
    """

    def build(self, source_file: Path, output_dir: Path) -> Path:
        """
        Build a native application using Briefcase.

        Args:
            source_file: Path to the Python source script
            output_dir: Directory to place the resulting application

        Returns:
            Path to the created application bundle/directory
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import briefcase
        except ImportError:
            raise PackagingError(
                "Briefcase not found. Please install with: pip install briefcase"
            )

        project_dir = output_dir / f"{source_file.stem}_app"
        project_dir.mkdir(parents=True, exist_ok=True)

        pyproject_content = f"""[tool.briefcase]
project_name = "{source_file.stem}"
version = "1.0.0"
bundle = "com.example.{source_file.stem}"
url = "https://example.com"
license = "MIT"
author = "ITS-Convert"
author_email = "its@example.com"

[tool.briefcase.app.{source_file.stem}]
sources = ["src/{source_file.stem}"]
requires = []

[tool.briefcase.app.{source_file.stem}.macOS]
requires = ["pyobjc-framework-cocoa"]

[tool.briefcase.app.{source_file.stem}.linux]
requires = []

[tool.briefcase.app.{source_file.stem}.windows]
requires = []
"""

        (project_dir / "pyproject.toml").write_text(pyproject_content)

        src_dir = project_dir / "src"
        src_dir.mkdir(exist_ok=True)
        import shutil
        shutil.copy2(source_file, src_dir / source_file.name)

        cmd_create = [
            "briefcase",
            "create",
            f"{source_file.stem}",
            "-p", str(project_dir),
        ]

        result = subprocess.run(
            cmd_create,
            capture_output=True,
            text=True,
            check=False,
            cwd=project_dir,
        )

        if result.returncode != 0:
            cmd_create_simple = [
                "briefcase",
                "create",
            ]
            result = subprocess.run(
                cmd_create_simple,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise PackagingError(
                    f"Briefcase create failed: {result.stderr}\nstdout: {result.stdout}"
                )

        cmd_build = [
            "briefcase",
            "build",
            f"{source_file.stem}",
        ]

        result = subprocess.run(
            cmd_build,
            capture_output=True,
            text=True,
            check=False,
            cwd=project_dir,
        )

        if result.returncode != 0:
            raise PackagingError(
                f"Briefcase build failed: {result.stderr}\nstdout: {result.stdout}"
            )

        dist_dir = project_dir / "dist"
        if dist_dir.exists():
            return dist_dir

        for platform_dir in ["macOS", "MacOS", "macos", "windows", "linux", "Linux"]:
            platform_path = project_dir / platform_dir
            if platform_path.exists():
                return platform_path

        raise PackagingError(
            f"Briefcase output not found in {project_dir}"
        )
