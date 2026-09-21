"""Packager registry — wrap scripts into executables or bundles."""
from __future__ import annotations

from pathlib import Path
from itsconvert.errors import PackagingError
from itsconvert.packagers.appimage_packager import AppImagePackager
from itsconvert.packagers.briefcase_packager import BriefcasePackager
from itsconvert.packagers.cx_freeze_packager import CxFreezePackager
from itsconvert.packagers.py2app_packager import Py2AppPackager
from itsconvert.packagers.py2exe_packager import Py2ExePackager

class Packager:
    """Base class for script packagers."""
    def build(self, source: Path, output_dir: Path) -> Path:
        raise NotImplementedError

class PyInstallerPackager(Packager):
    def build(self, source: Path, output_dir: Path) -> Path:
        import subprocess
        cmd = ["pyinstaller", "--onefile", "--distpath", str(output_dir), str(source)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise PackagingError(f"PyInstaller failed: {result.stderr}")
        return output_dir / source.stem

class NuitkaPackager(Packager):
    def build(self, source: Path, output_dir: Path) -> Path:
        import subprocess
        cmd = ["python", "-m", "nuitka", "--standalone", f"--output-dir={output_dir}", str(source)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise PackagingError(f"Nuitka failed: {result.stderr}")
        return output_dir / f"{source.stem}.dist" / source.stem

class PS2ExePackager(Packager):
    def build(self, source: Path, output_dir: Path) -> Path:
        import subprocess
        cmd = ["ps2exe", str(source), str(output_dir / f"{source.stem}.exe")]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise PackagingError(f"ps2exe failed: {result.stderr}")
        return output_dir / f"{source.stem}.exe"

class WrapperPackager(Packager):
    """Create a simple shell/batch wrapper that invokes the script."""
    def build(self, source: Path, output_dir: Path) -> Path:
        from itsconvert.utils import write_text
        ext = source.suffix
        if ext == ".py":
            wrapper = output_dir / f"run_{source.stem}.cmd"
            write_text(wrapper, f'@echo off\npython "%~dp0\{source.name}" %*\n')
        elif ext == ".sh":
            wrapper = output_dir / source.stem
            write_text(wrapper, f'#!/usr/bin/env bash\nexec bash "$(dirname "$0")/{source.name}" "$@"')
            wrapper.chmod(0o755)
        elif ext == ".ps1":
            wrapper = output_dir / f"run_{source.stem}.cmd"
            write_text(wrapper, f'@echo off\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0\{source.name}" %*\n')
        else:
            raise PackagingError(f"Cannot wrap {ext} files")
        return wrapper

class SHCPackager(Packager):
    def build(self, source: Path, output_dir: Path) -> Path:
        import shutil
        import subprocess
        if shutil.which("shc") is None:
            raise PackagingError("shc is not installed")
        output_file = output_dir / source.stem
        result = subprocess.run(
            ["shc", "-f", str(source), "-o", str(output_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PackagingError(result.stderr or result.stdout)
        return output_file

_BUILDERS = {
    "pyinstaller": PyInstallerPackager,
    "nuitka": NuitkaPackager,
    "ps2exe": PS2ExePackager,
    "wrapper": WrapperPackager,
    "shc": SHCPackager,
    "appimage": AppImagePackager,
    "cx_freeze": CxFreezePackager,
    "briefcase": BriefcasePackager,
    "py2app": Py2AppPackager,
    "py2exe": Py2ExePackager,
}

def get_packager(name: str) -> Packager:
    if name not in _BUILDERS:
        raise PackagingError(f"Unknown builder: {name}. Available: {', '.join(_BUILDERS)}")
    return _BUILDERS[name]()
