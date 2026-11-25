from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:  # 网页版和纯代码路径不依赖 torch
    from .model import LocalModel
except ImportError:  # pragma: no cover - 只在没装 torch 的环境触发
    LocalModel = None  # type: ignore[assignment]

from .axes import axis_report
from .cards import load_profile
from .cardreport import render_cards
from .onboarding import write_template
from .collide import CollideStats, collide_pairs
from .extract import extract_from_file
from .filter import apply_filter, load_evidence
from .forge import build_candidates, load_pack, load_pack_entry, summarize
from .gate import gate_statements, gate_summary
from .novelty import judge, load_known
from .relate import relate_pairs
from .report import build_result, write_report
from .search import search_mechanisms
from .schema import (
    Statement,
    candidate_from_dict,
    candidate_to_dict,
    gate_from_dict,
    gate_to_dict,
    statement_to_dict,
)

ROOT = Path(__file__).resolve().parent.parent


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line in _resolve(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    target.write_text(text + "\n", encoding="utf-8")


def _read_statements(path: str | Path, domain: str) -> list[Statement]:
    rows = _read_jsonl(path)
    statements = []
    for index, row in enumerate(rows, start=1):
        prefix = "a" if domain == "near" else "b"
        statements.append(
            Statement(
                id=str(row.get("id") or f"{prefix}{index:02d}"),
                text=str(row["text"]),
                domain=domain,
                source=str(row.get("source", "")),
                verified=bool(row.get("verified") or row.get("human_verified")),
            )
        )
    return statements


def _progress(label: str):
    def report(done: int, total: int) -> None:
        if done % 5 == 0 or done == total:
            print(f"{label} {done}/{total}", flush=True)

    return report


def _load_model(args: argparse.Namespace):
    if LocalModel is None:
        raise SystemExit(
            "这台机器上没有 torch,跑不了本地模型。用 `collider web` 走规则闸门,"
            "或者先装 torch 再用 forge。"
        )
    return LocalModel(model_dir=args.model_dir, device=args.device)


def _load_model_at(args: argparse.Namespace, path: str | None):
    if not path:
        return _load_model(args)
    original = args.model_dir
    args.model_dir = path
    model = _load_model(args)
    args.model_dir = original
    return model


def cmd_gate(args: argparse.Namespace) -> int:
    model = _load_model(args)
    statements = _read_statements(args.input, args.domain)
    results = gate_statements(statements, model, limit=args.limit, progress=_progress("gate"))
    _write_jsonl(args.out, [gate_to_dict(r) for r in results])
    summary = gate_summary(results)
    report = axis_report(results)
    print(json.dumps({"model": model.describe(), **summary}, ensure_ascii=False, indent=2))
    for warning in report["warnings"]:
        print(f"警告:{warning}")
    return 0


def cmd_axes(args: argparse.Namespace) -> int:
    results = [gate_from_dict(row) for row in _read_jsonl(args.input)]
    print(json.dumps(axis_report(results), ensure_ascii=False, indent=2))
    return 0


def cmd_relate(args: argparse.Namespace) -> int:
    original = args.model_dir
    if args.relate_model:
        args.model_dir = args.relate_model
    model = _load_model(args)
    args.model_dir = original
    near = _read_statements(args.near, "near")
    far = _read_statements(args.far, "far")
    kept, stats = relate_pairs(
        near, far, model, limit=args.limit, progress=_progress("relate")
    )
    rows = [
        {"near": n.id, "far": f.id, "near_text": n.text, "far_text": f.text}
        for n, f in kept
    ]
    _write_jsonl(args.out, rows)
    print(
        json.dumps(
            {
                "model": model.describe(),
                "pairs": stats.pairs,
                "related": stats.related,
                "errors": stats.errors,
                "out": str(_resolve(args.out)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_pack(pack_id: str) -> tuple[str, str]:
    try:
        near, far = load_pack(pack_id, _resolve("data/packs/index.json"))
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc
    return str(near), str(far)


def cmd_packs(args: argparse.Namespace) -> int:
    data = json.loads(_resolve("data/packs/index.json").read_text(encoding="utf-8"))
    for pack in data.get("packs", []):
        print(f'{pack["id"]}\t{pack["name"]}')
    return 0


def _load_types(path: str) -> dict[str, str]:
    from .forge import load_types

    return load_types(_resolve(path), _resolve("data/domains/types.json"))


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp import serve as serve_mcp

    serve_mcp()
    return 0


def cmd_api(args: argparse.Namespace) -> int:
    from .agenthttp import serve as serve_api

    serve_api(args.host, args.port)
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from .webapp import serve as serve_web

    serve_web(args.host, args.port, args.prefix)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .serve import serve

    serve(args.model_dir, args.host, args.port, _resolve(args.usage), _resolve(args.clients))
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    model = _load_model(args)
    path = _resolve(args.input)
    kept, results = extract_from_file(path, model, domain=args.domain)
    _write_jsonl(args.out, [statement_to_dict(stmt) for stmt in kept])
    print(
        json.dumps(
            {
                "input": str(path),
                "model": model.describe(),
                "sentences": len(results),
                "kept": len(kept),
                "out": str(_resolve(args.out)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    model = _load_model(args)
    near_results = gate_statements(
        _read_statements(args.near, "near"), model, progress=_progress("gate-near")
    )
    far_results = gate_statements(
        _read_statements(args.far, "far"), model, progress=_progress("gate-far")
    )
    rows = search_mechanisms(
        near_results, far_results, min_score=args.min_score, near_styles=_load_types(args.near)
    )
    _write_jsonl(args.out, rows)
    both = [row for row in rows if row["rank"] == 0]
    one = [row for row in rows if row["rank"] == 1]
    print(
        json.dumps(
            {
                "model": model.describe(),
                "near_passed": len([r for r in near_results if r.passed]),
                "far_passed": len([r for r in far_results if r.passed]),
                "candidates": len(rows),
                "cover_both": len(both),
                "cover_one": len(one),
                "out": str(_resolve(args.out)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    for row in both[: args.show]:
        print(f'{row["near"]}x{row["far"]} | {row["form"]} | 代价:{row["cost"]}')
    return 0


def _gate_side(side: str, doc: str | None, data: str | None, model, tag: str):
    if doc:
        kept, results = extract_from_file(_resolve(doc), model, domain=tag)
        return [result for result in results if result.passed]
    return gate_statements(
        _read_statements(data, tag), model, progress=_progress(f"gate-{tag}")
    )


def _unverified_count(results) -> int:
    return sum(1 for r in results if not r.statement.verified)


def _resolve_materials(args: argparse.Namespace) -> dict[str, Any]:
    """决定这一轮用哪四份素材:近域、远域、已知产品、证据。

    平台上的人可能什么都没带。不接等于拒客,瞎编远域又违反设计文档。
    所以按「有包 → 有材料 → 通用兜底」三档退,并把退到哪一档记在
    `notes` 里,报告和 stdout 都要说出来。
    """
    notes: list[str] = []
    pack_entry: dict[str, Any] = {}

    if args.pack:
        near, far = _load_pack(args.pack)
        pack_entry = load_pack_entry(args.pack)
        args.near, args.far = near, far
        args.near_doc = None
        args.far_doc = None
        return {
            "near": near,
            "far": far,
            "known": args.known or pack_entry.get("known"),
            "evidence": args.evidence or pack_entry.get("evidence"),
            "label": args.pack,
            "mode": "pack",
            "notes": notes,
        }

    generic_near = _resolve("data/domains/generic_near.jsonl")
    generic_far = _resolve("data/domains/generic_far.jsonl")

    near = args.near or args.near_doc
    far = args.far or args.far_doc
    mode = "materials"

    if not near and not far:
        mode = "generic"
        near, far = str(generic_near), str(generic_far)
        args.near_doc = args.far_doc = None
        notes.append("你没给素材:近域用 8 条通用经营约束,远域用 12 条通用合规义务,都是近似,不是你这个行业的事实")
    elif not far:
        mode = "generic-far"
        far = str(generic_far)
        args.far_doc = None
        notes.append("你没给远域:远域用 12 条通用合规义务近似。这一侧的结论必须先复核")
    elif not near:
        mode = "generic-near"
        near = str(generic_near)
        args.near_doc = None
        notes.append("你没给近域:近域用 8 条通用经营约束近似。这些不是你行业里已经发生的事")

    if args.idea:
        notes.append(f"你的方向:{args.idea}(只作为标签,没有当成约束)")

    return {
        "near": near,
        "far": far,
        "known": args.known,
        "evidence": args.evidence,
        "label": args.idea or args.pack or (Path(str(near)).stem if near else "未命名"),
        "mode": mode,
        "notes": notes,
    }


def cmd_forge(args: argparse.Namespace) -> int:
    materials = _resolve_materials(args)
    args.near, args.far = materials["near"], materials["far"]
    model = _load_model(args)
    near_results = _gate_side("near", args.near_doc, args.near, model, "near")
    far_results = _gate_side("far", args.far_doc, args.far, model, "far")
    if args.relate_model:
        relate_model = _load_model_at(args, args.relate_model)
        kept, stats = relate_pairs(
            [r.statement for r in near_results if r.passed],
            [r.statement for r in far_results if r.passed],
            relate_model,
            limit=args.relate_limit,
            progress=_progress("relate"),
        )
        near_ids = {n.id for n, _ in kept}
        far_ids = {f.id for _, f in kept}
        near_results = [r for r in near_results if r.statement.id in near_ids]
        far_results = [r for r in far_results if r.statement.id in far_ids]
        print(
            json.dumps(
                {"relate_pairs": stats.pairs, "related": stats.related, "errors": stats.errors},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
    styles = _load_types(args.near) if args.near else {}
    known_path = materials["known"] or "data/projects/known_products.jsonl"
    known = load_known(_resolve(known_path))
    merged = build_candidates(near_results, far_results, known, near_styles=styles)
    out_dir = _resolve(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "candidates.jsonl", merged)

    profile = load_profile(_resolve(args.profile))
    entries: list[dict[str, Any]] = []
    evidence_path = materials["evidence"]
    if evidence_path:
        evidence_file = _resolve(evidence_path)
        if evidence_file.exists():
            entries = load_evidence(evidence_file)

    summary = summarize(merged, profile, entries, known)
    cards = summary["cards"]
    if cards:
        primary = summary["primary"]
        meta = {
            "pack": materials["label"],
            "mode": materials["mode"],
            "notes": materials["notes"],
            "model": model.describe(),
            "primary": primary,
            "alternates": summary["alternates"],
            "unverified_far": _unverified_count(far_results),
            "unverified_far_items": [
                {"id": r.statement.id, "text": r.statement.text, "source": r.statement.source}
                for r in far_results
                if not r.statement.verified
            ],
            "far_contribution": sum(1 for row in merged if row.get("kw_far", 0) >= 1),
            "far_types": len({row.get("far_type") for row in merged if row.get("far_type")}),
        }
        report = out_dir / "report.md"
        report.write_text(render_cards(cards, meta), encoding="utf-8")
        _write_jsonl(out_dir / "cards.jsonl", cards)
    else:
        report = out_dir / "report.md"
        report.write_text(render_cards([], {
                                            "pack": materials["label"],
                                            "mode": materials["mode"],
                                            "notes": materials["notes"],
                                            "model": model.describe(),
                                            "unverified_far": _unverified_count(far_results),
                                            "far_contribution": sum(1 for row in merged if row.get("kw_far", 0) >= 1)}), encoding="utf-8")
        _write_jsonl(out_dir / "cards.jsonl", [])

    if materials["mode"] != "pack":
        template = write_template(cards, out_dir, materials["label"])
    else:
        template = None

    print(
        json.dumps(
            {
                "model": model.describe(),
                "candidates": len(merged),
                "cards": sum(1 for card in cards if card["status"] == "card"),
                "drafts": len(summary["drafts"]),
                "taken": len(summary["taken"]),
                "primary": summary["primary"]["form"] if summary["primary"] else None,
                "mode": materials["mode"],
                "notes": materials["notes"],
                "report": str(report),
                "template": str(template) if template else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_collide(args: argparse.Namespace) -> int:
    model = _load_model(args)
    near_results = gate_statements(
        _read_statements(args.near, "near"), model, progress=_progress("gate-near")
    )
    far_results = gate_statements(
        _read_statements(args.far, "far"), model, progress=_progress("gate-far")
    )
    near = [r.statement for r in near_results if r.passed]
    far = [r.statement for r in far_results if r.passed]
    candidates, stats = collide_pairs(
        near, far, model, limit=args.limit, progress=_progress("collide"), samples=args.samples
    )
    _write_jsonl(args.out, [candidate_to_dict(c) for c in candidates])
    print(
        json.dumps(
            {
                "model": model.describe(),
                "near_passed": len(near),
                "far_passed": len(far),
                "pairs": stats.pairs,
                "generated": stats.generated,
                "candidates": len(candidates),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_filter(args: argparse.Namespace) -> int:
    candidates = [candidate_from_dict(row) for row in _read_jsonl(args.candidates)]
    entries = load_evidence(_resolve(args.evidence)) if args.evidence else []
    apply_filter(candidates, entries)
    stats = CollideStats(pairs=len(candidates), generated=len(candidates))
    result = build_result(
        args.name,
        "external",
        args.near_domain,
        args.far_domain,
        [],
        [],
        candidates,
        stats,
    )
    md_path, json_path = write_report(result, args.out)
    print(f"report  {md_path}")
    print(f"result  {json_path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = json.loads(_resolve(args.config).read_text(encoding="utf-8"))
    model = _load_model(args)
    forge = _load_model_at(args, args.forge_model)
    near_domain = config["near"].get("domain", "near")
    far_domain = config["far"].get("domain", "far")
    near_results = gate_statements(
        _read_statements(config["near"]["file"], "near"),
        model,
        progress=_progress("gate-near"),
    )
    far_results = gate_statements(
        _read_statements(config["far"]["file"], "far"),
        model,
        progress=_progress("gate-far"),
    )
    near = [r.statement for r in near_results if r.passed]
    far = [r.statement for r in far_results if r.passed]
    limit = args.limit if args.limit is not None else config.get("limit")
    samples = args.samples if args.samples is not None else int(config.get("samples", 1))
    candidates, stats = collide_pairs(
        near, far, forge, limit=limit, progress=_progress("collide"), samples=samples
    )
    evidence_path = args.evidence or config.get("evidence")
    entries = []
    if evidence_path:
        resolved = _resolve(evidence_path)
        if resolved.exists():
            entries = load_evidence(resolved)
        else:
            print(f"警告:证据文件不存在,全部候选按草稿处理 {resolved}", flush=True)
    apply_filter(candidates, entries)
    result = build_result(
        config.get("name", Path(args.config).stem),
        model.describe(),
        near_domain,
        far_domain,
        near_results,
        far_results,
        candidates,
        stats,
    )
    out_dir = _resolve(args.out)
    md_path, json_path = write_report(result, out_dir)
    _write_jsonl(out_dir / "gated_near.jsonl", [gate_to_dict(r) for r in near_results])
    _write_jsonl(out_dir / "gated_far.jsonl", [gate_to_dict(r) for r in far_results])
    _write_jsonl(out_dir / "candidates.jsonl", [candidate_to_dict(c) for c in candidates])
    cand = result["candidates"]
    print(
        json.dumps(
            {
                "model": model.describe(),
                "near_passed": result["near"]["gate"]["passed"],
                "far_passed": result["far"]["gate"]["passed"],
                "pairs": cand["pairs"],
                "generated": cand["generated"],
                "alive": cand["alive"],
                "draft": cand["draft"],
                "report": str(md_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="collider")
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--device", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    gate = sub.add_parser("gate")
    gate.add_argument("--input", required=True)
    gate.add_argument("--out", required=True)
    gate.add_argument("--domain", choices=["near", "far"], default="near")
    gate.add_argument("--limit", type=int, default=None)
    gate.set_defaults(func=cmd_gate)

    axes = sub.add_parser("axes")
    axes.add_argument("--input", required=True)
    axes.set_defaults(func=cmd_axes)

    mcp = sub.add_parser("mcp", help="MCP stdio 服务器,给 agent 挂")
    mcp.set_defaults(func=cmd_mcp)

    api = sub.add_parser("api", help="JSON HTTP 接口,给远端 agent 用")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=18081)
    api.set_defaults(func=cmd_api)

    web = sub.add_parser("web")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8080)
    web.add_argument("--prefix", default="", help="挂在已有服务的子路径下时用,例如 /collider")
    web.set_defaults(func=cmd_web)

    pks = sub.add_parser("packs")
    pks.set_defaults(func=cmd_packs)

    srv = sub.add_parser("serve")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8080)
    srv.add_argument("--usage", default="runs/usage.jsonl")
    srv.add_argument("--clients", default="data/clients.json")
    srv.set_defaults(func=cmd_serve)

    ext = sub.add_parser("extract")
    ext.add_argument("--input", required=True)
    ext.add_argument("--out", required=True)
    ext.add_argument("--domain", default="imported")
    ext.set_defaults(func=cmd_extract)

    srch = sub.add_parser("search")
    srch.add_argument("--near", required=True)
    srch.add_argument("--far", required=True)
    srch.add_argument("--out", required=True)
    srch.add_argument("--show", type=int, default=10)
    srch.add_argument("--min-score", type=int, default=1)
    srch.set_defaults(func=cmd_search)

    forge = sub.add_parser("forge")
    forge.add_argument("--near", default=None)
    forge.add_argument("--far", default=None)
    forge.add_argument("--near-doc", default=None)
    forge.add_argument("--pack", default=None)
    forge.add_argument("--far-doc", default=None)
    forge.add_argument("--out", required=True)
    forge.add_argument("--known", default=None)
    forge.add_argument("--profile", default="data/me.json")
    forge.add_argument("--evidence", default=None)
    forge.add_argument("--relate-model", default=None)
    forge.add_argument("--relate-limit", type=int, default=None)
    forge.add_argument("--idea", default=None, help="一句话说你想做的方向,没有材料时作为标签")
    forge.set_defaults(func=cmd_forge)

    rel = sub.add_parser("relate")
    rel.add_argument("--near", required=True)
    rel.add_argument("--far", required=True)
    rel.add_argument("--out", required=True)
    rel.add_argument("--limit", type=int, default=None)
    rel.add_argument("--relate-model", default=None)
    rel.set_defaults(func=cmd_relate)

    collide = sub.add_parser("collide")
    collide.add_argument("--near", required=True)
    collide.add_argument("--far", required=True)
    collide.add_argument("--out", required=True)
    collide.add_argument("--limit", type=int, default=None)
    collide.add_argument("--samples", type=int, default=1)
    collide.set_defaults(func=cmd_collide)

    filt = sub.add_parser("filter")
    filt.add_argument("--candidates", required=True)
    filt.add_argument("--evidence", default=None)
    filt.add_argument("--out", required=True)
    filt.add_argument("--name", default="staged")
    filt.add_argument("--near-domain", default="near")
    filt.add_argument("--far-domain", default="far")
    filt.set_defaults(func=cmd_filter)

    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--evidence", default=None)
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--samples", type=int, default=None)
    run.add_argument("--forge-model", default=None)
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
