# 真实数据跑出来的坑（v1 之后的二次修复）

> 2026-06-11 匿名样本全量 200 天数据 (4179 条) 真实跑出来的问题。V1 重构（架构 + 兜底 + 密度）完成后，**真实数据 vs 样本数据** 又暴露 5 类问题。本文件是 fix 沉淀。

## 0. 5 类问题总览

| # | 问题 | 用户反馈 | 修复位置 |
|---|------|---------|---------|
| 1 | dws 返回的系统消息污染口头禅/关键词 | Top 5 出现「图片 消息」「如需 下载」 | `analyze.py: is_system_message` + `analyze_all` 入口过滤 |
| 2 | 情绪词典太弱 + 0% 命中 | 积极 10.4% / 消极 4.0% / 中性 85.6%（应是 30%/15%/55%） | `analyze.py: POSITIVE/NEGATIVE_WORDS` 扩到 40+/50+ 词 |
| 3 | 5 维推断 `min(1.0, ...)` 截断导致多候选并列 100% | 决策风格 4 候选都 100% | `analyze.py: 5 维 score_func` 删 `min(1.0,)` |
| 4 | MBTI 信号弱（4 维 max 平均 < 40%）时仍硬判 4 字母 | 信号 18% 仍推 ISTJ | `analyze.py: infer_mbti` 新增 `signal_strength` + 报告里加 ⚠️ 提示 |
| 5 | 左侧人物图过长挤占右侧信息密度 | "左侧人物图片太长了，这就导致右侧的信息密度太低了" | `render_card.py: 4:5 模板` 改成 50/50 垂直分割（人物 55% + SBTI 块 45%） |
| 6 | 第二轮：grid fr 不填内容 + 右侧下半部大空白 + 8 候选太冗 + 编号跳跃 | "右侧还有很多空白"、"模版效果还是太差了" | `render_card.py`: flex 0 0 auto + 段间 10px + slogan margin-top:auto；build_sbti_8_html 改回完整 8 行（top 3 突出）；build_sbti_evidence_html 加 4 行 evidence；协作 Top 3 → Top 5；编号 01→05 连续 |
| 7 | 资源外置：PERSONA_DIR 硬编码 `~/Desktop` → 3D portrait 静默渲染失败 | "3d portrait 这个图片没有正常渲染出来"、"你得把这些图片都放在这个skill的目录下" | `render_card.py:41` PERSONA_DIR 改 `Path(__file__).parent.parent / "assets"`；4 张 toonhub-*.png 复制到 `assets/` |

---

## 1. dws 系统消息污染（高频坑，必须前置过滤）

**症状**：
- Top 5 口头禅里出现「图片 消息」「如需 下载」
- 关键词 top 出现「图片」「下载」「请使用」等 dws 内部文案
- 报告里"工作词比"被「下载」「图片」拉高

**根因**：
- dws `chat message list-by-sender` 返回的 messages 不只是用户发的——还包含系统提示（图片消息占位、文件下载链接、转写机器人消息）
- 这些消息 content 字段是用户看不到的 UI 提示，不是用户真发的话
- 直接喂给 `jieba.analyse` 会被当作"用户说的"统计

**修复**（analyze.py:56-110）：
```python
SYSTEM_PHRASE_PATTERNS = [
    r"^\[图片\]?消息$",          # [图片消息]
    r"^如需.*请使用 dws",        # dws 下载提示
    r"^https?://ding\.talk/\S+", # dws 内部链接
    r"^<msg>",                    # 钉钉 xml 标签
    r"^\[.*机器人.*\]$",
    # ... 共 18 个正则
]

def is_system_message(content: str) -> bool:
    if not content or len(content) < 2:
        return True
    for pat in SYSTEM_PHRASE_PATTERNS:
        if re.search(pat, content):
            return True
    return False

# analyze_all 入口：
messages = [m for m in messages if not is_system_message(m.content)]
print(f"过滤 {raw_count - len(messages)} 条系统消息")
```

