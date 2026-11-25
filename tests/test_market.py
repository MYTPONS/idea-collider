import json
from pathlib import Path

from collider.market import judge, load_catalog, parse_search_output, judge_from_hits, Hit

ROOT = Path(__file__).resolve().parent.parent


def _checks():
    p = ROOT / "tests" / "fixtures" / "market_checks.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_regression_all_verified_blank_are_existing():
    catalog = load_catalog()
    checks = _checks()
    assert len(checks) >= 15
    for c in checks:
        v = judge(c["mechanism"], c["name"], catalog, None)
        assert v.state == "existing", f"{c['name']} not caught: {v.state}"
        assert v.product and v.source


def test_unknown_is_unchecked_not_market_absent():
    catalog = load_catalog()
    v = judge("no_such_mechanism_xyz", "不存在机制", catalog, None)
    assert v.state == "unchecked"  # 绝不能默认 not_found / 市场没有


def test_not_found_requires_search_evidence():
    catalog = load_catalog()
    ev = [{"mechanism": "no_such_mechanism_xyz", "verdict": "not_found", "n_results": 0, "query": "q"}]
    v = judge("no_such_mechanism_xyz", "不存在机制", catalog, ev)
    assert v.state == "not_found"


def test_existing_from_live_evidence():
    catalog = load_catalog()
    ev = [{"mechanism": "no_such_mechanism_xyz", "verdict": "existing",
           "product": "某平台", "source": "https://example.com", "query": "q"}]
    v = judge("no_such_mechanism_xyz", "不存在机制", catalog, ev)
    assert v.state == "existing"
    assert v.product == "某平台"


def test_parse_search_output():
    text = (
        "sources=['bing'] degraded=False elapsed=100ms results=2\n"
        " 1. [1.98] 阿里云 数字水印 产品文档\n"
        "    https://help.aliyun.com/x\n"
        "    视频版权水印\n"
        " 2. [0.10] 某博客\n"
        "    https://blog.example.com/y\n"
    )
    hits = parse_search_output(text)
    assert len(hits) == 2
    assert hits[0].title.startswith("阿里云")
    assert hits[0].url == "https://help.aliyun.com/x"


def test_judge_from_hits_prefers_product_page():
    hits = [Hit(title="阿里云 OSS 产品文档", url="https://help.aliyun.com/oss"),
            Hit(title="个人博客", url="https://blog.example.com")]
    rec = judge_from_hits("ro_snapshot", "只读快照", "q", hits)
    assert rec["verdict"] == "existing"
    assert "阿里云" in rec["product"]


def test_catalog_existing_survives_card_build_without_legacy_known_match():
    from collider.cards import Profile, build_card
    from collider.novelty import judge as judge_candidate

    row = {
        "mechanism": "differential_privacy",
        "name": "差分隐私",
        "form": "差分隐私（全量）｜证明聚合结果不暴露单条记录",
        "pairs": "「A」×「B」",
        "pair_count": 1,
        "near_text": "A",
        "far_text": "B",
        "near_style": "禁写",
        "far_type": "查阅",
        "effort": "simple",
        "cost": "x",
        "first_step": "x",
        "adjusted": 1.0,
    }
    novelty, product, overlap = judge_candidate(row, [])
    assert novelty == "existing"
    assert product is not None
    row.update(
        novelty=novelty,
        nearest=product["name"],
        nearest_gap=product["gap"],
        nearest_source=product["source"],
        overlap=overlap,
    )

    card = build_card(row, [], Profile(), [])

    assert card["status"] == "taken"
    assert card["existing"] == {
        "products": [product["name"]],
        "gap": product["gap"],
        "source": product["source"],
    }


def test_incomplete_or_malformed_market_evidence_stays_unchecked():
    catalog = load_catalog()
    mechanism = "no_such_mechanism_xyz"
    incomplete = [
        None,
        "not an evidence row",
        {"mechanism": mechanism, "verdict": "not_found", "n_results": 6},
        {"mechanism": mechanism, "verdict": "existing", "product": "某平台"},
    ]
    assert judge(mechanism, "不存在机制", catalog, incomplete).state == "unchecked"
    assert judge(
        mechanism,
        "不存在机制",
        catalog,
        {"mechanism": mechanism, "verdict": "not_found", "n_results": 6},
    ).state == "unchecked"
