"""Canonical registry for packaging adapters."""
from itsconvert.errors import PackagingError
from .pyinstaller_packager import PyInstallerPackager
from .nuitka_packager import NuitkaPackager
from .ps2exe_packager import Ps2ExePackager
from .shc_packager import ShcPackager
from .wrapper_packager import WrapperPackager
from .appimage_packager import AppImagePackager
from .cx_freeze_packager import CxFreezePackager
from .briefcase_packager import BriefcasePackager
from .py2app_packager import Py2AppPackager
from .py2exe_packager import Py2ExePackager

_BUILDERS = {
    'pyinstaller': PyInstallerPackager, 'nuitka': NuitkaPackager,
    'ps2exe': Ps2ExePackager, 'shc': ShcPackager, 'wrapper': WrapperPackager,
    'appimage': AppImagePackager, 'cx_freeze': CxFreezePackager,
    'briefcase': BriefcasePackager, 'py2app': Py2AppPackager, 'py2exe': Py2ExePackager,
}

def available_packagers() -> list[str]:
    return sorted(_BUILDERS)

def get_packager(name: str):
    try:
        return _BUILDERS[name]()
    except KeyError as exc:
        raise PackagingError(f"Unknown builder: {name}. Available: {', '.join(available_packagers())}") from exc
