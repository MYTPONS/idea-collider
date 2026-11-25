"""网页版:给不懂命令行的人用。

不是把 CLI 包一层皮肤。它要解决的是「一个人打开网页,没有素材,也不知道该填什么」:
- 表单直接问三件人一定答得上的事:你熟悉什么、你被什么卡过、你想到什么方向
- 后端把它们变成近域约束,再挑一个远域,用规则闸门跑完整条管线
- 结果页第一屏就是项目卡,不是 JSON,也不是给开发者看的日志

网页版使用规则闸门，不依赖模型权重。
报告里会写明这一轮用的是规则闸门(0.8167),不是微调模型(0.8667)。
"""

from __future__ import annotations

import html
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .cardreport import render_cards
from .cards import Profile, build_cards, load_profile, pick_recommendations
from .forge import build_candidates, load_pack_entry
from .gate import gate_statements
from .rulegate import RuleModel
from .schema import Statement

ROOT = Path(__file__).resolve().parent.parent
MAX_TEXT = 8000
MAX_BODY = 32 * 1024
# 1G 内存的机器上同时跑十几个请求没意义,排队比 OOM 好
MAX_CONCURRENT = 4
_slots = threading.Semaphore(MAX_CONCURRENT)
# 粗粒度限速:同一个 IP 每分钟最多 12 次碰撞
_RATE = 12
_WINDOW = 60.0
_hits: dict[str, list[float]] = {}
_hits_lock = threading.Lock()


def rate_limited(ip: str) -> bool:
    now = time.monotonic()
    with _hits_lock:
        recent = [t for t in _hits.get(ip, []) if now - t < _WINDOW]
        if len(recent) >= _RATE:
            _hits[ip] = recent
            return True
        recent.append(now)
        _hits[ip] = recent
        return False


def split_user_text(text: str) -> list[str]:
    parts = re.split(r"[。；;!?\n]+", text)
    out: list[str] = []
    seen: set[str] = set()
    for raw in parts:
        line = raw.strip().strip("-*0123456789. 、")
        if len(line) < 8 or len(line) > 200:
            continue
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out[:20]


# 只列真的存在的包。写一个不存在的 id 在页面上点了就 500,那是最差的体验。
PACKS = [
    ("ai-industry", "AI 行业 × 生成式 AI 合规", "近域是 AI 接入与 agent 产品的现实;远域是已核对的法规条文"),
    ("ai-forensics", "AI 行业 × 电子数据取证", "同一个近域,远域换成诉讼里的电子数据取证"),
    ("memory-saas", "记忆产品 × 个人信息保护", "近域是已上线的记忆产品,远域是个人信息保护的四项权利"),
    ("ai-gateway", "AI 接入层 × 个人信息保护", "近域是调用上游模型的接入层"),
    ("memory-pipl", "记忆产品 × 个保法条文", "远域是从法条原文抽出的二十条约束"),
]

