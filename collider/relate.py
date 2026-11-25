from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .schema import Statement


@dataclass
class RelateStats:
    pairs: int = 0
    related: int = 0
    errors: int = 0


def relate_pairs(
    near: Iterable[Statement],
    far: Iterable[Statement],
    model,
    limit: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[list[tuple[Statement, Statement]], RelateStats]:
    pairs = [(n, f) for n in near for f in far]
    if limit is not None:
        pairs = pairs[:limit]
    stats = RelateStats(pairs=len(pairs))
    kept: list[tuple[Statement, Statement]] = []
    for index, (near_stmt, far_stmt) in enumerate(pairs, start=1):
        out = model.relate(near_stmt.text, far_stmt.text)
        if out["error"]:
            stats.errors += 1
        elif out["related"]:
            stats.related += 1
            kept.append((near_stmt, far_stmt))
        if progress:
            progress(index, len(pairs))
    return kept, stats
