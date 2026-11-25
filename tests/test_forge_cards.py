import json

from collider import cli


class FakeModel:
    def __init__(self, *args, **kwargs):
        pass

    def describe(self) -> str:
        return "fake:0.5b"

    def classify(self, text: str) -> dict:
        return {"label": "constraint", "axis": "trust", "why": "外部事实", "raw": "", "error": None}

    def collide(self, near_text: str, far_text: str) -> dict:
        return {"interaction": True, "must": "", "form": "", "why": "", "raw": "", "error": None}


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
    )


def test_forge_writes_cards_and_names_the_primary(tmp_path, monkeypatch):
    near = tmp_path / "near.jsonl"
    write_jsonl(
        near,
        [
            {"id": "n1", "text": "用户无法导出自己的记忆副本", "verified": True},
            {"id": "n2", "text": "上游账号会在无通知的情况下失效", "verified": True},
        ],
    )
    far = tmp_path / "far.jsonl"
    write_jsonl(far, [{"id": "f1", "text": "个人有权查阅、复制其个人信息", "verified": False}])
    known = tmp_path / "known.jsonl"
    write_jsonl(
        known,
        [{"name": "阿里云 Memory", "what": "托管记忆", "satisfies": ["记忆"], "gap": "不提供最终用户自助的查阅、导出、删除入口"}],
    )
    evidence = tmp_path / "ev.json"
    evidence.write_text(
        json.dumps({"entries": [{"mechanisms": ["export"], "blocker": "平台不给导出,因为导出等于降低迁移成本"}]},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    out = tmp_path / "out"

    monkeypatch.setattr(cli, "LocalModel", FakeModel)
    code = cli.main([
        "forge", "--near", str(near), "--far", str(far), "--out", str(out),
        "--known", str(known), "--profile", str(tmp_path / "none.json"), "--evidence", str(evidence),
    ])
    assert code == 0
    assert (out / "report.md").exists()
    assert (out / "cards.jsonl").exists()
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "项目方向" in text
    assert "远域未复核：1 条" in text


def test_forge_warns_when_far_side_contributes_nothing(tmp_path, monkeypatch):
    near = tmp_path / "near.jsonl"
    write_jsonl(near, [{"id": "n1", "text": "上游账号会在无通知的情况下失效", "verified": True}])
    far = tmp_path / "far.jsonl"
    write_jsonl(far, [{"id": "f1", "text": "每张赌桌有最低和最高下注额", "verified": False}])
    out = tmp_path / "out"

    monkeypatch.setattr(cli, "LocalModel", FakeModel)
    assert cli.main([
        "forge", "--near", str(near), "--far", str(far), "--out", str(out),
        "--known", str(tmp_path / "empty.jsonl"), "--profile", str(tmp_path / "none.json"),
    ]) == 0
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "远域无贡献" in text or "远域关键词命中：" in text


def test_forge_with_empty_far_still_writes_a_report(tmp_path, monkeypatch):
    near = tmp_path / "near.jsonl"
    write_jsonl(near, [{"id": "n1", "text": "用户无法导出自己的记忆副本", "verified": True}])
    far = tmp_path / "far.jsonl"
    write_jsonl(far, [{"id": "f1", "text": "希望系统更好用", "verified": False}])
    out = tmp_path / "out"

    monkeypatch.setattr(cli, "LocalModel", FakeModel)
    assert cli.main([
        "forge", "--near", str(near), "--far", str(far), "--out", str(out),
        "--known", str(tmp_path / "empty.jsonl"), "--profile", str(tmp_path / "none.json"),
    ]) == 0
    assert "本次注意" in (out / "report.md").read_text(encoding="utf-8")
