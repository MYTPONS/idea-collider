"""给远端 agent 的 JSON HTTP 接口。

和网页版是两个东西:网页版给人看,这里给 agent 调。所以
- 输入输出都是 JSON,不渲染 markdown
- 出错返回结构化 error,不是 HTML 页面
- 返回里带 ask_user,agent 知道下一步该问什么
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .agentapi import TOOL_SCHEMAS, call_tool, list_packs

MAX_BODY = 256 * 1024
MAX_CONCURRENT = 4
_slots = threading.Semaphore(MAX_CONCURRENT)
_RATE = 30
_WINDOW = 60.0
_hits: dict[str, list[float]] = {}
_lock = threading.Lock()


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    with _lock:
        recent = [t for t in _hits.get(ip, []) if now - t < _WINDOW]
        if len(recent) >= _RATE:
            _hits[ip] = recent
            return True
        recent.append(now)
        _hits[ip] = recent
        return False


def make_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?")[0].rstrip("/") or "/"
            if path == "/health":
                self._json({"ok": True, "tools": len(TOOL_SCHEMAS)})
            elif path == "/tools":
                self._json({"tools": TOOL_SCHEMAS})
            elif path == "/packs":
                self._json({"packs": list_packs()})
            else:
                self._json({"error": "not_found"}, 404)

        def do_POST(self) -> None:
            path = self.path.split("?")[0].rstrip("/") or "/"
            ip = self.client_address[0]
            if _rate_limited(ip):
                self._json({"error": "rate_limited", "hint": "一分钟 30 次,稍后再试"}, 429)
                return
            if path not in ("/collide", "/tool"):
                self._json({"error": "not_found"}, 404)
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json({"error": "bad_length"}, 400)
                return
            if length > MAX_BODY:
                self._json({"error": "too_large", "limit": MAX_BODY}, 413)
                return
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._json({"error": "invalid_json"}, 400)
                return
            if not isinstance(body, dict):
                self._json({"error": "invalid_request", "hint": "请求体必须是对象"}, 400)
                return
            if not _slots.acquire(timeout=15):
                self._json({"error": "busy", "hint": "并发满了,稍后再试"}, 503)
                return
            try:
                if path == "/tool":
                    name = str(body.get("name", ""))
                    arguments = body.get("arguments") or {}
                    payload = call_tool(name, arguments if isinstance(arguments, dict) else {})
                else:
                    payload = call_tool("collide", body)
            except KeyError as exc:
                self._json({"error": "unknown_tool", "detail": str(exc)}, 404)
                return
            except Exception as exc:  # noqa: BLE001 - agent 要看到原因
                self._json({"error": type(exc).__name__, "detail": str(exc)}, 500)
                return
            finally:
                _slots.release()
            self._json(payload)

        def _json(self, payload: dict, code: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            return

    return Handler


def serve(host: str, port: int) -> None:
    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = Server((host, port), make_handler())
    print(json.dumps({"listen": f"http://{host}:{port}", "tools": [t["name"] for t in TOOL_SCHEMAS]}), flush=True)
    server.serve_forever()
