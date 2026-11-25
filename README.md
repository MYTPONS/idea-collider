# 项目碰撞机 / idea-collider

在没有具体需求、只有能力的情况下,把两个互不相干的领域的硬约束求交集,找出"约束互相冲突、而现有方案从未同时满足过"的产品形态。

它不生成点子。它生成候选,然后用四维过滤把九成五砍掉。留下的那一条才算方向。

仓库有三层:一层是方法与实验记录(`docs/`),一层是判断模型(gate / relate),一层是机制组合与反向核对(`search` / `forge`)。

## 模型

- 底座:`Qwen/Qwen2.5-0.5B-Instruct`
- 微调:LoRA,`r=16`、`alpha=32`、dropout 0.05,可训练参数 8.8M / 502M(1.75%)
- 三个任务:
  - `gate`:判断一条表述是约束还是痛点,并给轴向,实测 0.8667
  - `relate`:判断两条约束是否真的在同一件事上互相施加要求,实测 11/12
  - `collide`:给定近域、远域各一条约束,生成产品形态草稿
- 0.5B 的经验边界:**训过的任务准,没训过的一律退化**。任何未训练的二分类,它都全判 `true`
- 训练环境:CPU 可训 0.5B LoRA,48 条 6 epochs 约 6 分钟,168 条 3 epochs 约 21 分钟

## 管线

```
约束 JSONL
   │
   ├─ gate(模型)──── 约束/痛点 + 轴向,软表述在这里被砍
   │
   ├─ axes(代码)──── 轴向分布;少于三根轴或单轴过半就告警
   │
   ├─ relate(模型)── 两域逐对判相关性,不相关的对不进碰撞
   │
   ├─ search(代码)── 机制库 × 约束对枚举形态,按轴、远域风格、近域类型、关键词打分
   │
   ├─ collide(模型)─ 模型直接生成形态(与 search 二选一)
   │
   ├─ forge(代码)── search + 反向核对:机制关键词比对已知产品的 satisfies 与 gap
   │
   └─ filter(代码)── 四维证据核对,证据齐全才算 alive
```

模型只做判定与生成草稿。碰撞阶段对每一对约束都尝试给形态,不负责判死;四维过滤里的事实(已有产品、卡点、第一个客户)必须来自 `evidence` 文件,模型编造的一律标为 `draft`,不计入存活。这是 `docs/DESIGN.md` 第四维的直接落地。

`forge` 的产出是一张张**项目卡**,不是机制名。四维缺一维就降为草稿并写明缺哪一维;一次只推 1 主推 + 2 备选。

## 快速开始

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python --torch-backend=auto torch
uv pip install --python .venv/bin/python transformers peft accelerate datasets pytest
.venv/bin/hf download Qwen/Qwen2.5-0.5B-Instruct --local-dir artifacts/Qwen2.5-0.5B-Instruct
```

训练与评估:

```bash
.venv/bin/python train/prepare_data.py
.venv/bin/python train/build_collide_data.py
.venv/bin/python train/build_teacher_collide.py
.venv/bin/python train/train_lora.py --tasks gate
.venv/bin/python train/train_lora.py --tasks relate --gate-train data/relate_train.jsonl --gate-dev data/relate_dev.jsonl --collide /tmp/idea-collider/empty.jsonl
.venv/bin/python train/train_lora.py --tasks collide --collide data/collide_train2.jsonl --gate-train /tmp/idea-collider/empty.jsonl
```

机制组合:

```bash
.venv/bin/python -m collider search --near data/domains/memory_products.jsonl --far data/domains/data_rights.jsonl --out runs/search.jsonl
```

造与反向核对合一:

```bash
.venv/bin/python -m collider --model-dir artifacts/qwen-collider-merged forge \
  --near data/domains/memory_products.jsonl \
  --far data/domains/data_rights.jsonl \
  --out runs/forge
```

文档直接进也可以,模型先抽约束再撞:

```bash
.venv/bin/python -m collider --model-dir artifacts/qwen-extract4-merged forge \
  --near-doc docs/experiments/exp-05.md \
  --far-doc docs/experiments/exp-04.md \
  --out runs/forge-docs
