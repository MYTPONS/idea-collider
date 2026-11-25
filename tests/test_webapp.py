import re
from urllib.parse import parse_qs

from collider.webapp import index_body, run_collision, split_user_text


def form(**values) -> dict:
    pairs = "&".join(f"{k}={v}" for k, v in values.items())
    return parse_qs(pairs, keep_blank_values=True)


def test_index_asks_three_questions_a_person_can_answer():
    body = index_body()
    assert "你熟悉什么" in body
    assert "你被什么卡过" in body
    assert "撞哪个领域" in body


def test_split_keeps_only_usable_lines():
    lines = split_user_text("短\n上游账号会在无通知的情况下失效。客户要求请求内容不留存。\n\n" + "很长" * 200)
    assert "上游账号会在无通知的情况下失效" in lines
    assert "客户要求请求内容不留存" in lines
    assert all(8 <= len(line) <= 200 for line in lines)


def test_run_without_any_input_still_renders_a_result_page():
    code, body = run_collision(form(skills="Python", channel="", anti="", near="", idea="", pack=""))
    assert code == 200
    text = body.decode()
    assert "近域" in text and "远域" in text
    assert "报告原文" in text


def test_run_uses_the_users_own_constraints():
    near = "上游账号会在无通知的情况下失效。客户要求请求内容不留存"
    code, body = run_collision(
        form(skills="Python", channel="中转商朋友", anti="要牌照", near=near, idea="做接入", pack="")
    )
    text = body.decode()
    assert "近域用了你写的" in text
    assert "做接入" in text


def test_run_with_a_pack_uses_verified_material():
    code, body = run_collision(form(skills="Python", channel="", anti="", near="", idea="", pack="ai-industry"))
    text = body.decode()
    assert "AI 行业" in text
    assert "远域未复核" not in text or "0 条" in text


def test_report_never_claims_the_finetuned_score():
    _, body = run_collision(form(skills="", channel="", anti="", near="", idea="", pack=""))
    text = body.decode()
    assert "规则版" in text
    assert "0.8667" in text  # 明说不是它


def test_rate_limit_trips_after_twelve(monkeypatch):
    from collider import webapp

    monkeypatch.setattr(webapp, "_hits", {})
    results = [webapp.rate_limited("1.2.3.4") for _ in range(13)]
    assert results[:12] == [False] * 12
    assert results[12] is True
    assert webapp.rate_limited("5.6.7.8") is False


def test_oversized_body_is_refused():
    from collider.webapp import MAX_BODY

    assert MAX_BODY == 32 * 1024