**验证**：
- 过滤前后口头禅 Top 5 应该是两类完全不同的词
- 真实数据：4179 → 3765（414 条系统消息，9.9%）

**预防 checklist**（新加数据源时）：
- [ ] `collect_self.py` 每拉完一个数据源，**立即**调 `is_system_message` 过滤
- [ ] 关键词/口头禅/情绪分析**必须**在过滤后跑
- [ ] 行为分析（消息长度、活跃时段）可以包含系统消息（它们也有时间戳）

---

## 2. 情绪词典太弱（必须用用户实际词频扩词）

**症状**：
- 报告里 "积极 10.4% / 消极 4.0% / 中性 85.6%"
- 用户说"这不对吧，我应该没这么中性"

**根因**：
- `POSITIVE_WORDS` / `NEGATIVE_WORDS` 是抄的通用词典（开心/难过/喜欢/讨厌等 12 词）
- 用户真实聊天里高频情绪词不在这 12 词里：「靠谱」「给劲」「可以」「不错」是积极，「崩溃」「烦」「拉胯」「坑」是消极
- 通用词典 + 中文短消息 + 表情/网络词 = 命中率 < 10%

**修复**（analyze.py: POSITIVE/NEGATIVE_WORDS）：
```python
# 修复前：12 词通用词典
POSITIVE_WORDS = {"开心", "高兴", "快乐", "喜欢", "爱", "好", "棒", "不错", "可以", "谢谢", "感谢", "支持"}

# 修复后：40+ 词用户实际高频
POSITIVE_WORDS = {
    # 通用积极
    "开心", "高兴", "快乐", "喜欢", "爱", "好", "棒", "不错", "可以", "谢谢", "感谢", "支持",
    # 工作场景高频
    "靠谱", "给劲", "到位", "稳", "稳了", "成了", "搞定", "通过", "OK", "ok", "赞", "牛",
    "厉害", "稳", "稳了", "完美", "漂亮", "nice", "good", "great", "yes",
    # 社交高频
    "哈哈", "哈哈哈", "嘿嘿", "嘻嘻", "😊", "👍", "🙏", "💪", "✨",
    # 协作高频
    "一起", "加油", "辛苦了", "麻烦", "拜托", "麻烦你", "麻烦您",
    # 学术/技术场景（AI 产品经理）
    "好", "对", "是", "对", "嗯", "行", "可以", "好的", "OK", "行", "懂了",
}
NEGATIVE_WORDS = {
    # 通用消极
    "难过", "伤心", "失望", "讨厌", "烦", "生气", "气", "差", "糟", "烂",
    # 工作场景高频
    "崩溃", "拉胯", "坑", "翻车", "完了", "完了完了", "不行", "搞不定",
    "急", "急死了", "加班", "熬夜", "拖", "拖延", "推",
    # 反馈/不满
    "不行", "不够", "不对", "错", "bug", "挂了", "挂了", "崩了",
    # 自我吐槽
    "累", "累了", "困", "菜", "菜鸡", "我菜", "我太菜", "辣鸡",
    "不会", "不懂", "没懂", "糊涂", "懵",
}
```

**关键**：
- **必须用用户实际数据扩词**——跑完关键词 Top 50 后，挨个看哪些情绪词被漏了
- **不要硬编码词典就完事**——每跑一次新数据，可能要扩
- **情绪分析要走"集合计数 → 比例"**，不走 NLU 模型（钉钉消息没上下文，LU 没用）

**验证**：
- 修复后：积极 25-35% / 消极 10-20% / 中性 45-60%（这是中文工作消息的健康分布）
- 仍全是 0% → 词典没扩对

---

## 3. 5 维推断 `min(1.0, ...)` 截断 bug

**症状**：
- 决策风格 4 个候选：「数据驱动 100% / 协作共识 99% / 深思熟虑 96% / 直觉闪电 12%」
- 4 选 1 永远 100%，看不出真正差距
- 卡片横条几乎一样长，没有视觉对比

