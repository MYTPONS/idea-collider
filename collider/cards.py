"""项目卡:把「机制 × 约束对」的候选行组装成可开工的项目方向。

一张卡 = 四维 + 血缘 + 匹配。四维缺任何一维就降为草稿,并写明缺哪一维。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DAYS_BY_EFFORT = {"simple": 3, "medium": 7, "hard": 14}


@dataclass
class Profile:
    name: str = ""
    skills: list[str] = field(default_factory=list)
    channels: list[dict[str, Any]] = field(default_factory=list)
    hours_per_week: int = 0
    anti: list[dict[str, Any]] = field(default_factory=list)


def load_profile(path: str | Path) -> Profile:
    p = Path(path)
    if not p.exists():
        return Profile()
    data = json.loads(p.read_text(encoding="utf-8"))
    return Profile(
        name=str(data.get("name", "")),
        skills=[str(s) for s in data.get("skills", [])],
        channels=[c for c in data.get("channels", []) if isinstance(c, dict)],
        hours_per_week=int(data.get("hours_per_week", 0) or 0),
        anti=[a for a in data.get("anti", []) if isinstance(a, dict)],
    )


def _haystack(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key, ""))
        for key in ("form", "name", "near_text", "far_text", "must", "action", "cost")
    )


def match_profile(row: dict[str, Any], profile: Profile) -> dict[str, Any]:
    text = _haystack(row)
    form = str(row.get("form", ""))

    score = 0
    reasons: list[str] = []
    anti_hit: str | None = None
    for entry in profile.anti:
        keywords = [str(k) for k in entry.get("keywords", [])]
        if any(k and k in form for k in keywords):
            anti_hit = str(entry.get("name", ""))
            reasons.append(f"踩到不做项「{anti_hit}」")
            break

    for skill in profile.skills:
        if skill and skill in text:
            score += 2
            reasons.append(f"会 {skill}")

    channel: dict[str, Any] | None = None
    for candidate_channel in profile.channels:
        keywords = [str(k) for k in candidate_channel.get("keywords", [])]
        if any(k and k in text for k in keywords):
            score += 3
            channel = candidate_channel
            reasons.append(f"够得着 {candidate_channel.get('name', '')}")
            break

    return {
        "score": -1 if anti_hit else score,
        "reasons": reasons,
        "anti": anti_hit,
        "channel": channel,
    }


def match_mechanism_entry(row: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """证据条目:优先按 mechanisms 直配,退回旧的关键词命中。"""
    mechanism = str(row.get("mechanism", ""))
    for entry in entries:
        if mechanism and mechanism in [str(m) for m in entry.get("mechanisms", [])]:
            return entry
    haystack = _haystack(row).lower()
    best: dict[str, Any] | None = None
    best_score = 0
    for entry in entries:
        keywords = [str(k) for k in entry.get("match", [])]
        score = sum(1 for key in keywords if key.lower() in haystack)
        threshold = int(entry.get("min_score", 1))
        if score >= threshold and score > best_score:
            best, best_score = entry, score
    return best


def _existing(row: dict[str, Any], known: list[dict[str, Any]]) -> dict[str, Any] | None:
    """血缘:优先用 novelty 里已经贴上的产品名,否则按机制的症状词去比对已知产品。

    返回 None 表示「查过但没查出来」—— 项目卡会把它标成缺失,而不是当成空白。
    """
    name = str(row.get("nearest") or "")
    if name:
        for product in known:
            if str(product.get("name", "")) == name:
                gap = str(product.get("gap", "")).strip()
                if len(gap) >= 10:
                    return {"products": [name], "gap": gap}
        if str(row.get("novelty", "")) == "existing":
            return {
                "products": [name],
                "gap": str(row.get("nearest_gap", "")).strip(),
                "source": str(row.get("nearest_source", "")).strip(),
            }
        return None

    from .lineage import match_known

    lineage = match_known(str(row.get("mechanism", "")), known)
    if lineage and lineage["verdict"] == "gap" and len(lineage["gap"]) >= 10:
        return {"products": [lineage["product"]], "gap": lineage["gap"]}
    return None


def _is_taken(row: dict[str, Any], known: list[dict[str, Any]]) -> bool:
    if str(row.get("novelty", "")) == "existing":
        return True
    from .lineage import match_known

    lineage = match_known(str(row.get("mechanism", "")), known)
    return bool(lineage and lineage["verdict"] == "taken")


def build_card(
    row: dict[str, Any],
    known: list[dict[str, Any]],
    profile: Profile,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    entry = match_mechanism_entry(row, entries) or {}
    match = match_profile(row, profile)

    existing = _existing(row, known)

    blocker = str(entry.get("blocker", "")).strip()
    blocker_out = {"text": blocker} if len(blocker) >= 10 else None

    first_step = str(row.get("first_step", "")).strip()
    effort = str(row.get("effort", "medium"))
    days = DAYS_BY_EFFORT.get(effort, 7)
    mvp_out = {"cut": first_step, "days": days} if first_step else None

    fc = entry.get("first_customer")
    if isinstance(fc, dict) and fc.get("role") and fc.get("channel"):
        customer_out = {"role": str(fc["role"]), "channel": str(fc["channel"])}
    elif match.get("channel"):
        customer_out = {
            "role": str(match["channel"].get("role", "")),
            "channel": str(match["channel"].get("name", "")),
        }
    else:
        customer_out = None

    from .conflicts import conflict_for

    near_style = str(row.get("near_style", ""))
    far_type = str(row.get("far_type", ""))
    conflict = conflict_for(near_style, far_type)

    dims = {"existing": existing, "blocker": blocker_out, "mvp": mvp_out, "first_customer": customer_out}
    missing = [name for name, value in dims.items() if value is None]
    if conflict is None:
        missing = ["conflict", *missing]

    if _is_taken(row, known):
        status = "taken"
    elif missing:
        status = "draft"
    else:
        status = "card"

    lineage = None
    if existing:
        lineage = {"product": existing["products"][0], "gap": existing["gap"]}

    return {
        "id": str(row.get("mechanism", "")),
        "form": str(row.get("form", "")),
        "mechanism": str(row.get("mechanism", "")),
        "pairs": str(row.get("pairs", "")),
        "pair_count": int(row.get("pair_count", 1)),
        "near_text": str(row.get("near_text", "")),
        "far_text": str(row.get("far_text", "")),
        "near_style": near_style,
        "far_type": far_type,
        "conflict": conflict,
        "existing": existing,
        "blocker": blocker_out,
        "mvp": mvp_out,
        "first_customer": customer_out,
        "missing": missing,
        "status": status,
        "lineage": lineage,
        "match": match,
        "effort": effort,
        "cost": str(row.get("cost", "")),
        "first_step": first_step,
        "adjusted": float(row.get("adjusted", 0.0)),
    }


def build_cards(
    rows: list[dict[str, Any]],
    known: list[dict[str, Any]],
    profile: Profile,
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cards = [build_card(row, known, profile, entries) for row in rows]
    cards.sort(key=lambda c: (-c["match"]["score"], -c["adjusted"], c["id"]))
    return cards


def pick_recommendations(
    cards: list[dict[str, Any]], primary: int = 1, alternates: int = 2
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """只从 status == "card" 且没踩 anti 的里挑。"""
    eligible = [c for c in cards if c["status"] == "card" and not c["match"].get("anti")]
    if not eligible:
        return None, []
    head = eligible[0]
    rest = eligible[1 : 1 + alternates]
    return head, rest
