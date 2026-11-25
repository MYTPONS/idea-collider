"""MCP stdio 服务器:让 agent 直接挂上这四个工具。

协议是 JSON-RPC 2.0 over stdio,按行分帧(和 MCP 的 stdio 传输一致)。
不引入 mcp 包 —— 服务器这台机器只有 1G 内存,多一个依赖就多一份风险,
而这个协议面只需要 initialize / tools/list / tools/call 三个方法。
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .agentapi import TOOL_SCHEMAS, call_tool

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "idea-collider", "version": "0.1.0"}


def _result(msg_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle(message: dict) -> dict | None:
    method = message.get("method")
    msg_id = message.get("id")

    if method == "initialize":
        return _result(
            msg_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "tools/list":
        return _result(msg_id, {"tools": TOOL_SCHEMAS})
    if method == "tools/call":
        params = message.get("params") or {}
        name = str(params.get("name", ""))
        arguments = params.get("arguments") or {}
        try:
            payload = call_tool(name, arguments if isinstance(arguments, dict) else {})
        except KeyError as exc:
            return _error(msg_id, -32601, str(exc))
        except Exception as exc:  # noqa: BLE001 - 把原因回给 agent,不要静默
            return _error(msg_id, -32603, f"{type(exc).__name__}: {exc}")
        return _result(
            msg_id,
            {
                "content": [
                    {"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}
                ],
                "isError": False,
            },
        )
    if method in ("ping",):
        return _result(msg_id, {})
    if msg_id is None:
        return None
    return _error(msg_id, -32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = _error(None, -32700, "parse error")
        else:
            response = handle(message) if isinstance(message, dict) else _error(None, -32600, "invalid request")
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
