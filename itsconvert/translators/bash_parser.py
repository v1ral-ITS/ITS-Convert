from __future__ import annotations

from itsconvert.ir import Assign, Command, Print, ScriptIR, Value


class BashParser:
    def parse(self, source: str) -> ScriptIR:
        ir = ScriptIR(source_language="sh")
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("echo "):
                ir.nodes.append(Print(value=Value(kind="string", value=line[5:].strip().strip('"').strip("'"))))
                continue
            if "=" in line and not line.startswith("if ") and " " not in line.split("=", 1)[0]:
                name, value = line.split("=", 1)
                ir.nodes.append(Assign(name=name.strip(), value=Value(kind="string", value=value.strip().strip('"').strip("'"))))
                continue
            ir.nodes.append(Command(command=line))
        ir.warnings.append("Bash parser is line-based in v1 and supports simple constructs only")
        return ir
