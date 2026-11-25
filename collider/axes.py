from __future__ import annotations

from collections import Counter
from typing import Any

from .schema import AXIS_ZH, GateResult


def axis_report(results: list[GateResult]) -> dict[str, Any]:
    passed = [r for r in results if r.passed and r.axis]
    counts = Counter(r.axis for r in passed)
    total = sum(counts.values())
    warnings: list[str] = []
    if total and len(counts) < 3:
        warnings.append(
            f"通过闸门的约束只覆盖 {len(counts)} 根轴,低于三条,这一轮产出的家族大概率同质。"
        )
    if total and counts.most_common(1)[0][1] / total > 0.5:
        axis, n = counts.most_common(1)[0]
        warnings.append(
            f"「{AXIS_ZH.get(axis, axis)}」一根轴占 {n}/{total},先补没被压过的轴,再换远域。"
        )
    return {
        "constraints": total,
        "axes": [
            {
                "axis": axis,
                "zh": AXIS_ZH.get(axis, axis),
                "count": count,
                "share": round(count / total, 3) if total else 0.0,
            }
            for axis, count in counts.most_common()
        ],
        "warnings": warnings,
    }
