from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collider.schema import ALL_AXES, AXIS_GROUP
from collider.textutil import jaccard, normalize_text


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(text + "\n", encoding="utf-8")


def clean(raw: list[dict], test: list[dict]) -> tuple[list[dict], Counter]:
    kept: list[dict] = []
    seen: set[str] = set()
    reasons: Counter = Counter()
    for row in raw:
        text = str(row.get("text", "")).strip()
        label = str(row.get("label", "")).strip()
        axis = str(row.get("axis", "")).strip()
        why = str(row.get("why", "")).strip()
        if not 8 <= len(text) <= 80:
            reasons["length"] += 1
            continue
        if label not in ("constraint", "pain"):
            reasons["label"] += 1
            continue
        if axis not in ALL_AXES or AXIS_GROUP[axis] != label:
            reasons["axis"] += 1
            continue
        if not why or len(why) > 80:
            reasons["why"] += 1
            continue
        key = normalize_text(text)
        if key in seen:
            reasons["duplicate"] += 1
            continue
        if any(jaccard(text, other["input"], n=2) > 0.9 for other in kept):
            reasons["near_duplicate"] += 1
            continue
        if any(jaccard(text, case["text"], n=2) > 0.6 for case in test):
            reasons["test_leak"] += 1
            continue
        seen.add(key)
        kept.append(
            {
                "task": "gate",
                "input": text,
                "output": {"label": label, "axis": axis, "why": why},
                "source": "synthetic-teacher",
            }
        )
    return kept, reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/gate_synth.raw.jsonl")
    parser.add_argument("--test", default="eval/cases.jsonl")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    raw = read_jsonl(ROOT / args.raw)
    test = read_jsonl(ROOT / args.test)
    kept, reasons = clean(raw, test)
    random.Random(args.seed).shuffle(kept)
    dev_size = max(1, int(len(kept) * 0.1))
    dev, train = kept[:dev_size], kept[dev_size:]
    write_jsonl(ROOT / args.out_dir / "gate_train.jsonl", train)
    write_jsonl(ROOT / args.out_dir / "gate_dev.jsonl", dev)

    labels = Counter(row["output"]["label"] for row in kept)
    axes = Counter(row["output"]["axis"] for row in kept)
    print(f"raw         {len(raw)}")
    print(f"kept        {len(kept)}  train={len(train)} dev={len(dev)}")
    print(f"dropped     {dict(reasons)}")
    print(f"labels      {dict(labels)}")
    print(f"axes        {dict(axes.most_common())}")
    print(f"written     {ROOT / args.out_dir / 'gate_train.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
