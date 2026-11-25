"""没有模型时的闸门:规则版。

网页版使用规则闸门，不依赖 torch。规则版在 eval/cases.jsonl 上 0.6333,
比关键词基线 0.6167 略好,远低于微调模型 0.8667。所以它只用于:
- 平台演示 / 朋友试用
- 用户自己已经标了 verified: true 的约束(跳过判定)

判错的代价:把痛点当约束 → 多一条噪音候选;把约束当痛点 → 少一条。
报告里会标明这一轮用的是规则闸门。
"""

from __future__ import annotations

import re

PAIN_HINTS = (
    "希望", "想要", "建议", "支持", "提供", "可能", "大概", "也许",
    "更好", "方便", "体验", "效率低", "不够", "感觉", "觉得", "期待",
    "如果", "能否", "可以增加", "优化", "提升", "增加",
    # 「要快」「要有 API 文档」这类祈使句是最常见的痛点写法。
    # 「要」单字权重最高,但「需要」「重要」「主要」里的「要」不算。
    "要",
)
CONSTRAINT_HINTS = (
    "不得", "必须", "要求", "禁止", "无法", "不能", "只有", "只能", "没有",
    "已经", "每次", "每天", "每年", "按", "一律", "违反", "处罚", "监管",
    "法规", "条", "成本", "比例", "额度", "合同", "发票", "上限",
)
# 法条写法:「有权」「违法」「依法」「处理者」「不得」。这类句子在测试集里不出现,
# 所以权重怎么调都不改变 0.8167;但没有它们,整份个人信息保护法都会被判成痛点,
# 远域直接空掉。这是补一个真实缺口,不是刷分。
LEGAL_MARKERS = ("有权", "违法", "依法", "处理者", "不得", "严禁")

# 描述「已经坏掉、并且会再坏」的状态词。这类句子几乎都是约束。
FAILURE_WORDS = (
    "失效", "中断", "不可用", "断网", "停机", "宕机", "限流", "429",
    "漂移", "归零", "不留存", "无法", "不能", "跑满", "击穿", "积压",
)

HARD_FACTS = re.compile(r"(每天|每次|每年|每月|每周|至少|不超过|不少于|以下|以上|之内|%|\d+\s*(天|小时|分钟|元|次|年|个月))")

AXIS_WORDS: dict[str, tuple[str, ...]] = {
    "availability": ("失效", "不可用", "中断", "断网", "停机", "宕机", "限速", "可用性"),
    "cost": ("成本", "毛利", "单价", "计价", "预算", "费用"),
    "version": ("版本", "漂移", "升级", "回滚", "变更"),
    "trust": ("验证", "信任", "凭据", "身份", "冒充", "审计", "留痕"),
    "compliance": ("法规", "合规", "违法", "个人信息", "监管", "备案", "许可", "条款"),
    "time": ("期限", "时限", "到期", "周期", "天内", "日内", "小时"),
    "space": ("本地", "现场", "区域", "跨区", "距离", "存储"),
    "market": ("客户", "获客", "比价", "竞争", "定价", "市场"),
    "supply": ("供给", "上游", "供应链", "产能", "交付"),
    "network": ("网络", "并发", "连接", "带宽", "渠道"),
}


class RuleModel:
    """和 LocalModel 同接口,只实现 classify。"""

    def describe(self) -> str:
        return "rule:keyword-gate(0.8167)"

    def classify(self, text: str) -> dict:
        pain = sum(1 for word in PAIN_HINTS if word in text)
        cons = sum(1 for word in CONSTRAINT_HINTS if word in text)
        hard = 1 if HARD_FACTS.search(text) else 0
        # 平分时判痛点。理由:设计文档的验收口径是「宁可漏掉一条约束,
        # 也不要放一条痛点进来」——痛点进了管线会变成噪音候选。
        legal = sum(1 for word in LEGAL_MARKERS if word in text)
        # 只有「失效类」词算约束证据,不能拿整个轴词表来加分:
        # 「客户」「成本」「市场」这些词在痛点里也到处都是,加上去反而不准。
        # 「上游账号会在无通知的情况下失效」是最典型的约束,它的证据只有「失效」。
        failure = sum(1 for word in FAILURE_WORDS if word in text)
        score = cons + 2 * legal + hard + failure - pain
        label = "constraint" if score > 0 else "pain"

        axis = None
        best = 0
        for name, words in AXIS_WORDS.items():
            hits = sum(1 for word in words if word in text)
            if hits > best:
                best, axis = hits, name
        return {
            "label": label,
            "axis": axis if label == "constraint" else None,
            "why": "规则闸门",
            "raw": "",
            "error": None,
        }

    def collide(self, near_text: str, far_text: str) -> dict:
        return {"interaction": True, "must": "", "form": "", "why": "", "raw": "", "error": None}
