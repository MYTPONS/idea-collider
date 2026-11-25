from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .schema import Candidate, Statement
from .textutil import jaccard, normalize_text


@dataclass
class CollideStats:
    pairs: int = 0
    generated: int = 0
    deduped: int = 0
    parse_errors: int = 0


def collide_pairs(
    near: Iterable[Statement],
    far: Iterable[Statement],
    model,
    limit: int | None = None,
    progress: Callable[[int, int], None] | None = None,
    samples: int = 1,
) -> tuple[list[Candidate], CollideStats]:
    pairs = [(n, f) for n in near for f in far]
    if limit is not None:
        pairs = pairs[:limit]
    stats = CollideStats(pairs=len(pairs))
    candidates: list[Candidate] = []
    kept_keys: list[str] = []
    rounds = max(1, samples)
    total = len(pairs) * rounds
    done = 0
    for near_stmt, far_stmt in pairs:
        for _ in range(rounds):
            out = model.collide(near_stmt.text, far_stmt.text)
            if out["error"]:
                stats.parse_errors += 1
            elif out["form"]:
                stats.generated += 1
                key = normalize_text(out["form"])
                if not key:
                    stats.deduped += 1
                elif any(jaccard(key, old, n=2) > 0.8 for old in kept_keys):
                    stats.deduped += 1
                else:
                    kept_keys.append(key)
                    candidates.append(
                        Candidate(
                            id=f"c{len(candidates) + 1:03d}",
                            near=near_stmt,
                            far=far_stmt,
                            interaction=True,
                            must=out["must"],
                            form=out["form"],
                            why=out["why"],
                            raw=out["raw"],
                        )
                    )
            done += 1
            if progress:
                progress(done, total)
    return candidates, stats
