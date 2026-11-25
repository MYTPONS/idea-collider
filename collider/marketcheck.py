"""真实市场判据 CLI。

用法：
  python -m collider.marketcheck --runs 'runs/*/candidates.jsonl' --out runs/marketcheck
  python -m collider.marketcheck --runs 'runs/*/candidates.jsonl' --out runs/marketcheck --evidence runs/novelty_audit/live_evidence.jsonl
  python -m collider.marketcheck --regression          # 用 15 条已核记录做回归

产出（--out 目录下）：market_verdicts.jsonl（逐候选）、summary.md、unchecked.jsonl（待检索清单）。
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

from .market import load_catalog, judge, Verdict

ROOT = Path(__file__).resolve().parent.parent


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _rows_from(pattern: str) -> list[dict[str, Any]]:
    rows = []
    for f in sorted(glob.glob(str(ROOT / pattern))):
        for r in _load_jsonl(f):
            r["_run"] = Path(f).parent.name
            rows.append(r)
    return rows


def _pick_form_key(r: dict[str, Any]) -> str:
    return r.get("form") or f'{r.get("name","")}|{r.get("mechanism","")}'


def run(patterns: list[str], out: Path, evidence_path: str | None) -> dict[str, Any]:
    catalog = load_catalog()
    evidence = _load_jsonl(evidence_path) if evidence_path else []

    rows: list[dict[str, Any]] = []
    for pat in patterns:
        rows.extend(_rows_from(pat))
    if not rows:
        raise SystemExit(f"no candidate rows matched: {patterns}")

    out.mkdir(parents=True, exist_ok=True)
    verdicts = []
    for r in rows:
        if not r.get("mechanism"):
            verdicts.append({
                "run": r.get("_run", ""), "mechanism": "", "name": r.get("name", ""),
                "form": _pick_form_key(r), "old_novelty": r.get("novelty"),
                "market": "legacy", "product": "", "source": "",
                "reason": "legacy row: no mechanism field (old exp runs, pre-mechanism layer)",
            })
            continue
        v: Verdict = judge(r.get("mechanism", ""), r.get("name", ""), catalog, evidence)
        verdicts.append({
            "run": r.get("_run", ""),
            "mechanism": r.get("mechanism", ""),
            "name": r.get("name", ""),
            "form": _pick_form_key(r),
            "old_novelty": r.get("novelty"),
            "market": v.state,
            "product": v.product,
            "source": v.source,
            "reason": v.reason,
        })
    (out / "market_verdicts.jsonl").write_text(
        "\n".join(json.dumps(v, ensure_ascii=False) for v in verdicts) + "\n", encoding="utf-8")

    # 汇总
    def key_of(run_names: list[str] | None = None):
        seen = {}
        for v in verdicts:
            if run_names and v["run"] not in run_names:
                continue
            seen.setdefault(v["form"], v)
        return seen

    all_forms = key_of()
    cur_runs = ["memory-saas", "ai-industry", "ai-forensics", "ai-doc", "companion-casino"]
    cur_forms = key_of(cur_runs)

    from collections import Counter
    def dist(forms):
        return dict(Counter(v["market"] for v in forms.values()))

    unchecked = [v for v in cur_forms.values() if v["market"] == "unchecked"]
    (out / "unchecked.jsonl").write_text(
        "\n".join(json.dumps(v, ensure_ascii=False) for v in unchecked) + "\n", encoding="utf-8")

    old = dict(Counter(str(v["old_novelty"]) for v in verdicts))
    summary = {
        "candidates": len(verdicts),
        "old_blank": old.get("blank", 0),
        "distinct_forms_all": len(all_forms),
        "distinct_forms_current": len(cur_forms),
        "market_all": dist(all_forms),
        "market_current": dist(cur_forms),
        "unchecked_current": len(unchecked),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary_md(out / "summary.md", summary, cur_forms)
    return summary


def _write_summary_md(path: Path, s: dict[str, Any], cur_forms: dict[str, dict[str, Any]]) -> None:
    lines = [
        "# 真实市场判据统计",
        "",
        f"- 候选数：{s['candidates']}",
        f"- 旧判据标 `blank`（市场没有）的：{s['old_blank']}",
        f"- 去重形态：全部 {s['distinct_forms_all']}，当前 5 runs {s['distinct_forms_current']}",
        "",
        f"**当前 5 runs 去重形态的真实市场分布**：{s['market_current']}",
        "",
        f"**全部去重形态**：{s['market_all']}",
        "",
        "## 当前仍 `unchecked`（没证据，只代表「不在已知表里」）",
        "",
    ]
    for v in cur_forms.values():
        if v["market"] == "unchecked":
            lines.append(f"- {v['form']}  [{v['mechanism']}]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def regression() -> int:
    """用 market_checks.jsonl 里 15 条已核 blank，验证新判据全部判 existing。"""
    catalog = load_catalog()
    checks = _load_jsonl("runs/novelty_audit/market_checks.jsonl")
    ok = 0
    for c in checks:
        v = judge(c["mechanism"], c["name"], catalog, None)
        mark = "OK " if v.state == "existing" else "FAIL"
        if v.state == "existing":
            ok += 1
        print(f"{mark} {c['name']:8s} claimed={c['claimed']:6s} -> {v.state:9s} ({v.product})")
    print(f"\nregression: {ok}/{len(checks)} caught")
    return 0 if ok == len(checks) else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["runs/*/candidates.jsonl"])
    ap.add_argument("--out", default="runs/marketcheck")
    ap.add_argument("--evidence", default=None)
    ap.add_argument("--regression", action="store_true")
    args = ap.parse_args()
    if args.regression:
        raise SystemExit(regression())
    s = run(args.runs, ROOT / args.out, args.evidence)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