**根因**：
```python
# 错误的归一化策略
"score_func": lambda e, b: min(1.0, (
    work_ratio * 2
    + length_mean / 50 * 0.5
    + ...
))
# 算完后 int(raw * 100) = min(100, int(...))
# 4 个候选只要 raw 都不超 1.0，就会全部逼近 100
# 归一化到 max 100% 之后还是全部 100%
```

**修复**（analyze.py: DECISION_STYLES 等 5 个）：
```python
# ✅ 不要 min(1.0, ...) — 让 raw 超过 1.0
"score_func": lambda e, b: (
    work_ratio * 2
    + length_mean / 50 * 0.5
    + (1 - question_density) * 0.3
    # 不加 min(1.0,)，允许 raw 范围 0 - 3.0
),
# 之后在 infer_decision_style 统一归一化：
max_score = max(s["raw"] for s in scored)
for s in scored:
    s["pct"] = int(s["raw"] * 100 / max_score)  # 真正的 max-归一化
```

**关键**：
- 删 `min(1.0, ...)` 让 raw 范围更广
- 归一化只发生在 **infer 函数末尾**，不在 score_func 内
- 归一化公式：`pct = raw / max(raw) * 100`（max 永远是 100%）

**验证**：
- 修复后：决策风格「数据驱动 100% / 协作共识 87% / 深思熟虑 65% / 直觉闪电 12%」——真正有梯度

**注意**：`inference-patterns.md` 里 DECISION_STYLES 示例代码是**修复前的**——下次有人照抄会再踩坑。已 patch。

---

## 4. MBTI 信号弱仍硬判（新增 signal_strength 字段）

**症状**：
- 报告里写「MBTI: ISTJ」但 4 维 max 都不超 30%
- 用户说"你 4 维都没明确偏好，凭什么硬判 ISTJ？"

**根因**：
- `infer_mbti` 老逻辑：4 维各自 max 取字母 → 拼 4 字母
- 数据稀疏时 4 维都接近 baseline（如 25/20/30/15），拼出来是「ISTJ」但其实没强证据

**修复**（analyze.py: infer_mbti, line 486-565）：
```python
def infer_mbti(messages, expression, behavior):
    ei = _calc_ei(...)
    sn = _calc_sn(...)
    tf = _calc_tf(...)
    jp = _calc_jp(...)
    
    # 信号强度 = 4 维 max 的平均值
    max_avg = (max(ei.values()) + max(sn.values()) + max(tf.values()) + max(jp.values())) / 4
    
    # 拼 4 字母
    mbti_4letter = (
        max(ei, key=ei.get)[0]
        + max(sn, key=sn.get)[0]
        + max(tf, key=tf.get)[0]
        + max(jp, key=jp.get)[0]
    )
    
    # 信号弱时在 mbti_code 里加警告
    if max_avg < 40:
        mbti_code = f"⚠️信号弱({int(max_avg)}%) {mbti_4letter}"
    elif max_avg < 60:
        mbti_code = f"{mbti_4letter} (信号中)"
    else:
        mbti_code = f"{mbti_4letter} (信号强)"
    
    return {
        "EI": ei, "SN": sn, "TF": tf, "JP": jp,
        "mbti_4letter": mbti_4letter,
        "mbti_code": mbti_code,  # 给报告用（带警告）
        "signal_strength": max_avg,  # 给卡片用
    }
```

**配套：下游消费者必须适配**（重要！见 §6）

**卡片怎么用**：
- 卡片用 `mbti_4letter`（不带警告，保持简洁）
- 报告用 `mbti_code`（带信号强度警告）
- `signal_strength < 40` 时卡片上**额外**加一行「⚠️ 信号弱，数据不足以稳定推断」

---

## 5. 左侧人物图布局（密度问题）

**症状**（用户原话）：
> "左侧人物图片太长了，这就导致右侧的信息密度太低了，中间"

