---
name: work-selfie
description: |
  WorkSelfie：从用户授权的钉钉工作痕迹（消息+文档+听记+多维表格）中提炼职场人格，输出
  「有梗但有依据的自我分析报告 + 野兽派×二次元风 4:5 职场人格卡 PNG」。
  默认数据 in-memory 处理；只有用户明确开启月度导出时，才把原始聊天按月份保存到 skill 目录外的本地文件。
  产物**默认先本地输出**到 `~/Downloads/`（报告 .md + 名片 .png），需要时通过 `--send-to-dingtalk` 经 dws chat 机器人发回用户自己的钉钉。
  触发词：「WorkSelfie」「自查」「蒸馏自己」「看看我」「看看我自己」「我是谁」「自我画像」「我的野兽派名片」
cli_version: ">=1.0.15"
data_policy: "default-full-history"
output_policy: "local-first"
---

# WorkSelfie · 工作方式自拍

> 「不是自拍你的脸，是自拍你的工作方式。」

这个 Skill 把工作聊天、文档、听记和表格里留下的信号，变成一份可解释的自我分析报告和一张能分享的职场自拍卡——但**你的聊天记录、文档正文只活在内存里，闭着眼睛跑、关掉就没了**。

## 触发条件

| 用户说 | 模式 |
|--------|------|
| `WorkSelfie` / `自查` / `蒸馏自己` / `看看我` / `看看我自己` | 完整跑一遍（含知情同意） |
| `我是谁` / `自我画像` | 完整跑一遍 |
| `我的野兽派名片` / `再来一张名片` | 跳到 Phase 4（基于现有 snapshot 重出图） |
| `看看我的变化` / `增量自查` | 只跑增量 + diff（不重出名片） |

