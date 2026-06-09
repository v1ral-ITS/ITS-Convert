from __future__ import annotations

from abc import ABC, abstractmethod
from itsconvert.ir import ScriptIR


class ParserBase(ABC):
    @abstractmethod
    def parse(self, source: str) -> ScriptIR:
        raise NotImplementedError


class EmitterBase(ABC):
    @abstractmethod
    def emit(self, ir: ScriptIR) -> str:
        raise NotImplementedError
