from collider.cardreport import render_cards

CARD = {
    "id": "ro_snapshot",
    "form": "只读快照",
    "pairs": "「A」×「B」",
    "pair_count": 1,
    "existing": {"products": ["阿里云 Memory"], "gap": "不提供查阅导出入口"},
    "blocker": {"text": "平台方不提供导出"},
    "mvp": {"cut": "只读接口", "days": 3},
    "first_customer": {"role": "中转商", "channel": "中转商圈子"},
    "missing": [],
    "status": "card",
    "effort": "simple",
    "cost": "多占存储",
    "match": {"score": 5, "reasons": ["会 Python", "够得着 中转商圈子"], "anti": None, "channel": None},
    "lineage": None,
}


def test_render_puts_primary_first_and_lists_drafts():
    draft = dict(CARD, id="x", form="草稿形态", status="draft", missing=["blocker"], blocker=None)
    text = render_cards([CARD, draft], {"pack": "p", "model": "m", "unverified_far": 2, "far_contribution": 3})
    assert text.index("主推") < text.index("只读快照")
    assert "第一个客户：中转商,来自 中转商圈子" in text
    assert "草稿形态" in text
    assert "远域未复核：2 条" in text


def test_zero_far_contribution_warns():
    text = render_cards([], {"pack": "p", "model": "m", "unverified_far": 0, "far_contribution": 0})
    assert "远域无贡献" in text


def test_single_far_type_is_still_no_contribution():
    text = render_cards([], {"pack": "p", "model": "m", "unverified_far": 0,
                             "far_contribution": 9, "far_types": 1})
    assert "远域无贡献" in text


def test_multiple_far_types_count_as_contribution():
    text = render_cards([], {"pack": "p", "model": "m", "unverified_far": 0,
                             "far_contribution": 2, "far_types": 4})
    assert "远域起了作用" in text
    assert "4 种" in text


def test_no_complete_card_explains_why():
    draft = dict(CARD, status="draft", missing=["blocker"], blocker=None)
    text = render_cards([draft], {"pack": "p", "model": "m", "unverified_far": 0, "far_contribution": 1})
    assert "这一轮没有四维齐全的方向" in text


def test_anti_card_is_not_shown_as_primary():
    anti_card = dict(CARD, match={"score": -1, "reasons": ["踩到不做项「要牌照」"], "anti": "要牌照", "channel": None})
    text = render_cards([anti_card], {"pack": "p", "model": "m", "unverified_far": 0, "far_contribution": 1})
    assert "这一轮没有四维齐全的方向" in text
    # 不在主推里,但仍留在草稿/列表里,不静默消失
    assert "只读快照" in text


def test_reasons_fall_back_when_profile_misses():
    card = dict(CARD, match={"score": 0, "reasons": [], "anti": None, "channel": None})
    text = render_cards([card], {"pack": "p", "model": "m", "unverified_far": 0, "far_contribution": 1})
    assert "档案未命中" in text
