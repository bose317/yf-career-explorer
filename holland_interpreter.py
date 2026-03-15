"""Holland Code 五层解读引擎.

规则层：计算分数结构、兼容度、张力等结构化数据。
OaSIS 层：查询加拿大 NOC 职业匹配。
AI 层：调用 Qwen3-32B 大语言模型，基于规则 + 真实职业数据生成自然语言五层报告。
"""

from openai import OpenAI
import streamlit as st

# ── Qwen3-32B API 配置 ───────────────────────────────────────────
QWEN_BASE_URL = "http://113.108.105.54:3000/v1"
QWEN_API_KEY = "9e7d5b627e4ac73da50e5c1182a81b02bd43e34e16992c49b0ccc968ae4ad9b2"
QWEN_MODEL = "Qwen/Qwen3-32B"

# ── RIASEC 邻近关系（六边形模型）──────────────────────────────────
ADJACENT_PAIRS = {
    frozenset(("R", "I")), frozenset(("I", "A")), frozenset(("A", "S")),
    frozenset(("S", "E")), frozenset(("E", "C")), frozenset(("C", "R")),
}
OPPOSITE_PAIRS = {
    frozenset(("R", "S")), frozenset(("I", "E")), frozenset(("A", "C")),
}

RIASEC_ORDER = ["R", "I", "A", "S", "E", "C"]

TYPE_LETTER_TO_NAME = {
    "R": "Realistic", "I": "Investigative", "A": "Artistic",
    "S": "Social", "E": "Enterprising", "C": "Conventional",
}

DIMENSION_CN = {
    "R": "现实型 (Realistic)",
    "I": "研究型 (Investigative)",
    "A": "艺术型 (Artistic)",
    "S": "社会型 (Social)",
    "E": "企业型 (Enterprising)",
    "C": "常规型 (Conventional)",
}

# 六维详细描述（用于 prompt 丰富解读）
DIMENSION_DETAILS = {
    "R": {
        "tasks": "操作工具、机械、设备，户外劳动，动手修理与制造",
        "environment": "工厂、工地、实验室、户外场所，强调动手与实物操作",
        "behaviors": "偏好明确任务、可见成果，重视效率和实用性",
    },
    "I": {
        "tasks": "研究、分析、实验、数据解读、理论建模",
        "environment": "实验室、研究机构、学术环境，强调独立思考与深度探索",
        "behaviors": "好奇心强，喜欢提问和解决复杂问题，重视证据和逻辑",
    },
    "A": {
        "tasks": "创作、设计、表演、写作、视觉艺术",
        "environment": "工作室、剧场、设计公司、自由职业，强调自主与创造空间",
        "behaviors": "追求原创与美感，不喜欢重复性规则，重视个人表达",
    },
    "S": {
        "tasks": "教学、辅导、护理、社会服务、团队协作",
        "environment": "学校、医院、社区机构、非营利组织，强调人际互动",
        "behaviors": "关注他人需求，善于倾听与沟通，重视合作与帮助",
    },
    "E": {
        "tasks": "管理、销售、谈判、创业、项目推动",
        "environment": "商业公司、销售团队、管理层、创业环境，强调影响力与目标",
        "behaviors": "喜欢领导和说服，敢于冒险，追求成就和地位",
    },
    "C": {
        "tasks": "数据录入、文件管理、财务核算、流程执行",
        "environment": "办公室、金融机构、行政部门，强调秩序与规范",
        "behaviors": "注重细节和准确性，喜欢有章可循的工作方式",
    },
}


