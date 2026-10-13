"""cx_freeze adapter. Build on the target OS with its tool installed."""
import importlib.util
import subprocess
import sys
from pathlib import Path
from itsconvert.errors import PackagingError

class CxFreezePackager:
    def build(self, source_file: Path, output_dir: Path) -> Path:
        required_platform = None
        if required_platform and sys.platform != required_platform:
            raise PackagingError('cx_freeze requires ' + required_platform)
        if importlib.util.find_spec('cx_Freeze') is None:
            raise PackagingError('Install cx_Freeze into the current Python environment')
        source_file = source_file.resolve(strict=True)
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        setup_file = output_dir / 'itsconvert_setup.py'
        if 'cx_freeze' == 'cx_freeze':
            script = "from cx_Freeze import setup, Executable\nsetup(name=" + repr(source_file.stem) + ", version='1.0', executables=[Executable(" + repr(str(source_file)) + ")])\n"
            args = ['build_exe', '--build-exe', str(output_dir / 'dist')]
        elif 'cx_freeze' == 'py2exe':
            script = "from setuptools import setup\nimport py2exe\nsetup(console=[" + repr(str(source_file)) + "], options={'py2exe': {'dist_dir': " + repr(str(output_dir / 'dist')) + "}})\n"
            args = ['py2exe']
        else:
            script = "from setuptools import setup\nsetup(app=[" + repr(str(source_file)) + "], setup_requires=['py2app'])\n"
            args = ['py2app', '--dist-dir', str(output_dir / 'dist')]
        setup_file.write_text(script, encoding='utf-8')
        result = subprocess.run([sys.executable, str(setup_file), *args], cwd=output_dir, capture_output=True, text=True, check=False)
        if result.returncode:
            raise PackagingError(result.stderr or result.stdout)
        dist = output_dir / 'dist'
        pattern = '*.app' if 'exe' == 'app' else source_file.stem + ('.exe' if sys.platform == 'win32' else '')
        candidates = list(dist.glob(pattern))
        if not candidates:
            raise PackagingError(f'No cx_freeze artifact found in {dist}')
        return candidates[0]
