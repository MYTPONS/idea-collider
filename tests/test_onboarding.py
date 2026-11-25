import json

from collider import cli
from collider.onboarding import render_template


class FakeModel:
    def __init__(self, *args, **kwargs):
        pass

    def describe(self) -> str:
        return "fake:0.5b"

    def classify(self, text: str) -> dict:
        return {"label": "constraint", "axis": "trust", "why": "", "raw": "", "error": None}

    def collide(self, near_text, far_text):
        return {"interaction": True, "must": "", "form": "", "why": "", "raw": "", "error": None}


def test_no_materials_falls_back_to_generic_and_says_so(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(cli, "LocalModel", FakeModel)
    assert cli.main(["forge", "--out", str(out)]) == 0
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "这一轮用了什么" in text
    assert "通用" in text
    assert (out / "材料模板.md").exists()


def test_idea_only_is_recorded_as_a_label_not_a_constraint(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(cli, "LocalModel", FakeModel)
    assert cli.main(["forge", "--idea", "做跨境电商", "--out", str(out)]) == 0
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "做跨境电商" in text
    assert "只作为标签" in text


def test_missing_far_falls_back_but_missing_near_does_not(tmp_path, monkeypatch):
    near = tmp_path / "near.jsonl"
    near.write_text('{"id": "n1", "text": "客户第一次付款前不会承认产品有用", "verified": false}\n', encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(cli, "LocalModel", FakeModel)
    assert cli.main(["forge", "--near", str(near), "--out", str(out)]) == 0
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "没给远域" in text
    assert (out / "材料模板.md").exists()


def test_pack_mode_writes_no_template(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(cli, "LocalModel", FakeModel)
    assert cli.main(["forge", "--pack", "memory-saas", "--out", str(out)]) == 0
    assert not (out / "材料模板.md").exists()


def test_template_lists_the_directions_it_actually_hit():
    cards = [
        {
            "form": "只读快照（全量）｜留一份可看的副本",
            "status": "draft",
            "near_text": "客户要求随时可查",
            "mechanism": "ro_snapshot",
        }
    ]
    text = render_template(cards, "我的领域")
    assert "只读快照" in text
    assert "客户要求随时可查" in text
    assert "data/domains/<你的领域>.jsonl" in text


def test_template_with_no_direction_tells_the_user_the_constraints_are_soft():
    text = render_template([], "空")
    assert "两侧约束都太软" in text
