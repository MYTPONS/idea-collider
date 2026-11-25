import copy

from collider.filter import apply_filter, load_evidence, match_entry
from collider.schema import Candidate, Statement

ENTRY = {
    "match": ["模型身份"],
    "existing": {"products": ["New API", "LiteLLM"], "gap": "两者都不提供可出示的模型身份凭据"},
    "blocker": "中转商默认客户不会追问,客户也拿不到凭据,双方都不提",
    "mvp": {"cut": "响应里附带上游 model 字段与响应头摘要,不做签名", "days": 2},
    "first_customer": {"role": "共享 key 池运营者", "channel": "New API 部署者圈子"},
    "source": "docs/experiments/exp-01.md",
}


def make_candidate(form: str = "可验证的模型身份凭据") -> Candidate:
    return Candidate(
        id="c001",
        near=Statement(id="a4", text="客户无法验证模型身份"),
        far=Statement(id="b5", text="获客靠口碑"),
        interaction=True,
        must="两边同时满足",
        form=form,
        why="",
    )


def test_valid_evidence_makes_candidate_alive():
    cand = apply_filter([make_candidate()], [ENTRY])[0]
    assert cand.verdict == "alive"
    assert all(d.ok for d in cand.dimensions.values())


def test_missing_evidence_stays_draft():
    cand = apply_filter([make_candidate()], [])[0]
    assert cand.verdict == "draft"
    assert not any(d.ok for d in cand.dimensions.values())


def test_generic_customer_rejects_candidate():
    entry = copy.deepcopy(ENTRY)
    entry["first_customer"] = {"role": "中小企业", "channel": "有需求的人"}
    cand = apply_filter([make_candidate()], [entry])[0]
    assert cand.verdict == "dead"
    assert not cand.dimensions["first_customer"].ok


def test_too_long_mvp_rejects_candidate():
    entry = copy.deepcopy(ENTRY)
    entry["mvp"] = {"cut": "做一个完整平台", "days": 30}
    cand = apply_filter([make_candidate()], [entry])[0]
    assert cand.verdict == "dead"
    assert not cand.dimensions["mvp"].ok


def test_match_requires_keyword():
    assert match_entry(make_candidate("普通工具"), [ENTRY]) is None


def test_match_entry_prefers_the_more_specific_entry():
    weak = {"match": ["模型"], "existing": {}}
    strong = {"match": ["模型", "凭据"], "existing": {}}
    assert match_entry(make_candidate(), [weak, strong]) is strong


def test_min_score_requires_multiple_keywords():
    entry = {"match": ["模型", "凭据"], "min_score": 2, "existing": {}}
    assert match_entry(make_candidate("模型身份凭据"), [entry]) is entry
    assert match_entry(make_candidate("模型工具"), [entry]) is None


def test_load_evidence_reads_entries(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text('{"entries": []}', encoding="utf-8")
    assert load_evidence(path) == []
