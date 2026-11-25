from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .axes import axis_report
from .gate import gate_summary
from .schema import DIMENSION_ZH, DimensionResult, Candidate, GateResult, candidate_to_dict


def build_result(
    name: str,
    model_desc: str,
    near_domain: str,
    far_domain: str,
    near_results: list[GateResult],
    far_results: list[GateResult],
    candidates: list[Candidate],
    stats: Any,
) -> dict[str, Any]:
    def section(results: list[GateResult]) -> dict[str, Any]:
        return {
            "gate": gate_summary(results),
            "axes": axis_report(results),
            "rejected": [
                {
                    "id": r.statement.id,
                    "text": r.statement.text,
                    "label": r.label,
                    "axis": r.axis,
                    "why": r.why,
                    "error": r.error,
                }
                for r in results
                if not r.passed
            ],
        }

    alive = [c for c in candidates if c.verdict == "alive"]
    draft = [c for c in candidates if c.verdict == "draft"]
    dead = [c for c in candidates if c.verdict == "dead"]
    return {
        "name": name,
        "model": model_desc,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "near_domain": near_domain,
        "far_domain": far_domain,
        "near": section(near_results),
        "far": section(far_results),
        "candidates": {
            "pairs": stats.pairs,
            "generated": stats.generated,
            "deduped": stats.deduped,
            "parse_errors": stats.parse_errors,
            "alive": len(alive),
            "dead": len(dead),
            "draft": len(draft),
        },
        "acceptance": {
            "ok": len(alive) >= 1,
            "rule": "单轮至少一条候选通过四维过滤",
            "note": "只有四维证据齐全的候选计为 alive;模型草稿一律是 draft。",
        },
        "results": [candidate_to_dict(c) for c in candidates],
    }


def _dims_text(dims: dict[str, DimensionResult]) -> str:
    failed = [DIMENSION_ZH[name] for name, d in dims.items() if not d.ok]
    return "、".join(failed) if failed else "全部通过"


def _cell(value: object) -> str:
    return str(value).replace("|", "／").replace("\n", " ")


def render_markdown(result: dict[str, Any]) -> str:
    near, far = result["near"], result["far"]
    cands = result["candidates"]
    lines = [
        f"# 碰撞报告:{result['near_domain']} × {result['far_domain']}",
        "",
        f"- 时间:{result['created_at']}",
        f"- 模型:{result['model']}",
        "",
        "## 约束闸门",
        "",
        "| 域 | 输入 | 通过 | 砍掉 | 解析失败 |",
        "|---|---|---|---|---|",
    ]
    for label, section in (("近域", near), ("远域", far)):
        gate = section["gate"]
        lines.append(
            f"| {label} | {gate['total']} | {gate['passed']} | {gate['rejected']} | {gate['errors']} |"
        )
    for label, section in (("近域", near), ("远域", far)):
        rejected = section["rejected"]
        if not rejected:
            continue
        lines += ["", f"### 被砍掉的{label}表述", "", "| id | 表述 | 判定 | 理由 |", "|---|---|---|---|"]
        for row in rejected:
            verdict = row["label"] or row["error"] or "unparsed"
            lines.append(
                f"| {row['id']} | {_cell(row['text'])} | {verdict} | {_cell(row['why'])} |"
            )
    lines += ["", "## 约束轴向", ""]
    for label, section in (("近域", near), ("远域", far)):
        axes = section["axes"]
        lines.append(f"### {label}")
        lines.append("")
        if not axes["axes"]:
            lines.append("没有通过闸门的约束。")
        else:
            lines.append("| 轴 | 条数 | 占比 |")
            lines.append("|---|---|---|")
            for row in axes["axes"]:
                lines.append(f"| {row['zh']} | {row['count']} | {row['share']} |")
        for warning in axes["warnings"]:
            lines.append(f"- 警告:{warning}")
        lines.append("")
    lines += [
        "## 候选",
        "",
        f"配对 {cands['pairs']} 组,生成形态 {cands['generated']} 条,去掉重复 {cands['deduped']} 条,"
        f"最终 {cands['alive'] + cands['dead'] + cands['draft']} 条候选。",
        "",
        "| id | 形态 | 判定 | 未通过维度 |",
        "|---|---|---|---|",
    ]
    for cand in result["results"]:
        verdict = {"alive": "存活", "dead": "作废", "draft": "待核实"}[cand["verdict"]]
        dims = {
            name: DimensionResult(name, value["ok"], value["detail"])
            for name, value in (cand.get("dimensions") or {}).items()
        }
        lines.append(
            f"| {cand['id']} | {_cell(cand['form'])} | {verdict} | {_dims_text(dims)} |"
        )
    ordered = sorted(
        result["results"], key=lambda c: {"alive": 0, "dead": 1, "draft": 2}[c["verdict"]]
    )
    lines += [
        "",
        "## 碰撞明细",
        "",
        "| 组合 | 必须同时满足 | 形态 | 判定依据 |",
        "|---|---|---|---|",
    ]
    for cand in ordered:
        combo = f"{cand['near']['id']} × {cand['far']['id']}"
        lines.append(
            f"| {combo} | {_cell(cand['must'])} | {_cell(cand['form'])} | {_cell(cand['why'])} |"
        )
    drafts = [c for c in result["results"] if c["verdict"] == "draft"]
    if drafts:
        lines += [
            "",
            "## 待核实",
            "",
            "下面这些候选只有模型草稿,四维证据未提供,按设计文档一律不算存活。",
            "",
        ]
        for cand in drafts:
            lines.append(f"- {cand['id']}:{cand['form']}")
    lines += [
        "",
        "## 验收",
        "",
        f"- 存活候选:{cands['alive']}",
        f"- 通过:{'是' if result['acceptance']['ok'] else '否'}",
        f"- 口径:{result['acceptance']['note']}",
        "",
    ]
    return "\n".join(lines)


def write_report(result: dict[str, Any], out_dir: str | Path) -> tuple[Path, Path]:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    json_path = path / "result.json"
    md_path = path / "report.md"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return md_path, json_path
