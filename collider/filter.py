from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import DIMENSIONS, Candidate, DimensionResult

VAGUE_MARKERS = (
    "体验不好",
    "不够智能",
    "效率低",
    "有需求",
    "有痛点",
    "一些类似",
    "中小企业",
    "感觉",
    "可能",
    "大概",
)

GENERIC_ROLES = ("企业", "中小企业", "客户", "用户", "商家", "有需求的人", "所有人")


def load_evidence(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise ValueError("evidence file must contain an 'entries' list")
    return [entry for entry in entries if isinstance(entry, dict)]


def match_entry(cand: Candidate, entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    haystack = cand.form.lower()
    best: dict[str, Any] | None = None
    best_score = 0
    for entry in entries:
        keywords = [str(key) for key in entry.get("match", [])]
        score = sum(1 for key in keywords if key.lower() in haystack)
        threshold = int(entry.get("min_score", 1))
        if score >= threshold and score > best_score:
            best, best_score = entry, score
    return best


def _vague(text: str) -> bool:
    return any(marker in text for marker in VAGUE_MARKERS)


def _check_existing(entry: dict[str, Any]) -> DimensionResult:
    data = entry.get("existing")
    if not isinstance(data, dict):
        return DimensionResult("existing", False, "没有给出已有的具体产品")
    products = [str(p).strip() for p in data.get("products", [])]
    gap = str(data.get("gap", "")).strip()
    if not products:
        return DimensionResult("existing", False, "没有给出已有的具体产品名")
    if any(len(p) < 2 or _vague(p) for p in products):
        return DimensionResult("existing", False, "产品名不具体")
    if len(gap) < 6 or _vague(gap):
        return DimensionResult("existing", False, "没有说出这些人卡在哪")
    return DimensionResult("existing", True, "已列出产品与缺口")


def _check_blocker(entry: dict[str, Any]) -> DimensionResult:
    blocker = str(entry.get("blocker", "")).strip()
    if len(blocker) < 10:
        return DimensionResult("blocker", False, "卡点说得太空")
    if _vague(blocker):
        return DimensionResult("blocker", False, "卡点里仍是套话")
    return DimensionResult("blocker", True, "卡点具体")


def _check_mvp(entry: dict[str, Any]) -> DimensionResult:
    data = entry.get("mvp")
    if not isinstance(data, dict):
        return DimensionResult("mvp", False, "没有说出第一版砍到什么")
    cut = str(data.get("cut", "")).strip()
    days = data.get("days")
    if len(cut) < 10:
        return DimensionResult("mvp", False, "没有说出第一版砍到什么")
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 14:
        return DimensionResult("mvp", False, "工期不是一到十四天内的具体数字")
    return DimensionResult("mvp", True, f"{days} 天:{cut}")


def _check_first_customer(entry: dict[str, Any]) -> DimensionResult:
    data = entry.get("first_customer")
    if not isinstance(data, dict):
        return DimensionResult("first_customer", False, "没有给出第一个客户与来源")
    role = str(data.get("role", "")).strip()
    channel = str(data.get("channel", "")).strip()
    if len(role) < 2 or role in GENERIC_ROLES:
        return DimensionResult("first_customer", False, "客户角色不具体")
    if len(channel) < 3 or _vague(channel):
        return DimensionResult("first_customer", False, "没有说出从哪认识这个客户")
    return DimensionResult("first_customer", True, f"{role},来自{channel}")


CHECKERS = {
    "existing": _check_existing,
    "blocker": _check_blocker,
    "mvp": _check_mvp,
    "first_customer": _check_first_customer,
}


def apply_filter(candidates: list[Candidate], entries: list[dict[str, Any]]) -> list[Candidate]:
    for cand in candidates:
        entry = match_entry(cand, entries)
        cand.evidence = entry
        if entry is None:
            cand.dimensions = {
                name: DimensionResult(name, False, "未提供证据") for name in DIMENSIONS
            }
            cand.verdict = "draft"
            continue
        cand.dimensions = {name: CHECKERS[name](entry) for name in DIMENSIONS}
        cand.verdict = "alive" if all(d.ok for d in cand.dimensions.values()) else "dead"
    return candidates
