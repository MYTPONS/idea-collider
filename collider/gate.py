from __future__ import annotations

from collections import Counter
from typing import Callable, Iterable

from .schema import AXIS_GROUP, GateResult, Statement


def gate_statements(
    statements: Iterable[Statement],
    model,
    limit: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[GateResult]:
    items = list(statements)
    if limit is not None:
        items = items[:limit]
    results: list[GateResult] = []
    for index, stmt in enumerate(items, start=1):
        out = model.classify(stmt.text)
        label = out["label"]
        error = out["error"]
        why = out["why"]
        if stmt.verified:
            if label != "constraint":
                why = f"人工复核为约束(模型判为 {label or error})"
            label = "constraint"
            error = None
            if out["axis"] and AXIS_GROUP.get(out["axis"]) != "constraint":
                out = {**out, "axis": None}
        results.append(
            GateResult(
                statement=stmt,
                label=label,
                axis=out["axis"],
                why=why,
                raw=out["raw"],
                error=error,
            )
        )
        if progress:
            progress(index, len(items))
    return results


def gate_summary(results: list[GateResult]) -> dict:
    labels = Counter(r.label or "unparsed" for r in results)
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "rejected": sum(1 for r in results if not r.passed),
        "errors": sum(1 for r in results if r.error),
        "labels": dict(labels),
    }
