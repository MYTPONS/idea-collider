import pytest

pytest.importorskip("torch")
from collider.model import LocalModel


@pytest.mark.slow
def test_finetuned_model_judges_obvious_cases():
    model = LocalModel()
    assert model.kind in ("adapter", "merged")
    assert model.classify("希望接口响应更快。")["label"] == "pain"
    assert model.classify("上游配额在无通知的情况下失效。")["label"] == "constraint"


@pytest.mark.slow
def test_finetuned_model_collides():
    model = LocalModel()
    out = model.collide("客户无法验证响应来自哪个具体模型。", "获客只靠口碑与熟人转介。")
    assert out["error"] is None
    assert isinstance(out["interaction"], bool)
