from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CONSTRAINT_AXES = (
    "availability",
    "cost",
    "version",
    "trust",
    "compliance",
    "time",
    "space",
    "market",
    "supply",
    "network",
    "observation",
)

PAIN_AXES = ("prediction", "feeling", "feature", "wish")

ALL_AXES = CONSTRAINT_AXES + PAIN_AXES

AXIS_GROUP = {**{a: "constraint" for a in CONSTRAINT_AXES}, **{a: "pain" for a in PAIN_AXES}}

AXIS_ZH = {
    "availability": "可用性",
    "cost": "成本",
    "version": "版本",
    "trust": "信任",
    "compliance": "合规",
    "time": "时间",
    "space": "空间",
    "market": "市场",
    "supply": "供给侧",
    "network": "网络",
    "observation": "已观察事实",
    "prediction": "预测",
    "feeling": "感受",
    "feature": "功能条目",
    "wish": "愿望",
}

DIMENSIONS = ("existing", "blocker", "mvp", "first_customer")

DIMENSION_ZH = {
    "existing": "现在有人做吗",
    "blocker": "做的人卡在哪",
    "mvp": "两周内能出最小可验证版本吗",
    "first_customer": "第一个客户是谁、从哪认识",
}


@dataclass
class Statement:
    id: str
    text: str
    domain: str = "near"
    source: str = ""
    verified: bool = False


@dataclass
class GateResult:
    statement: Statement
    label: str | None
    axis: str | None
    why: str
    raw: str = ""
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.label == "constraint" and self.error is None


@dataclass
class DimensionResult:
    name: str
    ok: bool
    detail: str


@dataclass
class Candidate:
    id: str
    near: Statement
    far: Statement
    interaction: bool
    must: str
    form: str
    why: str
    raw: str = ""
    evidence: dict[str, Any] | None = None
    dimensions: dict[str, DimensionResult] = field(default_factory=dict)
    verdict: str = "draft"


def statement_to_dict(stmt: Statement) -> dict[str, Any]:
    return {
        "id": stmt.id,
        "text": stmt.text,
        "domain": stmt.domain,
        "source": stmt.source,
        "verified": stmt.verified,
    }


def statement_from_dict(obj: dict[str, Any]) -> Statement:
    return Statement(
        id=str(obj["id"]),
        text=str(obj["text"]),
        domain=str(obj.get("domain", "near")),
        source=str(obj.get("source", "")),
        verified=bool(obj.get("verified") or obj.get("human_verified")),
    )


def gate_to_dict(result: GateResult) -> dict[str, Any]:
    return {
        **statement_to_dict(result.statement),
        "label": result.label,
        "axis": result.axis,
        "why": result.why,
        "error": result.error,
    }


def gate_from_dict(obj: dict[str, Any]) -> GateResult:
    return GateResult(
        statement=statement_from_dict(obj),
        label=obj.get("label"),
        axis=obj.get("axis"),
        why=str(obj.get("why", "")),
        error=obj.get("error"),
    )


def candidate_to_dict(cand: Candidate) -> dict[str, Any]:
    return {
        "id": cand.id,
        "near": statement_to_dict(cand.near),
        "far": statement_to_dict(cand.far),
        "interaction": cand.interaction,
        "must": cand.must,
        "form": cand.form,
        "why": cand.why,
        "evidence": cand.evidence,
        "dimensions": {
            name: {"ok": d.ok, "detail": d.detail} for name, d in cand.dimensions.items()
        },
        "verdict": cand.verdict,
    }


def candidate_from_dict(obj: dict[str, Any]) -> Candidate:
    dims = {
        name: DimensionResult(name=name, ok=bool(d["ok"]), detail=str(d["detail"]))
        for name, d in (obj.get("dimensions") or {}).items()
    }
    cand = Candidate(
        id=str(obj["id"]),
        near=statement_from_dict(obj["near"]),
        far=statement_from_dict(obj["far"]),
        interaction=bool(obj.get("interaction", True)),
        must=str(obj.get("must", "")),
        form=str(obj.get("form", "")),
        why=str(obj.get("why", "")),
        evidence=obj.get("evidence"),
        dimensions=dims,
        verdict=str(obj.get("verdict", "draft")),
    )
    return cand
