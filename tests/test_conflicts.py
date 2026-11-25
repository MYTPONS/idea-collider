from collider.conflicts import conflict_for


def test_every_near_style_has_at_least_one_conflict():
    from collider.conflicts import CONFLICTS

    near_styles = {"禁写", "绑定", "改写", "承诺", "打扰", "断裂"}
    for style in near_styles:
        assert any(key[0] == style for key in CONFLICTS), style


def test_conflict_text_names_both_sides():
    text = conflict_for("禁写", "更正")
    assert text
    assert "写入" in text
    assert "更正" in text


def test_compatible_pair_has_no_conflict():
    # 禁写 × 查阅 是「不让改 + 要能看」,只读快照就能同时满足,不算冲突
    assert conflict_for("禁写", "查阅") is None
    assert conflict_for("承诺", "禁止") is None
