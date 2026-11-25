"""没素材时的下一步:给用户一份可以直接填的材料模板。

平台上的人不该看到「无结果」就卡住。这里按他这一轮命中的方向,生成
三份能直接改的文件:近域约束、远域约束、已知产品与证据。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _short(text: str, limit: int = 34) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def render_template(cards: list[dict[str, Any]], label: str) -> str:
    directions = [c for c in cards if c["status"] in ("card", "draft")][:8]
    lines = [
        f"# 给自己的材料模板:{label}",
        "",
        "这一轮用的是通用约束,不是你这个行业里真实发生过的事。所以结论只能当提问,不能当方向。",
        "把下面三份文件填掉,再用同一个命令跑一次,产出就会从「近似」变成「你的」。",
        "",
        "## 1. 近域约束(你自己够得着的那个领域)",
        "",
        "写已经发生、能判真假、违反它有代价的事。不要写「希望」「支持」「用户体验不好」。",
        "文件:`data/domains/<你的领域>.jsonl`,一行一条:",
        "",
        "```json",
        '{"id": "a1", "text": "……", "source": "你从哪知道的", "verified": true}',
        "```",
        "",
        "这一轮撞出来的方向,提示你该去找哪一类事实:",
        "",
    ]
    for card in directions:
        lines.append(f"- {_short(card['form'], 40)} ← {_short(card.get('near_text', ''), 40)}")
    lines += [
        "",
        "## 2. 远域约束(离你远、但约束硬的领域)",
        "",
        "法规、行业标准、物理限制。每条必须能指到出处,不能靠回忆。",
        "文件:`data/domains/<远域>.jsonl`,字段同上,`source` 填法规名与条号。",
        "",
        "## 3. 已知产品与它们留下的缺口",
        "",
        "这一维决定「有没有人做过」。一个产品一条,`gap` 必须具体:",
        "",
        "```json",
        '{"id": "k1", "name": "产品名", "what": "它做什么", '
        '"satisfies": ["它做到的事"], "gap": "它没做到的具体一件事", "source": "官网或文档"}',
        "```",
        "",
        "## 4. 卡点与第一个客户(证据文件)",
        "",
        "模型不判断这两维,必须由人提供。按机制名挂上去:",
        "",
        "```json",
        '{"entries": [{"mechanisms": ["ro_snapshot"], '
        '"blocker": "具体到人、能复述的卡点", '
        '"first_customer": {"role": "具体角色", "channel": "你从哪认识他"}}]}',
        "```",
        "",
        "填完跑:",
        "",
        "```bash",
        ".venv/bin/python -m collider forge --near data/domains/<你的领域>.jsonl \\",
        "  --far data/domains/<远域>.jsonl --known data/projects/<你的产品>.jsonl \\",
        "  --evidence data/evidence/<你的证据>.json --out runs/mine",
        "```",
    ]
    if not directions:
        lines += [
            "",
            "这一轮连方向都没撞出来,说明两侧约束都太软。先各写五条能判真假的硬约束再来。",
        ]
    return "\n".join(lines) + "\n"


def write_template(cards: list[dict[str, Any]], out_dir: Path, label: str) -> Path:
    path = out_dir / "材料模板.md"
    path.write_text(render_template(cards, label), encoding="utf-8")
    return path