显式参数（可选）：
- `--days N` ：覆盖默认窗口（**默认走"全量"模式**——dws 翻页所有会话，时间窗 ≤ 365 天）
- `--skip-consent` ：跳过知情同意（仅当用户已明确授权时）
- `--no-card` ：只发文本报告，不出 PNG 名片
- `--text-only` ：只发文本报告和可视化，不出野兽派×二次元名片
- `--provider {auto,dws,lark}` ：办公软件 CLI provider。`dws` 为当前实采路径；`lark` 为预留入口，先跑 `scripts/bootstrap_cli.py --provider lark --dry-run` 完成 CLI/鉴权准备。
- `--monthly-export` ：聊天记录过多或要做全年/全量分析时启用；按月份调用 `dws chat message list-all`，每月保存 `messages.jsonl` + `monthly-analysis.md`。
- `--monthly-output-dir PATH` ：月度导出目录，默认 `~/Downloads/work-selfie/monthly-chat`，**禁止指向 skill 的 `data/`**。
- `--monthly-max-pages N` / `--monthly-page-size N` ：每月翻页上限和每页数量；触达上限时把该月标记为 `possibly_truncated`。
- `--send-to-dingtalk` ：**默认 False**。需要把报告/名片发回自己钉钉时显式开（涉及 dws pat 中风险 scope 授权）
- `--style {1x1,4x5,9x16}` ：名片比例（**默认 4:5 = 720x900，缩尺寸 + 字号 +22% 组合**——800x1000 留白太多已被淘汰，详见 [v10-card-density-fixes.md §v11](./references/v10-card-density-fixes.md#v11-卡片缩尺寸--字号-22--3d-图与-sbti-块重叠)）

## 严格禁止 (NEVER DO)

- **❌ 绝不允许把原始消息/文档原文写入 skill 目录的 `data/`**——只允许 `data/last_snapshot.json`（分析结果摘要）
- **❌ 绝不允许把分析报告（.md / .docx / .html）默认发钉钉**——默认先本地输出到 `~/Downloads/`，需要时用户显式 `--send`
- **❌ 绝不允许把 Profile Card PNG 长期保存**——临时文件在 `/tmp/self-distill-*.png`，**发完即删**（dry-run 模式例外，要让用户能看预览）
- **❌ 绝不允许跨用户复用**——snapshot 内置 userId，userId 不匹配时强制重新全量
- **❌ 绝不允许跳过知情同意**（除非用户显式 `--skip-consent`）
- **❌ 绝不允许把数据上传到云端 AI 训练集**——只走本机的 LLM 推理
- **❌ 绝不允许冒用浏览器、curl 或未声明 API 冒充办公软件采集能力**——所有数据采集必须走已声明的 provider CLI（`dws` / `lark-cli`）
- **❌ 绝不允许硬编码绝对路径引用 skill 外部资源**（如 `~/Desktop/toonhub-*.png`）——任何图片/音频/字体等资源必须放在 `skill_dir/assets/`，用 `Path(__file__).parent.parent / "assets"` 引用。否则换台机器、用户搬家、被清理桌面时，渲染会静默失败（Chrome headless 不报错，`<img src="">` 直接显示 alt 文字）
- **❌ 绝不允许在卡片里出现「未分类选手」「????」「数据样本不够」等空 fallback 标签**——所有维度都必须给有意义的人设标签 + 一句话总结（兜底统一为「均衡型」）
- **❌ 绝不允许省略 5 维推断的 secondary**——决策/沟通/压力/价值观/信息处理 每维都返回 primary + secondary
- **❌ 绝不允许用 Keirsey 4 分法映射人物图**——SBTI 人设与 3D 小人分开：`PERSONA_LIBRARY` 管人设，`FIGURE_LIBRARY/select_figure()` 按小人视觉特征 + 表达/行为信号选图。
- **❌ 绝不允许"先渲染卡片再生成报告"**——流程是 **先完整报告 → 再渲染卡片**，卡片内容必须从报告派生
- **❌ 绝不允许自画 SVG 人物插画当名片主体**——野兽派×二次元靠**几何拼贴 + emoji + 字体**做人物暗示，不要精细插画（精细插画看起来糙且与"野兽派×二次元"调性冲突）。如需真实人物图，让用户给参考图
- **❌ 绝不允许对称 / 平铺的纯网格排版**——必须非对称、留白张力、字体对比强烈（这是"新时代野兽派"的核心调性）
- **❌ 绝不允许"30s+ 极致渲染"成为默认**——野兽派靠 4-5s 内的几何拼贴 + Chrome headless 单帧出图
- **❌ 绝不允许把名片默认设成 1050x600 (1.75:1 商业名片) 或 1200x1200 (社交头像) 或 1200x1050**——**默认必须 4:5 (720x900)**（800x1000 留白太多已淘汰，缩 10% + 字号 +22% 是当前默认）

## 严格要求 (MUST DO)

- **默认数据 in-memory**：常规模式下所有拉到的消息/文档在 Python 进程内存中处理，处理完毕即释放；**绝不调用 `json.dump` 把原始数据写到 skill 目录**
- **月度导出例外必须显式授权**：只有用户要求「更全面 / 全年 / 全量 / 避免截断 / 按月份」或显式传 `--monthly-export` 时，才允许把原始聊天按月份保存到 `~/Downloads/work-selfie/monthly-chat` 或用户指定目录；仍然禁止写入 `data/`。
- **知情同意先行**：每次跑（除非 `--skip-consent`）必须先展示 [references/privacy-disclosure.md](./references/privacy-disclosure.md) 的精简版，让用户看到「采什么+怎么用+怎么不存」并回复 Y
- **provider 选择协议**：默认 `--provider auto`，但必须先用 `scripts/bootstrap_cli.py --provider auto --dry-run` 检查本机可用 CLI；用户明确公司用钉钉则 `dws`，明确用飞书/Lark 则 `lark`。
- **dws 命令合法性协议**：所有 dws 命令执行前必须用 [dws skill](../dws/SKILL.md) 资料确认；不确定时用 `dws <path> --help` 查证。
- **lark-cli 预留协议**：飞书/Lark 场景必须先按 [lark-shared](../lark-shared/SKILL.md) 完成 `lark-cli config init` 与 split-flow 用户授权；当前 `lark` provider 只提供 CLI/鉴权与数据源映射入口，未完成采集前不得假装已生成真实 Lark 分析。
- **危险操作确认**：发回报告/名片前必须把"内容预览 + 发送目标（自己的 userId）"展示给用户确认
- **失败优雅降级**：某个数据源（chat/doc/minutes/aitable）失败时，跳过该维度，标注「⚠️ 本维度数据采集失败：<原因>」，不让全流程挂
- **跨周期增量**：从 `data/last_snapshot.json` 读 `last_run_at`，新数据的 `--start` = `last_run_at`，合并到历史摘要
- **userId 校验**：从 `data/last_snapshot.json` 读 `user_id`，与当前 `dws contact user get-self` 比对；不匹配时报警并强制全量
- **流程顺序固定**：`采集 → 分析 → 完整报告（10 章深度）→ 渲染卡片（基于报告）→ 本地保存 → [可选] 发钉钉（先报告文档，再卡片 PNG）`
- **报告 = source of truth**：卡片上的所有内容必须来自 `build_report_text()` 的输出；不得瞎填
- **Agent 必须回传完整报告文本**：默认本地保存 `.md` + `.png` 后，最终回复里必须直接粘贴完整分析报告正文；不要只给文件路径、钉钉文档链接或报告摘要。PNG 用本地路径交付，报告文本由 agent 本身发送给用户。
- **空字段兜底**：任何推断字段为空时返回「均衡型 / 多元型」+ 一句话总结，**绝不**用「未分类」「????」「数据不足」」
- **dense card 必填满右侧**（2026-06-11 视觉反馈后更新）：默认 4:5 右侧从 `left: 41%` 起、宽 `59%`，只放 3 个数据模块（SBTI 8 候选、5 维人格、表达 DNA）+ 底部 76px 横向 slogan；**禁止再放协作 Top 5 模块**。剩余空白通过固定 720x900 画布、硬编码行高、压缩段间距处理，不靠协作榜或大黑块凑密度。
- **SBTI 8 候选排名必完整展示**（fix #10 沉淀）：完整 8 行（top 3 黑色突出 + 5 个灰色 max(1, min-5) 兜底），**禁止**精简为 top 3 + 1 行汇总（信息密度太低）。详见 [real-run-findings.md §9.2](./references/real-run-findings.md#92-sbti-8-候选完整展示top-3-突出--5-兜底)
- **默认 4:5 卡片必须删除协作 Top 5**：协作数据仍可留在完整文字报告的「行为模式」里，但 PNG 卡片不再展示协作 Top 5，也不在左侧 evidence 重复「协作 Top1」。
- **资源必须内嵌 skill_dir**（fix #10 沉淀）：所有引用的图片/字体/音频必须放在 `~/.hermes/skills/self-distill/assets/`，代码用 `Path(__file__).parent.parent / "assets"` 引用。**禁止**硬编码 `~/Desktop/...` 等用户特定绝对路径——skill 必须可移植，任何用户 clone/安装后必须能直接渲染。详细踩坑见 [real-run-findings.md §10](./references/real-run-findings.md#10-资源外置导致渲染静默失败)
- **3D 小人必须按图像特征选择**：橙色眼镜=专注深潜，绿色比 V=积极讲解，粉色举拳=项目推进，蓝色指向=侦察响应；选择条件必须来自 `expression_dna` + `behavior_patterns` + SBTI Top1 加成，详见 `references/persona-library-spec.md`。
- **dense card 左侧禁用大面积纯黑块**：左侧默认 41% 宽，人物图高度 59%；SBTI 只做小信息卡，背景使用新野兽派几何方块（黄/红/绿/米色）承接，不再用 `top:25%; height:80%` 的黑色大块压住半张卡。
- **dense card 缩尺寸 + 字号 +22% 组合**（v11 沉淀）：当 4:5 800x1000 留白太多时，**优先缩 10% 尺寸（720x900）同时 +22% 字号**（row 9px→11px、模块标题 9px→11px、footer 8px→9px）。只缩尺寸不放大字号 → 留白更显眼；只放大字号不缩尺寸 → 卡片看着笨重。两者必须同步调。详见 [v10-card-density-fixes.md §v11.1](./references/v10-card-density-fixes.md#v111-缩尺寸-10--字号-22-组合)
- **聊天过多时必须按月份处理**：当用户要全年/全量/尽可能完整的自我画像时，优先启用 `--monthly-export`；每个月独立翻页到 `hasMore=false` 或 `--monthly-max-pages`，并生成该月 `monthly-analysis.md`（重点工作、进展、用户行为特性）。若某月 `possibly_truncated=true`，必须提示按周拆分该月重跑。

## 数据流

```
[知情同意]
  ↓
[选择 provider] → auto / dws / lark
  ├─ dws: scripts/bootstrap_cli.py --provider dws --dry-run
  └─ lark: scripts/bootstrap_cli.py --provider lark --dry-run（预留入口，按 lark-shared 走 split-flow 授权）
  ↓
[查自己 userId]  →  dws contact user get-self（lark 后续映射为 lark-cli user 身份）
  ↓
[读 last_snapshot.json]（决定增量起点）
  ↓
[并发拉 4 类数据 — 默认 in-memory；全量聊天建议 monthly-export]
  ├─ 消息快跑：collect_self.py in-memory
  ├─ 消息全量：monthly_export.py → dws chat message list-all --start --end --limit --cursor（按月份）
  - 听记：dws minutes list mine --start --end （**默认全量扫描所有**）
  ├─ 文档：dws doc search --creator-uid <self.uid> --start --end
  └─ 表格：dws aitable base list + base search --creator <self.uid>
  ↓
[analyze_expression] 词频/句式/口头禅/情绪
  ↓
[analyze_behavior] 活跃时段/协作 Top/消息长度分布
  ↓
[infer_personality] MBTI 4维度 / SBTI 8 风格 / 动物 12 候选
                    / 5 维推断（决策/沟通/压力/价值观/信息处理）
                    / 性格标签 / 摸鱼伪装
  ↓
[Step 4a · 生成完整报告]  build_report_text()
  - 报告 .md 10 章完整（数据概览 / 表达 DNA / 行为 / MBTI / SBTI 8 / 动物 12 / 5 维 / 标签 / 历史 / 隐私）
  - 卡片 PNG，4:5 (720x900)，**左侧人物图正常渲染**（不是 alt 文字"3D portrait"占位）

  [Step 4b · 渲染卡片]  render_card(template, png, analysis)
  └─ 左侧 41%：人物图 59% 高 + 新野兽派几何色块 + SBTI 小信息卡（不使用大面积黑底）
  └─ 右侧 59% 信息面板（grid 硬编码：24px 72px 34px 208px 172px 132px，内容整体向右）
      ├─ 02 SBTI 8 候选排行（完整 8 行 + footer）
      ├─ 03 5 维推断详表（每维 primary+secondary 同行 + footer）
      ├─ 04 表达 DNA 关键数据（Top 5 词/消息长度/表达/情绪 + footer）
      └─ 底部 76px 横向 slogan（贴右侧面板底部，不再用大黑块凑密度）
  └─ 顶部：top-strip + name-block + identity-strip（grid row 0/1/2）
  └─ 编号：左侧 01 职场 SBTI + 右侧 02-04 连续
  └─ 见 [real-run-findings.md §9](./references/real-run-findings.md#9-第二轮布局重构flex-等分--模块精简v9-卡片) 布局设计原则
  ↓
[Step 5 · 预览 + 用户确认]
  ↓
[Step 6a · 本地保存]  →  ~/Downloads/self-distill-{user}-{days}.md
                       + ~/Downloads/self-distill-{user}-{ts}.png
  ↓
[Step 6b · 如 --send 才发钉钉]
  ├─ 完整报告：dws doc create --content-file report.md   ← 转钉钉文档（"长文"用文档承载）
  │            dws chat message send --text 文档链接      ← 私聊消息推送文档链接
  └─ 卡片 PNG： dws chat message send --msg-type file --file-path png   ← 图片消息
  ↓
[清理]  删除 /tmp/self-distill-*.png + 临时 report.md
  ↓
[更新 last_snapshot.json]（仅摘要，不含 raw_data）
```

## 输出物

**默认本地输出**（拷贝到 `~/Downloads/`）：

- `self-distill-{user}-{days}.md` — 完整深度分析报告（10 章，含 SBTI 8 候选 + 5 维推断 secondary + 表达 DNA 完整数据）
- `self-distill-{user}-{ts}.png` — 4:5 (720x900) Profile Card PNG（左侧人物图 + 新野兽派方块 + 右侧 3 个数据模块；无协作 Top 5）

**启用 `--monthly-export` 时额外本地输出**（默认 `~/Downloads/work-selfie/monthly-chat/`）：

- `YYYY-MM/messages.jsonl` — 该月原始聊天记录（含原文，只保存在本地输出目录）
- `YYYY-MM/monthly-analysis.md` — 该月核心工作信息：重点工作、进展、用户行为特性、完整性提醒
- `manifest.json` — 月份、消息数、页数、是否可能截断、文件路径汇总

**仅当 `--send` 时**（dws 机器人发给自己）：

- 1 个**钉钉文档**（完整报告 .md 转的 alidocs 在线文档）
- 1 条**私聊消息**（文档链接）
- 1 张**图片消息**（卡片 PNG）

⚠️ dws doc create 需要中风险 scope（`doc:create`）——首次用 `--send` 时若报 `PAT_MEDIUM_RISK_NO_PERMISSION`，引导用户跑：

```bash
dws pat chmod doc:create --grant-type permanent --agentCode self-distill --yes
```

详细授权流程见 [dws/references/pat-authorization.md](../dws/references/pat-authorization.md)。

---

1. **Markdown 报告**（一条文本消息），结构：
   ```
   ## 🔮 自查报告 · 2026-06-11
   
   ### 📊 数据来源（知情同意）
   - 消息：3,421 条（最近 30 天）
   - 听记：12 场
   - 文档：8 篇
   - 表格：3 个
   
   ### 🎭 数字人画像
   - 性格标签：{标签}
   - 口头禅 Top 5：...
   - 行为逻辑：{3-5 句描述}
   
   ### 🐾 趣味推断
   - 职场 SBTI：{类型}（理由：...）
   - MBTI 4 维度：{E/I} {S/N} {T/F} {J/P}（各自证据：...）
   - 最像的动物：{动物}（理由：...）
   
   ### 📈 工作报告
   - 协作 Top 5：{人名+消息数}
   - 活跃时段：{高峰时段}
   - 消息偏好：{均值长度、表情密度、群聊/单聊比}
   
   ### 🔄 与上次的差异
   - {diff 列表}
   ```

2. **野兽派×二次元 名片 PNG**（一条图片消息）

## 危险操作

| 操作 | 必须确认 |
|------|---------|
| 给用户发报告（任何形式） | 先展示报告全文 + 发送目标（userId）+ 标题 |
| 给用户发图片（名片） | 先展示图片预览（HTML+Chrome headless 渲染的 PNG，存到 `~/Downloads/self-distill-preview.png`） |
| 重置 last_snapshot.json | 明确告知"将丢失历史，无法做 diff" |
| 首次运行知情同意 | 完整文案展示 |

## 命令发现

本 skill 不直接调 dws 命令——通过以下脚本间接调：

- `scripts/main.py` — 端到端编排（知情同意 → 采集/月度导出 → 分析 → diff → 报告 → 渲染 → 本地输出 / dws 发送）
- `scripts/bootstrap_cli.py` — provider CLI 自检/配置引导（`--provider auto|dws|lark`；lark 按 split-flow 输出下一步）
- `scripts/workselfie_providers.py` — provider registry（dws 已接通，lark-cli 预留数据源与鉴权入口）
- `scripts/collect_self.py` — 4 数据源快跑采集：user get-self / chat / minutes list mine / doc search / aitable base list
- `scripts/monthly_export.py` — 按月份调用 `dws chat message list-all`，保存 `messages.jsonl` 并生成每月 `monthly-analysis.md`
- `scripts/analyze.py` — 表达 DNA + 行为模式 + MBTI/SBTI/动物 + 性格 6 项 + KPI 快乐版 + 职场宣言 + 摸鱼标签
- `scripts/render_card.py` — 野兽派×二次元名片渲染（**v9 默认 4:5**，HTML+CSS+SVG+Chrome headless，flex column 等分填满）
- `scripts/send_report.py` — dws 发送层（文本 + 图片）
- `scripts/snapshot.py` — 元数据持久化（**唯一允许写 `data/` 的脚本**）

`scripts/render_card_v5.py` / `v6.py` / `v7.py` 是历史迭代版本（v1-v7 设计探索），保留为参考，**不要调用**。v8/v9 集成在 `render_card.py` 中。

### 渲染技术选型（重要！）

- ❌ **不要用 matplotlib**——CJK 字体配置麻烦（必须 `FontProperties(fname=...)` 传 `text()`，改 `rcParams['font.sans-serif']` 会被字体缓存覆盖），野兽派效果粗糙，emoji 渲染不可控
- ✅ **用 HTML+CSS+SVG + Chrome headless 截图**——CJK 字体直接 `font-family: 'PingFang HK', ...` 在 head style 指定即可；野兽派撞色 / 几何拼贴 / 不对称布局用 CSS 实现；emoji 浏览器原生渲染；Chrome 截图 `--window-size=W,H` 控制尺寸
- ⚠️ Python `str.format()` 模板里所有 CSS 的 `{}` 必须转义成 `{{}}`，否则报 `Single '}' encountered in format string`
- ⚠️ **dense card 不要用 `grid-template-rows: 1fr` 等分模块**（grid fr 只分配轨道高度，section 内部不填满），也**不要用 `flex: 1 1 0` + 段内 space-between**（段内 row 间距巨大）。默认 4:5 正解是固定 6 行数据区 + 绝对定位的 76px 底部横向 slogan。详细踩坑见 [real-run-findings.md §9.1](./references/real-run-findings.md#91-根因grid-fr--段内-space-between-都不填内容)
- ⚠️ **dense card 排名模块永远完整展示 8 行**（top 3 黑色突出 + 5 个灰色兜底）——**不要**精简到 top 3 + 1 行汇总。信息密度 > 视觉简洁。详细迭代见 [real-run-findings.md §9.2](./references/real-run-findings.md#92-sbti-8-候选完整展示top-3-突出--5-兜底)

## 详细参考

- [references/privacy-disclosure.md](./references/privacy-disclosure.md) — 知情同意文案（精简+完整版）
- [references/analysis-frameworks.md](./references/analysis-frameworks.md) — MBTI/SBTI/动物/性格标签方法论
- [references/card-style-guide.md](./references/card-style-guide.md) — 野兽派×二次元 视觉规范
- [references/troubleshooting.md](./references/troubleshooting.md) — 常见错误与降级策略
- [references/output-design-principles.md](./references/output-design-principles.md) — **三大设计原则**：先报告后卡片 / 空字段兜底 / 卡片信息密度（v1 重构沉淀）
- [references/persona-library-spec.md](./references/persona-library-spec.md) — **8 SBTI 风格各自独立分类标准** 规格说明（PERSONA_LIBRARY 怎么用、怎么扩展）
- [references/dws-doc-share-pattern.md](./references/dws-doc-share-pattern.md) — **dws 发送长报告为钉钉文档** 的标准 pattern（doc create + 链接分享 + PNG 配套）
- [references/inference-patterns.md](./references/inference-patterns.md) — **5 维 N-from-N + 连续评分** 推断模式（怎么避免「未分类」、怎么归一化）
- [references/real-run-findings.md](./references/real-run-findings.md) — **真实数据跑出来的坑**（系统消息污染 / 情绪词典 / 5 维归一化 / MBTI 信号弱 / 左侧人物图布局 / Chrome timeout / 字典扩展的连锁断裂 / v9 dense card 布局重构）
- [references/v10-card-density-fixes.md](./references/v10-card-density-fixes.md) — **v10 4 段 footer 注脚 + 人物图 35% + grid 硬编码 8 row + 协作 Top 5**（2026-06-11 真实数据视觉反馈驱动的迭代：右侧"看着很空"→ 4 段 footer + 硬编码 8 row）

## 目录结构

```
~/.hermes/skills/self-distill/
├── SKILL.md                            # 本文件
├── scripts/
│   ├── main.py                         # 端到端编排
│   ├── collect_self.py                 # 4 数据源采集（in-memory）
│   ├── monthly_export.py                # 按月份导出聊天 + 每月分析（skill data 外）
│   ├── analyze.py                      # 表达 + 行为 + 趣味推断（3 模块合一）
│   ├── render_card.py                  # 名片渲染 v9（HTML+CSS+Chrome headless，4:5 默认，flex 等分填满）
│   ├── send_report.py                  # dws 发送层
│   └── snapshot.py                     # 元数据层（唯一写 data/ 的脚本）
├── assets/
│   ├── toonhub-1.png                  # 专注橙：长消息/抽象词/工作词高
│   ├── toonhub-2.png                  # 元气绿：积极情绪/讲解/氛围带动
│   ├── toonhub-3.png                  # 推进粉：项目推进/稳定白天/核心协作
│   └── toonhub-4.png                  # 侦察蓝：问句/短回复/群聊/快速响应
├── references/
│   ├── privacy-disclosure.md           # 知情同意文案
│   ├── analysis-frameworks.md          # MBTI/SBTI/动物/性格方法论
│   ├── card-style-guide.md             # 野兽派×二次元视觉规范
│   ├── output-design-principles.md     # 三大设计原则（先报告后卡片 / 兜底 / 密度）
│   ├── persona-library-spec.md         # SBTI 人设 + 3D 小人特征选择标准
│   ├── dws-doc-share-pattern.md        # dws 发送长报告为钉钉文档的 pattern
│   ├── inference-patterns.md           # 5 维 N-from-N + 连续评分推断模式
│   ├── real-run-findings.md            # 真实数据跑出来的坑（5 类二次修复 + v9 dense card 布局重构 + 资源内嵌规则）
│   └── troubleshooting.md              # 故障降级
└── data/
    └── last_snapshot.json              # 唯一持久化文件（仅摘要，不含 raw_data）
```

历史迭代：`scripts/render_card_v5.py` / `v6.py` / `v7.py` 是 v1-v7 设计探索的归档。**不要调用它们**，新需求改 `render_card.py`。
