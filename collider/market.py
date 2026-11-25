"""真实市场判据（替代 novelty.judge 的 28 行关键词匹配）。

核心约定：`blank`（市场没有）是一种**证据状态**，不是默认值。
没有做过检索、没有贴到具体产品，就只能标 `unchecked`，绝不能标 `not_found`。

三种状态：
- existing   ：目录里命中一个具名产品（带 source），或真实检索命中明确产品页
- not_found  ：真实检索跑过，没有可信产品命中（evidence 记录 query + 结果数）
- unchecked  ：没有目录命中，也没有跑过检索——只知道「不在已知表里」

对外接口：
- load_catalog()
- judge(mechanism_id, name, catalog, evidence) -> Verdict
- search_live(query, count, cmd, timeout) -> list[Hit]   （真检索，可插拔）
- judge_from_hits(...)  （把检索结果收敛成状态，保守规则）
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "market" / "products.jsonl"

# 目录命中里用来判「明确产品页」的词（保守，只认这些，避免把一篇博客当产品）
PRODUCT_TOKENS = ("平台", "服务", "系统", "SDK", "产品", "官网", "帮助中心", "解决方案", "组件")


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    category: str
    mechanisms: tuple[str, ...]
    what: str
    source: str


@dataclass
class Verdict:
    state: str  # existing | not_found | unchecked
    product: str = ""
    source: str = ""
    reason: str = ""
    query: str = ""

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def load_catalog(path: Path | None = None) -> list[Product]:
    p = path or CATALOG
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        out.append(
            Product(
                id=r["id"],
                name=r["name"],
                category=r.get("category", ""),
                mechanisms=tuple(r.get("mechanisms", [])),
                what=r.get("what", ""),
                source=r.get("source", ""),
            )
        )
    return out


def _catalog_hit(mechanism_id: str, name: str, catalog: Sequence[Product]) -> Product | None:
    for product in catalog:
        if mechanism_id in product.mechanisms:
            return product
    # 名称兜底：产品名里直接含机制名（例如「阅后即焚」）
    if name:
        for product in catalog:
            if name in product.name or name in product.category:
                return product
    return None


def judge(
    mechanism_id: str,
    name: str,
    catalog: Sequence[Product] | None = None,
    evidence: Sequence[dict[str, Any]] | Mapping[str, Any] | None = None,
) -> Verdict:
    """证据优先：目录 → 检索证据 → 否则 unchecked（永不默认 not_found）。"""
    catalog = catalog if catalog is not None else load_catalog()
    hit = _catalog_hit(mechanism_id, name, catalog)
    if hit is not None:
        return Verdict("existing", hit.name, hit.source, "catalog", "")

    if isinstance(evidence, Mapping):
        evidence = [evidence]
    elif isinstance(evidence, (str, bytes)) or not isinstance(evidence, Sequence):
        evidence = []
    for ev in evidence:
        if not isinstance(ev, Mapping) or ev.get("mechanism") != mechanism_id:
            continue
        query = str(ev.get("query") or "")
        product = str(ev.get("product") or "")
        source = str(ev.get("source") or "")
        if ev.get("verdict") == "existing" and product and source:
            return Verdict("existing", product, source, "live-search", query)
        if ev.get("verdict") == "not_found" and query:
            n = ev.get("n_results", 0)
            return Verdict("not_found", "", "", f"searched, {n} results, no product", query)
    return Verdict("unchecked", "", "", "no evidence: not in catalog, search not run", "")


# ---------------- 真检索（可插拔 search-hub） ----------------

def default_search_cmd() -> str:
    return os.environ.get(
        "SEARCH_HUB_CMD",
        f"uv run --project {Path.home() / 'search-hub'} python -m search_hub.cli",
    )


@dataclass
class Hit:
    title: str
    url: str
    snippet: str = ""
    score: float = 0.0


_ITEM = re.compile(r"^\s*\d+\.\s*\[([0-9.]+)\]\s*(.*)$")
_URL = re.compile(r"^\s*(https?://\S+)\s*$")


def parse_search_output(text: str) -> list[Hit]:
    """解析 search_hub.cli 的文本输出。"""
    hits: list[Hit] = []
    lines = text.splitlines()
    i = 0
    cur: Hit | None = None
    while i < len(lines):
        m = _ITEM.match(lines[i])
        if m:
            if cur:
                hits.append(cur)
            cur = Hit(title=m.group(2).strip(), url="", score=float(m.group(1)))
            i += 1
            continue
        if cur is not None:
            u = _URL.match(lines[i])
            if u and not cur.url:
                cur.url = u.group(1)
            elif lines[i].strip() and cur.url:
                if not cur.snippet:
                    cur.snippet = lines[i].strip()
        i += 1
    if cur:
        hits.append(cur)
    return hits


def search_live(query: str, count: int = 6, cmd: str | None = None, timeout: int = 240) -> list[Hit]:
    args = shlex.split(cmd or default_search_cmd()) + [query, str(count)]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"search failed rc={proc.returncode}: {proc.stderr[-400:]}")
    return parse_search_output(proc.stdout)


def judge_from_hits(mechanism_id: str, name: str, query: str, hits: Sequence[Hit]) -> dict[str, Any]:
    """把检索结果收敛成一条 evidence 行（保守：必须有明确产品信号才算 existing）。"""
    if not hits:
        return {"mechanism": mechanism_id, "query": query, "verdict": "not_found",
                "n_results": 0, "product": "", "source": ""}
    # 明确产品页：标题含产品词，且不是纯博客/百科
    for h in hits:
        if any(tok in h.title for tok in PRODUCT_TOKENS) and h.url:
            return {"mechanism": mechanism_id, "query": query, "verdict": "existing",
                    "n_results": len(hits), "product": h.title, "source": h.url}
    return {"mechanism": mechanism_id, "query": query, "verdict": "not_found",
            "n_results": len(hits), "product": "", "source": ""}