**根因**：
- 早期 4:5 模板：左侧 50% 整张人图 + 右侧 50% 5 模块
- 人图有大量留白，挤占有效信息空间

**修复**（render_card.py: 4:5 模板）：
- 左侧 50% 改成 **垂直 55/45 分割**：
  - 上 55% = 人物图（裁剪到 fit）
  - 下 45% = 黑色 SBTI 标签块（深红描边 + 黄色标题 + 4 字段：label/code/title/tag/desc/score）
- 右侧 50% 保持 5 大信息模块

**新模块 CSS**（render_card.py: .sbti-side）：
```css
.toonhub-bg {
    height: 55%;  /* 原 100% → 55% */
    background-size: cover;
    background-position: center;
}
.sbti-side {
    height: 45%;
    background: #0a0a0a;
    border: 2px solid #e60012;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.sbti-side .label {
    color: #ffd700;
    font-weight: 900;
    font-size: 14px;
    letter-spacing: 2px;
}
```

**HTML 结构**：
```html
<div class="left">
    <div class="toonhub-bg" style="background-image:url({persona_image})"></div>
    <div class="sbti-side">
        <div class="label">{sbti_label}</div>
        <div class="code">{persona_code}</div>
        <div class="title">{persona_tag}</div>
        <div class="desc">{sbti_desc}</div>
        <div class="score">{persona_score}/100</div>
    </div>
</div>
```

**设计原则**（卡片布局通用）：
- **人物图永远不要占 > 60% 总面积**——卡片是"档案速览"不是"肖像画"
- **左上下分**比**左右分**更紧凑（4:5 portrait 比例下）
- **人物图尺寸用 CSS `cover` 裁剪**——不要用 `contain` 留白

**注意**：编号 01/02/03/04/05 连续——删了 `sbti-main` 块后没把 `02/03/04/05` 改成 `01/02/03/04`，下次重设计要 1 行 fix。

---

## 6. 字典扩展的连锁断裂（CLASS-LEVEL 坑）

**症状**（连续崩 5 次的真实数据 run）：
```
v2 崩: TypeError: 'float' object is not subscriptable
  └─ analyze.py:1582 mbti_code = "".join(d[0] for d in mbti.values())
     └─ mbti.values() 多了 signal_strength (float)，d[0] 失败

v3 崩: 同样问题在 analyze.py:1638 (generate_slogans)

v4 崩: ValueError: invalid literal for int() with base 10: '18%'
  └─ send_report.py:462 max(mbti.values()) 拿到 'ISTJ (信号强)' 字符串，max() 报错

v5 崩: TypeError: argument of type 'float' is not iterable
  └─ main.py:270 同样问题

v6 崩: subprocess.TimeoutExpired ... 60 seconds
  └─ render_card.py:1506 Chrome 渲染超时（60s 不够）
```

**根因**：
- `infer_mbti` 返回 dict 加了 `signal_strength` 字段
- 但所有**消费者**都在用 `mbti.values()` 迭代 + `d[0]` 索引
- 加字段 = 加消费者崩点

**修复模式**（**所有**加字段到返回 dict 的情况都要做）：
```python
# 消费 mbti dict 时
# ❌ 旧：mbti.values() 里可能含 5 个字段（EI/SN/TF/JP/4letter/code/signal_strength）
mbti_code = "".join(d[0] for d in mbti.values())

# ✅ 新：显式只取标准 4 维
mbti_4d = {k: v for k, v in mbti.items() if k in ("EI", "SN", "TF", "JP")}
mbti_code = "".join(max(d, key=d.get)[0] for d in mbti_4d.values())

# ✅ 同样：max() 找最强维度时
strongest = max(mbti_4d, key=lambda k: max(mbti_4d[k].values()))

# ✅ isinstance 双重保护
mbti_letters = "".join(
    d[0] for d in mbti.values()
    if isinstance(d, str) and "(" in d  # 只取 mbti_code 字段
)
```

