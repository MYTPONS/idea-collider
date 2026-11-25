# exp-07 造与反向合一

## 目的

把"机制组合造形态"和"拿已有产品验缺口"接成一条流水线,一个命令出结果。

## 实现

`collider forge --near ... --far ... --out ... --known ...`

1. gate 判两域约束
2. `search_mechanisms` 出机制组合
3. `novelty.judge` 拿组合里的机制关键词比对已知产品的 satisfies 与 gap
   - 机制关键词命中某产品 satisfies → 已被做
   - 命中某产品 gap → 空白,且标明补的是谁的缺口
   - 都不命中 → 空白
4. 按形态去重,同一形态撞的多个约束对合并
5. 出 `report.md`(空白/部分重叠/已被做三组)与 `candidates.jsonl`

## 结果

memory_products × data_rights,23 条组合去重成 15 条:

- 空白 14 条
- 已被做 1 条:闸门审批,Claude Duet 的"敏感操作前请求批准"已覆盖
- 明确补缺口 2 条:导出、改写前时间锁,补阿里云 Memory 的"不提供查阅导出删除入口"

## 结论

- 反向验证真实起作用:闸门审批被认出来是 Claude Duet 已做的,没有被当成新机会
- 造的部分真实起作用:导出、便携格式这类形态是机制关键词与产品 gap 对上才出的,不是随机组合
- 覆盖不足:known_products 只有 5 个产品,gap 写得太粗,导致大部分组合 nearest 为空

## 下一步

- known_products 扩到 20 个以上,每个 gap 写细
- 机制关键词补"账户/跨平台"一类,让便携格式能对上阿里云 Memory 的"记忆锁定在账户内"
