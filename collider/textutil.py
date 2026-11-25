from __future__ import annotations

import json
import re
from typing import Any


def first_json_object(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    start = raw.find("{")
    while start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[start:])
        except json.JSONDecodeError:
            start = raw.find("{", start + 1)
            continue
        if isinstance(obj, dict):
            return obj
        start = raw.find("{", start + 1)
    return None


_PUNCT = re.compile(r"[\s，。、；：！？,.;:!?\"'“”‘’()（）\[\]{}<>《》]")


def normalize_text(text: str) -> str:
    return _PUNCT.sub("", text or "")


def char_ngrams(text: str, n: int = 3) -> set[str]:
    chars = list(normalize_text(text))
    if len(chars) < n:
        return {"".join(chars)} if chars else set()
    return {"".join(chars[i : i + n]) for i in range(len(chars) - n + 1)}


def jaccard(a: str, b: str, n: int = 3) -> float:
    ga, gb = char_ngrams(a, n), char_ngrams(b, n)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def one_line(text: str, limit: int = 80) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"