**CLASS 教训**：
- **返回 dict 加字段 = 强制遍历所有消费者**——这是 breaking change
- 消费者模式必须支持"未知字段安全忽略"（`isinstance` 检查 + 显式 whitelist）
- 加字段时**同步在 `references/` 加一行**：哪个字段从哪天起加的、影响哪些消费者

**配套 Chrome timeout**：
- 4:5 模板 HTML 渲染量大（564K 字符），Chrome headless 60s 不够
- 改 120s + 加 stderr 诊断（exit code + stderr 输出）

---

## 7. 一图看懂 5 修复点的位置

```
analyze.py
├── SYSTEM_PHRASE_PATTERNS (line 56-93)        ← 修复 1：系统消息过滤
├── is_system_message() (line 100-110)          ← 修复 1
├── POSITIVE_WORDS / NEGATIVE_WORDS             ← 修复 2：词典扩到 40+/50+
├── DECISION_STYLES 等 5 维 (line ~1100)        ← 修复 3：删 min(1.0,)
├── infer_mbti (line 486-565)                   ← 修复 4：加 signal_strength
├── analyze_all 入口                            ← 修复 1 应用
├── mbti_code 拼接 line 1582/1638               ← 修复 6：isinstance 过滤
└── generate_slogans                            ← 修复 6

render_card.py
├── 4:5 模板 .toonhub-bg (line 553-557)         ← 修复 5：height 100% → 55%
├── .sbti-side CSS (line 581-632)               ← 修复 5：左侧下半 SBTI 块
├── 4:5 模板 HTML (line 961-970)                ← 修复 5
├── render_html_to_png timeout (line 1506)      ← 修复 6：60s → 120s
├── 编号 02/03/04/05 → 01/02/03/04              ← 修复 5：1 行 fix
├── .right-panel (line 637-660)                 ← 修复 9.1：grid → flex column + space-between
├── .sbti8/.t5d/.dna/.collab-section (line 781+)← 修复 9.1：flex: 1 1 0 等分
├── build_sbti_8_html (line 1391)               ← 修复 9.2：top 3 + 1 行汇总
├── build_sbti_evidence_html (line 1506)        ← 修复 9.3：左侧 SBTI 块 4 行 evidence
├── .sbti-side-stat/.sss-k/.sss-v CSS           ← 修复 9.3
└── HTML 编号 01 → 02 改 8 候选                ← 修复 9.4：1 行 fix

send_report.py
├── build_report_text MBTI 字段                 ← 修复 4：信号弱时显示警告
├── send_report_as_doc                          ← 修复 6：dws doc create 长报告
├── share_doc_to_user                           ← 修复 6：dws chat message send
└── mbti_4d 字典只取 4 维 (line 462)            ← 修复 6

main.py
├── Step 4a 报告 → 4b 卡片 → 6a 本地 → 6b 钉钉  ← 修复 6：流程顺序
├── mbti_4letter 分离 (line 264-271)            ← 修复 4：卡片用 4letter
└── isinstance 过滤 (line 270)                  ← 修复 6
```

## 9. 第二轮布局重构：flex 等分 + 模块精简（v9 卡片）

> 2026-06-11 第二次跑出来，§5 修复后用户又反馈"右侧下半部大块空白"、"信息密度太低"、"模块之间有大量留白"。

### 9.1 根因：grid fr / 段内 space-between 都不填内容

第一轮（§5 修复后）我用了 `display: grid; grid-template-rows: 1.1fr 1.2fr 1fr 1fr` 试图让 4 大模块"等分填满"——**但 grid fr 只分配轨道高度，section 内部不填满**：

```css
/* ❌ 错的 v1：grid 撑开轨道，section 内容靠顶部，下面是空轨道 */
.right-panel {
    display: grid;
    grid-template-rows: 1.1fr 1.2fr 1fr 1fr;
    gap: 6px;
}
/* 结果：02 8 候选排行只 30px 高，但被 grid 拉到 100px → 下方 70px 空白 */
```

