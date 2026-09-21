"""AppImage packager for creating portable Linux applications."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from itsconvert.errors import PackagingError

class AppImagePackager:
    """
    Create AppImage bundles using linuxdeploy or appimagetool.

    Supports two approaches:
    1. linuxdeploy + plugins (recommended, modern)
    2. appimagetool (legacy)

    Requires:
    - For linuxdeploy: linuxdeploy-x86_64.AppImage and plugins in PATH
    - For appimagetool: appimagetool and AppDir structure
    """

    def __init__(self, use_linuxdeploy: bool = True):
        """
        Initialize the AppImage packager.

        Args:
            use_linuxdeploy: If True, use linuxdeploy. If False, use appimagetool.
        """
        self.use_linuxdeploy = use_linuxdeploy

    def build(self, source_file: Path, output_dir: Path) -> Path:
        """
        Build an AppImage from a Python script or executable.

        Args:
            source_file: Path to the source script or compiled binary
            output_dir: Directory to place the resulting AppImage

        Returns:
            Path to the created AppImage file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.use_linuxdeploy:
            return self._build_with_linuxdeploy(source_file, output_dir)
        else:
            return self._build_with_appimagetool(source_file, output_dir)

    def _build_with_linuxdeploy(self, source_file: Path, output_dir: Path) -> Path:
        """Build using linuxdeploy (modern approach)."""
        linuxdeploy_path = shutil.which("linuxdeploy-x86_64.AppImage") or \
                         shutil.which("linuxdeploy")

        if not linuxdeploy_path:
            raise PackagingError(
                "linuxdeploy not found. Please install linuxdeploy-x86_64.AppImage "
                "from https://github.com/linuxdeploy/linuxdeploy/releases"
            )

        appdir = output_dir / "AppDir"
        if appdir.exists():
            shutil.rmtree(appdir)
        appdir.mkdir(parents=True)

        usr_dir = appdir / "usr"
        usr_dir.mkdir(exist_ok=True)
        bin_dir = usr_dir / "bin"
        bin_dir.mkdir(exist_ok=True)

        if source_file.suffix == ".py":
            target_bin = bin_dir / source_file.name
            shutil.copy2(source_file, target_bin)

            aprun = appdir / "AppRun"
            aprun_script = r"""#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
exec python3 "$HERE/usr/bin/$(basename "$SELF")" "$@"
"""
            aprun.write_text(aprun_script)
            aprun.chmod(0o755)

            desktop_file = appdir / f"{source_file.stem}.desktop"
            desktop_content = f"""[Desktop Entry]
Type=Application
Name={source_file.stem}
Exec=AppRun
Icon={source_file.stem}
Terminal=true
Categories=Utility;
"""
            desktop_file.write_text(desktop_content)
        else:
            target_bin = bin_dir / source_file.name
            shutil.copy2(source_file, target_bin)

            aprun = appdir / "AppRun"
            aprun_script = f"""#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${{SELF%/*}}
exec "$HERE/usr/bin/{source_file.name}" "$@"
"""
            aprun.write_text(aprun_script)
            aprun.chmod(0o755)

            desktop_file = appdir / f"{source_file.stem}.desktop"
            desktop_content = f"""[Desktop Entry]
Type=Application
Name={source_file.stem}
Exec=AppRun
Icon={source_file.stem}
Terminal=false
Categories=Utility;
"""
            desktop_file.write_text(desktop_content)

        output_appimage = output_dir / f"{source_file.stem}-x86_64.AppImage"

        cmd = [
            str(linuxdeploy_path),
            "--appdir", str(appdir),
            "--executable", str(aprun),
            "--desktop-file", str(desktop_file),
            "--output", "appimage",
        ]

        if source_file.suffix == ".py":
            cmd.extend(["--plugin", "python"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise PackagingError(
                f"linuxdeploy failed: {result.stderr}\nstdout: {result.stdout}"
            )

        expected_output = output_dir / f"{source_file.stem}-x86_64.AppImage"
        if expected_output.exists():
            return expected_output

        appimages = list(output_dir.glob("*.AppImage"))
        if appimages:
            return appimages[0]

        raise PackagingError(
            f"AppImage not found in {output_dir}. linuxdeploy output: {result.stdout}"
        )

    def _build_with_appimagetool(self, source_file: Path, output_dir: Path) -> Path:
        """Build using appimagetool (legacy approach)."""
        appimagetool_path = shutil.which("appimagetool-x86_64.AppImage") or \
                           shutil.which("appimagetool")

        if not appimagetool_path:
            raise PackagingError(
                "appimagetool not found. Please install from "
                "https://github.com/AppImage/AppImageKit/releases"
            )

        appdir = output_dir / "AppDir"
        if appdir.exists():
            shutil.rmtree(appdir)
        appdir.mkdir(parents=True)

        if source_file.suffix == ".py":
            usr_bin = appdir / "usr" / "bin"
            usr_bin.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, usr_bin / source_file.name)

            aprun = appdir / "AppRun"
            aprun_script = r"""#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
exec python3 "$HERE/usr/bin/$(basename "$SELF")" "$@"
"""
            aprun.write_text(aprun_script)
            aprun.chmod(0o755)
        else:
            usr_bin = appdir / "usr" / "bin"
            usr_bin.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, usr_bin / source_file.name)

            aprun = appdir / "AppRun"
            aprun_script = f"""#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${{SELF%/*}}
exec "$HERE/usr/bin/{source_file.name}" "$@"
"""
            aprun.write_text(aprun_script)
            aprun.chmod(0o755)

        desktop_file = appdir / f"{source_file.stem}.desktop"
        desktop_content = f"""[Desktop Entry]
Type=Application
Name={source_file.stem}
Exec=AppRun
Icon={source_file.stem}
Terminal=false
Categories=Utility;
"""
        desktop_file.write_text(desktop_content)

        output_appimage = output_dir / f"{source_file.stem}-x86_64.AppImage"

        cmd = [
            str(appimagetool_path),
            str(appdir),
            str(output_appimage),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise PackagingError(
                f"appimagetool failed: {result.stderr}\nstdout: {result.stdout}"
            )

        if not output_appimage.exists():
            raise PackagingError(f"AppImage not created at {output_appimage}")

        return output_appimage
