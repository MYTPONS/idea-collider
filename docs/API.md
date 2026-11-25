# HTTP 接口

一次请求算一次碰撞,计量写在 `runs/usage.jsonl`,按次计费以此为凭证。

## 启动

```bash
.venv/bin/python -m collider --model-dir artifacts/qwen-collider-merged serve \
  --host 127.0.0.1 --port 8080 --usage runs/usage.jsonl
```

启动时加载模型,约 30 秒。之后每次请求 5 到 10 秒。

## 鉴权与配额

客户清单放在 `--clients` 指向的文件(默认 `data/clients.json`),格式见 `data/clients.example.json`:

```json
{"clients": [{"name": "客户名", "token": "下发的凭证", "quota": 100}]}
```

- 文件存在时,`POST /collide` 必须带 `Authorization: Bearer <token>`,否则 401
- `quota` 是次数上限,用尽后 402;填 0 表示不限
- 文件不存在时不鉴权,只适合本机调试
- 每次成功请求在 `runs/usage.jsonl` 记一行,带 `client` 字段

凭证不要写进仓库,`clients.example.json` 里的 `REPLACE_ME` 会被忽略。

## 接口

### `GET /health`

```json
{"ok": true, "model": "merged:qwen-collider-merged"}
```

### `POST /collide`

请求体:

```json
{
  "near": ["用户不能直接修改记忆内容", "记忆绑定在单个平台账户上"],
  "far": ["个人有权查阅、复制其个人信息", "个人发现信息不准确，有权请求更正"]
}
```

`near` 与 `far` 可以给字符串,也可以给 `{"id": "...", "text": "..."}`。每侧最多 40 条。

也可以只给行业包,不让客户准备素材:

```json
{"pack": "memory-saas"}
```

包清单见 `data/packs/index.json`,可用 `collider packs` 列出。

响应:

```json
{
  "candidates": 7,
  "blank": 6,
  "partial": 0,
  "existing": 1,
  "recommended": [
    {
      "form": "只读快照（可查视图）｜留一份可看的副本,但谁都不能改",
      "first_step": "写一个只读接口,把已有数据渲染成快照,不提供任何写入入口",
      "pairs": "「用户不能直接修改记忆内容」×「个人有权查阅、复制其个人信息」"
    }
  ],
  "usage": {"at": "...", "near": 3, "far": 3, "candidates": 7, "seconds": 8.6}
}
```

`recommended` 只给空白且第一版简单的条目,最多 5 条。完整候选见命令行 `forge` 的报告。

## 计量

每次成功请求追加一行:

```json
{"at": "2026-11-09T11:38:25", "near": 3, "far": 3, "near_passed": 2, "far_passed": 1, "candidates": 7, "blank": 6, "partial": 0, "existing": 1, "seconds": 8.6}
```

`near_passed` 与 `far_passed` 是模型判定为硬约束的条数。被判定为痛点或无法解析的条目不计入碰撞,但请求本身仍算一次。

## 计费口径

- 按请求计次,不按候选条数
- 失败请求(400 / 500)不计次
- 单次上限每侧 40 条,超出返回 400

## 当前限制

- 没有 HTTPS,TLS 交给前置代理
- 没有并发控制,模型推理串行
- 结果同步返回,长任务会占住连接
