from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class BuildConfig:
    work_dir: Path
    output_dir: Path
    prefer_nuitka: bool = False