PAGE_HEAD = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
body{{margin:0;font:16px/1.65 -apple-system,"Segoe UI","Noto Sans SC",sans-serif;
background:#fbfaf8;color:#1c1b19;padding:24px 16px 64px}}
main{{max-width:760px;margin:0 auto}}
h1{{font-size:26px;line-height:1.3;margin:0 0 6px}}
h2{{font-size:19px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid #e6e2dc}}
h3{{font-size:17px;margin:22px 0 8px}}
p.lead{{color:#6b665f;margin:0 0 26px}}
fieldset{{border:1px solid #e6e2dc;border-radius:10px;padding:16px;margin:0 0 18px;background:#fff}}
legend{{font-weight:600;padding:0 6px}}
label{{display:block;font-weight:600;margin:14px 0 6px;font-size:15px}}
label span{{font-weight:400;color:#6b665f;display:block;font-size:13px;margin-top:2px}}
input[type=text],textarea,select{{width:100%;padding:10px;border:1px solid #d8d3cb;border-radius:8px;
font:inherit;background:#fff;color:inherit}}
textarea{{min-height:96px;resize:vertical}}
button{{font:inherit;font-weight:600;background:#1c1b19;color:#fff;border:0;border-radius:9px;
padding:13px 22px;cursor:pointer;width:100%;margin-top:8px}}
button:hover{{opacity:.88}}
.pack{{display:block;border:1px solid #e6e2dc;border-radius:10px;padding:12px 14px;margin:8px 0;background:#fff}}
.pack b{{display:block}}
.pack i{{font-style:normal;color:#6b665f;font-size:13px}}
ul.list{{padding-left:20px}}
.card{{border:1px solid #e6e2dc;border-radius:12px;padding:18px 20px;margin:0 0 18px;background:#fff}}
.card.primary{{border-color:#1c1b19;border-width:2px;box-shadow:0 2px 12px rgba(0,0,0,.05)}}
.card dl{{margin:0}}
.card dt{{font-size:12px;letter-spacing:.04em;color:#8a847c;margin-top:12px}}
.card dd{{margin:2px 0 0}}
.badge{{display:inline-block;font-size:12px;padding:2px 9px;border-radius:99px;background:#f0ede8;
color:#6b665f;margin-left:8px;vertical-align:middle}}
.warn{{background:#fff8e6;border:1px solid #f0dcae;border-radius:10px;padding:12px 14px;margin:0 0 20px}}
.note{{background:#f4f2ee;border-radius:10px;padding:12px 14px;font-size:14px;color:#5b564f;margin:0 0 20px}}
details{{margin:10px 0}}
summary{{cursor:pointer;font-weight:600}}
pre{{white-space:pre-wrap;font-size:13px;background:#f4f2ee;border-radius:8px;padding:12px;overflow:auto}}
a.back{{display:inline-block;margin-top:24px;color:#1c1b19}}
@media (prefers-color-scheme:dark){{
body{{background:#14130f;color:#e8e4dc}}
h2{{border-color:#2e2b25}}
p.lead,label span,.pack i,.card dt{{color:#a09a90}}
fieldset,.card,.pack{{background:#1b1a16;border-color:#2e2b25}}
input[type=text],textarea,select{{background:#111009;border-color:#3a362e}}
button{{background:#e8e4dc;color:#14130f}}
.card.primary{{border-color:#e8e4dc}}
.badge{{background:#2a2721;color:#a09a90}}
.warn{{background:#2e2610;border-color:#5a4a1c}}
.note,pre{{background:#1f1e19;color:#b8b2a8}}
a.back{{color:#e8e4dc}}
}}
</style></head><body><main>"""

PAGE_TAIL = "</main></body></html>"


def page(title: str, body: str) -> bytes:
    return (PAGE_HEAD.format(title=html.escape(title)) + body + PAGE_TAIL).encode("utf-8")


def index_body(message: str = "") -> str:
    options = "".join(
        f'<label class="pack"><b>{html.escape(name)}</b>'
        f'<i>{html.escape(note)}</i>'
        f'<input type="radio" name="pack" value="{pid}" style="margin-top:8px"></label>'
        for pid, name, note in PACKS
    )
    warn = f'<div class="warn">{html.escape(message)}</div>' if message else ""
    return f"""
<h1>项目碰撞机</h1>
<p class="lead">说清楚你熟悉什么、被什么卡过,它把你的约束和另一个领域的硬约束撞在一起,
挑出「必须同时满足两边」的产品方向。只推一条,不给你一百个选项。</p>
{warn}
<form method="post" action="run">
<fieldset>
<legend>一、你熟悉什么</legend>
<label>你实际会做的事
<span>比如:写 Python、部署服务、做代理、接模型 API。用逗号分开。</span></label>
<input type="text" name="skills" placeholder="Python, 部署, 模型接入" value="Python, TypeScript, API integration">
<label>你够得着的人
<span>第一批客户从这些人里来。说不出具体人,方向就是假的。</span></label>
<input type="text" name="channel" placeholder="比如:做中转的朋友、自托管的圈子">
<label>你不做的事
<span>用逗号分开。踩到就自动排除。比如:要牌照、要 7x24 值守。</span></label>
<input type="text" name="anti" placeholder="要牌照, 要驻场, 要招投标" value="要牌照, 要驻场, 要招投标">
</fieldset>

<fieldset>
<legend>二、你被什么卡过</legend>
<label>已经发生、你能说出真假的事实
<span>一行一条。写「上游账号会在无通知下失效」,不要写「希望接口更稳」。
不填也行,但这样跑出来的是通用约束,只能当提问。</span></label>
<textarea name="near" placeholder="上游账号会在没有通知的情况下失效&#10;客户要求请求内容不留存&#10;对公收款需要发票和合同"></textarea>
<label>你想到的方向
<span>只当标签,不当约束。可以不填。</span></label>
<input type="text" name="idea" placeholder="比如:做跨境电商">
</fieldset>

<fieldset>
<legend>三、撞哪个领域</legend>
<p style="margin:0 0 6px;color:#6b665f;font-size:14px">不选就用通用合规义务近似。选了用我复核过的素材。</p>
<label class="pack"><b>不指定(通用约束)</b><i>两侧都是通用约束,结论只能当提问</i>
<input type="radio" name="pack" value="" checked style="margin-top:8px"></label>
{options}
</fieldset>

<button type="submit">碰撞</button>
</form>
"""


def _form_value(form: dict, key: str) -> str:
    value = form.get(key, [""])[0]
    return value[:MAX_TEXT].strip()


def _csv(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、;；\n]+", value) if item.strip()]


def run_collision(form: dict) -> tuple[int, bytes]:
    skills = _csv(_form_value(form, "skills"))
    anti_words = _csv(_form_value(form, "anti"))
    channel_name = _form_value(form, "channel")
    near_text = _form_value(form, "near")
    idea = _form_value(form, "idea")
    pack_id = _form_value(form, "pack")

    profile = Profile(
        name="web",
        skills=skills,
        channels=[{"name": channel_name or "你填的圈子", "keywords": _csv(near_text)[:6] or [channel_name], "role": channel_name or "第一批客户"}]
        if channel_name
        else [],
        hours_per_week=10,
        anti=[{"name": word, "keywords": [word]} for word in anti_words],
    )

    sections: list[str] = []
    notes: list[str] = []
    mode = "generic"
    near_statements: list[Statement] = []
    far_statements: list[Statement] = []

    if pack_id:
        entry = load_pack_entry(pack_id, ROOT / "data" / "packs" / "index.json")
        near_path = ROOT / entry["near"]
        far_path = ROOT / entry["far"]
        near_statements = _read_statements(near_path, "n", "near")
        far_statements = _read_statements(far_path, "f", "far")
        known = _read_jsonl(ROOT / entry["known"]) if entry.get("known") else []
        # 证据文件里有卡点与第一个客户 —— 这两维模型不判,没带证据就只能出草稿
        entries = _load_evidence(ROOT / entry["evidence"]) if entry.get("evidence") else []
        mode = "pack"
        notes.append(f"用了行业包「{entry.get('name', pack_id)}」的素材")
        if not entries:
            notes.append("这个包没有证据文件:卡点与第一个客户只能由你补,现在出的是草稿")
        else:
            notes.append(f"证据文件里有 {len(entries)} 条卡点,已用于判断「做的人卡在哪」")
    else:
        lines = split_user_text(near_text)
        if lines:
            # 用户亲手写下的按约束处理(等价于 domain 文件里的 verified: true)。
            # 闸门是用来挡模型抽出来的噪音的,不该反过来挡用户自己。
            near_statements = [
                Statement(id=f"n{i+1}", text=t, domain="near", verified=True)
                for i, t in enumerate(lines)
            ]
            mode = "materials"
            notes.append(f"近域用了你写的 {len(lines)} 条约束,按你的判断直接当约束处理(未经模型复判)")
        else:
            near_statements = _read_statements(ROOT / "data/domains/generic_near.jsonl", "gn", "near")
            notes.append("你没写约束,近域用了 8 条通用经营约束(近似)")
        far_statements = _read_statements(ROOT / "data/domains/generic_far.jsonl", "gf", "far")
        notes.append("远域用了 12 条通用合规义务,其中 6 条已核对法条、6 条待复核")
        known = _read_jsonl(ROOT / "data/projects/known_products.jsonl")
        entries = []

    if idea:
        notes.append(f"你的方向:{idea}(只当标签)")

    model = RuleModel()
    near_results = gate_statements(near_statements, model)
    far_results = gate_statements(far_statements, model)
    rows = build_candidates(near_results, far_results, known)
    cards = build_cards(rows, known, profile, entries)
    primary, alternates = pick_recommendations(cards)

    label = idea or next((name for pid, name, _ in PACKS if pid == pack_id), "") or "你的方向"
    meta = {
        "pack": label,
        "model": model.describe(),
        "primary": primary,
        "alternates": alternates,
        "unverified_far": sum(1 for r in far_results if not r.statement.verified),
        "unverified_far_items": [
            {"id": r.statement.id, "text": r.statement.text, "source": r.statement.source}
            for r in far_results
            if not r.statement.verified
        ],
        "far_contribution": sum(1 for row in rows if row.get("kw_far", 0) >= 1),
        "far_types": len({row.get("far_type") for row in rows if row.get("far_type")}),
        "notes": notes
        + [
            "闸门用的是规则版(在人工测试集上 0.8167),不是微调模型(0.8667)。"
            "网页版使用规则闸门，不依赖模型权重。"
        ],
    }
    report = render_cards(cards, meta)

    rejected = [r for r in near_results if not r.passed]
    sections.append('<p><a class="back" href="./">← 再撞一次</a></p>')
    sections.append(f"<h1>{html.escape(meta['pack'])}</h1>")
    sections.append(
        f'<p class="lead">近域 {len(near_results)} 条,过闸 {sum(1 for r in near_results if r.passed)} 条;'
        f"远域 {len(far_results)} 条,过闸 {sum(1 for r in far_results if r.passed)} 条;"
        f"命中 {len(cards)} 个方向。</p>"
    )
    sections.append(f'<details><summary>报告原文(可复制)</summary><pre>{html.escape(report)}</pre></details>')
    if rejected:
        items = "".join(f"<li>{html.escape(r.statement.text)}<br><i>判为 {html.escape(r.label or '解析失败')}</i></li>" for r in rejected[:8])
        sections.append(f"<h2>被闸门挡掉的近域表述（{len(rejected)}）</h2><ul class='list'>{items}</ul>")
    return 200, page(meta["pack"], "".join(sections))


def _load_evidence(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("entries") if isinstance(data, dict) else data
    return [item for item in (items or []) if isinstance(item, dict)]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_statements(path: Path, prefix: str, domain: str) -> list[Statement]:
    out: list[Statement] = []
    for index, row in enumerate(_read_jsonl(path), start=1):
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        out.append(
            Statement(
                id=str(row.get("id") or f"{prefix}{index}"),
                text=text,
                domain=domain,
                source=str(row.get("source", "")),
                verified=bool(row.get("verified")),
            )
        )
    return out


def make_handler(prefix: str = "") -> type[BaseHTTPRequestHandler]:
    prefix = prefix.rstrip("/")

    class Handler(BaseHTTPRequestHandler):
        def _trim(self) -> str:
            path = self.path.split("?")[0]
            if prefix and path.startswith(prefix):
                path = path[len(prefix):] or "/"
            return path

        def do_GET(self) -> None:
            raw = self.path.split("?")[0]
            # 不带斜杠访问子路径时补一个,否则相对链接会指到上一级
            if prefix and raw == prefix:
                self.send_response(301)
                self.send_header("Location", prefix + "/")
                self.end_headers()
                return
            path = self._trim()
            if path in ("/", "/index.html"):
                self._send(200, page("项目碰撞机", index_body()))
            elif path == "/health":
                self._json({"ok": True, "gate": RuleModel().describe()})
            else:
                self._send(404, page("找不到", "<h1>找不到这一页</h1><p><a class='back' href='./'>回首页</a></p>"))

        def do_POST(self) -> None:
            if self._trim() != "/run":
                self._send(404, b"not found")
                return
            ip = self.client_address[0]
            if rate_limited(ip):
                self._send(429, page("慢一点", "<h1>一分钟最多 12 次</h1><p>等一会儿再试。</p><p><a class='back' href='./'>回首页</a></p>"))
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    self._send(413, page("太长了", "<h1>一次最多 32KB</h1>"))
                    return
                raw = self.rfile.read(length).decode("utf-8", "ignore")
                form = parse_qs(raw, keep_blank_values=True)
            except (ValueError, UnicodeDecodeError):
                self._send(400, page("请求有误", "<h1>表单没读进来</h1>"))
                return
            if not _slots.acquire(timeout=20):
                self._send(503, page("忙", "<h1>现在排不上队</h1><p>过一会儿再试。</p>"))
                return
            try:
                code, body = run_collision(form)
            except Exception as exc:  # noqa: BLE001 - 页面要给出可读的原因
                body = page("出错了", f"<h1>这一轮跑失败了</h1><div class='warn'>{html.escape(str(exc))}</div><p><a class='back' href='./'>返回修改</a></p>")
                code = 500
            finally:
                _slots.release()
            self._send(code, body)

        def _send(self, code: int, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: dict) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            return

    return Handler


def serve(host: str, port: int, prefix: str = "") -> None:
    """prefix:挂在已有服务的子路径下时用,比如 /collider。

    复用 80 端口上已经跑着的东西(archrescue),不再为这一页开新端口:
    一台 1G 内存的机器上没有理由为两个网站维护两套入口。
    """
    handler_class = make_handler(prefix)

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = Server((host, port), handler_class)
    print(
        json.dumps(
            {"listen": f"http://{host}:{port}{prefix}/", "gate": RuleModel().describe()},
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()