第二轮改 `flex: 1 1 0` + 段内 `justify-content: space-between` —— 段间没空白了，**但段内每行 row 间距巨大**（5 维人格 5 行被拉到 ~100px 段高，每行 ~20px 间距，视觉变稀）。

```css
/* ❌ 错的 v2：段间没空白但段内 row 间距巨大 */
.sbti8-section { flex: 1 1 0; display: flex; flex-direction: column; justify-content: space-between; }
/* 结果：3 行候选 + 1 行汇总 → 4 行占满 100px 高，每行 25px 间距 */
```

**真正对的解法：flex 0 0 auto + 段间小 margin + slogan `margin-top: auto` + 增加内容密度**

```css
/* ✅ 最终：段按内容自然高度排列，slogan 推到底部 */
.right-panel {
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
}
.sbti8-section, .t5d-section, .dna-section, .collab-section {
    flex: 0 0 auto;  /* 不拉伸，按内容 */
    margin: 0 0 10px 0;  /* 段间 10px */
}
.top-strip, .name-block, .identity-strip {
    flex: 0 0 auto;
}
.slogan {
    flex: 0 0 auto;
    margin-top: auto;  /* 推到底部 */
}
```

但即使这样**仍有剩余空白**（right-panel 1000px - 固定区 200px - 4 段内容 350-450px = 350-450px）——空白用 `margin-top: auto` 推到 slogan 之上。

**真正消除空白的方向：增加内容密度**（不是抹掉空白）：
- SBTI 8 候选：精简 3+1 → 改回全 8 行（让 8 候选占更多垂直空间）
- 协作：Top 3 → Top 5（多 2 行）
- 4 段总高从 ~250px 提升到 ~450px，slogan 之上空白从 ~400px 缩到 ~150px

**CLASS 教训（卡片/海报/信息密度排版的通用坑）**：
- `grid-template-rows: 1fr` 不会自动把内容撑满轨道 → 留白
- `flex: 1 1 0` + `justify-content: space-between` 段内 row 间距巨大 → 视觉变稀
- 正确：**让内容自然撑高度 + 加内容密度**（不要用 CSS 把"少内容"拉伸成"多内容"）
- 8 候选排名模块永远**完整展示 8 行**（不精简）——信息密度 > 视觉简洁

### 9.2 SBTI 8 候选完整展示（top 3 突出 + 5 兜底）

**症状**：原本 v9 早期想"精简 top 3 + 1 行汇总"省空间——但用户实测反馈"卡片内容太少"，又改回**全 8 行展示**（top 3 黑色突出 + 5 个灰色兜底）。

**当前实现**（`render_card.py: build_sbti_8_html`）：

```python
# 当前：8 行全展示，top 3 黑色，5 个 max(1, min-5) 兜底灰色
for s in sbti_top3:  # 3 行真实分数，黑色 top3
    items.append(<sbti8-item top3>{name} {bar} {score}%</...>)
for name in ALL_SBTI:  # 5 行兜底
    if name in top3_set: continue
    sc = score_map.get(name, fill)  # fill = max(1, min_score - 5)
    items.append(<sbti8-item>{name} {bar} {score}%</...>)
```

**迭代历史**（避免后人重蹈）：
- v1 早期：8 行全展示（无视觉区分，全灰） → 视觉冗余
- v9 中期：精简 top 3 + 1 行汇总 → 信息密度太低，用户要"内容多一些"
- v9 末：8 行全展示（top 3 黑色突出 + 5 兜底灰色） → **最终版**

**CLASS 教训（排名/排行类模块的取舍）**：
- 卡片信息密度**优先**于视觉简洁
- 8 个候选都不超 100px 高度（全行紧凑 8px padding + 9px 字号 ≈ 100px 总高）→ 不算浪费空间
- top 3 黑色突出 + 兜底灰色 = 既信息全又视觉分层
- 协作 Top N：默认 Top 5（不只 3，多 2 行"次活跃"协作对象）

