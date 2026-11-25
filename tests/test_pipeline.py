import json

from collider import cli

EVIDENCE = {
    "entries": [
        {
            "match": ["模型身份"],
            "existing": {
                "products": ["New API", "LiteLLM"],
                "gap": "两者都不提供可向第三方出示的模型身份凭据",
            },
            "blocker": "中转商默认客户不会追问,客户也拿不到凭据,双方都不提",
            "mvp": {"cut": "响应里附带上游 model 字段与响应头摘要,不做签名", "days": 2},
            "first_customer": {
                "role": "共享 key 池运营者",
                "channel": "New API 部署者圈子",
            },
            "source": "docs/experiments/exp-01.md",
        }
    ]
}


class FakeModel:
    def __init__(self, *args, **kwargs):
        pass

    def describe(self) -> str:
        return "fake:0.5b"

    def classify(self, text: str) -> dict:
        if "希望" in text:
            return {"label": "pain", "axis": "wish", "why": "愿望", "raw": "", "error": None}
        return {"label": "constraint", "axis": "trust", "why": "外部事实", "raw": "", "error": None}

    def collide(self, near_text: str, far_text: str) -> dict:
        return {
            "interaction": True,
            "must": "两边同时满足",
            "form": "可验证的模型身份凭据",
            "why": "",
            "raw": "",
            "error": None,
        }


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
    )


def test_run_end_to_end(tmp_path, monkeypatch):
    near = tmp_path / "near.jsonl"
    far = tmp_path / "far.jsonl"
    evidence = tmp_path / "evidence.json"
    config = tmp_path / "config.json"
    out = tmp_path / "out"

    write_jsonl(
        near,
        [
            {"id": "a1", "text": "客户无法独立验证响应来自哪个具体模型。"},
            {"id": "a2", "text": "希望接口响应更快。"},
            {"id": "a3", "text": "模型行为在版本之间漂移。"},
        ],
    )
    write_jsonl(
        far,
        [
            {"id": "b1", "text": "时间窗刚性,超时不可挽回。"},
            {"id": "b2", "text": "获客只靠口碑与熟人转介。"},
        ],
    )
    evidence.write_text(json.dumps(EVIDENCE, ensure_ascii=False), encoding="utf-8")
    config.write_text(
        json.dumps(
            {
                "name": "fake-run",
                "near": {"domain": "AI 接入层", "file": str(near)},
                "far": {"domain": "殡葬服务", "file": str(far)},
                "evidence": str(evidence),
                "limit": 10,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "LocalModel", FakeModel)
    assert cli.main(["run", "--config", str(config), "--out", str(out)]) == 0

    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert result["near"]["gate"] == {
        "total": 3,
        "passed": 2,
        "rejected": 1,
        "errors": 0,
        "labels": {"constraint": 2, "pain": 1},
    }
    assert result["candidates"]["pairs"] == 4
    assert result["candidates"]["alive"] == 1
    assert result["candidates"]["draft"] == 0
    assert (out / "report.md").exists()
    assert (out / "candidates.jsonl").exists()
