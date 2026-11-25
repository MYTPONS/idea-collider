from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXP_DIR = ROOT / "docs" / "experiments"
BULLET = re.compile(r"^-\s+([ab]\d+)\s+(.+)$")


def constraints_under(text: str, heading_tokens: tuple[str, ...]) -> dict[str, str]:
    found: dict[str, str] = {}
    active = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            active = any(token in stripped for token in heading_tokens)
            continue
        if active:
            match = BULLET.match(stripped)
            if match:
                found[match.group(1)] = match.group(2).strip()
    return found


def table_rows(text: str) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("| 组合"):
            inside = True
            continue
        if not inside:
            continue
        if not stripped.startswith("|"):
            inside = False
            continue
        if set(stripped) <= set("|-: "):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 4 and "×" in cells[0]:
            rows.append((cells[0], cells[1], cells[2], cells[3]))
    return rows


def load_experiments(names: tuple[str, ...] | None = None) -> list[dict]:
    base_a: dict[str, str] = {}
    experiments: list[dict] = []
    for path in sorted(EXP_DIR.glob("exp-0*.md")):
        if names is not None and path.stem not in names:
            continue
        text = path.read_text(encoding="utf-8")
        if not base_a:
            base_a = constraints_under(text, ("A 的硬约束",))
        extra_a = constraints_under(text, ("近域约束扩轴",))
        side_a = {**base_a, **extra_a}
        side_b = constraints_under(text, ("B 的硬约束",))
        if not side_a or not side_b:
            raise ValueError(f"missing constraints in {path.name}")
        experiments.append(
            {
                "name": path.stem,
                "source": path.relative_to(ROOT).as_posix(),
                "a": side_a,
                "b": side_b,
                "rows": table_rows(text),
            }
        )
    return experiments


def build(experiments: list[dict]) -> tuple[list[dict], dict[str, int]]:
    positives: list[dict] = []
    counts: dict[str, int] = {}
    for exp in experiments:
        a, b = exp["a"], exp["b"]
        exp_pos = 0
        for combo, must, form, verdict in exp["rows"]:
            left, right = combo.split("×", 1)
            near_ids = re.findall(r"a\d+", left)
            far_ids = re.findall(r"b\d+", right)
            if not near_ids or not far_ids:
                continue
            near_text = "并且".join(a[i] for i in near_ids if i in a)
            far_text = "并且".join(b[i] for i in far_ids if i in b)
            if not near_text or not far_text:
                continue
            why = verdict.replace("**", "").replace("砍:", "").strip()
            output = {
                "interaction": True,
                "must": must,
                "form": form,
                "why": why,
            }
            for _ in range(10):
                positives.append(
                    {
                        "task": "collide",
                        "input": {"near": near_text, "far": far_text},
                        "output": output,
                        "source": exp["source"],
                    }
                )
            exp_pos += 1
        counts[exp["name"]] = exp_pos
    return positives, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/collide_train.jsonl")
    args = parser.parse_args()
    experiments = load_experiments()
    rows, counts = build(experiments)
    positives = sum(1 for row in rows if row["output"]["interaction"])
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(f"positives {positives}  total {len(rows)}")
    print(f"per experiment {counts}")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
