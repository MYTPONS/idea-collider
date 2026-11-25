from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mechanism:
    id: str
    name: str
    action: str
    cost: str
    axes: tuple[str, ...]
    keywords: tuple[str, ...]
    effort: str = "medium"
    targets: tuple[str, ...] = ()
    targets_far: tuple[str, ...] = ()
    pairs: tuple[tuple[str, str], ...] = ()
    first_step: str = ""


MECHANISMS: tuple[Mechanism, ...] = (
    Mechanism(
        "ro_snapshot", "只读快照", "留一份可看的副本,但谁都不能改", "多占一份存储,还要防它过期",
        ("compliance", "trust", "observation"), ("看", "查", "副本", "记录"), "simple",
        ("禁写", "承诺"), ("查阅",),
        (("禁写", "查阅"), ("承诺", "查阅"), ("禁写", "更正"), ("承诺", "更正")),
        first_step='写一个只读接口,把已有数据渲染成快照,不提供任何写入入口',
    ),
    Mechanism(
        "per_use_billing", "按次计费", "每次调用单独结算,不打包", "用户会为了省钱少用",
        ("cost", "market"), ("计费", "成本", "按次"), "medium", ("承诺",), (), (),
        first_step='在调用处埋一次计数,按次出账单,不做套餐',
    ),
    Mechanism(
        "tiered_disclosure", "分级披露", "按权限分层次给内容,越权看不到", "权限表要一直维护",
        ("trust", "compliance"), ("权限", "分级", "披露"), "medium",
        ("禁写", "承诺"), ("查阅",),
        (("禁写", "查阅"), ("承诺", "查阅")),
        first_step='先只做两级:全看和不看,把权限判断放在返回前',
    ),
    Mechanism(
        "dual_write", "双写", "同一份数据同时写两处,互为备份", "成本翻倍,还要处理不一致",
        ("availability", "time"), ("备份", "双写", "同步"), "medium",
        ("断裂",), ("删除",), (("断裂", "删除"),),
        first_step='同一笔写入同步落两处,读时优先主库,对账任务每天跑一次',
    ),
    Mechanism(
        "shadow_copy", "影子副本", "后台静默复制一份,前台无感", "占空间,且同步会滞后",
        ("availability", "version"), ("副本", "同步", "后台"), "simple",
        ("断裂",), ("删除", "限期"), (("断裂", "删除"), ("断裂", "限期")),
        first_step='写入时后台异步复制一份,前台不等它完成',
    ),
    Mechanism(
        "threshold_alert", "阈值告警", "越线就弹提示,不替人做决定", "阈值要调,误报会被关掉",
        ("observation", "time"), ("阈值", "告警", "提示"), "simple",
        ("打扰",), ("限期", "删除"), (("打扰", "限期"), ("打扰", "删除")),
        first_step='定一个数值阈值,越线只发通知,不自动处理',
    ),
    Mechanism(
        "seat_license", "席位制", "按人头收费,不按用量", "小团队也要付全价",
        ("cost", "market"), ("席位", "人头", "订阅"), "medium", ("绑定",), (), (),
        first_step='按账号数计费,超出人数就多买席位',
    ),
    Mechanism(
        "hot_cold_tier", "冷热分层", "常看的放近处,不常看的压到底层", "冷数据取回慢",
        ("cost", "space"), ("分层", "冷热", "存储"), "medium",
        ("打扰",), ("限期",), (("打扰", "限期"),),
        first_step='按最后访问时间分两档,冷档换更便宜的存储',
    ),
    Mechanism(
        "approval_gate", "闸门审批", "关键动作要人点头才放行", "多一道流程,急事卡住",
        ("trust", "compliance"), ("审批", "闸门", "放行"), "medium",
        ("改写",), ("更正",), (("改写", "更正"), ("承诺", "更正")),
        first_step='在写动作前插一道人工确认,不确认就不执行',
    ),
    Mechanism(
        "local_fallback", "本地兜底", "远端不可用时切本地,保证不断", "本地能力弱,结果会缩水",
        ("availability", "supply"), ("本地", "兜底", "断网"), "medium",
        ("断裂",), ("限期", "删除"), (("断裂", "限期"), ("断裂", "删除")),
        first_step='远端超时就切本地轻量版本,结果标注降级',
    ),
    Mechanism(
        "time_lock", "时间锁", "到期自动解封,期间不能动", "不能续期,急事会卡住",
        ("time", "version"), ("到期", "锁", "期限"), "simple",
        ("改写", "断裂", "承诺", "打扰"), ("限期",),
        (("改写", "限期"), ("断裂", "限期"), ("承诺", "限期"), ("打扰", "限期")),
        first_step='给记录加一个到期时间,到期前拒绝所有修改',
    ),
    Mechanism(
        "budget_cap", "预算封顶", "花到上限就停,不让人超额", "超出需求时会被嫌死板",
        ("cost", "time"), ("预算", "封顶", "上限"), "simple",
        ("打扰", "承诺"), ("限期",), (("打扰", "限期"), ("承诺", "限期")),
        first_step='给每次调用设额度上限,超了就中断',
    ),
    Mechanism(
        "allowlist", "白名单", "只放行点过名的,其余一律拒", "新东西默认进不来",
        ("trust", "network"), ("白名单", "放行", "名单"), "simple", ("禁写", "绑定"), (), (),
        first_step='维护一张放行名单,不在名单里的默认拒绝',
    ),
    Mechanism(
        "rate_limit", "限流", "超过频率就拒,保护后端", "高峰期正常请求也会被拒",
        ("availability", "cost"), ("限流", "频率", "拒绝"), "simple", ("打扰",), (), (),
        first_step='按调用方计数,超过频率就返回 429',
    ),
    Mechanism(
        "prepaid", "预付费", "先充钱再消费,余额为负即停", "要垫资,体验差",
        ("cost", "trust"), ("预付", "余额", "充值"), "simple", ("承诺",), (), (),
        first_step='先充值再扣费,余额为零即停服',
    ),
    Mechanism(
        "proof_hash", "存证哈希", "每条记录算指纹,事后能验", "只防篡改,不防伪造",
        ("trust", "version"), ("哈希", "指纹", "留痕"), "simple",
        ("承诺", "改写"), ("更正",), (("承诺", "更正"), ("改写", "更正")),
        first_step='每条记录算 sha256,写进一个只追加的日志',
    ),
    Mechanism(
        "multi_witness", "多方见证", "两方各自留证,互相对账", "要协调,且能合谋",
        ("trust", "network"), ("见证", "对账", "两方"), "medium",
        ("改写", "承诺"), ("更正",), (("改写", "更正"), ("承诺", "更正")),
        first_step='两边各存一份哈希,定期交换比对',
    ),
    Mechanism(
        "shard_store", "分片存储", "拆开放不同地方,单点拿不到全貌", "拼回来麻烦",
        ("space", "trust"), ("分片", "拆分", "多处"), "hard",
        ("禁写",), ("查阅", "删除"), (("禁写", "查阅"), ("禁写", "删除")),
        first_step='把一条数据拆成多片,分存不同位置,取时需要凑齐',
    ),
    Mechanism(
        "differential_privacy", "差分隐私", "发布前加噪声", "精度下降",
        ("trust", "observation"), ("噪声", "差分", "隐私"), "hard",
        ("禁写", "承诺"), ("查阅",), (("禁写", "查阅"), ("承诺", "查阅")),
        first_step='统计结果加拉普拉斯噪声再发布',
    ),
    Mechanism(
        "federated", "联邦计算", "数据不动,模型动", "通信成本高",
        ("space", "trust"), ("联邦", "不出域", "本地训练"), "hard",
        ("禁写", "绑定"), ("查阅", "删除"), (("禁写", "查阅"), ("绑定", "查阅")),
        first_step='把计算下发到数据所在端,只回传参数',
    ),
    Mechanism(
        "central_audit", "集中审计", "所有动作进一个账本,统一查", "账本本身成为单点",
        ("trust", "observation"), ("审计", "账本", "日志"), "medium",
        ("改写", "承诺"), ("查阅",), (("改写", "查阅"), ("承诺", "查阅")),
        first_step='所有写动作统一记进一个账本,提供按条件查询',
    ),
    Mechanism(
        "decentralized_audit", "去中心化审计", "多方各自存证,不用统一中心", "难保证一致",
        ("trust", "network"), ("去中心", "多方", "各自"), "hard",
        ("禁写", "承诺"), ("查阅",), (("禁写", "查阅"), ("承诺", "查阅")),
        first_step='多方各自存证,查询时交叉验证',
    ),
    Mechanism(
        "subscription", "订阅制", "按时间打包收费,不按次", "用不满也觉得亏",
        ("cost", "market"), ("订阅", "包月", "年费"), "simple", ("绑定", "承诺"), (), (),
        first_step='按月打包收费,不按用量结算',
    ),
    Mechanism(
        "lottery", "抽签", "名额有限就抽,不拼手速", "结果随机,急事没保障",
        ("market", "time"), ("抽签", "随机", "名额"), "hard", ("打扰",), (), (),
        first_step='名额有限时随机抽取,不按提交顺序',
    ),
    Mechanism(
        "queue", "排队", "先来先服务,不插队", "等待时间不可控",
        ("time", "supply"), ("排队", "队列", "等待"), "simple",
        ("打扰",), ("限期",), (("打扰", "限期"),),
        first_step='请求进队列按序处理,给出预计等待时间',
    ),
    Mechanism(
        "bidding", "竞价", "出价高者得,价格浮动", "价格不可预期",
        ("market", "cost"), ("竞价", "出价", "拍卖"), "hard", ("打扰",), (), (),
        first_step='资源放出来让买方出价,价高者得',
    ),
    Mechanism(
        "deposit", "押金", "先交钱,违约就扣", "占用资金,用户抵触",
        ("trust", "cost"), ("押金", "保证金", "违约"), "simple", ("承诺",), (), (),
        first_step='先收一笔押金,违约或损坏时扣除',
    ),
    Mechanism(
        "escrow", "托管", "钱或数据先放中间方,条件满足才放", "多一个中间人",
        ("trust", "market"), ("托管", "中间方", "条件"), "hard",
        ("绑定", "承诺"), ("更正",), (("绑定", "更正"), ("承诺", "更正")),
        first_step='钱或数据先放中间方,条件满足才释放',
    ),
    Mechanism(
        "replay", "重放", "同样的输入可以重跑一遍", "要存输入,隐私风险",
        ("version", "observation"), ("重跑", "重放", "复现"), "simple",
        ("改写",), ("更正",), (("改写", "更正"), ("承诺", "更正")),
        first_step='把输入原文存档,需要时按同一版本重跑',
    ),
    Mechanism(
        "watermark", "水印", "结果里埋标记,能追到来源", "能被洗掉",
        ("trust", "version"), ("水印", "标记", "溯源"), "simple",
        ("承诺", "改写"), ("更正",), (("承诺", "更正"), ("改写", "更正")),
        first_step='在输出里嵌入一段可解析的标记',
    ),
    Mechanism(
        "freeze", "冻结", "锁定当前状态,谁都不能动", "不能改,急事卡住",
        ("version", "time"), ("冻结", "锁定", "快照"), "simple",
        ("断裂", "改写"), ("删除", "限期"), (("断裂", "删除"), ("断裂", "限期"), ("改写", "删除")),
        first_step='把当前状态锁定成不可修改的版本',
    ),
    Mechanism(
        "revoke", "撤销", "给出方随时可撤回", "依赖对方配合",
        ("trust", "version"), ("撤回", "撤销", "收回"), "simple",
        ("改写", "承诺"), ("更正", "删除"),
        (("改写", "更正"), ("承诺", "更正"), ("改写", "删除"), ("承诺", "删除")),
        first_step='给每条授权加撤销入口,撤销后即时生效',
    ),
    Mechanism(
        "export", "导出", "生成一份用户可带走的副本", "导出后系统管不到",
        ("compliance", "space"), ("导出", "带走", "下载"), "simple",
        ("承诺", "绑定", "断裂"), ("查阅",),
        (("绑定", "查阅"), ("断裂", "查阅"), ("承诺", "查阅")),
        first_step='提供一个导出按钮,生成标准格式文件',
    ),
    Mechanism(
        "portable_format", "便携格式", "按公开格式输出,别的平台能读", "要维护格式兼容",
        ("compliance", "network"), ("格式", "标准", "互通"), "simple",
        ("绑定", "断裂"), ("查阅",), (("绑定", "查阅"), ("断裂", "查阅")),
        first_step='按公开 schema 输出,附字段说明',
    ),
    Mechanism(
        "unbind", "解绑", "允许把数据从账户上摘下来", "摘下来就管不到了",
        ("compliance", "trust"), ("解绑", "摘除", "脱钩"), "simple",
        ("绑定",), ("删除",), (("绑定", "删除"),),
        first_step='允许把数据从账户摘下来,改成独立持有',
    ),
    Mechanism(
        "notarize", "第三方公证", "由中立方核验并留证", "要付公证费",
        ("trust",), ("公证", "中立", "核验"), "hard",
        ("承诺",), ("查阅", "更正"), (("承诺", "查阅"), ("承诺", "更正")),
        first_step='接入第三方存证服务,对关键结果做核验',
    ),
    Mechanism(
        "discard", "即焚", "请求处理完立即丢弃,不留任何副本", "出错时无法回溯",
        ("trust", "time"), ("不留", "丢弃", "即焚"), "simple",
        ("断裂", "打扰"), ("删除",), (("断裂", "删除"), ("打扰", "删除")),
        first_step='处理完立刻删除原始请求,不留缓存和日志',
    ),
    Mechanism(
        "stateless", "无状态", "每次请求独立,不跨请求携带任何数据", "体验断裂,每次都要重新交代",
        ("trust", "version"), ("无状态", "不携带", "独立"), "simple",
        ("断裂",), ("删除", "限期"), (("断裂", "删除"), ("断裂", "限期")),
        first_step='每次请求独立处理,不落任何跨请求状态',
    ),
    Mechanism(
        "invoice", "开票", "按业务开正规票据,能进账", "有账期,现金流慢",
        ("market", "compliance"), ("发票", "票据", "对公"), "simple", ("绑定",), (), (),
        first_step='接一个开票通道,按业务出票',
    ),
    Mechanism(
        "escrow_release", "托管放款", "钱先由平台代收,确认服务完成后才放给陪玩师", "平台要垫资,还要跑对账",
        ("compliance", "cost", "availability"), ("预付款", "退款", "放款", "托管", "失联", "跳单", "结算"), "medium",
        ("断裂", "承诺"), ("承诺",),
        (("断裂", "义务"), ("承诺", "义务"), ("绑定", "义务"), ("承诺", "查阅"), ("断裂", "查阅")),
        first_step='订单改成待确认状态,确认后才触发打款',
    ),
    Mechanism(
        "bond", "保证金", "陪玩师先交一笔保证金,违约从里面扣", "新人进不来,要处理退款",
        ("trust", "cost", "availability"), ("失联", "跳单", "违约", "投诉"), "medium",
        ("断裂", "承诺"), ("承诺",),
        (("断裂", "义务"), ("承诺", "义务"), ("断裂", "查阅"), ("承诺", "查阅")),
        first_step='先从接单前冻结一小笔额度开始,不真收钱',
    ),
    Mechanism(
        "cooling_off", "冷静期", "付款后一段时间内可以无理由退", "会被当成免费试用",
        ("compliance", "time", "trust"), ("退单", "退款", "中途", "退货", "七天"), "simple",
        ("承诺",), ("承诺", "更正", "其他"),
        (("承诺", "义务"), ("承诺", "禁止"), ("承诺", "查阅")),
        first_step='订单里加一个可退窗口,过期自动关',
    ),
    Mechanism(
        "segment_release", "分段放款", "按服务进度分批放款,做完一段放一段", "对账变复杂",
        ("cost", "time", "trust"), ("时长", "分段", "进度", "结算"), "medium",
        ("断裂", "承诺"), ("查阅",),
        (("断裂", "义务"), ("承诺", "义务"), ("断裂", "查阅"), ("承诺", "查阅")),
        first_step='先把一单拆成两段,各放一半',
    ),
    Mechanism(
        "order_binding", "站内绑定", "下单后双方只能通过站内渠道联系,站外交易不计入保障", "用户会绕过",
        ("trust", "compliance"), ("站外", "私下", "微信", "私下交易"), "simple",
        ("绑定",), ("其他", "承诺"),
        (("绑定", "禁止"), ("绑定", "义务"), ("绑定", "查阅")),
        first_step='聊天入口只留站内,检测到联系方式就提示',
    ),
    Mechanism(
        "session_capture", "全程留痕", "服务过程录音或录屏存证,纠纷时调取", "存储和隐私成本",
        ("compliance", "trust", "observation"), ("辱骂", "骚扰", "纠纷", "封号"), "hard",
        ("打扰", "断裂"), ("查阅",),
        (("打扰", "义务"), ("断裂", "义务"), ("打扰", "查阅"), ("断裂", "查阅")),
        first_step='先只存文字聊天记录,不碰语音',
    ),
    Mechanism(
        "minor_gate", "未成年闸门", "识别到未成年人就限制下单和打赏", "误判会挡住正常用户",
        ("compliance", "trust"), ("未成年", "退款", "监护人"), "medium",
        ("承诺", "绑定"), ("承诺", "其他"),
        (("承诺", "义务"), ("绑定", "禁止"), ("承诺", "查阅")),
        first_step='先做实名年龄校验,不合格直接不展示付费项',
    ),
    Mechanism(
        "invoice_split", "分账开票", "平台、陪玩师分别开票,钱按比例分账", "要对接税务",
        ("compliance", "cost", "market"), ("开票", "发票", "抽成", "个税"), "hard",
        ("绑定",), ("其他", "查阅"),
        (("绑定", "义务"), ("绑定", "查阅")),
        first_step='先给企业客户开平台服务费那一张',
    ),
)


def mechanisms_for(near_axis: str | None, far_axis: str | None) -> tuple[Mechanism, ...]:
    out: list[Mechanism] = []
    for mechanism in MECHANISMS:
        if near_axis and near_axis in mechanism.axes:
            out.append(mechanism)
        elif far_axis and far_axis in mechanism.axes:
            out.append(mechanism)
    return tuple(out)


def mechanisms_by_axis(axis: str) -> tuple[Mechanism, ...]:
    return tuple(mechanism for mechanism in MECHANISMS if axis in mechanism.axes)
