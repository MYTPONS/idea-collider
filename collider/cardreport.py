"""项目卡的 markdown 报告。产出单位是一张卡,不是一行机制名。"""

from __future__ import annotations

from typing import Any


def _cell(value: object) -> str:
    return str(value).replace("|", "／").replace("\n", " ")


def _card_block(card: dict[str, Any], heading: str) -> list[str]:
    existing = card.get("existing") or {}
    products = "、".join(existing.get("products", [])) or "未确认"
    gap = existing.get("gap") or "未确认"
    blocker = (card.get("blocker") or {}).get("text") or "未确认"
    mvp = card.get("mvp") or {}
    customer = card.get("first_customer") or {}
    reasons = "、".join(card.get("match", {}).get("reasons", [])) or "档案未命中,需你自判"

    lines = [
        f"### {heading}{card['form']}",
        "",
        f"- 撞的约束：{card.get('pairs', '')}",
        f"- 冲突在哪（{card.get('near_style') or '?'} × {card.get('far_type') or '?'}）：{card.get('conflict') or '未识别（两边不是真冲突）'}",
        f"- 现在有人做吗：{products} —— 缺口:{gap}",
        f"- 做的人卡在哪：{blocker}",
        f"- 两周第一版：{mvp.get('cut', '未确认')}(约 {mvp.get('days', '?')} 天)",
        f"- 第一个客户：{customer.get('role', '未确认')},来自 {customer.get('channel', '未确认')}",
        f"- 为什么是你：{reasons}",
        f"- 难度 / 代价：{card.get('effort', '')} / {card.get('cost', '')}",
        "",
    ]
    return lines


def render_cards(cards: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    primary_pick = meta.get("primary")
    alternates = meta.get("alternates") or []
    if primary_pick is None:
        complete = [c for c in cards if c["status"] == "card"]
        eligible = [c for c in complete if not c["match"].get("anti")]
        primary_pick = eligible[0] if eligible else None
        if primary_pick is not None:
            rest = [c for c in eligible if c is not primary_pick]
            alternates = rest[:2]

    lines = [f"# 项目方向:{meta.get('pack', '未命名')}", ""]

    if primary_pick is None:
        lines += [
            "## 主推",
            "",
            "这一轮没有四维齐全的方向。下面草稿区里缺的那一维补上,才谈得上开工。",
            "",
        ]
    else:
        lines += ["## 主推", ""]
        lines += _card_block(primary_pick, "")

    if alternates:
        lines += ["## 备选", ""]
        for index, card in enumerate(alternates, start=2):
            lines += _card_block(card, f"{index}. ")

    drafts = [c for c in cards if c["status"] == "draft"]
    lines += [f"## 草稿(四维没齐)（{len(drafts)}）", ""]
    if not drafts:
        lines += ["无", ""]
    else:
        lines += ["| 方向 | 缺 | 撞的约束 |", "|---|---|---|"]
        for card in drafts[:20]:
            missing = "、".join(card["missing"])
            lines.append(f"| {_cell(card['form'])} | {missing} | {_cell(card['pairs'])} |")
        lines.append("")

    taken = [c for c in cards if c["status"] == "taken"]
    lines += [f"## 已被做（{len(taken)}）", ""]
    if not taken:
        lines += ["无", ""]
    else:
        lines += ["| 方向 | 已知产品 |", "|---|---|"]
        for card in taken[:20]:
            product = (card.get("existing") or {}).get("products") or ["未指明"]
            lines.append(f"| {_cell(card['form'])} | {_cell('、'.join(product))} |")
        lines.append("")

    needs = [c for c in cards if c["status"] == "draft" and "blocker" in c["missing"]]
    if needs:
        lines += ["## 要补的证据", ""]
        lines += [
            "下面这些方向已经撞上了真冲突。补齐括号里缺的那几维,再跑一次就会升级成项目卡:",
            "",
        ]
        for card in needs[:12]:
            gaps = [name for name in card["missing"] if name in ("blocker", "first_customer", "existing")]
            lines.append(f"- {card['form']}（缺 {'、'.join(gaps)}）")
        lines.append("")

    excluded = [c for c in cards if c["match"].get("anti")]
    if excluded:
        lines += [f"## 已排除(踩到你的不做项)（{len(excluded)}）", ""]
        lines += ["| 方向 | 排除理由 |", "|---|---|"]
        for card in excluded[:20]:
            lines.append(f"| {_cell(card['form'])} | 踩到不做项「{_cell(card['match']['anti'])}」 |")
        lines.append("")

    notes = meta.get("notes") or []
    if notes:
        lines += ["## 这一轮用了什么", ""]
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    lines += ["## 本次注意", ""]
    unverified = meta.get("unverified_far", 0)
    lines.append(f"- 远域未复核：{unverified} 条" + ("(结论前必须先复核)" if unverified else ""))
    for item in meta.get("unverified_far_items", [])[:8]:
        lines.append(f"  - {item.get('id', '')} {item.get('text', '')[:40]}（来源：{item.get('source', '未标')}）")
    if unverified > 8:
        lines.append(f"  - 其余 {unverified - 8} 条见 data/domains 下的远域文件")
    contribution = meta.get("far_contribution", 0)
    far_types = meta.get("far_types", 0)
    if far_types > 1:
        lines.append(
            f"- 远域起了作用：命中的远域类型 {far_types} 种，其中 {contribution} 行还有关键词直接命中"
        )
    elif far_types == 1:
        lines.append("- 远域无贡献：候选撞的是同一种远域类型，换别的远域也是同一批形态")
    elif contribution:
        lines.append(f"- 远域关键词命中：{contribution} 行")
    else:
        lines.append("- 远域无贡献：这一轮换哪个远域都是同一批形态,结论不可用")
    if meta.get("model"):
        lines.append(f"- 模型：{meta['model']}")
    lines.append("")
    return "\n".join(lines)