# ── 规则引擎 ────────────────────────────────────────────────────
def compute_rule_outputs(scores: dict) -> dict:
    """基于六维分数，产出结构化规则判定结果。"""
    ranked = sorted(RIASEC_ORDER, key=lambda t: scores[t], reverse=True)
    top3 = ranked[:3]

    gap_1_2 = scores[ranked[0]] - scores[ranked[1]]
    gap_2_3 = scores[ranked[1]] - scores[ranked[2]]
    gap_top3_max = scores[ranked[0]] - scores[ranked[2]]
    gap_high_low = scores[ranked[0]] - scores[ranked[5]]

    if gap_1_2 >= 1.0 and gap_top3_max >= 1.5:
        structure_type = "集中型"
        structure_desc = "主兴趣非常突出，方向感较明确"
    elif gap_top3_max <= 0.6:
        structure_type = "均衡型"
        structure_desc = "前三项分数非常接近，兴趣较为广泛"
    elif gap_1_2 <= 0.3 and gap_2_3 >= 0.8:
        structure_type = "双核心型"
        structure_desc = "前两项分数接近且同时突出，存在双重兴趣驱动"
    elif gap_high_low <= 1.0:
        structure_type = "分散型"
        structure_desc = "各维度分数差异较小，兴趣尚未分化明显"
    else:
        structure_type = "梯度型"
        structure_desc = "兴趣呈现逐级递减的梯度分布"

    complements = []
    tensions = []
    for i in range(len(top3)):
        for j in range(i + 1, len(top3)):
            pair = frozenset((top3[i], top3[j]))
            if pair in ADJACENT_PAIRS:
                complements.append(
                    f"{DIMENSION_CN[top3[i]]} 与 {DIMENSION_CN[top3[j]]} 相邻互补"
                )
            elif pair in OPPOSITE_PAIRS:
                tensions.append(
                    f"{DIMENSION_CN[top3[i]]} 与 {DIMENSION_CN[top3[j]]} 处于对角，可能存在内部张力"
                )

    certainties = []
    uncertainties = []
    if gap_1_2 >= 1.0:
        certainties.append(f"主兴趣 {DIMENSION_CN[ranked[0]]} 较为明确")
    else:
        uncertainties.append(f"第一与第二兴趣差距较小({gap_1_2:.1f})，需进一步验证主次")
    if gap_2_3 <= 0.3:
        uncertainties.append(f"第二与第三兴趣非常接近({gap_2_3:.1f})，排序可能因情境变化")
    else:
        certainties.append(f"前三码排序相对稳定")

    return {
        "sorted_types": [{"type": t, "label": DIMENSION_CN[t], "score": round(scores[t], 2)} for t in ranked],
        "top3": top3,
        "top3_labels": [DIMENSION_CN[t] for t in top3],
        "gaps": {
            "gap_1_2": round(gap_1_2, 2),
            "gap_2_3": round(gap_2_3, 2),
            "gap_top3_max": round(gap_top3_max, 2),
            "gap_high_low": round(gap_high_low, 2),
        },
        "structure_type": structure_type,
        "structure_desc": structure_desc,
        "complements": complements,
        "tensions": tensions,
        "certainties": certainties,
        "uncertainties": uncertainties,
    }


# ── OaSIS NOC 职业查询 ──────────────────────────────────────────
def fetch_noc_matches_for_interpretation(top3: list[str]) -> dict:
    """调用 OaSIS 获取与 Holland Code 前三码匹配的 NOC 职业列表。

    Returns:
        {
            "success": bool,
            "matches": [{"code": "21232", "title": "Software developers..."}, ...],
            "descriptions": {"21232": {"title": "...", "description": "...", "duties": [...]}},
            "error": str or None,
        }
    """
    from oasis_client import fetch_oasis_matches, fetch_noc_unit_profile

    interest_names = [TYPE_LETTER_TO_NAME[t] for t in top3]
    oasis_result = fetch_oasis_matches(interest_names[0], interest_names[1], interest_names[2])

    result = {
        "success": oasis_result["success"],
        "matches": oasis_result["matches"],
        "descriptions": {},
        "error": oasis_result.get("error"),
    }

    if not oasis_result["success"]:
        return result

    # 获取前 10 个 NOC 的详细描述（避免过多 API 调用）
    for match in oasis_result["matches"][:10]:
        code = match["code"]
        try:
            profile = fetch_noc_unit_profile(code)
            if profile.get("title"):
                result["descriptions"][code] = {
                    "title": profile["title"],
                    "example_titles": profile.get("example_titles", [])[:6],
                    "main_duties": profile.get("main_duties", [])[:5],
                    "employment_requirements": profile.get("employment_requirements", [])[:3],
                }
        except Exception:
            pass

    return result


# ── AI 提示词构建 ────────────────────────────────────────────────
SYSTEM_PROMPT = """你是一名严谨的 Holland Code / RIASEC 职业兴趣测评解读顾问，同时精通加拿大 NOC（National Occupational Classification）职业体系。你的任务不是预测命运，而是把兴趣结构解释清楚，结合真实的职业数据，提供可验证的探索建议。

全局约束：
1. 兴趣不等于能力，不得做决定论判断。
2. 不得只列职业名称，必须解释该职业的核心任务、工作环境、日常工作内容，以及为什么与用户的兴趣结构匹配。
3. 当分数接近时，必须明确写出"不确定性"和"需要继续验证"的部分。
4. 语言应专业、清晰、克制，避免空泛鼓励。
5. 输出使用中文。
6. 不要输出任何思考过程，直接输出最终结果。
7. 每一层的内容都要详细、具体、有深度，避免笼统泛泛的描述。
8. 在讨论职业方向时，必须结合提供的 NOC 职业数据（职位名称、核心职责、任职要求），进行具体分析。"""


