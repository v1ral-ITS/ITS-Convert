from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class PackagerBase(ABC):
    @abstractmethod
    def build(self, source_file: Path, output_dir: Path) -> Path:
        raise NotImplementedError
