from pathlib import Path

from collider.forge import build_candidates, load_types
from collider.search import far_style, near_style, search_mechanisms
from collider.schema import GateResult, Statement


def st(ident: str, text: str, axis: str) -> GateResult:
    return GateResult(
        statement=Statement(id=ident, text=text, domain="test"),
        label="constraint",
        axis=axis,
        why="test",
    )


def test_each_row_records_its_own_pair_types():
    near = [
        st("n1", "系统不允许用户直接写入或修改记忆", "compliance"),
        st("n2", "上游模型账号无通知失效，请求中断", "availability"),
    ]
    far = [
        st("f1", "个人有权查阅、复制其个人信息", "compliance"),
        st("f2", "交易记录留存不少于三年", "time"),
        st("f3", "不得向未成年人提供打赏", "compliance"),
    ]
    near_by_id = {r.statement.id: r.statement.text for r in near}
    far_by_id = {r.statement.id: r.statement.text for r in far}

    rows = search_mechanisms(near, far)
    assert rows

    for row in rows:
        expected_near = near_style(near_by_id[row["near"]]) or {
            "compliance": "承诺",
            "availability": "断裂",
        }.get(row["near_axis"], "")
        expected_far = far_style(far_by_id[row["far"]]) or {
            "compliance": "查阅",
            "time": "限期",
        }.get(row["far_axis"], "")
        assert row["near_style"] == expected_near, row
        assert row["far_type"] == expected_far, row


def test_keyword_score_is_per_row():
    near = [
        st("n1", "记忆绑定在单个平台账户上，换平台记忆清零", "trust"),
        st("n2", "用户无法导出自己的记忆副本", "compliance"),
    ]
    far = [st("f1", "个人有权查阅、复制其个人信息", "compliance")]

    rows = search_mechanisms(near, far, min_score=0)
    export = [row for row in rows if row["mechanism"] == "export"]

    assert {row["kw"] for row in export} == {0, 1}, export


def test_merge_keeps_pairs_that_hit_different_far_types():
    near = [st("n1", "系统不允许用户直接写入或修改记忆，用户没有写入权", "compliance")]
    far = [
        st("f1", "个人有权查阅、复制其个人信息", "compliance"),
        st("f2", "个人发现个人信息不准确，有权请求更正", "compliance"),
    ]

    merged = build_candidates(near, far, [], min_score=0)

    multi = [row for row in merged if row["pair_count"] > 1]
    assert multi, [(row["mechanism"], row["pair_count"]) for row in merged]
    ro = next(row for row in multi if row["mechanism"] == "ro_snapshot")
    assert "查阅" in ro["pairs"] and "更正" in ro["pairs"], ro


def test_negative_marker_does_not_swallow_the_correction_right():
    # b2 就是「个人信息不准确…有权请求更正」,「不准」是「不准确」的前缀,不能判成禁止
    assert far_style("个人发现其个人信息不准确或不完整,有权请求更正、补充。") == "更正"
    assert far_style("不得向未成年人提供打赏") == "禁止"
    assert far_style("未经批准不准上线运营") == "禁止"


def test_declared_pairs_win_over_far_style_whitelist():
    # ro_snapshot 声明解「承诺×更正」,但 FAR_STYLES["更正"] 里没有它。
    # pairs 非空时必须以 pairs 为准,否则文档写的那条永远不触发。
    near = [st("n1", "产品只承诺少问几遍,从不承诺可查、可改、可带走", "market")]
    verbatim = "个人发现其个人信息不准确或不完整,有权请求更正、补充。拒绝受理即违法。"
    far = [st("f1", verbatim, "compliance")]

    assert far_style(verbatim) == "更正"
    assert near_style(near[0].statement.text) == "承诺"

    rows = search_mechanisms(near, far)
    assert "ro_snapshot" in {row["mechanism"] for row in rows}, rows


def test_type_table_is_loaded_by_file_name():
    root = Path(__file__).resolve().parent.parent
    table = load_types(root / "data" / "domains" / "memory_products.jsonl", root / "data" / "domains" / "types.json")
    assert table["a1"] == "禁写"
    assert load_types(root / "data" / "domains" / "no_such_domain.jsonl", root / "data" / "domains" / "types.json") == {}


def test_explicit_type_table_wins_over_text_inference():
    near = [st("n1", "记忆绑定在单个平台账户上，换平台记忆清零", "trust")]
    far = [st("f1", "个人有权查阅、复制其个人信息", "compliance")]
    # 文本推断是"绑定",但类型表把它标成"禁写"
    assert near_style(near[0].statement.text) == "绑定"

    inferred = search_mechanisms(near, far, min_score=0)
    assert {row["near_style"] for row in inferred} == {"绑定"}

    rows = search_mechanisms(near, far, min_score=0, near_styles={"n1": "禁写"})
    assert rows
    assert {row["near_style"] for row in rows} == {"禁写"}


def test_pure_axis_match_is_gated_out_by_default():
    # 纯靠轴向/白名单进来的一律不放行:每行必须有机制关键词,
    # 或者机制能解的症状出现在近域原文里。
    near = [st("n1", "上游账号会在无通知的情况下失效", "availability")]
    far = [st("f1", "处理者必须在规定期限内响应", "time")]
    rows = search_mechanisms(near, far)
    assert rows
    assert all(row["kw"] >= 1 or row["sym"] >= 1 for row in rows), rows


def test_action_words_outrank_negation():
    # 「必须在规定期限内响应查阅、更正、删除请求,不得以没有这个功能为由拒绝」
    # 讲的是三项权利,不是禁令。动作词优先于「不得」。
    assert far_style("处理者必须在规定期限内响应查阅、更正、删除请求,不得以没有这个功能为由拒绝。") == "删除"
    assert far_style("处理者必须响应查阅请求,不得拒绝") == "查阅"
    # 没有具体动作的禁令仍然判禁止
    assert far_style("不得利用算法对交易价格实施不合理的差别待遇") == "禁止"


def test_verification_words_are_not_data_rights():
    assert far_style("支付机构要求平台对每笔交易做实名核验和反洗钱识别") == "义务"
    assert far_style("应用商店对上架应用要求实名认证和内容审核") == "义务"
