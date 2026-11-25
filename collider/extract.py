from __future__ import annotations

import re
from pathlib import Path

from .gate import gate_statements
from .schema import Statement

SPLIT = re.compile(r"[。；;!\?\n]+")


def split_sentences(text: str, min_len: int = 10, max_len: int = 220) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in SPLIT.split(text):
        sentence = raw.strip().strip("-*0123456789. ")
        if not sentence or sentence.startswith("|") or sentence.startswith("#"):
            continue
        if len(sentence) < min_len or len(sentence) > max_len:
            continue
        if sentence in seen:
            continue
        seen.add(sentence)
        out.append(sentence)
    return out


def extract_from_text(
    text: str,
    model,
    domain: str = "imported",
    prefix: str = "x",
    min_len: int = 10,
):
    sentences = split_sentences(text, min_len=min_len)
    statements = [
        Statement(id=f"{prefix}{index + 1}", text=sentence, domain=domain)
        for index, sentence in enumerate(sentences)
    ]
    results = gate_statements(statements, model)
    kept = [result.statement for result in results if result.passed]
    return kept, results


def extract_from_file(path: Path, model, domain: str = "imported", prefix: str = "x"):
    return extract_from_text(path.read_text(encoding="utf-8"), model, domain=domain, prefix=prefix)
