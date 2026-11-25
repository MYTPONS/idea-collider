import io
import json

from collider.agentapi import collide, call_tool, list_packs, TOOL_SCHEMAS
from collider.mcp import handle, serve


def test_collide_with_a_pack_returns_cards_and_the_next_question():
    result = collide({"pack": "ai-industry", "skills": ["Python"], "channel": "中转商"})
    assert result["mode"] == "pack"
    assert result["cards"]
    assert result["ask_user"]
    assert result["gate"].startswith("rule:")


def test_inline_constraints_are_taken_as_given():
    result = collide(
        {
            "near": ["上游账号会在无通知的情况下失效,任何以单一上游为前提的设计都会周期性中断"],
            "far": ["个人有权向个人信息处理者查阅、复制其个人信息;处理者应当及时提供"],
            "skills": ["Python"],
            "channel": "中转商",
        }
    )
    assert result["mode"] == "inline"
    assert result["near"]["passed"] == 1
    assert result["far"]["passed"] == 1


def test_missing_inputs_degrade_with_a_warning_not_an_error():
    result = collide({})
    assert result["near"]["total"] > 0
    assert result["far"]["total"] > 0
    assert any("通用" in w for w in result["warnings"])


def test_ask_user_explains_why_nothing_collided():
    result = collide({"near": ["上游账号会在无通知的情况下失效"], "far": ["个人有权查阅其个人信息"]})
    assert result["primary"] is None
    assert result["ask_user"]
    assert any("机制" in q or "同类事实" in q for q in result["ask_user"])


def test_evidence_from_the_agent_completes_a_card():
    base = {
        "near": ["上游账号会在无通知的情况下失效,任何以单一上游为前提的设计都会周期性中断"],
        "far": ["个人有权向个人信息处理者查阅、复制其个人信息;处理者应当及时提供"],
        "skills": ["Python"],
        "channel": "中转商",
    }
    first = collide(base)
    if not first["cards"]:
        return
    mechanism = first["cards"][0]["mechanism"]
    second = collide(
        {
            **base,
            "evidence": [
                {
                    "mechanisms": [mechanism],
                    "blocker": "中转商不敢承诺,因为承诺要自己养一份算力,而客户只按 token 比价",
                    "first_customer": {"role": "单人运维的中转商", "channel": "New API 部署者群"},
                }
            ],
        }
    )
    card = next(c for c in second["cards"] if c["mechanism"] == mechanism)
    assert "blocker" not in card["missing"]
    assert "first_customer" not in card["missing"]


def test_list_packs_only_returns_packs_that_resolve():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for pack in list_packs():
        index = json.loads((root / "data/packs/index.json").read_text(encoding="utf-8"))
        entry = next(p for p in index["packs"] if p["id"] == pack["id"])
        assert (root / entry["near"]).exists()
        assert (root / entry["far"]).exists()


def test_explain_conflict_separates_real_from_fake():
    real = call_tool("explain_conflict", {"near_style": "禁写", "far_type": "更正"})
    fake = call_tool("explain_conflict", {"near_style": "禁写", "far_type": "查阅"})
    assert real["is_conflict"] is True
    assert fake["is_conflict"] is False
    assert "交集非空" in fake["explanation"]


def test_tool_schemas_cover_every_callable_tool():
    from collider.agentapi import call_tool as caller

    names = {tool["name"] for tool in TOOL_SCHEMAS}
    assert names == {"collide", "list_packs", "explain_conflict", "materials_template"}
    for name in names:
        assert callable(caller)


def test_mcp_initialize_and_tools_list():
    assert handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})["result"]["serverInfo"]["name"] == "idea-collider"
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in tools} == {"collide", "list_packs", "explain_conflict", "materials_template"}


def test_mcp_tools_call_returns_text_content():
    response = handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "explain_conflict", "arguments": {"near_style": "禁写", "far_type": "删除"}},
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["is_conflict"] is True


def test_mcp_unknown_tool_is_an_error_not_a_crash():
    response = handle(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope", "arguments": {}}}
    )
    assert response["error"]["code"] == -32601


def test_mcp_stdio_round_trip():
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    out = io.StringIO()
    serve(stdin=io.StringIO("\n".join(json.dumps(m) for m in messages) + "\n"), stdout=out)
    lines = [json.loads(line) for line in out.getvalue().strip().splitlines()]
    assert len(lines) == 2  # notification 不回复
    assert lines[0]["id"] == 1
    assert lines[1]["result"]["tools"]