def build_user_prompt(scores: dict, rule_outputs: dict,
                      noc_data: dict,
                      stage: str = "高中", scenario: str = "选专业",
                      background: str = "") -> str:
    """构建发给大模型的 user prompt，包含 OaSIS NOC 职业数据。"""
    scores_str = " / ".join(f"{DIMENSION_CN[t]}={scores[t]:.2f}" for t in RIASEC_ORDER)
    top3_str = "".join(rule_outputs["top3"])

    # 构建六维详细描述
    dim_details = ""
    for t in RIASEC_ORDER:
        d = DIMENSION_DETAILS[t]
        dim_details += f"  - {DIMENSION_CN[t]}：典型任务={d['tasks']}；偏好环境={d['environment']}；行为特征={d['behaviors']}\n"

    # 构建 NOC 职业数据段
    noc_section = ""
    if noc_data.get("success") and noc_data.get("matches"):
        noc_section = "\n【OaSIS 匹配的 NOC 职业列表】\n"
        noc_section += f"基于前三码 {top3_str}，通过加拿大 OaSIS 职业兴趣搜索系统匹配到以下职业：\n\n"

        for i, match in enumerate(noc_data["matches"], 1):
            code = match["code"]
            title = match["title"]
            noc_section += f"{i}. NOC {code} — {title}\n"

            desc_info = noc_data["descriptions"].get(code)
            if desc_info:
                if desc_info.get("example_titles"):
                    noc_section += f"   具体职位举例：{', '.join(desc_info['example_titles'])}\n"
                if desc_info.get("main_duties"):
                    noc_section += f"   核心职责：\n"
                    for duty in desc_info["main_duties"]:
                        noc_section += f"     - {duty}\n"
                if desc_info.get("employment_requirements"):
                    noc_section += f"   任职要求：\n"
                    for req in desc_info["employment_requirements"]:
                        noc_section += f"     - {req}\n"
            noc_section += "\n"
    else:
        noc_section = "\n【NOC 职业数据】\n暂未获取到匹配职业数据，请基于 Holland Code 理论给出一般性职业方向分析。\n"

    prompt = f"""以下是用户的 Holland Code 测评数据、规则层分析结果以及来自加拿大 OaSIS 系统的真实职业匹配数据。请据此生成完整的五层深度解读报告。

【输入数据】
- 六维分数（满分 5.0）：{scores_str}
- 前三码：{top3_str}
- 用户阶段：{stage}
- 应用场景：{scenario}
- 补充背景：{background if background else "无"}

【六维度参考知识】
{dim_details}
【规则层计算结果】
- 排序：{' > '.join(f"{d['label']}({d['score']})" for d in rule_outputs['sorted_types'])}
- 分差：第1-2名差={rule_outputs['gaps']['gap_1_2']}，第2-3名差={rule_outputs['gaps']['gap_2_3']}，最高-最低差={rule_outputs['gaps']['gap_high_low']}
- 结构类型：{rule_outputs['structure_type']}（{rule_outputs['structure_desc']}）
- 互补关系：{'; '.join(rule_outputs['complements']) if rule_outputs['complements'] else '无明显互补'}
- 张力关系：{'; '.join(rule_outputs['tensions']) if rule_outputs['tensions'] else '无明显张力'}
- 确定之处：{'; '.join(rule_outputs['certainties'])}
- 待验证处：{'; '.join(rule_outputs['uncertainties']) if rule_outputs['uncertainties'] else '无'}
{noc_section}
请严格按以下五层结构输出，每层使用 Markdown 二级标题（##）。每层内容要详细、具体、有深度：

## 第一层：六维基础解释
逐一解释 R、I、A、S、E、C 六个维度对该用户的具体含义。
- 对每个维度，结合其分数高低，详细说明该维度代表的任务偏好、工作环境偏好和典型行为方式
- 对高分项（前三码），用 3-5 句详细阐述其偏好表现、在日常学习/工作中的具体体现、以及可能带来的优势
- 对中间项，说明其潜在价值和在特定情境下可能被激活的可能性
- 对低分项，说明"相对不优先"的含义，但也指出低分不代表完全排斥
- 结尾用一段话（不少于 3 句）综合概括该用户的整体兴趣画像

## 第二层：前三码组合含义
- 先写 2-3 句总定义，描绘该三码组合的整体人格画像
- 分别用 2-3 句详细解释主码（第一码）、副码（第二码）、辅码（第三码）在组合中的不同作用：
  - 主码：核心兴趣驱动力，决定"被什么吸引"
  - 副码：实现方式和路径偏好，决定"如何去做"
  - 辅码：补充特征和辅助能力，决定"还擅长什么"
- 强调排列顺序的重要性（同样三个字母，不同排列含义不同）
- 说明该组合最容易被哪类学习或工作情境激活（举 2-3 个具体场景）
- 结合 NOC 职业数据，给出 4-8 类具体方向示例，每个示例需说明：该方向包含哪些具体职位、为什么与该组合匹配、日常工作内容是什么

## 第三层：分数结构与差距分析
- 基于规则层的结构类型判定，详细解释用户属于哪种兴趣结构
- 用具体数字说明分差意味着什么（例如"你的 I 和 A 仅差 0.2 分，这意味着..."）
- 明确列出"结果清晰处"（2-3 点）和"不确定处"（2-3 点）
- 详细说明这种分数结构对以下方面的影响：
  - 专业选择策略（是应该明确方向还是保持开放探索）
  - 职业探索方式（是深耕单一领域还是尝试跨界组合）
  - 决策时间线（是否需要更多信息才能做出决定）

## 第四层：一致性与内部张力
- 结合 RIASEC 六边形模型，详细分析前三码之间的位置关系
- 指出该组合内部最强的互补关系，并举例说明互补在实际工作/学习中如何体现
- 若存在张力（对角关系），详细解释：
  - 张力的具体表现（例如"既想自由创作，又追求数据精确"）
  - 张力可能带来的内心冲突和外部表现
  - 张力的积极面——独特优势和创新潜力
- 给出 3-4 条具体的环境设计建议，每条建议要：
  - 说明建议的具体内容
  - 解释为什么适合该用户
  - 举一个实际例子（如课程、项目、岗位类型）

## 第五层：现实映射与行动建议
必须结合前面提供的 NOC 职业数据进行具体分析。分为三类输出：

### 适合尝试（匹配度较高）
- 列出 3-5 个具体方向，每个方向需包含：
  - 对应的 NOC 职业代码和名称
  - 该职业的核心工作内容和日常任务
  - 为什么与用户的前三码高度匹配（从任务偏好、环境偏好、行为方式三个角度）
  - 相关的学习路径和专业方向

### 适合观察（有潜力但需验证）
- 列出 2-3 个方向，说明：
  - 对应的职业领域和具体岗位
  - 为什么有潜力（与哪个维度相关）
  - 需要验证什么（例如是否真的喜欢某类任务）

### 暂不建议过早锁定
- 列出 1-2 个方向，说明：
  - 当前证据不足的原因
  - 在什么条件下可以重新考虑

### 30-90 天验证计划
给出一个分阶段的具体行动计划：
- **第 1-30 天（信息收集阶段）**：3 个具体行动
- **第 31-60 天（初步体验阶段）**：3 个具体行动
- **第 61-90 天（深度验证阶段）**：3 个具体行动

### 3 个可执行的小实验
设计 3 个低成本、可在短期内完成的探索实验，每个实验包含：目标、具体做法、预期收获、判断标准。"""

    return prompt


# ── AI 调用 ──────────────────────────────────────────────────────
def _get_client():
    """获取 OpenAI 兼容客户端（指向 Qwen3-32B）。"""
    return OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)


def stream_interpretation(scores: dict, stage: str, scenario: str,
                          background: str, noc_data: dict = None):
    """流式调用 Qwen3-32B 生成五层解读，返回 (stream, rule_outputs)。

    Args:
        scores: 六维分数
        stage: 用户阶段
        scenario: 应用场景
        background: 补充背景
        noc_data: OaSIS NOC 匹配数据（如已预先获取）
    """
    rule_outputs = compute_rule_outputs(scores)

    # 如果未提供 NOC 数据，则实时获取
    if noc_data is None:
        noc_data = fetch_noc_matches_for_interpretation(rule_outputs["top3"])

    user_prompt = build_user_prompt(scores, rule_outputs, noc_data, stage, scenario, background)

    client = _get_client()
    stream = client.chat.completions.create(
        model=QWEN_MODEL,
        max_tokens=8000,
        stream=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    return stream, rule_outputs, noc_data