```

产出:

- `runs/forge/report.md` — **项目方向**:一张主推卡 + 最多两张备选卡,每张带四维(已有产品与缺口 / 卡点 / 两周第一版 / 第一个客户)、"为什么是你"、难度与代价;四维没齐的降到草稿区并写明缺哪一维
- `runs/forge/cards.jsonl` — 全部项目卡(含草稿、已被做、踩到你 anti 项被排除的)
- `runs/forge/candidates.jsonl` — 底层的机制 × 约束对,保留用于排查

项目卡的"为什么是你"来自 `data/me.json`（技能 / 够得着的渠道 / 每周时间 / 不做的类型）。公开仓库只提供脱敏模板 `data/me.example.json`；开始时复制一份并填入自己的情况：

```bash
cp data/me.example.json data/me.json
```

没有这个文件也能跑，只是匹配分为 0。第一个客户优先取证据文件里的值，其次取你档案里够得着的渠道。

分步命令:

```bash
.venv/bin/python -m collider gate --input data/domains/ai_access.jsonl --out runs/gated.jsonl
.venv/bin/python -m collider relate --near data/domains/memory_products.jsonl --far data/domains/data_rights.jsonl --out runs/related.jsonl --relate-model artifacts/qwen-relate-merged
.venv/bin/python -m collider filter --candidates runs/candidates.jsonl --evidence data/evidence/exp05.json --out runs/filtered
```

## 碰撞出一个项目

两种入口,产出是同一种东西:

```bash
# 1. 说一个领域:直接选预制包(近域已备好约束与已知产品)
.venv/bin/python -m collider --model-dir artifacts/qwen-collider-merged forge --pack ai-industry --out runs/ai-industry

# 2. 传材料:文档先进闸门抽约束,再撞
.venv/bin/python -m collider --model-dir artifacts/qwen-collider-merged forge \
  --near-doc 我的领域.md --far data/domains/ai_forensics.jsonl --out runs/mine
```

一次产出一份 `report.md`:

1. **主推**(1 张):撞的约束、已有产品与它留的缺口、做的人卡在哪、两周第一版、第一个客户、为什么是你
2. **备选**(最多 2 张):同样的四维
3. **草稿**:四维缺哪一维写在表里,补齐即可升级
4. **已被做**:已知产品已覆盖,不再推
5. **本次注意**:远域有几条没复核、远域到底起没起作用(全是同一种远域类型 = 没起作用,结论不可用)

能不能开工看主推那张卡的"第一个客户"是不是你够得着的人——这一维砍掉九成五,和手工跑的时候一样。

### 没有素材的时候

不会拒绝,也不会瞎编远域。按三档退,每一档都在报告的"这一轮用了什么"里写明:

| 你给了 | 走哪档 | 用的是什么 |
|---|---|---|
| 一个包名 | `--pack` | 包里核过的近域、远域、已知产品、证据 |
| 近域 + 远域文件 | 材料 | 你自己的 |
| 只有近域 | `generic-far` | 远域用 12 条通用合规义务近似,必须先复核 |
| 只有远域 | `generic-near` | 近域用 8 条通用经营约束近似 |
| 什么都没给 | `generic` | 两侧都通用 |
| 只有一句想法 | 加 `--idea` | 走 `generic`,你的话只当标签 |

后四档还会在输出目录里写一份 `材料模板.md`:按这一轮撞出来的方向,告诉你该去哪找哪一类事实、文件长什么样、填完怎么重跑。通用约束全部标 `verified: false`,报告里逐条列出。

一句话:**它可以先用近似约束陪你跑一遍,但不会假装那是你行业的事实。**

## 行业包

客户不想自己准备素材时,直接选包:

```bash
.venv/bin/python -m collider packs
.venv/bin/python -m collider --model-dir artifacts/qwen-collider-merged forge --pack memory-pipl --out runs/pack-pipl
```

包清单在 `data/packs/index.json`,一个包就是一对近域/远域文件。加新行业等于加一条。

## HTTP 接口

一次请求算一次碰撞,按次计费的计量写在 `runs/usage.jsonl`:

```bash
.venv/bin/python -m collider --model-dir artifacts/qwen-collider-merged serve --port 8080
curl -X POST http://127.0.0.1:8080/collide -H 'Content-Type: application/json' \
  -d '{"near":["用户不能直接修改记忆"],"far":["个人有权查阅、复制其个人信息"]}'
