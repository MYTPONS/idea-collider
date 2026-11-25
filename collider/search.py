from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .mechanisms import Mechanism, mechanisms_by_axis, mechanisms_for
from .symptoms import symptoms_for
from .schema import GateResult

FAR_STYLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("删除", ("freeze", "revoke", "shard_store", "shadow_copy", "time_lock", "watermark", "discard", "stateless")),
    ("更正", ("replay", "multi_witness", "approval_gate", "revoke", "watermark", "proof_hash")),
    ("查阅", ("ro_snapshot", "tiered_disclosure", "differential_privacy", "shard_store", "proof_hash", "decentralized_audit", "export", "portable_format", "notarize", "session_capture", "invoice_split", "escrow_release", "multi_witness")),
    ("限期", ("threshold_alert", "queue", "time_lock", "approval_gate", "replay", "cooling_off", "segment_release", "minor_gate")),
    ("义务", ("escrow_release", "deposit", "cooling_off", "segment_release", "order_binding", "session_capture", "minor_gate", "invoice_split", "allowlist", "approval_gate", "tiered_disclosure", "notarize")),
    ("禁止", ("order_binding", "minor_gate", "cooling_off", "allowlist", "approval_gate")),
)


def near_style(text: str) -> str:
    if any(word in text for word in ("不允许用户直接写入", "没有写入权", "不能改", "不可修改", "只读", "无权写入")):
        return "禁写"
    if any(word in text for word in ("不留存", "不保留", "不许留", "不存原始")):
        return "断裂"
    # 「上游账号会在通知的情况下失效」先撞上「账号」就会被判成绑定。
    # 断连/失效是更能定性的一根轴,放在账户词之前。
    if any(word in text for word in ("断连", "断裂", "归零", "上游", "中断", "失效", "不可用", "停机", "失联", "跳单", "跑单", "不来")):
        return "断裂"
    if any(word in text for word in ("账户", "绑定", "对公", "收款", "实名", "账号", "抽成", "提现", "结算", "开票")):
        return "绑定"
    if any(word in text for word in ("改写", "漂移", "覆盖", "变更", "悄悄改", "虚报", "货不对板")):
        return "改写"
    if any(word in text for word in ("承诺", "成本", "身份", "保证", "计价", "预算", "退款", "退单", "退给", "退货", "赔付")):
        return "承诺"
    if any(word in text for word in ("打扰", "推送", "通知", "提醒", "弹窗", "辱骂", "骚扰", "封号")):
        return "打扰"
    return ""


AXIS_STYLE_FAR = {
    "compliance": "查阅",
    "time": "限期",
    "version": "更正",
    "trust": "更正",
    "observation": "查阅",
    "cost": "限期",
    "space": "查阅",
    "network": "查阅",
    "supply": "限期",
    "availability": "限期",
    "market": "限期",
}

AXIS_STYLE_NEAR = {
    "availability": "断裂",
    "version": "改写",
    "trust": "承诺",
    "compliance": "承诺",
    "time": "限期",
    "cost": "承诺",
    "market": "承诺",
    "supply": "断裂",
    "network": "断裂",
    "observation": "承诺",
    "space": "断裂",
}


def far_style(far_text: str) -> str:
    """远域约束讲的是哪一种要求。

    顺序很重要:**先说动作,再说禁令**。一条规定里出现「查阅/更正/删除/留存」
    就说明它在讲这件事,哪怕同时带着「不得」——「必须在期限内响应查阅、更正、
    删除请求,不得以没有这个功能为由拒绝」讲的是三项权利,不是禁令。

    「不准确」「不完全」里的「不准」也不是禁令,先抹掉再判。
    """
    if any(word in far_text for word in ("删除", "清除", "erase", "销毁", "抹掉")):
        return "删除"
    if any(word in far_text for word in ("更正", "改正", "修正", "纠正", "撤回", "修改")):
        return "更正"
    if any(word in far_text for word in ("查阅", "查询", "查看", "复制", "获取", "导出", "访问")):
        return "查阅"
    if any(word in far_text for word in ("留存", "保留", "存档", "留痕", "备份", "日志", "底稿", "保存")):
        return "查阅"
    if any(word in far_text for word in ("时限", "期限", "到期", "天内", "日内", "小时内", "周期内", "不少于")):
        return "限期"
    negative_text = re.sub(r"不准(?:确|全)", "", far_text)
    if any(word in negative_text for word in ("禁止", "严禁", "不得", "不许", "不准", "取缔")):
        return "禁止"
    if any(word in far_text for word in ("评估", "审计", "报告", "制度", "预案", "培训", "宣传")):
        return "其他"
    if any(word in far_text for word in ("应当", "必须", "要求", "负责", "建立", "采取", "落实", "执行", "核验", "实名")):
        return "义务"
    return ""


def _style_ids(style: str) -> tuple[str, ...]:
    for name, ids in FAR_STYLES:
        if name == style:
            return ids
    return ()


