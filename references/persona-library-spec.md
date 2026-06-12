# 3D 小人选择与 SBTI 人设规格

> 当前版本把「人设标签」和「3D 小人」拆开：SBTI 决定卡片上的职业人格标签，`select_figure()` 决定左侧渲染哪一个小人。
> 不再固定 `SBTI -> 图片`，而是基于小人自身视觉特征 + 用户行为/表达信号评分选择。

## 设计原则

- **SBTI 人设**：回答「这个人像什么工作风格」；由 `PERSONA_LIBRARY` 的 8 个 SBTI 风格负责。
- **3D 小人**：回答「哪张小人的视觉气质最贴近这次数据」；由 `FIGURE_LIBRARY` 的 4 张图负责。
- **禁止 Keirsey 4 分法**：不要把 MBTI 先转 NT/NF/SJ/SP 再选图；这会丢失用户真实行为信号。
- **允许 SBTI 作为强信号，但不是唯一信号**：比如「讲师」会强推绿色元气图，但如果数据明显短问句/侦察型，蓝色仍可胜出。

## 4 个小人的条件

| 小人 | 文件 | 视觉特征 | 适合的数据特征 | 典型 SBTI 加成 |
|---|---|---|---|---|
| 专注橙 · 深潜研究员 | `toonhub-1.png` | 橙色眼镜小人，衣服写 STAY FOCUSED，表情认真 | 长消息、工作词高、抽象词多、深度分析、抗干扰 | 深潜者、架构师 |
| 元气绿 · 讲解气氛组 | `toonhub-2.png` | 绿色小人双手比 V，表情外放、开心 | 积极情绪高、长表达、解释/讲解多、带动氛围 | 讲师 |
| 推进粉 · 项目推进官 | `toonhub-3.png` | 粉色小人双拳举起，像冲刺完成后庆祝 | 工作日稳定、低深夜/低周末、核心协作强、推进项目 | 指挥官、记者 |
| 侦察蓝 · 快速响应兵 | `toonhub-4.png` | 蓝色小人指向前方，衣服写 FOCUS，行动感强 | 问句多、短回复多、群聊多、深夜响应、信息侦察 | 侦察兵、甩手掌柜、火警 |

兜底：如果数据均衡，`select_figure()` 会自然选择分数最高的小人；当前均衡数据通常会落到粉色推进或橙色专注，取决于协作/工作词/长消息信号。

## 选择函数

```python
def select_figure(sbti_code, expression, behavior):
    # 输入：SBTI Top1、表达 DNA、行为模式
    # 输出：{image, image_name, color, label, visual, score, scores}
```

评分信号摘要：

- `orange_focus`：SBTI 深潜者/架构师 + mean length + long_msg_ratio + work_ratio + ABSTRACT_KEYWORDS 命中。
- `green_energy`：SBTI 讲师 + positive emotion + long_msg_ratio + mean length + 非单字回复。
- `pink_execution`：SBTI 指挥官/记者 + top_collab_share + 低 late/weekend + work_ratio + 白天高峰。
- `blue_scout`：SBTI 侦察兵/甩手掌柜/火警 + question density + single_char_ratio + group ratio + late_night_ratio。

## SBTI 人设仍保留独立分类

`PERSONA_LIBRARY` 仍负责 8 个 SBTI 风格的标签和匹配度：

| SBTI 风格 | 主要信号 | 人话标签 |
|---|---|---|
| 深潜者 | 长消息占比 + 工作词密度 + 抽象词 | 深度内卷型 |
| 甩手掌柜 | 群聊主导 + 单字回复多 | 佛系指挥型 |
| 火警 | 负面词密度 + 凌晨活跃 + 深夜高峰 | 红色警戒型 |
| 架构师 | 抽象关键词密度 + 长消息 + 不爱问号 | PPT 永动机型 |
| 侦察兵 | 问句密度高 + 短消息 + 凌晨活跃 | 信息掮客型 |
| 记者 | 数据/截图/记录关键词 + Top1 协作占比高 | 数据狂魔型 |
| 指挥官 | 不凌晨 + 不周末 + 单核协作 | 人形 Gantt 型 |
| 讲师 | 长消息占比 + 不爱单字 + 均长 | 传道授业型 |

`select_persona()` 的输出现在会合并两层结果：

- `code/tag/score`：来自 SBTI 人设。
- `image/color/figure_*`：来自 `select_figure()` 的小人选择。

## 扩展指南

新增小人时：

1. 把图片放到 `assets/`，不要硬编码外部绝对路径。
2. 在 `FIGURE_LIBRARY` 增加 `image/image_name/color/label/visual`。
3. 在 `select_figure()` 增加一个分数 key，分数必须来自表达/行为信号，而不是纯主观映射。
4. 为新小人补一条测试，确保特定数据特征会选到这张图。

调整条件时：

- 先看小人的视觉特征，再选信号；不要为了某个 SBTI 标签强行指定图。
- 一个 SBTI 可以选到不同小人，只要数据特征变化明显。
- 默认 4:5 PNG 必须保持人物图正常渲染，不能出现 alt 文本或空白占位。