```

接口说明见 `docs/API.md`。

## 结果

60 条人工标注测试集(`eval/cases.jsonl`),约束与痛点各 30 条,训练集从未使用这些样本:

| 方案 | 准确率 | 说明 |
|---|---|---|
| 关键词基线 | 0.6167 | 命中「希望/要/支持/可能」等词就判痛点 |
| Qwen2.5-0.5B 零样本 | 0.4333 | 同一提示不微调,大量约束被判成痛点 |
| 微调后 | **0.8667** | LoRA 适配器,约束/痛点各 26/30 判对 |

相关性判断(`data/relate_dev.jsonl`,12 条留出):

| 方案 | 准确率 | 说明 |
|---|---|---|
| 未微调 | 7/12 | 全判 related,等于正类比例 |
| 微调后 | **11/12** | 只有一例边界判错 |

机制组合(`memory_products × data_rights`,6 × 4 对):

| 阶段 | 候选 | 空白 | 已被做 |
|---|---|---|---|
| 只按轴匹配 | 55 | — | — |
| 加远域风格与关键词 | 23 | 14 | 1 |
| 加近域类型 | 32 | 11 | 3 |

推荐列表里可动手的:账户内便携格式、导出、只读快照、改写前时间锁、撤销。反向核对指出导出与便携格式补的是阿里云 Memory 的缺口,闸门审批已被 Claude Duet 覆盖。

## 目录

```
collider/            推理与管线
  model.py           模型加载、gate/collide/relate 调用
  gate.py            约束闸门
  axes.py            轴向分布与告警
  relate.py          相关性筛选
  collide.py         配对、生成、去重
  mechanisms.py      机制库(47 个,带动作/代价/轴/关键词/难度/近域类型)
  search.py          机制 × 约束组合
  novelty.py         反向核对:比对已知产品的 satisfies 与 gap
  filter.py          四维证据核对
  report.py          markdown / JSON 报告
  cli.py             命令行
train/
  prepare_data.py    清洗合成闸门数据并切分
  build_collide_data.py  从 docs/experiments/*.md 解析碰撞样本
  build_teacher_collide.py  生成教师碰撞样本
  train_lora.py      LoRA 微调与合并,支持 --tasks
  evaluate.py        三口径评估
data/                训练数据、领域约束、证据、已知产品
eval/                人工测试集与评估结果
docs/                方法、决策、实验记录
configs/             运行配置
runs/                运行产物(不入库)
```

## 数据 provenance

- 人工测试集 `eval/cases.jsonl` 是四轮实验沉淀的 60 条表述,只做测试。
- 闸门训练集 870 条由教师模型按固定提示生成,清洗后 868 条,已做去重、轴一致性校验与测试集泄漏检查。
- 相关性训练集 `data/relate_train.jsonl` 48 条、留出 12 条,标签人工判定。
- 碰撞训练集两套:一套从 `docs/experiments/exp-01..04.md` 解析(28 行 × 10);一套是教师样本 `data/collide_train2.jsonl` 168 条(84 对 × 2 形态),带产品名。
- 已知产品 `data/projects/known_products.jsonl` 20 个,每个带 what / satisfies / gap,来源为各自官网。

## 设计边界

- 0.5B 不做事实核查。已有产品、卡点、客户来源必须由人填进 `evidence`;没有证据的候选只算草稿。
- 模型生成的上限等于教师样本的水平。要超出,得靠机制组合,不是继续堆样本。
- 机制库与近域类型表是手工维护的,换新域要补 `data/domains/types.json`。
- 远域约束必须来自可查文档,不能靠模型回忆。这个实现不替你抓文档,只负责判定与碰撞。
- 自动化不改变 `docs/DECISION.md` 的业务判断:在没有三次真实客户对话之前,系统化提高的仍然是产量,不是证据。

## 文档

- `docs/DESIGN.md` — 机制、六条硬规则、四维过滤、验收标准、已知失效模式
- `docs/DECISION.md` — 四轮之后的决策
- `docs/experiments/exp-01..09.md` — 实验记录
- `data/README.md` — 数据来源与清洗口径

## 给 agent 用

网页表单只能问一轮:人填完拿到草稿,没有下一步。agent 能接着问,所以接口在返回结果的同时返回**下一步该问什么**;

```json
{"counts": {"cards": 1, "drafts": 5},
 "primary": {...},
 "ask_user": ["主推是「无状态」。先确认:这个方向你现在能动手吗？", "还有别的卡点吗？"]}
```

把用户的回答放进 `evidence` 再调一次,草稿就升级成项目卡。

```bash
python -m collider mcp                                     # MCP stdio,给本地 agent 挂
python -m collider api --host 0.0.0.0 --port 18081         # HTTP JSON,给远端 agent
```

四个工具:`collide` / `list_packs` / `explain_conflict` / `materials_template`。完整说明见 `docs/AGENT.md`。

## 网页版

给不懂命令行的人用，不需要 torch（网页版使用规则闸门，不是微调模型）：

```bash
.venv/bin/python -m collider web --host 127.0.0.1 --port 18080
```

页面只问三个问题:你熟悉什么、你被什么卡过、撞哪个领域。近域那一栏写下的句子直接当成约束(不再经过闸门复判);留空就走通用约束,并在结果页说明「这一轮用的是近似」。

部署到公网前请在前面加 TLS 反向代理，并把监听地址、限流和鉴权配置改成你自己的。

限制:每 IP 每分钟 12 次、单次请求体 32KB、同时最多 4 个碰撞。闸门是 `collider/rulegate.py` 的规则版，在人工测试集上 0.8167，低于微调模型的 0.8667，页面会写明这一点。
