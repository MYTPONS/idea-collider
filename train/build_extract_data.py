from __future__ import annotations

import json
import pathlib
import random
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
random.seed(17)

OBLIGATION = ["必须", "不得", "应当", "禁止", "只能", "不能", "一律", "要求", "义务", "违法", "违规", "须"]

TRAIN_DOCS = ["docs/DESIGN.md", "docs/DECISION.md", "README.md"]
TRAIN_DOCS += [f"docs/experiments/exp-0{i}.md" for i in (1, 2, 3, 5, 6, 7, 8, 9)]
TEST_DOCS = ["docs/experiments/exp-04.md"]


def sentences(rel: str) -> list[str]:
    path = ROOT / rel
    if not path.exists():
        return []
    out: list[str] = []
    for raw in re.split(r"[。；;\n]+", path.read_text(encoding="utf-8")):
        sentence = raw.strip().strip("-*0123456789. |")
        if not sentence or sentence.startswith("|") or sentence.startswith("#"):
            continue
        if 12 <= len(sentence) <= 160:
            out.append(sentence)
    return out


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def row(text: str, label: str, axis: str) -> dict:
    return {
        "task": "gate",
        "input": {"text": text},
        "output": {"label": label, "axis": axis},
        "why": "",
        "source": "extract-teacher",
    }


def split_docs(docs: list[str]) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    for rel in docs:
        for sentence in sentences(rel):
            if any(word in sentence for word in OBLIGATION):
                positive.append(sentence)
            else:
                negative.append(sentence)
    return dedupe(positive), dedupe(negative)


def main() -> int:
    positives, negatives = split_docs(TRAIN_DOCS)
    positives = positives * 2
    random.shuffle(negatives)
    negatives = negatives[: max(len(positives), 120)]
    rows = [row(text, "constraint", "compliance") for text in positives]
    rows += [row(text, "pain", "feeling") for text in negatives]
    random.shuffle(rows)
    split = int(len(rows) * 0.85)
    train, dev = rows[:split], rows[split:]
    for name, data in (("extract_train.jsonl", train), ("extract_dev.jsonl", dev)):
        path = ROOT / "data" / name
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in data) + "\n", encoding="utf-8")
        print(name, len(data))
    test_positive, _ = split_docs(TEST_DOCS)
    path = ROOT / "data" / "extract_holdout.jsonl"
    path.write_text(
        "\n".join(json.dumps(row(text, "constraint", "compliance"), ensure_ascii=False) for text in test_positive) + "\n",
        encoding="utf-8",
    )
    print("holdout 正例", len(test_positive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
