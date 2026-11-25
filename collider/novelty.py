from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mechanisms import MECHANISMS

BY_ID = {mechanism.id: mechanism for mechanism in MECHANISMS}


def load_known(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value or "")


def judge_keywords(candidate: dict[str, Any], known: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None, float]:
    """旧判据（保留供参考/回归）：关键词子串匹配 known 表。它把「不在表里」当「市场没有」，
    正是被替换掉的那部分。不要在新代码里调用。"""
    mechanism = BY_ID.get(candidate.get("mechanism", ""))
    if mechanism is None:
        return "blank", None, 0.0
    keywords = [keyword for keyword in mechanism.keywords if len(keyword) >= 2]
    best_sat = 0
    best_gap = 0
    sat_product: dict[str, Any] | None = None
    gap_product: dict[str, Any] | None = None
    for product in known:
        satisfies = _text(product.get("satisfies"))
        gap = _text(product.get("gap"))
        sat = sum(1 for keyword in keywords if keyword in satisfies)
        gap_hits = sum(1 for keyword in keywords if keyword in gap)
        if sat > best_sat:
            best_sat = sat
            sat_product = product
        if gap_hits > best_gap:
            best_gap = gap_hits
            gap_product = product
    if best_sat >= 1:
        return "existing", sat_product, float(best_sat)
    if best_gap >= 1:
        return "blank", gap_product, float(best_gap)
    return "blank", None, 0.0


def judge(
    candidate: dict[str, Any],
    known: list[dict[str, Any]],
    market_catalog: list | None = None,
) -> tuple[str, dict[str, Any] | None, float]:
    """真实市场判据（替代关键词判据）。

    映射到既有三态词汇，保持下游 cards/summarize 不变：
      market existing  -> "existing"（贴具体产品名 + source）
      market not_found -> "blank"（真的检索过且没找到，才允许叫市场没有）
      market unchecked -> "partial"（有证据缺失：不在已知表里、也没检索过，绝不叫市场没有）
    """
    from .market import judge as market_judge, load_catalog

    verdict = market_judge(
        candidate.get("mechanism", ""),
        candidate.get("name", ""),
        market_catalog if market_catalog is not None else load_catalog(),
        candidate.get("market_evidence") or None,
    )
    if verdict.state == "existing":
        gap = ""
        for product in known:
            if product.get("name") == verdict.product:
                gap = product.get("gap", "")
                break
        return "existing", {"name": verdict.product, "gap": gap, "source": verdict.source}, 1.0
    if verdict.state == "not_found":
        return "blank", None, 0.0
    return "partial", None, 0.0
