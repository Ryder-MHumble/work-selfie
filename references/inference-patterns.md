# 推断模式：5 维 N-from-N + 候选连续评分

> 解决"分类选手: ?"的根本问题——所有候选都给分，永远有结果。
>
> ⚠️ v1 真实数据跑出来 5 个 bug，**必读 [real-run-findings.md](./real-run-findings.md)**——本文件示例代码的 `min(1.0, ...)` 已被 patch。

## 为什么不能用 if 触发器

```python
# ❌ 反模式：if 触发器
def infer_sbti(messages, expression, behavior):
    candidates = []
    if avg_len > 60 and work_ratio > 0.3:  # 6 个候选都是这种 if
        candidates.append({"type": "深潜者", "score": 95, ...})
    if group_ratio > 0.7 and single_char_ratio > 0.2:
        candidates.append({"type": "甩手掌柜", "score": 80, ...})
    # ... 5 个候选都没触发 → 返回空
    if not candidates:
        return {"type": "未分类", "score": 0}  # ← 卡片上变成 "?"
    return candidates[:3]
```

**问题**：阈值调严了，6 个 if 全不满足 → 空 → 卡片显示"未分类"或"?"。**用户明确反感**这种结果。

## 正确做法：连续 0-100 评分 + 永远 Top N

```python
# ✅ 正确：连续评分（⚠️ 不要 min(1.0, ...) — 让 raw 超过 1.0，归一化在 infer 函数末尾）
SBTI_CANDIDATES = [
    {
        "name": "深潜者",
        "score_func": lambda e, b: (
            max(0, (e["length_stats"]["mean"] - 30) / 80) * 0.4
            + e["category"]["work_ratio"] * 1.0
            + e["category"]["long_msg_ratio"] * 0.6
            # 不加 min(1.0,)，让 raw 范围 0 - 3.0
        ),
    },
    {
        "name": "甩手掌柜",
        "score_func": lambda e, b: (
            b["group_vs_p2p"]["group"] * 0.5
            + e["category"]["single_char_ratio"] * 1.2
            + (1 - e["category"]["long_msg_ratio"]) * 0.3
        ),
    },
    # ... 6-12 个候选，每个都给连续评分
]

def infer_sbti(messages, expression, behavior):
    candidates = []
    for c in SBTI_CANDIDATES:
        raw = c["score_func"](expression, behavior)
        score = int(min(100, max(0, raw * 100)))
        if score >= 30:  # 低于 30 不展示
            candidates.append({
                "type": c["name"],
                "score": score,
                "evidence": _sbti_evidence(c["name"], expression, behavior),
            })

    candidates.sort(key=lambda x: -x["score"])
    if not candidates:
        # 兜底：所有都 < 30 也强制返回 Top 3
        for c in SBTI_CANDIDATES:
            raw = c["score_func"](expression, behavior)
            candidates.append({"type": c["name"], "score": max(1, int(raw * 100)), "evidence": "数据不足"})
        candidates.sort(key=lambda x: -x["score"])
        return candidates[:3]
    return candidates[:3]
```

**关键点**：
1. **每个候选都算分**——不靠 if 触发的"是/否"
2. **永远返回 Top N**——即使 < 30 也兜底
3. **每个候选都给 evidence 证据**——不只是数字

## 5 维 N-from-N 推断（决策/沟通/压力/价值观/信息处理）

5 个维度，每个维度都有 3-4 个候选类型，从 N 个候选中选 1 个。

| 维度 | 候选 |
|------|------|
| 决策风格 | 数据驱动型 / 直觉闪电型 / 深思熟虑型 / 协作共识型 |
| 沟通偏好 | 直球型 / 委婉派 / 数据党 / 气氛组 |
| 压力反应 | 沉默消化型 / 快速响应型 / 向外求援型 |
| 价值观 | 效率优先 / 质量优先 / 关系优先 / 创新优先 |
| 信息处理 | 视觉优先 / 文字深度 / 口头快闪 / 结构化记录 |

**实现**：

