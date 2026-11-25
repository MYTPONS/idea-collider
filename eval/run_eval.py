import json
import os
import sys
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

BASE_URL = os.environ.get("EVAL_BASE_URL", "http://127.0.0.1:11434/v1")
API_KEY = os.environ.get("EVAL_API_KEY", "none")
MODEL = os.environ.get("EVAL_MODEL", "qwen3:8b")
CONCURRENCY = int(os.environ.get("EVAL_CONCURRENCY", "4"))

SYSTEM = """你在做一项分类任务。给一段表述,判断它是「约束」还是「痛点」。

约束的定义:外部强加、不可协商、能判真假。违反它有物理、经济或法律的直接后果。
痛点、预测、期望、功能条目、感受,都不是约束。

判定要点:
- 已经发生过的事实可能是约束;还没发生、只是推测会发生的,不是约束。
- 能具体到阈值、比例、规则、法规条文的,倾向约束。
- 带有「应该」「希望」「要」「会」「可能」的,倾向不是约束。
- 功能列表(支持某事)不是约束。
- 无法判真假的表述不是约束。

只输出一个 JSON 对象,不要别的文字:
{"label": "constraint" 或 "pain", "reason": "一句话理由"}"""


def call(text):
    body = json.dumps(
        {
            "model": MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": text},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + API_KEY,
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def parse(raw):
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        obj = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    label = str(obj.get("label", "")).strip().lower()
    if label in ("constraint", "约束"):
        return "constraint"
    if label in ("pain", "痛点"):
        return "pain"
    return None


def run_case(case):
    t0 = time.time()
    try:
        raw = call(case["text"])
        pred = parse(raw)
        err = None if pred else "unparseable"
    except Exception as exc:
        raw = ""
        pred = None
        err = type(exc).__name__ + ": " + str(exc)[:120]
    return {
        "text": case["text"],
        "gold": case["label"],
        "pred": pred,
        "axis": case.get("axis"),
        "why": case.get("why"),
        "raw": raw,
        "error": err,
        "secs": round(time.time() - t0, 2),
    }


def main():
    rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else "eval/cases.jsonl") if l.strip()]
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(run_case, rows))

    ok = [r for r in results if r["pred"] == r["gold"]]
    bad = [r for r in results if r["pred"] != r["gold"]]
    unparsed = [r for r in results if r["pred"] is None]

    print("model       ", MODEL)
    print("total       ", len(results))
    print("accuracy    ", round(len(ok) / len(results), 4))
    print("unparseable ", len(unparsed))
    print()

    labels = ["constraint", "pain"]
    for gold in labels:
        for pred in labels:
            n = sum(1 for r in results if r["gold"] == gold and r["pred"] == pred)
            print(f"{gold:11s} -> {pred:11s} {n}")
    print()

    by_axis = {}
    for r in results:
        bucket = by_axis.setdefault(r["axis"], [0, 0])
        bucket[1] += 1
        if r["pred"] == r["gold"]:
            bucket[0] += 1
    print("per axis (correct/total)")
    for axis, (good, total) in sorted(by_axis.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        print(f"  {axis:13s} {good}/{total}")
    print()

    print("errors")
    for r in bad:
        print(f"  gold={r['gold']:10s} pred={str(r['pred']):10s} axis={r['axis']}")
        print(f"    text: {r['text'][:90]}")
        print(f"    why : {r['why']}")
    print()

    out = os.environ.get("EVAL_OUT", "eval/result.json")
    summary = {
        "model": MODEL,
        "accuracy": round(len(ok) / len(results), 4),
        "unparseable": len(unparsed),
        "errors": len(bad),
        "per_axis": {k: {"correct": v[0], "total": v[1]} for k, v in by_axis.items()},
    }
    with open(out, "w") as fh:
        json.dump({"summary": summary, "results": results}, fh, ensure_ascii=False, indent=2)
    print("written", out)


if __name__ == "__main__":
    main()
