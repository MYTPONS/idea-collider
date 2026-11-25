import json

from collider.lineage import match_known
from collider.symptoms import symptoms_for

PRODUCTS = [
    {"name": "New API", "satisfies": ["多上游路由", "渠道管理", "额度计费"], "gap": "返回的 model 字段来自渠道配置,不能证明上游真的是哪个模型;没有面向客户的凭据"},
    {"name": "阿里云 Memory", "satisfies": ["跨会话记忆", "自动提取"], "gap": "不提供最终用户自助的查阅、导出、删除入口"},
    {"name": "Claude Duet", "satisfies": ["记忆调用", "操作前审批"], "gap": "审批只覆盖操作,不覆盖画像本身的查看、更正与导出"},
    {"name": "Replit Monitoring Agent", "satisfies": ["自动告警响应", "变更留痕"], "gap": "只覆盖工程运维场景,不处理用户侧数据与合规请求"},
    {"name": "OpenRouter", "satisfies": ["多模型聚合", "用量计费"], "gap": "托管方自己就是信任源,不提供第三方可验证的证据"},
    {"name": "CLIProxyAPI", "satisfies": ["订阅转 API", "多账号池"], "gap": "账号属于个人订阅,高并发触发风控,没有对客户的可用性承诺"},
]


def test_products_that_already_solve_it_are_marked_taken():
    got = match_known("allowlist", PRODUCTS)
    assert got["verdict"] == "gap"  # 只有账号池产品,没有白名单能力
    got = match_known("approval_gate", PRODUCTS)
    assert got["product"] == "Claude Duet"


def test_gap_lineage_finds_the_product_that_left_it_open():
    got = match_known("ro_snapshot", PRODUCTS)
    assert got["verdict"] == "gap"
    assert got["product"] == "阿里云 Memory"
    assert "查阅" in got["gap"]


def test_mechanism_with_no_matching_symptom_has_no_lineage():
    assert match_known("lottery", PRODUCTS) is None


def test_every_mechanism_has_a_symptom_list():
    from collider.mechanisms import MECHANISMS

    for mechanism in MECHANISMS:
        assert symptoms_for(mechanism.id), f"{mechanism.id} 没有症状词"


def test_mechanism_ids_are_unique():
    from collider.mechanisms import MECHANISMS

    ids = [m.id for m in MECHANISMS]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
