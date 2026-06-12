# v10 dense card 布局重构（4 段 footer 注脚 + 人物图 35% + 协作 Top 5）

> 迭代日期：2026-06-11
> 来源：用户对 v9 输出物（4 大模块 + slogan）的真实视觉反馈
> 状态：已被 v11 取代（v11 缩尺寸 720x900 + 字号 +22% + 3D 图/SBTI 块重叠），v10 仍保留作为方法论参考

## 触发本次迭代的 3 个用户反馈

1. **"右侧内容看着很空"**（v9 末态：4 段挤顶部 0-470px，470-900px 是大块浅色空白）—— 4 段总内容 ~400px，right-panel 1000px，必然有 ~600px 空白
2. **"希望这个卡片里面的内容能多一些"** —— 用户希望密度提升
3. **"把『职场SBTI』的模块往上移动一些，因为这个人物的高度太高了，这就导致右侧的内容看着很空，所以可以切割一下左侧的人物图片尺寸"** —— 左侧 3D 人物图 55% 太高，把 SBTI 块挤到底部

## 4 个修复点（按优先级）

### Fix 1 · 人物图 55% → 35%（SBTI 块 45% → 65%）

**问题**：`.toonhub-bg` 占 55% 高 + `.sbti-side` 占 45% 高 → SBTI 块只有 450px，4 段 evidence 装不下 + SBTI 块看着空

**修复**：
```css
.toonhub-bg {
    height: 35%;            /* 紧凑——给人图够看脸/头的高度即可 */
}
.sbti-side {
    position: absolute;
    top: 35%; left: 0;      /* 从 35% 开始 */
    width: 38%;
    height: 65%;            /* 拉高到 65% */
}
```

**踩坑**：patch 工具如果 old_string 与 new_string 之间有重叠内容，会把 `.sbti-side {}` 块拆成两半（一个块只含 top/left/width/height，另一个块只含 padding/display/border-top）—— **CSS 解析时后者覆盖前者，导致 height 丢失**。修复后必须 read_file 确认 CSS 块完整。

### Fix 2 · grid 1fr 1fr 1fr 1fr → 硬编码 8 row

**问题**：用 `grid-template-rows: auto auto auto 1fr 1fr 1fr 1fr auto` 时，auto 行（top-strip / name / identity）会被内容撑大，挤掉 1fr 空间——4 段实际只 100px 高而不是 1fr 分配的 190px

**试过且失败的方案**：
- `minmax(170px, 1fr)` —— min 不生效，1fr 仍被 auto 行挤掉
- `flex: 1 1 0` + 段内 space-between —— 段内 row 间距巨大（行高 80px）
- `flex: 1 1 auto` + slogan `margin-top: auto` —— 4 段堆顶部 + slogan 之上 400px 空白

**正解**：硬编码 8 row 高度：
```css
grid-template-rows: 24px 64px 30px 1fr 1fr 1fr 1fr 64px;
gap: 4px;
```

数学：1000 - 38 (padding) - 24 - 64 - 30 - 64 = 780
780 - 7×4 (gap) = 752
1fr = 752 / 4 = 188px（4 段每段 188px）

**段内底部留白 ~30px**（4 段内容总 ~470px / 4 段 = ~120px，剩 68px）—— 视觉可接受，因为有 footer 注脚填补

### Fix 3 · 4 段末尾 footer 注脚（红色 ▎ + 1px 虚线）

**问题**：4 段内容 ~120px，但 grid 1fr 分配 188px → 段内底部 ~68px 留白

**修复**：每段末尾加 1 行 `<div class="xxx-footer">▎{解释}</div>`：

| 段 | footer 文字 |
|---|---|
| 02 SBTI 8 候选 | ▎Top 3 = 8 候选中分数最高的 3 项 · 其他 5 个分数用 Top 最低 - 5 兜底 |
| 03 5 维 | ▎基于 5 维度独立推断 · primary 与 secondary 差距 = 决策漂移空间 |
| 04 DNA | ▎Top 5 词 = 真实话题 · 工作词比 = 干正事的比例 |
| 05 协作 | ▎Top 5 累计 N 次 · 占 Top N 总消息 X% |

**CSS**：
```css
.xxx-footer {
    font-size: 8px; color: #D62828; font-weight: 600;
    margin-top: 4px; padding-top: 4px;
    border-top: 1px dashed rgba(0,0,0,0.15);
    letter-spacing: 0.02em;
}
```

**设计语言**：▎ 红色字符是野兽派×二次元调性（与左下 SBTI 块的红色边框呼应），1px 虚线让 footer 视觉分离但不破坏密度

### Fix 4 · 协作 Top 3 → Top 5

**问题**：mock 数据 5 个 collaborator 是默认；只取 3 个让 05 段内容更少

**修复**：`build_collab_html` 取 `[:5]` 不只 `[:3]`

