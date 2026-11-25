import json
from pathlib import Path

from collider.rulegate import RuleModel

ROOT = Path(__file__).resolve().parent.parent


def test_rule_gate_clears_the_keyword_baseline():
    rows = [json.loads(l) for l in (ROOT / "eval" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    model = RuleModel()
    correct = sum(1 for r in rows if model.classify(r["text"])["label"] == r["label"])
    accuracy = correct / len(rows)
    # 关键词基线 0.6167,规则版必须明显高于它,但不假装达到微调的 0.8667
    assert accuracy >= 0.75
    assert accuracy <= 0.87


def test_implies_sentences_are_pains():
    model = RuleModel()
    assert model.classify("AI 响应要快。")["label"] == "pain"
    assert model.classify("接口要稳定。")["label"] == "pain"


def test_hard_facts_are_constraints():
    model = RuleModel()
    assert model.classify("上游允许的并发数有硬上限,超出直接返回错误码而非排队。")["label"] == "constraint"
    assert model.classify("网络日志必须留存不少于六个月。")["label"] == "constraint"


def test_classify_returns_the_same_shape_as_the_model():
    out = RuleModel().classify("客户要求请求内容不留存")
    assert set(out) == {"label", "axis", "why", "raw", "error"}
