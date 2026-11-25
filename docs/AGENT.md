# 给 agent 用的接法

网页表单只能问一轮:人填完,拿到草稿,然后没有下一步。agent 可以接着问,所以这里的接口
在返回结果的同时,**返回下一步该问什么**(`ask_user`)。把用户回答放进 `evidence` 再调一次,草稿就会升级成项目卡。

## 三种接法

| 方式 | 命令 | 适用 |
|---|---|---|
| MCP(stdio) | `python -m collider mcp` | 本地或远端 agent 直接挂进程 |
| HTTP JSON | `python -m collider api --host 0.0.0.0 --port 18081` | 远端 agent、别的语言 |
| 网页 | `python -m collider web` | 人直接用 |

## MCP 配置

Claude Code / 任何支持 stdio MCP 的客户端:

```json
{
  "mcpServers": {
    "idea-collider": {
      "command": "/usr/bin/python3",
      "args": ["-m", "collider", "mcp"],
      "cwd": "/path/to/idea-collider"
    }
  }
}
```

远端机器上没装代码也行,直接连 HTTP:

```bash
curl -s -X POST http://127.0.0.1:18081/collide -H 'Content-Type: application/json' \
  -d '{"pack":"ai-industry","skills":["Python"],"channel":"中转商"}'
```

## 四个工具

### `collide`

输入键都可选:

| 键 | 说明 |
|---|---|
| `pack` | 行业包 id,先调 `list_packs` |
| `near` / `far` | 约束字符串数组 |
| `near_text` / `far_text` | 素材原文,按句切 |
| `near_file` / `far_file` | 文件路径 |
| `skills` / `channel` / `anti` | 用户的技能、够得着的人、不做的类型 |
| `evidence` | 用户回答的卡点与第一个客户,按机制名挂 |

返回:

```json
{
  "mode": "pack",
  "counts": {"cards": 1, "drafts": 5, "taken": 1},
  "primary": {...},
  "alternates": [...],
  "cards": [{"form": "...", "status": "card|draft|taken", "missing": [...], "conflict": "..."}],
  "ask_user": ["下一步该问用户的话"],
  "warnings": ["远域用的是通用合规义务,必须先复核才能当结论"],
  "rejected_near": [...],
  "unverified_far": [...]
}
```

`status == "card"` 才算能开工。`draft` 的 `missing` 里写着缺哪一维,`ask_user` 里就是对应的问法。

### `list_packs`

返回可用的行业包。用户说「AI 行业」时先看这里。

### `explain_conflict`

查一对「近域类型 × 远域类型」是不是真冲突。`禁写 × 查阅` 不是(只读快照就能同时满足),
`禁写 × 更正` 是。agent 拿这个拦住假候选。

### `materials_template`

用户什么都没有时,给他一份「该去收集什么事实」的模板。

## 一个完整的对话

```
agent: collide({"pack": "ai-industry", "channel": "中转商"})
  → counts: {cards: 1, drafts: 5}
  → ask_user: ["主推是「无状态」。先确认:这个方向你现在能动手吗？", "还有别的卡点吗？"]

agent: (把这两个问题问用户)

agent: collide({"pack": "ai-industry", "channel": "中转商",
                "evidence": [{"mechanisms": ["stateless"],
                              "blocker": "用户回答的卡点",
                              "first_customer": {"role": "...", "channel": "..."}}]})
  → 对应的 draft 升级为 card
```

## 边界

- 网页版使用规则闸门 `0.8167`，不是微调模型 `0.8667`。`gate` 字段会写明。
- `warnings` 非空时不要把这些结论当成用户行业的事实。
- `unverified_far` 里的条目没核对过法规原文,引用前必须自己核实。
