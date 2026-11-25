import json
from pathlib import Path

from collider.schema import ALL_AXES, AXIS_GROUP
from collider.textutil import jaccard

ROOT = Path(__file__).resolve().parent.parent


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_gate_train_is_consistent():
    rows = read(ROOT / "data" / "gate_train.jsonl")
    assert len(rows) >= 500
    for row in rows:
        assert row["task"] == "gate"
        assert 8 <= len(row["input"]) <= 80
        output = row["output"]
        assert output["label"] in ("constraint", "pain")
        assert output["axis"] in ALL_AXES
        assert AXIS_GROUP[output["axis"]] == output["label"]
        assert output["why"]


def test_gate_train_does_not_leak_test_cases():
    train = read(ROOT / "data" / "gate_train.jsonl")
    test = read(ROOT / "eval" / "cases.jsonl")
    for row in train:
        for case in test:
            assert jaccard(row["input"], case["text"], n=2) <= 0.6


def test_gate_split_is_disjoint():
    train = read(ROOT / "data" / "gate_train.jsonl")
    dev = read(ROOT / "data" / "gate_dev.jsonl")
    assert not {row["input"] for row in train} & {row["input"] for row in dev}


def test_collide_data_rows_are_generative():
    rows = read(ROOT / "data" / "collide_train.jsonl")
    assert rows
    for row in rows:
        assert row["output"]["interaction"] is True
        assert row["output"]["form"]
        assert row["output"]["must"]
