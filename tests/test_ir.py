from itsconvert.ir import ScriptIR


def test_ir_defaults():
    ir = ScriptIR(source_language="py")
    assert ir.source_language == "py"
    assert ir.nodes == []
    assert ir.warnings == []
