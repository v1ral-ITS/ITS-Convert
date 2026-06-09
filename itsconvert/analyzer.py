from __future__ import annotations

from itsconvert.ir import ScriptIR


def summarize_ir(ir: ScriptIR) -> str:
    lines = [
        f"Source language: {ir.source_language}",
        f"Nodes: {len(ir.nodes)}",
    ]
    if ir.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in ir.warnings)
    return "\n".join(lines)
