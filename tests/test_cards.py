import json

from collider.cards import (
    Profile,
    build_card,
    build_cards,
    load_profile,
    match_profile,
    pick_recommendations,
)


def sample_row(**over):
    base = {
        "mechanism": "ro_snapshot",
        "form": "只读快照（可查视图）｜留一份可看的副本",
        "pairs": "「A」×「B」",
        "pair_count": 1,
        "near_text": "上游账号会失效",
        "far_text": "有权查阅",
        "effort": "simple",
        "cost": "多占一份存储",
        "first_step": "写一个只读接口",
        "near_style": "禁写",
        "far_type": "更正",
        "novelty": "blank",
        "nearest": "阿里云 Memory",
        "overlap": 1.0,
        "adjusted": 2.0,
    }
    base.update(over)
    return base


KNOWN = [{"name": "阿里云 Memory", "gap": "不提供最终用户自助的查阅、导出、删除入口"}]
ENTRY = [{"mechanisms": ["ro_snapshot"], "blocker": "平台方不提供导出,因为导出等于降低迁移成本"}]


def test_match_profile_scores_skill_and_channel():
    profile = Profile(
        name="x",
        skills=["Python"],
        channels=[{"name": "中转商圈子", "keywords": ["上游"], "role": "中转商"}],
        hours_per_week=10,
        anti=[{"name": "要牌照", "keywords": ["牌照"]}],
    )
    row = {"form": "导出｜Python 脚本", "near_text": "上游账号会失效", "far_text": "个人有权查阅"}
    got = match_profile(row, profile)
    assert got["score"] == 5
    assert got["channel"]["role"] == "中转商"
    assert got["anti"] is None


def test_missing_profile_file_is_not_an_error(tmp_path):
    profile = load_profile(tmp_path / "nope.json")
    assert profile.skills == []
    assert match_profile({"form": "导出", "near_text": "", "far_text": ""}, profile)["score"] == 0


def test_anti_keyword_marks_and_negates():
    profile = Profile("x", [], [], 10, [{"name": "要牌照", "keywords": ["牌照"]}])
    got = match_profile({"form": "牌照代申请", "near_text": "", "far_text": ""}, profile)
    assert got["anti"] == "要牌照"
    assert got["score"] == -1


def test_full_card_has_all_four_dimensions():
    profile = Profile("x", [], [{"name": "中转商圈子", "keywords": ["上游"], "role": "中转商"}], 10, [])
    card = build_card(sample_row(), KNOWN, profile, ENTRY)
    assert card["status"] == "card"
    assert card["missing"] == []
    assert card["existing"]["products"] == ["阿里云 Memory"]
    assert card["mvp"]["days"] == 3
    assert card["first_customer"]["role"] == "中转商"


def test_missing_blocker_degrades_to_draft_and_names_the_gap():
    profile = Profile("x", [], [{"name": "c", "keywords": ["上游"], "role": "中转商"}], 10, [])
    card = build_card(sample_row(), KNOWN, profile, [])
    assert card["status"] == "draft"
    assert card["missing"] == ["blocker"]


def test_no_real_conflict_is_not_a_card():
    # 禁写 × 查阅 是「不让改 + 要能看」,只读快照就能同时满足,不算碰撞
    profile = Profile("x", [], [{"name": "c", "keywords": ["上游"], "role": "中转商"}], 10, [])
    card = build_card(sample_row(far_type="查阅"), KNOWN, profile, ENTRY)
    assert card["status"] == "draft"
    assert "conflict" in card["missing"]
    assert card["conflict"] is None


def test_missing_first_step_degrades_to_draft():
    profile = Profile("x", [], [{"name": "c", "keywords": ["上游"], "role": "中转商"}], 10, [])
    card = build_card(sample_row(first_step=""), KNOWN, profile, ENTRY)
    assert card["status"] == "draft"
    assert "mvp" in card["missing"]
    assert card["mvp"] is None


def test_no_lineage_product_degrades_to_draft():
    profile = Profile("x", [], [{"name": "c", "keywords": ["上游"], "role": "中转商"}], 10, [])
    card = build_card(sample_row(nearest=""), [], profile, ENTRY)
    assert card["status"] == "draft"
    assert "existing" in card["missing"]


def test_taken_mechanism_is_not_a_card():
    card = build_card(
        sample_row(novelty="existing"), [{"name": "p", "gap": "x" * 10}], Profile("x", [], [], 10, []), []
    )
    assert card["status"] == "taken"


def test_anti_match_stays_in_list_but_is_not_recommended():
    profile = Profile(
        "x", [], [{"name": "中转商圈子", "keywords": ["上游"], "role": "中转商"}], 10,
        [{"name": "要牌照", "keywords": ["快照"]}],
    )
    cards = build_cards([sample_row()], KNOWN, profile, ENTRY)
    primary, alternates = pick_recommendations(cards)
    assert primary is None and alternates == []
    assert cards[0]["match"]["anti"] == "要牌照"
    assert cards[0]["status"] == "card"


def test_recommendations_are_capped():
    profile = Profile("x", [], [{"name": "c", "keywords": ["上游"], "role": "中转商"}], 10, [])
    rows = [sample_row(mechanism=f"m{i}", form=f"形态{i}") for i in range(5)]
    entries = [{"mechanisms": [f"m{i}"], "blocker": "卡点具体到人,能复述"} for i in range(5)]
    cards = build_cards(rows, KNOWN, profile, entries)
    primary, alternates = pick_recommendations(cards)
    assert primary is not None
    assert len(alternates) == 2


def test_evidence_entry_matches_by_mechanism_not_by_keyword():
    profile = Profile("x", [], [], 10, [])
    entries = [
        {"mechanisms": ["export"], "blocker": "导出会降低迁移成本,平台不肯做"},
        {"match": ["只读"], "blocker": "这条应该匹配不到"},
    ]
    card = build_card(sample_row(mechanism="export"), KNOWN, profile, entries)
    assert card["blocker"]["text"].startswith("导出会降低迁移成本")


def test_profile_json_is_loadable():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    profile = load_profile(root / "data" / "me.example.json")
    assert profile.name
    assert profile.channels
    assert profile.anti
