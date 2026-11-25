from __future__ import annotations

from typing import Any, Iterable

import json
from pathlib import Path

from .novelty import judge
from .search import search_mechanisms


def load_pack_entry(pack_id: str, root: Path | None = None) -> dict[str, Any]:
    base = root or Path("data/packs/index.json")
    data = json.loads(base.read_text(encoding="utf-8"))
    for pack in data.get("packs", []):
        if pack.get("id") == pack_id:
            return pack
    raise KeyError(f"unknown pack: {pack_id}")


def load_pack(pack_id: str, root: Path | None = None) -> tuple[Path, Path]:
    pack = load_pack_entry(pack_id, root)
    return Path(pack["near"]), Path(pack["far"])


def load_types(path: Path, root: Path | None = None) -> dict[str, str]:
    """近域类型表:按文件名从 data/domains/types.json 取,没有就返回空。"""
    base = root or Path("data/domains/types.json")
    if not base.exists():
        return {}
    table = json.loads(base.read_text(encoding="utf-8"))
    return table.get(Path(path).stem, {})


def build_candidates(
    near_results: Iterable,
    far_results: Iterable,
    known: list[dict[str, Any]],
    near_styles: dict[str, str] | None = None,
    min_score: int = 1,
) -> list[dict[str, Any]]:
    rows = search_mechanisms(
        list(near_results), list(far_results), min_score=min_score, near_styles=near_styles
    )
    for row in rows:
        verdict, product, score = judge(row, known)
        row["novelty"] = verdict
        row["nearest"] = product["name"] if product else ""
        row["nearest_gap"] = str(product.get("gap", "")) if product else ""
        row["nearest_source"] = str(product.get("source", "")) if product else ""
        row["overlap"] = round(score, 3)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["mechanism"], []).append(row)
    merged: list[dict[str, Any]] = []
    for group in grouped.values():
        group.sort(
            key=lambda item: (
                -(item.get("kw", 0) + item.get("sym", 0)),
                -item["adjusted"],
                item["far"],
            )
        )
        picked: list[dict[str, Any]] = []
        seen_types: set[str] = set()
        for item in group:
            key = item.get("far_type") or ""
            if key and key in seen_types:
                continue
            picked.append(item)
            if key:
                seen_types.add(key)
            if len(picked) >= 3:
                break
        first = dict(picked[0])
        first["pairs"] = " / ".join(
            f'「{item.get("near_text", item["near"])}」×「{item.get("far_text", item["far"])}」'
            for item in picked
        )
        first["pair_count"] = len(picked)
        merged.append(first)
    merged.sort(key=lambda row: (-row["adjusted"], row["mechanism"]))
    return merged


def summarize(
    merged: list[dict[str, Any]],
    profile: Any | None = None,
    entries: list[dict[str, Any]] | None = None,
    known: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from .cards import Profile, build_cards, pick_recommendations

    counts = {
        key: len([row for row in merged if row["novelty"] == key])
        for key in ("blank", "partial", "existing")
    }
    cards = build_cards(merged, known or [], profile or Profile(), entries or [])
    primary, alternates = pick_recommendations(cards)
    return {
        "candidates": len(merged),
        **counts,
        "cards": cards,
        "primary": primary,
        "alternates": alternates,
        "drafts": [card for card in cards if card["status"] == "draft"],
        "taken": [card for card in cards if card["status"] == "taken"],
        "recommended": [
            {"form": card["form"], "first_step": card["first_step"], "pairs": card["pairs"]}
            for card in ([primary] if primary else []) + alternates
        ],
    }