**配套**：CSS `.collab-item` 行高 1.0 → 1.5 让 5 行 row 紧凑可读

## 关键验证（用 PIL 扫描 PNG）

**right-panel 4 段实际分布**（扫描 x=320 找黑色 row 文字位置）：
- 02 候选：y=158-346（约 188px ✓）
- 03 5 维：y=346-540（约 194px ✓）
- 04 DNA：y=540-730（约 190px ✓）
- 05 协作：y=730-904（约 174px ✓）
- slogan：y=918-986

4 段紧贴排列，段间无大空白，slogan 紧贴底部。

## 失败案例存档

1. **patch 工具拆分 CSS 块**：必须 read_file 确认 CSS 块完整，否则 height 丢失 → 段显示异常
2. **grid 1fr 1fr 1fr 1fr**：auto 行撑大挤掉 1fr 空间 —— 必须硬编码 auto 行高度
3. **minmax(170px, 1fr)**：min 不生效，1fr 仍被挤 —— 不要用 minmax 兜底
4. **flex 1 1 0 + 段内 space-between**：段内 row 间距巨大（80px/row）—— 不可用
5. **vision_analyze 工具在长 session 后可能不返回文本**：用 PIL 像素扫描 + sips 切图代替视觉验证

---

# v11 卡片缩尺寸 + 字号 +22% + 3D 图与 SBTI 块重叠（当前默认）

> 迭代日期：2026-06-11
> 来源：用户对 v10 输出物的第二轮视觉反馈（"右侧内容看着很空"+"把『职场SBTI』模块往上移因为人物图太高"+"缩小整个卡片高度并放大字号"）
> 状态：**当前默认**——已合并到 `scripts/render_card.py` v11

## 触发本次迭代的 3 个用户反馈

1. **"右侧内容看着很空"**（v10 末态：4 段总内容 ~600px，1000px 卡片有 400px 段内留白）
2. **"把『职场SBTI』的模块往上移动一些，因为这个人物的高度太高了，这就导致右侧的内容看着很空，所以可以切割一下左侧的人物图片尺寸"**——用户**主动要求 SBTI 块与 3D 图重叠**，不是简单二分
3. **"缩小整个卡片的高度，然后放大右侧和左侧相关的文本大小，同时允许左侧的『职场SBTI』的模块盖住一些 3d 图片的下"**——尺寸缩 10% + 字号 +22% + 板块重叠，三件事必须同步做

## v11 3 个修复点

### v11.1 缩尺寸 10% + 字号 +22% 组合

**问题**：v10 4:5 (800x1000) 留白太多，但 4 段内容已经填到 600px+——单独缩尺寸不放大字号，剩余空间显得更空

**正解**：**两者必须同步调**——缩尺寸 10% (800x1000 → 720x900) + 字号 +22% (row 9px→11px, collab 10px→12px, footer 8px→9px, title 9px→11px)

| 元素 | v10 (800x1000) | v11 (720x900) |
|---|---|---|
| `.sbti8-item` row | 9px / line 1.6 | **11px / line 1.5** |
| `.sbti8-title` | 9px | **11px** |
| `.t5d-row` | 9px / line 1.5 | **11px / line 1.5** |
| `.dna-row` | 9px / line 1.5 | **11px / line 1.5** |
| `.collab-item` | 10px / line 1.5 | **12px / line 1.5** |
| `.xxx-footer` | 8px | **9px** |
| `grid-template-rows` | 24 64 30 1fr 1fr 1fr 1fr 64 | **22 60 28 1fr 1fr 1fr 1fr 60** |

**同步改的尺寸字段**（CSS 宽度也要跟着调）：
- `.sbti8-score` width 28 → 32
- `.t5d-label` width 24 → 28
- `.dna-k` width 42 → 50
- `.collab-rank` width 16 → 18
- `.collab-bar` width 60 → 70, height 8 → 9
- `.collab-count` min-width 24 → 28

**反模式**：
- ❌ 只缩尺寸不放大字号 → 留白更显眼
- ❌ 只放大字号不缩尺寸 → 卡片看着笨重、违反小红书帖图比例
- ❌ 缩 20% 字号 +30% ——破坏视觉比例，野兽派不要求"字号挤满"

### v11.2 板块重叠：SBTI 块覆盖 3D 图下部 25%

**问题**：v10 是简单二分——3D 图 35% 顶 + SBTI 块 65% 底，**两者是独立块**，视觉上"图"和"标签"分离

