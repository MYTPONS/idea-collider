from collider.gate import gate_statements
from collider.schema import Statement


class PainModel:
    def classify(self, text: str) -> dict:
        return {"label": "pain", "axis": "wish", "why": "模型判为愿望", "raw": "", "error": None}


def test_human_verified_statement_bypasses_gate():
    results = gate_statements([Statement(id="a4", text="客户无法独立验证模型。", verified=True)], PainModel())
    assert results[0].passed
    assert "人工复核" in results[0].why


def test_unverified_statement_is_still_rejected():
    results = gate_statements([Statement(id="a4", text="客户无法独立验证模型。")], PainModel())
    assert not results[0].passed
