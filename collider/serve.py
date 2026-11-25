from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .cards import Profile, load_profile
from .forge import build_candidates, load_pack, load_types, summarize
from .gate import gate_statements
from .model import LocalModel
from .novelty import load_known
from .schema import Statement


def _statements(items, prefix: str, domain: str) -> list[Statement]:
    out: list[Statement] = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            ident = str(item.get("id") or f"{prefix}{index + 1}")
        else:
            text = str(item).strip()
            ident = f"{prefix}{index + 1}"
        if text:
            out.append(Statement(id=ident, text=text, domain=domain))
    return out


def _generic_sides() -> tuple[list[dict], list[dict]]:
    def read(path: str) -> list[dict]:
        p = Path(path)
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

    return read("data/domains/generic_near.jsonl"), read("data/domains/generic_far.jsonl")


def _pack_evidence(pack_id: str) -> list[dict]:
    from .filter import load_evidence
    from .forge import load_pack_entry

    try:
        entry = load_pack_entry(pack_id)
    except KeyError:
        return []
    path = entry.get("evidence")
    if not path:
        return []
    resolved = Path(path)
    if not resolved.exists():
        return []
    return load_evidence(resolved)


def load_clients(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    clients: dict[str, dict] = {}
    for item in data.get("clients", []):
        token = str(item.get("token", "")).strip()
        if token and token != "REPLACE_ME":
            clients[token] = {
                "name": str(item.get("name", "unnamed")),
                "quota": int(item.get("quota", 0)),
            }
    return clients


def make_handler(model, known, usage_path: Path, clients: dict[str, dict], max_items: int = 40):
    used: dict[str, int] = {token: 0 for token in clients}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?")[0] == "/health":
                self._json({"ok": True, "model": model.describe(), "auth": bool(clients)})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if self.path.split("?")[0] != "/collide":
                self._json({"error": "not found"}, 404)
                return
            client = None
            if clients:
                header = self.headers.get("Authorization") or ""
                token = header[7:].strip() if header.lower().startswith("bearer ") else ""
                client = clients.get(token)
                if client is None:
                    self._json({"error": "unauthorized"}, 401)
                    return
                if client["quota"] and used[token] >= client["quota"]:
                    self._json({"error": "quota exhausted", "quota": client["quota"]}, 402)
                    return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._json({"error": "invalid json"}, 400)
                return
            if body.get("pack"):
                try:
                    near_path, far_path = load_pack(str(body["pack"]))
                except KeyError:
                    self._json({"error": "unknown pack"}, 400)
                    return
                near_items = [
                    json.loads(line)
                    for line in near_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                far_items = [
                    json.loads(line)
                    for line in far_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                near_styles = load_types(near_path)
                entries = _pack_evidence(str(body["pack"]))
            else:
                near_items = body.get("near") or []
                far_items = body.get("far") or []
                near_styles = {}
                entries = []
            # 平台上的人可能只丢一句想法甚至什么都不带。不接等于拒客,
            # 所以缺哪一侧就用通用约束兜底,并在 mode / notes 里说清楚。
            mode = "materials"
            notes: list[str] = []
            if not near_items and not far_items:
                near_items, far_items = _generic_sides()
                mode = "generic"
                notes.append("没有提供素材:两侧都用通用约束近似,结论只能当提问")
            elif not far_items:
                _, far_items = _generic_sides()
                mode = "generic-far"
                notes.append("没有提供远域:用通用合规义务近似,这一侧必须先复核")
            elif not near_items:
                near_items, _ = _generic_sides()
                mode = "generic-near"
                notes.append("没有提供近域:用通用经营约束近似,这些不是你行业里已发生的事实")
            if body.get("idea"):
                notes.append(f"你的方向:{body['idea']}(只作为标签)")
            if mode != "materials":
                near_styles = {}
                entries = []
            if len(near_items) > max_items or len(far_items) > max_items:
                self._json({"error": f"at most {max_items} items per side"}, 400)
                return
            started = time.time()
            near_results = gate_statements(_statements(near_items, "n", "near"), model)
            far_results = gate_statements(_statements(far_items, "f", "far"), model)
            merged = build_candidates(near_results, far_results, known, near_styles=near_styles)
            profile_path = Path("data/me.json")
            profile = load_profile(profile_path) if profile_path.exists() else Profile()
            result = summarize(merged, profile, entries, known)
            token_key = next((key for key, value in clients.items() if value is client), "")
            if token_key:
                used[token_key] += 1
            usage = {
                "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                "client": client["name"] if client else "anonymous",
                "near": len(near_items),
                "far": len(far_items),
                "near_passed": sum(1 for item in near_results if item.passed),
                "far_passed": sum(1 for item in far_results if item.passed),
                **{key: result[key] for key in ("candidates", "blank", "partial", "existing")},
                "seconds": round(time.time() - started, 1),
            }
            with usage_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(usage, ensure_ascii=False) + "\n")
            result["mode"] = mode
            result["notes"] = notes
            result["usage"] = usage
            if client:
                result["quota"] = {"limit": client["quota"], "used": used[token_key]}
            self._json(result)

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


def serve(model_dir: str | None, host: str, port: int, usage: Path, clients_path: Path) -> None:
    model = LocalModel(model_dir)
    known = load_known(Path("data/projects/known_products.jsonl"))
    clients = load_clients(clients_path)
    usage.parent.mkdir(parents=True, exist_ok=True)
    handler = make_handler(model, known, usage, clients)
    server = ThreadingHTTPServer((host, port), handler)
    print(
        json.dumps(
            {
                "listen": f"http://{host}:{port}",
                "model": model.describe(),
                "usage": str(usage),
                "clients": len(clients),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()
