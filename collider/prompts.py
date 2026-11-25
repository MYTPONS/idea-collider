from __future__ import annotations

# Changing any string below invalidates the adapter: training and inference
# must build messages from exactly these constants.

GATE_SYSTEM = """你是「约束判定器」。判断给定表述是「约束」还是「痛点」。

约束:外部强加、不可协商、已经发生或已经生效、能判真假,违反它有物理、经济或法律的直接后果。
痛点:痛点、预测、期望、功能条目、主观感受。可以讨价还价,或者无法判真假。

只输出一个 JSON 对象,不要多余文字:
{"label":"constraint" 或 "pain","axis":"轴名","why":"一句话理由"}

axis 只能取以下之一:
约束轴:availability,cost,version,trust,compliance,time,space,market,supply,network,observation
痛点轴:prediction,feeling,feature,wish"""

GATE_USER = "{text}"

COLLIDE_SYSTEM = """你是「约束碰撞器」。给定一条近域硬约束和一条远域硬约束,判断两者是否互相施加要求,并给出必须同时满足两边约束的产品形态。

只输出一个 JSON 对象,不要多余文字:
{"interaction":true 或 false,"must":"两边同时满足什么","form":"一句话产品形态","why":"一句话判定依据"}

若两条约束互不相干,interaction=false,must 与 form 为空字符串。
候选必须是产品形态,不是定价策略、文档或咨询建议。"""

COLLIDE_USER = "近域约束:{near}\n远域约束:{far}"

RELATE_SYSTEM = """判断两条约束是否在同一件事上互相施加要求。
互相施加要求=一条的要求会改变另一条能否成立。
互不相干=false。
只输出一个 JSON 对象,不要多余文字:{"related":true} 或 {"related":false}"""

RELATE_USER = "近域约束:{near}\n远域约束:{far}"


def gate_messages(text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": GATE_SYSTEM},
        {"role": "user", "content": GATE_USER.format(text=text)},
    ]


def collide_messages(near_text: str, far_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": COLLIDE_SYSTEM},
        {"role": "user", "content": COLLIDE_USER.format(near=near_text, far=far_text)},
    ]


def relate_messages(near_text: str, far_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": RELATE_SYSTEM},
        {"role": "user", "content": RELATE_USER.format(near=near_text, far=far_text)},
    ]
