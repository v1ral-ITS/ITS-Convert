from __future__ import annotations

from itsconvert.ir import Assign, Command, Print, ScriptIR, Value


class PowerShellParser:
    def parse(self, source: str) -> ScriptIR:
        ir = ScriptIR(source_language="ps1")
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("write-host "):
                ir.nodes.append(Print(value=Value(kind="string", value=line[11:].strip().strip('"').strip("'"))))
                continue
            if line.startswith("$") and "=" in line:
                name, value = line.split("=", 1)
                ir.nodes.append(Assign(name=name.strip().lstrip("$"), value=Value(kind="string", value=value.strip().strip('"').strip("'"))))
                continue
            ir.nodes.append(Command(command=line))
        ir.warnings.append("PowerShell parser is line-based in v1 and supports simple constructs only")
        return ir
