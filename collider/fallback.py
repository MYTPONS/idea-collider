"""用户没带素材时的兜底。

平台上一个人可能只丢进来一句「我做跨境电商」,既没有约束文件,也没有文档。
不接就等于把人挡在门外;瞎编远域又违反设计文档(远域必须来自可查文档)。

所以分三档,每档都明确告诉用户拿到了什么、缺什么:

1. 一句话 + 已有行业包  → 直接用包
2. 一句话 + 没有对应包  → 近域走 generic_near 里的通用约束,远域走 generic_far 里的通用义务,并标注「近似」
3. 什么都没有            → 只跑远域侧,产出一份「约束清单」,告诉用户下一步该提供什么
"""

from __future__ import annotations

from pathlib import Path

GENERIC_NEAR = Path("data/domains/generic_near.jsonl")
GENERIC_FAR = Path("data/domains/generic_far.jsonl")


def generic_paths(root: Path | None = None) -> tuple[Path, Path]:
    base = root or Path(".")
    return base / GENERIC_NEAR, base / GENERIC_FAR
