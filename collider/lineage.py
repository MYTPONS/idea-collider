from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 这些词太常见,出现在任何产品的 gap 里都不说明它做过这个机制。
GENERIC = frozenset(
    {
        "验证", "证明", "争议", "第三方", "变化", "成本", "账号", "上游",
        "日志", "存储", "额度", "独立", "记录", "查看", "附加",
    }
)


@dataclass(frozen=True)
class Lineage:
    """已知产品与它的缺口。机制命中 gap 才算「这个产品把这一块留空了」。"""

    name: str
    gap: str


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value or "")


def match_known(mechanism_id: str, known: list[dict[str, Any]]) -> dict[str, Any] | None:
    """在已知产品里找最贴这个机制的一个。

    先用机制的 symptoms(它解什么症状)比对 satisfies:命中说明有人做过了。
    再比对 gap:命中说明有人做、但这一块留空了 —— 这是我们想要的「血缘」。
    只认有区分度的词;两边都没命中的机制返回 None,项目卡会因此把 existing
    标成缺失,而不是假装「没人做」。
    """
    from .symptoms import symptoms_for

    words = [
        w for w in symptoms_for(mechanism_id) if len(w) >= 2 and w not in GENERIC
    ]
    if not words:
        return None

    best_gap: dict[str, Any] | None = None
    best_gap_hits = 0
    best_sat: dict[str, Any] | None = None
    best_sat_hits = 0
    for product in known:
        gap = _text(product.get("gap"))
        satisfies = _text(product.get("satisfies"))
        gap_hits = sum(1 for word in words if word in gap)
        sat_hits = sum(1 for word in words if word in satisfies)
        if gap_hits > best_gap_hits:
            best_gap, best_gap_hits = product, gap_hits
        if sat_hits > best_sat_hits:
            best_sat, best_sat_hits = product, sat_hits

    # 一个词撞上 satisfies 说明不了什么(「额度」同时出现在额度计费与配额告警里)。
    # 至少两个症状词命中才认为这个产品真的做过这件事。
    if best_sat is not None and best_sat_hits >= 2 and best_sat_hits > best_gap_hits:
        return {"verdict": "taken", "product": best_sat["name"], "gap": str(best_sat.get("gap", "")), "hits": best_sat_hits}
    if best_gap is not None and best_gap_hits >= 1:
        return {"verdict": "gap", "product": best_gap["name"], "gap": str(best_gap.get("gap", "")), "hits": best_gap_hits}
    return None