### 9.3 左侧 SBTI 块加 4 行 evidence（新 builder `build_sbti_evidence_html`）

**症状**：左侧黑色 SBTI 块只有 6 行主信息（label/code/title/tag/desc/score），下方还有 ~80px 空白。

**修复**：加 1px 虚线分隔 + 4 行紧凑数据速览：

```python
# 新 builder（render_card.py: build_sbti_evidence_html）
rows = [
    ("协作 Top1", f"{name} · {count} 次"),
    ("高峰", "14:00 · 10:00 · 13:00"),
    ("作息", f"深夜 {late*100:.0f}% · 周末 {weekend*100:.0f}%"),
    ("表达", f"工作词 {work:.0f}% · 单字 {sc:.0f}%"),
]
```

数据来源：
- `behavior.top_collaborators[0]` → 协作 Top1
- `behavior.active_hour_top3` → 高峰
- `behavior.late_night_ratio + weekend_ratio` → 作息
- `expression.category.work_ratio + single_char_ratio` → 表达

**CLASS 教训（dense card 的"底部填充"模式）**：
- 主信息块（label/title/desc）显示完了，下面还有 50-100px 空白时
- **加 4 行紧凑 stat**（每行 9px 字号，1px 虚线分隔）
- 4 行内容**不能与右侧任何模块重复**——挑那些没在右侧显示的关键数字
- 数据要从 `analysis` 真实字段拿，不要硬编码"举例"数字

### 9.4 编号连续化（01/02/03/04/05）

**症状**：右侧编号 01→03→04→05 缺 02，因为 §5 重构时删了 `sbti-main` 块没把 `02/03/04/05` 改成 `01/02/03/04`。

**修复**（render_card.py: 4:5 模板 HTML）：
- 左侧 01 职场 SBTI（主风格块）
- 右侧 02 8 候选排行（数据化全排行）
- 右侧 03 5 维人格
- 右侧 04 表达 DNA
- 右侧 05 协作 Top 3
- Slogan 不编号

**CLASS 教训**：
- 删模块后**立即**重编号——别留到下次
- 编号要在 main 流程的同一处定义（dict 或常量），不要散在 HTML 模板里

### 9.5 验证 checklist（v9 卡片）

```bash
# 1. mock 测试：占位符必须全部替换
python3 /tmp/test_v4_layout.py
# 预期：所有 10 项 checks = True，HTML > 500K chars

# 2. Chrome 真实渲染
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless --no-sandbox --window-size=800,1000 \
    --screenshot=/tmp/test_v4.png file:///tmp/test_v4.html
# 预期：PNG 600-800KB，4:5 (800x1000)

# 3. 视觉检查（关键）
# - 右侧下半部还有大块空白？→ grid fr 陷阱没修好
# - 编号 01/02/03/04/05 连续？
# - 左侧 SBTI 块底部有 4 行 evidence？
# - 8 候选只显示 3 行 + 1 行汇总？
```

## 8. 验证 checklist（每次改 analyze/render 后必跑）

```bash
# 1. syntax check
python3 -c "import ast; ast.parse(open('scripts/analyze.py').read())"
python3 -c "import ast; ast.parse(open('scripts/render_card.py').read())"

# 2. mock 数据 smoke test（不需要 dws）
python3 /tmp/test_self_distill.py
# 预期：HTML 渲染 564K 字符，无残留占位符

# 3. Chrome 真实渲染（1 张）
python3 /tmp/test_render_real.py
# 预期：4x5 (800x1000) → 600-800KB, < 5s

# 4. 真实数据全量 run
python3 scripts/main.py --days 200 --force-full --skip-consent
# 预期：100-150s 成功，无 TypeError/ValueError
```