```python
DECISION_STYLES = [
    {
        "name": "数据驱动型",
        "desc": "做决定前先看数字，凭感觉不如凭报表",
        # ⚠️ 不要 min(1.0, ...)，让 raw 超 1.0
        "score_func": lambda e, b: (
            e["category"]["work_ratio"] * 2
            + e["length_stats"]["mean"] / 50 * 0.5
            + (1 - e["punctuation_density"]["question"]) * 0.3
        ),
    },
    # ... 3 个其他候选
]

def infer_decision_style(e, b):
    scored = []
    for c in DECISION_STYLES:
        raw = c["score_func"](e, b)  # raw 是 0-3+ 的连续值
        scored.append({"name": c["name"], "desc": c["desc"], "raw": raw})
    # 归一化在 infer 末尾（不放在 score_func 里）
    max_raw = max(s["raw"] for s in scored) or 1
    for s in scored:
        s["score"] = int(s["raw"] * 100 / max_raw)  # 真正 max-归一化
    scored.sort(key=lambda x: -x["score"])
    primary = scored[0]
    return {
        "primary": primary["name"],
        "primary_desc": primary["desc"],
        "primary_score": primary["score"],
        "all": scored,  # 深度报告里展示其他候选
    }
```

**关键点**：
- **归一化**到 max 100%——避免主选永远 100%（决策/沟通/压力等对比才有意义）
- **all 字段保留全部候选**——深度报告里要展示"其他候选: 深思熟虑型 87% / 协作共识型 65% / 直觉闪电型 13%"

## 架构：深度分析报告（primary）→ 卡片（abstract）

```
analyze_all(messages) →
  {
    expression_dna: {...},        # 完整数据层
    behavior_patterns: {...},     # 完整数据层
    personality: {mbti, sbti, animal, tags},
    sbti_top3: [...],             # 8 候选 Top 3（深度报告用）
    animal_top3: [...],           # 12 候选 Top 12（深度报告用）
    decision_style: {...},        # 4 选 1 + all
    communication_style: {...},   # 4 选 1 + all
    stress_response: {...},       # 3 选 1 + all
    value_tendency: {...},        # 4 选 1 + all
    info_processing: {...},       # 4 选 1 + all
  }
                ↓
        build_report_text(analysis)  # 10 章节深度报告
                ↓
        render_card(template)        # 从 analysis 二次抽象出 5-7 个信息
```

**反模式**（早期版本犯过）：
```
analyze_all(messages) →
  {
    sbti_code: "指挥官",        # 卡片要 1 个就只输出 1 个
    animal: "狼",
    mbti: "INTJ",
  }
                ↓
        render_card(template)    # 报告里就没数据可用
```

**核心**：**analyze 层输出"用户可能问的所有问题的答案"**，render 层只负责"挑 5-7 个最关键的"。

## Python `in` 操作符优先级坑

```python
# ❌ 会报 TypeError
score = (b.get("active_hour_top3", [12])[0] in (22, 23, 0, 1, 2, 3)) * 0.4
# 实际解析：(x in (22, 23, 0, 1, 2, 3)) * 0.4 ← 这是对的
# 但写成：
score = b.get("active_hour_top3", [12])[0] in (22, 23, 0, 1, 2, 3) * 0.4
# 实际解析：b.get(...)[0] in ((22, 23, 0, 1, 2, 3) * 0.4)
#                                = b.get(...)[0] in (22, 23, 0, 1, 2, 3, 22, 23, 0, 1, 2, 3, ...)  # 重复一次
# 但 Python 不知道 * 应该应用在哪里 → TypeError: can't multiply sequence by non-int

# ✅ 永远加括号
score = (b.get("active_hour_top3", [12])[0] in (22, 23, 0, 1, 2, 3)) * 0.4

# 三目同理
score = (x if cond else y) * 0.3  # ✅
score = x if cond else y * 0.3    # ❌ 解析为 x if cond else (y * 0.3)
```

## 复现检查清单

新加一个推断维度（如"团队角色"）时：
- [ ] 候选类型列表（3-6 个）
- [ ] 每个候选有 `score_func: lambda e, b -> 0-1` 连续评分
- [ ] 每个候选有 `desc` 人话解读
- [ ] 推断函数：(1) 算 raw 分 → (2) 转 0-100 → (3) 归一化（max 100%）→ (4) sort → (5) 永远返回 Top 3
- [ ] 推断函数返回 `{primary, primary_desc, primary_score, all}` 4 个字段
- [ ] 在 `analyze_all` 中调用
- [ ] 在 `build_report_text` 中作为独立章节
- [ ] 在 `render_card` 中**只取 `primary` 一个标签**——不要把 5 个候选都塞卡片

## 文件位置

- `scripts/analyze.py` — 推断函数实现（SBTI_CANDIDATES / ANIMAL_CANDIDATES / DECISION_STYLES / 等）
- `scripts/send_report.py` — `build_report_text()` 5 维章节渲染
- `scripts/render_card.py` — `build_traits_5d_html()` 卡片横排 5 列
- `scripts/main.py` — `five_dimensions` 字典拼装