def infer_params(near_text: str, far_text: str) -> tuple[str, str]:
    if "改写" in near_text:
        timing = "改写前"
    elif "断连" in near_text or "断裂" in near_text or "归零" in near_text:
        timing = "断连时"
    elif "账户" in near_text:
        timing = "账户内"
    else:
        timing = ""
    if "删除" in far_text:
        scope = "全量"
    elif "更正" in far_text:
        scope = "单条"
    elif "查阅" in far_text or "查询" in far_text:
        scope = "可查视图"
    elif "时限" in far_text or "期限" in far_text:
        scope = "限时"
    else:
        scope = "全量"
    return timing, scope


def _score(mechanism: Mechanism, near_text: str, far_text: str) -> int:
    """机制名关键词(白名单/放行/名单)命中近域或远域的次数。

    只统计两字以上的词:单字「看」「查」会命中「查阅权」「查看」这类
    远域表述,让任何约束都靠一个「查」字过关。
    """
    text = near_text + far_text
    return sum(1 for keyword in mechanism.keywords if len(keyword) >= 2 and keyword in text)


def _symptom_score(mechanism: Mechanism, near_text: str) -> int:
    """机制能解的症状词在近域文本里命中几次。按多字词计数。"""
    return sum(1 for word in symptoms_for(mechanism.id) if word in near_text)


def search_mechanisms(
    near_results: list[GateResult],
    far_results: list[GateResult],
    min_score: int = 1,
    near_styles: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    near = [r for r in near_results if r.passed]
    far = [r for r in far_results if r.passed]
    styles = near_styles or {}
    picks: list[tuple[GateResult, GateResult, int, Mechanism, int, str, str, str, str, int, int, int]] = []
    for n in near:
        for f in far:
            timing, scope = infer_params(n.statement.text, f.statement.text)
            style = (
                styles.get(n.statement.id)
                or near_style(n.statement.text)
                or AXIS_STYLE_NEAR.get(n.axis or "", "")
            )
            far_type = far_style(f.statement.text) or AXIS_STYLE_FAR.get(f.axis or "", "")
            allowed = _style_ids(far_type)
            for rank, mechanism in _candidates(n.axis, f.axis):
                # pairs 是机制自己声明的「近域类型 × 远域类型」职责表,比 FAR_STYLES
                # 白名单更具体。声明了 pairs 就只认 pairs;没声明才退回白名单。
                if mechanism.pairs:
                    if style and far_type and (style, far_type) not in mechanism.pairs:
                        continue
                else:
                    if allowed and mechanism.id not in allowed:
                        continue
                    if mechanism.targets and style and style not in mechanism.targets:
                        continue
                    if mechanism.targets_far and far_type and far_type not in mechanism.targets_far:
                        continue
                kw_near = _score(mechanism, n.statement.text, "")
                kw_far = _score(mechanism, f.statement.text, "")
                kw = kw_near + kw_far
                sym = _symptom_score(mechanism, n.statement.text)
                if sym == 0 and kw < min_score:
                    continue
                # 没有声明 pairs 的机制只能靠远域白名单进,这一层最弱:
                # 远域必须自己留下证据(机制名或它解的症状出现在远域原文里),
                # 否则「白名单」会跟「内容标识」这种毫不相干的约束配在一起。
                if not mechanism.pairs:
                    far_sym = sum(1 for w in symptoms_for(mechanism.id) if w in f.statement.text)
                    if kw_far == 0 and far_sym == 0:
                        continue
                score = kw + sym + (2 if rank == 0 else 1)
                picks.append((n, f, rank, mechanism, score, timing, scope, style, far_type, kw, sym, kw_far))
    freq = Counter(mechanism.id for _, _, _, mechanism, _, _, _, _, _, _, _, _ in picks)
    rows: list[dict[str, Any]] = []
    for n, f, rank, mechanism, score, timing, scope, style, far_type, kw, sym, kw_far in picks:
        penalty = 0.15 * math.log(freq[mechanism.id])
        rows.append(
            {
                "near": n.statement.id,
                "far": f.statement.id,
                "near_text": n.statement.text,
                "far_text": f.statement.text,
                "near_style": style,
                "far_type": far_type,
                "near_axis": n.axis,
                "far_axis": f.axis,
                "mechanism": mechanism.id,
                "timing": timing,
                "scope": scope,
                "name": mechanism.name,
                "form": f"{timing}{mechanism.name}（{scope}）｜{mechanism.action}",
                "must": f"{n.statement.text}；同时{f.statement.text}",
                "cost": mechanism.cost,
                "effort": mechanism.effort,
                "first_step": mechanism.first_step,
                "rank": rank,
                "kw": kw,
                "kw_far": kw_far,
                "sym": sym,
                "score": score,
                "freq": freq[mechanism.id],
                "adjusted": round(score - penalty, 3),
            }
        )
    rows.sort(key=lambda row: (-row["adjusted"], row["near"], row["far"]))
    return rows


def _candidates(near_axis: str | None, far_axis: str | None):
    seen: set[str] = set()
    for mechanism in mechanisms_for(near_axis, far_axis):
        if mechanism.id in seen:
            continue
        seen.add(mechanism.id)
        yield 0, mechanism
    for axis in (near_axis, far_axis):
        if not axis:
            continue
        for mechanism in mechanisms_by_axis(axis):
            if mechanism.id in seen:
                continue
            seen.add(mechanism.id)
            yield 1, mechanism
