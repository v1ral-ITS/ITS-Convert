"""Packager registry — wrap scripts into executables or bundles."""
from __future__ import annotations

from pathlib import Path
from itsconvert.errors import PackagingError


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
        cmd = ["python", "-m", "nuitka", "--standalone", "--output-dir={output_dir}", str(source)]
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
        ext = source.suffix
        if ext == ".py":
            wrapper = output_dir / f"{source.stem}.cmd"
            wrapper.write_text(f'@echo off\npython "%~dp0{source.name}" %*\n', encoding="utf-8")
        elif ext == ".sh":
            wrapper = output_dir / source.stem
            wrapper.write_text(f'#!/usr/bin/env bash\nexec python3 "$(dirname "$0")/{source.name}" "$@"\n', encoding="utf-8")
            wrapper.chmod(0o755)
        elif ext == ".ps1":
            wrapper = output_dir / f"{source.stem}.cmd"
            wrapper.write_text(f'@echo off\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0{source.name}" %*\n', encoding="utf-8")
        else:
            raise PackagingError(f"Cannot wrap {ext} files")
        return wrapper


class SHCPackager(Packager):
    def build(self, source: Path, output_dir: Path) -> Path:
        import subprocess
        cmd = ["shc", "-f", str(source), "-o", str(output_dir / source.stem)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise PackagingError(f"shc failed: {result.stderr}")
        return output_dir / source.stem


_BUILDERS = {
    "pyinstaller": PyInstallerPackager,
    "nuitka": NuitkaPackager,
    "ps2exe": PS2ExePackager,
    "wrapper": WrapperPackager,
    "shc": SHCPackager,
}


def get_packager(name: str) -> Packager:
    if name not in _BUILDERS:
        raise PackagingError(f"Unknown builder: {name}. Available: {', '.join(_BUILDERS)}")
    return _BUILDERS[name]()