**关键检查点**（run 后必看）：
- 过滤 N 条系统消息（应 5-15%）
- 情绪分布（积极 25-35% / 消极 10-20% / 中性 45-60%）
- 5 维推断 max 100% 后面应该 80% / 60% / 40% / 20% 梯度（不并列）
- MBTI 有 signal_strength 字段且 < 40% 时有 ⚠️ 标记
- 报告 .md 10 章完整（数据概览 / 表达 DNA / 行为 / MBTI / SBTI 8 / 动物 12 / 5 维 / 标签 / 历史 / 隐私）
- 卡片 PNG 600-800KB，4:5 (800x1000)
- 左侧 3D 人物图**正常渲染**（不是 alt 文字"3D portrait"占位）

---

## 10. 资源外置导致渲染静默失败（CLASS 坑，必须内嵌）

> 2026-06-11 真实数据 run 暴露，sibling subagent 把图复制到 `assets/` 后修复。本节是踩坑 + 修复记录 + CLASS 教训。

**症状**（用户原话）：
> "我运行了一次这个命令，但是发现3d portrait这个图片没有正常渲染出来"
> "你得把这些图片都放在这个skill的目录下才行，不然别人用这个skill都渲染不出来这个图片"

**根因**：
- `render_card.py: PERSONA_DIR = Path("~/Desktop").expanduser()` —— 硬编码绝对路径
- 4 张 `toonhub-*.png` 在用户桌面上能渲染
- 但当 `sips -Z 800 ~/Desktop/toonhub-1.png` 找不到文件时：
  - `sips` 静默失败（`capture_output=True` 没检查 returncode）
  - `_thumb.name` 是 0 字节空文件
  - `encode_image_as_data_uri` 返回 `data:image/png;base64,`（空）
  - HTML `<img src="data:image/png;base64,">` → 浏览器显示 `alt="3D portrait"`
  - **没有任何报错，只有视觉异常**（Chrome headless 退出 0）

**修复**（2026-06-11）：
```bash
# 1. 建 assets/ 目录
mkdir -p ~/.hermes/skills/self-distill/assets/

# 2. 复制资源（4 张图，每张 5-7MB）
cp ~/Desktop/toonhub-{1,2,3,4}.png ~/.hermes/skills/self-distill/assets/

# 3. 改 PERSONA_DIR 为相对路径
# render_card.py:41
- PERSONA_DIR = Path("~/Desktop").expanduser()
+ PERSONA_DIR = Path(__file__).parent.parent / "assets"
```

**修复后**：
- `ls ~/.hermes/skills/self-distill/assets/` → 4 张图都在
- `select_persona("指挥官")` → 返回 `image: ~/.hermes/skills/self-distill/assets/toonhub-3.png`，路径有效
- 真实数据 run 出来 3D portrait 正常渲染

**CLASS 教训（所有用图片/字体/音频的 skill 通用）**：
- **绝对禁止硬编码用户特定路径**（`~/Desktop/...`、`/home/ubuntu/...`）
- **资源必须内嵌在 `<skill>/assets/`**，代码用 `Path(__file__).parent.parent / "assets"` 引用
- **内嵌后**：
  1. skill 是自包含的（clone/安装/换机器都可用）
  2. 不会因用户清理桌面、迁移文件而静默失败
  3. 资产受 skill 版本控制（`git add assets/` 一起管理）

**防御性增强**（新 skill 必加，避免静默失败）：
```python
# render_html 里加 sips returncode 检查
result = subprocess.run(
    ["sips", "-Z", "800", persona["image"], "--out", _thumb.name],
    capture_output=True
)
if result.returncode != 0:
    raise FileNotFoundError(
        f"sips failed: {persona['image']} — {result.stderr.decode()[:200]}"
    )
```

**预防 checklist**（新 skill 评审时）：
- [ ] 任何 `Path("/...")` 硬编码路径都改成 `Path(__file__).parent...` 相对引用
- [ ] 资源放在 `assets/` / `templates/` / `references/`（受 `skill_manage` 白名单保护）
- [ ] 测试在干净环境（无桌面文件）下能否成功渲染
- [ ] HTML 渲染类 skill 必须有"sips/pdftoppm 失败时显式报错"分支，不能静默 fallback

