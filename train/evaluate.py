from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collider.model import LocalModel

PAIN_MARKERS = (
    "应该",
    "希望",
    "想要",
    "最好",
    "支持",
    "提供",
    "具备",
    "体验",
    "方便",
    "高效",
    "可能会",
    "预计",
    "未来",
    "感觉",
    "觉得",
    "建议",
    "尽快",
    "需要",
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def keyword_predict(text: str) -> str:
    return "pain" if any(marker in text for marker in PAIN_MARKERS) else "constraint"


def prf(gold: list[str], pred: list[str], label: str) -> dict[str, float]:
    tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
    fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
    fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["keyword", "base", "finetuned"], default="finetuned")
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--cases", default="eval/cases.jsonl")
    parser.add_argument("--out", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    cases = read_jsonl(ROOT / args.cases)
    if args.limit:
        cases = cases[: args.limit]

    if args.mode == "keyword":
        model_desc = "keyword-baseline"
        predictions = [keyword_predict(case["text"]) for case in cases]
        raws = [""] * len(cases)
    else:
        model_dir = "base" if args.mode == "base" else args.model_dir
        model = LocalModel(model_dir=model_dir, device=args.device)
        model_desc = model.describe()
        predictions, raws = [], []
        for index, case in enumerate(cases, start=1):
            out = model.classify(case["text"])
            predictions.append(out["label"])
            raws.append(out["raw"])
            if index % 10 == 0 or index == len(cases):
                print(f"eval {index}/{len(cases)}", flush=True)

    gold = [case["label"] for case in cases]
    correct = sum(1 for g, p in zip(gold, predictions) if g == p)
    unparseable = sum(1 for p in predictions if p is None)
    per_axis: dict[str, list[int]] = {}
    for case, pred in zip(cases, predictions):
        bucket = per_axis.setdefault(case["axis"], [0, 0])
        bucket[1] += 1
        bucket[0] += int(pred == case["label"])

    results = []
    for case, pred, raw in zip(cases, predictions, raws):
        results.append(
            {
                "text": case["text"],
                "gold": case["label"],
                "pred": pred,
                "axis": case["axis"],
                "why": case.get("why"),
                "raw": raw,
                "error": None if pred else "unparsed",
            }
        )

    summary = {
        "mode": args.mode,
        "model": model_desc,
        "cases": len(cases),
        "accuracy": round(correct / len(cases), 4) if cases else 0.0,
        "unparseable": unparseable,
        "per_label": {
            label: prf(gold, predictions, label) for label in ("constraint", "pain")
        },
        "per_axis": {
            axis: {"correct": good, "total": total, "accuracy": round(good / total, 4)}
            for axis, (good, total) in sorted(per_axis.items())
        },
        "confusion": dict(
            Counter(f"{g}->{p}" for g, p in zip(gold, predictions))
        ),
    }
    out_path = ROOT / (args.out or f"eval/result_{args.mode}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {key: summary[key] for key in ("mode", "model", "cases", "accuracy", "unparseable")},
            ensure_ascii=False,
            indent=2,
        )
    )
    print("per label", json.dumps(summary["per_label"], ensure_ascii=False))
    print("confusion", json.dumps(summary["confusion"], ensure_ascii=False))
    print("per axis")
    for axis, value in summary["per_axis"].items():
        print(f"  {axis:13s} {value['correct']}/{value['total']}")
    print("errors")
    for row in results:
        if row["pred"] != row["gold"]:
            print(f"  gold={row['gold']:10s} pred={str(row['pred']):10s} axis={row['axis']} text={row['text']}")
    print(f"written {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
