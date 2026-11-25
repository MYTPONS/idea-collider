"""给 agent 用的接口层。

网页表单的毛病是只能问一轮:人填完,拿到一堆草稿,然后没有下一步。
agent 不一样 —— 它可以接着问「那谁卡在哪」「第一个客户是谁」,把答案喂回来。
所以这一层的产出必须包含**下一句该问什么**,而不只是结果。

同一个 `collide()` 被三处调用:
- `collider mcp`(stdio,本地或远端 agent 直接挂)
- `POST /api/collide`(HTTP,远端 agent)
- 网页版(表单只是这个函数的一层皮)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .cards import Profile, build_cards, pick_recommendations
from .forge import build_candidates, load_pack_entry
from .gate import gate_statements
from .rulegate import RuleModel
from .schema import Statement

ROOT = Path(__file__).resolve().parent.parent

MISSING_QUESTIONS = {
    "conflict": "这两条约束真的互相冲突吗？如果有什么办法能同时满足,这条就该砍。",
    "existing": "这个方向现在有没有具体产品？给我名字。它的缺口用一句话说清楚。",
    "blocker": "做类似东西的人具体卡在哪？要能复述的那种,不是「体验不好」。",
    "first_customer": "第一个客户是谁、你在哪认识他？说不出具体人和渠道,这条方向就是假的。",
}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    import json

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_evidence(path: Path) -> list[dict]:
    import json

    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("entries") if isinstance(data, dict) else data
    return [item for item in (items or []) if isinstance(item, dict)]


def _statements_from_rows(rows: list[dict], domain: str, prefix: str) -> list[Statement]:
    out: list[Statement] = []
    for index, row in enumerate(rows, start=1):
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        out.append(
            Statement(
                id=str(row.get("id") or f"{prefix}{index}"),
                text=text,
                domain=domain,
                source=str(row.get("source", "")),
                verified=bool(row.get("verified")),
            )
        )
    return out


def _split_text(text: str) -> list[str]:
    parts = re.split(r"[。；;!?\n]+", text)
    out: list[str] = []
    seen: set[str] = set()
    for raw in parts:
        line = raw.strip().strip("-*0123456789. 、")
        if not 8 <= len(line) <= 200 or line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out[:20]


def _profile_from(request: dict) -> Profile:
    given = request.get("profile")
    if isinstance(given, dict):
        return Profile(
            name=str(given.get("name", "agent")),
            skills=[str(s) for s in given.get("skills", [])],
            channels=[c for c in given.get("channels", []) if isinstance(c, dict)],
            hours_per_week=int(given.get("hours_per_week", 0) or 0),
            anti=[a for a in given.get("anti", []) if isinstance(a, dict)],
        )
    channel = str(request.get("channel", "")).strip()
    skills = [str(s) for s in request.get("skills", []) if str(s).strip()]
    anti = [str(a) for a in request.get("anti", []) if str(a).strip()]
    near_words = _split_text(str(request.get("near_text", "")))[:6]
    return Profile(
        name="agent",
        skills=skills,
        channels=[{"name": channel, "keywords": near_words or [channel], "role": channel}]
        if channel
        else [],
        hours_per_week=10,
        anti=[{"name": word, "keywords": [word]} for word in anti],
    )


def _resolve_side(request: dict, key: str, generic: str, domain: str, prefix: str):
    """一侧素材:包 / 显式文件 / 内联文本 / 通用兜底。返回 (statements, how, note)。"""
    pack = request.get("pack")
    if pack:
        entry = load_pack_entry(str(pack), ROOT / "data" / "packs" / "index.json")
        path = ROOT / entry[key]
        return _statements_from_rows(_read_jsonl(path), domain, prefix), "pack", f"{key} ← 包 {pack} 的 {entry[key]}"

    explicit = request.get(f"{key}_file")
    if explicit:
        path = Path(str(explicit))
        if not path.is_absolute():
            path = ROOT / path
        return _statements_from_rows(_read_jsonl(path), domain, prefix), "file", f"{key} ← {explicit}"

    inline = request.get(key) or []
    if isinstance(inline, str):
        inline = _split_text(inline)
    if inline:
        rows = inline if isinstance(inline[0], dict) else [{"text": str(item)} for item in inline]
        return _statements_from_rows(rows, domain, prefix), "inline", f"{key} ← 调用方给的 {len(rows)} 条"

    path = ROOT / generic
    return _statements_from_rows(_read_jsonl(path), domain, prefix), "generic", f"{key} ← 通用兜底 {generic}"


def _ask_user(
    cards: list[dict],
    primary: dict | None,
    near_passed: int = 0,
    far_passed: int = 0,
    row_count: int = 0,
) -> list[str]:
    """agent 下一步该问用户什么。这是这一层存在的理由。"""
    if primary is not None:
        questions = [
            f"主推是「{primary['form']}」。先确认:这个方向你现在能动手吗？两周内第一版只做「{primary['mvp']['cut']}」。",
        ]
        if primary.get("blocker"):
            questions.append(f"补充问一句:还有别的卡点吗？现在是「{primary['blocker']['text']}」。")
        return questions

    drafts = [card for card in cards if card["status"] == "draft"]
    if not drafts:
        if near_passed and far_passed and row_count == 0:
            return [
                f"约束过闸了(近域 {near_passed} 条、远域 {far_passed} 条),但没有任何机制同时匹配两边。"
                "这通常说明两边讲的是不同的事情:补几条同类事实(同一根轴上的),或者换一个远域再试。",
            ]
        if not near_passed:
            return [
                "近域一条约束都没留下。写已经发生、能判真假、违反有代价的事,比如「上游会在无通知下失效」。",
            ]
        if not far_passed:
            return [
                "远域一条约束都没留下。给法规条文、行业标准或物理限制,每条要能指到出处。",
            ]
        return [
            "这一轮一个方向都没撞出来。两侧约束都太软:先各写五条能判真假、违反有代价的事实,再来一次。",
        ]
    questions: list[str] = []
    for card in drafts[:3]:
        for dim in card["missing"]:
            if dim in MISSING_QUESTIONS:
                questions.append(f"「{card['form']}」—— {MISSING_QUESTIONS[dim]}")
    return questions[:6]


def collide(request: dict) -> dict[str, Any]:
    """一行请求跑完整条管线,返回给 agent 的结构化结果。

    request 的键(都可选):
      pack            行业包 id
      near / far      内联约束:字符串数组,或 {"text": ...} 数组
      near_text / far_text  一段文本,按句切
      near_file / far_file  文件路径
      skills / channel / anti   给匹配用的档案
      profile         完整档案 dict
      evidence        证据条目数组(卡点与第一个客户)
      apply_user_inputs  真正的 verified
    """
    model = RuleModel()
    profile = _profile_from(request)

    near_statements, near_how, near_note = _resolve_side(
        request, "near", "data/domains/generic_near.jsonl", "near", "n"
    )
    far_statements, far_how, far_note = _resolve_side(
        request, "far", "data/domains/generic_far.jsonl", "far", "f"
    )

    if request.get("near_text") and near_how == "generic":
        text_near = _split_text(str(request["near_text"]))
        if text_near:
            near_statements = [
                Statement(id=f"n{i+1}", text=t, domain="near", verified=True)
                for i, t in enumerate(text_near)
            ]
            near_how, near_note = "inline", f"near ← 调用方写的 {len(text_near)} 条"

    if request.get("far_text") and far_how == "generic":
        text_far = _split_text(str(request["far_text"]))
        if text_far:
            far_statements = [Statement(id=f"f{i+1}", text=t, domain="far") for i, t in enumerate(text_far)]
            far_how, far_note = "inline", f"far ← 调用方写的 {len(text_far)} 条"

    # 调用方自带素材时,把它当成已验证的:agent 和人已经判断过了,
    # 规则闸门不该反过来把它们挡掉。
    if near_how in ("inline", "file"):
        near_statements = [
            Statement(s.id, s.text, s.domain, s.source, s.verified or near_how == "inline")
            for s in near_statements
        ]

    notes = [near_note, far_note]
    warnings: list[str] = []
    if near_how == "generic":
        warnings.append("近域用的是通用经营约束,不是你行业里发生过的事实")
    if far_how == "generic":
        warnings.append("远域用的是通用合规义务,必须先复核才能当结论")

    known: list[dict] = []
    entries: list[dict] = []
    if request.get("pack"):
        entry = load_pack_entry(str(request["pack"]), ROOT / "data" / "packs" / "index.json")
        if entry.get("known"):
            known = _read_jsonl(ROOT / entry["known"])
        if entry.get("evidence"):
            entries = _load_evidence(ROOT / entry["evidence"])
    if not known:
        known = _read_jsonl(ROOT / "data/projects/known_products.jsonl")
    evidence_path = request.get("evidence_file")
    if evidence_path:
        entries = _load_evidence(ROOT / evidence_path if not Path(str(evidence_path)).is_absolute() else Path(str(evidence_path)))
    if request.get("evidence"):
        entries = [item for item in request["evidence"] if isinstance(item, dict)] + entries

    near_results = gate_statements(near_statements, model)
    far_results = gate_statements(far_statements, model)
    rows = build_candidates(near_results, far_results, known)
    cards = build_cards(rows, known, profile, entries)
    primary, alternates = pick_recommendations(cards)

    return {
        "mode": "pack" if request.get("pack") else ("inline" if near_how == "inline" else near_how),
        "gate": model.describe(),
        "notes": notes,
        "warnings": warnings,
        "near": {"total": len(near_results), "passed": sum(1 for r in near_results if r.passed)},
        "far": {"total": len(far_results), "passed": sum(1 for r in far_results if r.passed)},
        "counts": {
            "cards": sum(1 for c in cards if c["status"] == "card"),
            "drafts": sum(1 for c in cards if c["status"] == "draft"),
            "taken": sum(1 for c in cards if c["status"] == "taken"),
        },
        "primary": primary,
        "alternates": alternates,
        "cards": cards,
        "ask_user": _ask_user(
            cards,
            primary,
            near_passed=sum(1 for r in near_results if r.passed),
            far_passed=sum(1 for r in far_results if r.passed),
            row_count=len(rows),
        ),
        "rejected_near": [
            {"id": r.statement.id, "text": r.statement.text, "label": r.label}
            for r in near_results
            if not r.passed
        ],
        "unverified_far": [
            {"id": r.statement.id, "text": r.statement.text, "source": r.statement.source}
            for r in far_results
            if not r.statement.verified
        ],
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "collide",
        "description": (
            "把两个领域的硬约束求交集,返回项目卡。产出是「能不能开工」的判断,不是点子列表。"
            "四维(已有产品与缺口 / 卡点 / 两周第一版 / 第一个客户)缺一维的会降为草稿并返回 missing。"
            "返回里的 ask_user 是下一步该问用户的问题,把答案放进 evidence 再调用一次即可补全。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack": {"type": "string", "description": "行业包 id,见 list_packs"},
                "near": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "近域约束:用户够得着的领域里,已经发生、能判真假的事实",
                },
                "far": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "远域约束:法规、行业标准、物理限制。每条要能指到出处",
                },
                "near_text": {"type": "string", "description": "近域素材原文,按句切分"},
                "far_text": {"type": "string", "description": "远域素材原文,按句切分"},
                "skills": {"type": "array", "items": {"type": "string"}, "description": "用户会做的事"},
                "channel": {"type": "string", "description": "用户够得着的人,第一批客户从这里来"},
                "anti": {"type": "array", "items": {"type": "string"}, "description": "用户不做的类型"},
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "mechanisms": {"type": "array", "items": {"type": "string"}},
                            "blocker": {"type": "string"},
                            "first_customer": {
                                "type": "object",
                                "properties": {"role": {"type": "string"}, "channel": {"type": "string"}},
                            },
                        },
                    },
                    "description": "用户回答的卡点与第一个客户,按机制名挂上",
                },
            },
        },
    },
    {
        "name": "list_packs",
        "description": "列出可用的行业包。用户说「AI 行业」这类话时先看这里有没有现成的。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "explain_conflict",
        "description": "查某一对「近域类型 × 远域类型」到底是不是真冲突。不是冲突的组合不该被当成项目。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "near_style": {
                    "type": "string",
                    "enum": ["禁写", "绑定", "改写", "承诺", "打扰", "断裂"],
                },
                "far_type": {
                    "type": "string",
                    "enum": ["查阅", "更正", "删除", "限期", "义务", "禁止"],
                },
            },
            "required": ["near_style", "far_type"],
        },
    },
    {
        "name": "materials_template",
        "description": "用户没有素材时,拿一份告诉他该去收集什么事实的模板。",
        "inputSchema": {
            "type": "object",
            "properties": {"label": {"type": "string", "description": "用户说的方向,只作标题"}},
        },
    },
]


def list_packs() -> list[dict[str, Any]]:
    import json

    data = json.loads((ROOT / "data" / "packs" / "index.json").read_text(encoding="utf-8"))
    out = []
    for pack in data.get("packs", []):
        out.append(
            {
                "id": pack["id"],
                "name": pack.get("name", pack["id"]),
                "note": pack.get("note", ""),
                "has_evidence": bool(pack.get("evidence")),
            }
        )
    return out


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "collide":
        return collide(arguments)
    if name == "list_packs":
        return {"packs": list_packs()}
    if name == "explain_conflict":
        from .conflicts import conflict_for

        near_style = str(arguments.get("near_style", ""))
        far_type = str(arguments.get("far_type", ""))
        text = conflict_for(near_style, far_type)
        return {
            "near_style": near_style,
            "far_type": far_type,
            "is_conflict": text is not None,
            "explanation": text
            or "这两边可以同时满足(交集非空),不构成碰撞。别把它当项目。",
        }
    if name == "materials_template":
        from .onboarding import render_template

        return {"markdown": render_template([], str(arguments.get("label", "你的方向")))}
    raise KeyError(f"unknown tool: {name}")