**正解**：让 SBTI 块**主动覆盖** 3D 图下部：
```css
.toonhub-bg {
    position: absolute;
    top: 0; left: 0;
    width: 38%;
    height: 50%;            /* 人物图 50% 高 */
}
.toonhub-bg::after {        /* 渐变叠层：30% 透明 → 100% 黑色 */
    background: linear-gradient(180deg,
        rgba(242, 239, 233, 0) 30%,
        rgba(10, 10, 10, 0.95) 100%);
}
.sbti-side {
    position: absolute;
    top: 25%; left: 0;      /* 从 25% 开始，**盖住 3D 图 25-50% 区域** */
    width: 38%;
    height: 80%;            /* 撑到 100% 高度 */
    background: #0A0A0A;
    border-top: 4px solid #D62828;  /* 顶部红边 视觉锚点 */
}
```

**视觉链条**：
- y=0-25%：3D 图全显示
- y=25-30%：3D 图渐变到黑（toonhub-bg::after 渐变）
- y=25-100%：黑色 SBTI 块覆盖（带 4px 红色顶边）

**为什么这样更好**：
1. "图"和"标签"是 1 个组合而非 2 个独立块——视觉节奏更紧
2. 3D 图 50% 高度足够显示脸/头/胸（`object-position: center 18%` 让脸靠上）
3. SBTI 块 80% 高度有 ~720px 空间容纳 4 段 evidence + 主风格
4. 红色顶边 4px 是"图"和"块"的分界锚点，野兽派调性强化

**反模式**：
- ❌ top: 50% / height: 50%——SBTI 块在最底下、3D 图独立完整，调性散
- ❌ top: 0 / height: 50%——SBTI 块从顶部开始、3D 图被完全盖掉一半
- ❌ 用 padding 让 SBTI 块避开 3D 图区域（padding 25% = 浪费 25% 空间）

### v11.3 字号放大后 4 段自然填满 grid 1fr

**v10 痛点**：9px 字号 + 1000px 高度 → 4 段总高 ~600px，grid 1fr 分配 4×190=760px，段内底部 ~40px 留白

**v11 解决**：11px 字号 + 900px 高度 → 4 段每段行高 16.5px (line 1.5)：
- 02 候选：8 行 × 16.5 + title 16.5 + footer 13.5 = 161.5px
- 03 5 维：5 行 × 16.5 + title + footer = 112.5px
- 04 DNA：4 行 × 16.5 + title + footer = 95.5px
- 05 协作：5 行 × 18 (12px 字号) + title + footer = 121.5px

总 4 段内容 491px。grid 1fr 分配 (900 - 22-60-28-60 - 7×4) / 4 = 170.5px per section

**段内底部留白**：02 段 9px、03 段 58px、04 段 75px、05 段 49px

03/04/05 段内仍有 50-75px 留白——**v11 接受**这个留白作为视觉呼吸（比 v9/v10 段间大留白更舒服），因为 02 段填满、footer 注脚提供视觉锚点

**反模式**：
- ❌ 字号 +50% 让 4 段填满 → row 28px/行，调性太"大字报"非野兽派
- ❌ 缩高度到 600px → 4 段 row 都挤，视觉密度过高

## v11 关键验证

**左侧 (x=137) 颜色扫描**（720x900）：
- 0-2% 高度：浅色
- 2-28% 高度：**粉色（3D 图）**——人物图清晰可见 234px
- 28% 高度：红色 4px 描边（sbti-side 顶边）
- 28-100% 高度：黑色 SBTI 块

**右侧 (x=360) 颜色扫描**（720x900）：
- 0-19% 高度：top-strip + name + 身份条
- 21-31%：**02 候选 8 行**
- 33-50%：**03 5 维 + 04 DNA**
- 50-72%：**05 协作 Top 5**
- 72-89%：slogan 黑底黄字
- **整段 y=166-820（654px）填满，段间无大空白**

## v11 失败案例存档

1. **vision_analyze 工具在 session 后段不返回文本**：用 PIL 像素扫描 + sips 切图代替视觉验证
2. **单独缩尺寸不放大字号**：剩余留白更显眼——必须缩尺寸+放大字号同步
3. **用 padding 避开重叠区域**：浪费 25% 空间——直接用 z-index + 渐变叠层做无缝过渡
4. **SBTI 块 100% 高度 + 红色顶边**：红色边是图/块分界锚点，**不能省**

## v11 vs v10 关键差异速查

| 维度 | v10 | v11 |
|---|---|---|
| 卡片尺寸 | 800x1000 | **720x900**（缩 10%） |
| 字号 (row) | 9px | **11px**（+22%） |
| 字号 (collab) | 10px | **12px** |
| 字号 (footer) | 8px | **9px** |
| 3D 图高度 | 35% | **50%** |
| SBTI 块起始 | top: 35% | **top: 25%**（**主动覆盖** 3D 图底部） |
| SBTI 块高度 | 65% | **80%** |
| 板块关系 | 简单二分 | **重叠** + 红色 4px 顶边 + 渐变叠层 |
| grid-template-rows | 24 64 30 1fr 1fr 1fr 1fr 64 | **22 60 28 1fr 1fr 1fr 1fr 60** |
