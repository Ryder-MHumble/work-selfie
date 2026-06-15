# WorkSelfie

> 不是自拍你的脸，是自拍你在工位上活成了哪种角色。

[English README](README.en.md)

![WorkSelfie demo cards](examples/cards/demo-grid.png)

每天都在上班，但很少有人真的看见你是怎么工作的。

你可能是那个：

- 群里消息炸了，最后默默把混乱问题拆成清单的人。
- 会上没说几句，但会后把方案、风险、下一步全补齐的人。
- 一边回“收到”，一边在脑子里重排优先级、救火、催进度的人。
- 明明只是发了几条消息，却已经在团队里完成了一次小型调度的人。

WorkSelfie 做的事情很简单：让你的 agent 读取你授权的工作痕迹，然后生成一份有梗但有依据的自我报告，再把结果画成一张可以分享的 4:5 职场自拍卡。

它不是让你填问卷，也不是给你贴一个“INTJ/ENFP”的玄学标签。它更像一个懂打工人的旁观者：看你怎么说话、什么时候出现、怎么推进事情、怎么救场、怎么和别人协作，然后说：

> 「原来你不是普通打工人，你是这个团队里的隐藏职业。」

## 它会给你什么

- 一张可以发朋友圈/小红书/群聊的职场自拍卡，里面有 3D 小人、SBTI 排名、表达 DNA 和五维推断。
- 一份完整文字报告，解释你为什么像这个角色，而不是只给一个玄学标签。
- 一套可复用的 agent skill，换一批数据、换一个人，也能跑出新的工作自拍。

## 小人不是随机贴上去的

WorkSelfie 会根据你的行为信号挑小人：

- **橙色眼镜小人**：长消息多、抽象词多、系统化表达明显，像在脑内画架构图。
- **绿色比 V 小人**：语气积极、喜欢解释、经常把事情讲清楚，像团队里的气氛讲师。
- **粉色举拳小人**：白天稳定推进、目标明确、协作中心感强，像项目里的执行发动机。
- **蓝色指向小人**：短回复、问题多、响应快、喜欢侦察信息，像群聊里的信号雷达。

所以卡片不是装饰，它是对你工作方式的一次视觉翻译。

## 怎么开始

把仓库放进你正在使用的 agent 的 skills 目录即可。只要你的 agent 支持本地 `SKILL.md` / skills 文件夹，就不限定 Codex。

```bash
git clone https://github.com/Ryder-MHumble/work-selfie.git

# 示例：放到你自己的 agent skills 目录
mkdir -p ~/.agents/skills
cp -R work-selfie ~/.agents/skills/work-selfie
```

如果你用的是其他 agent，把 `~/.agents/skills` 换成它自己的 skills 目录即可，例如：

```bash
cp -R work-selfie ~/.codex/skills/work-selfie
cp -R work-selfie ~/.claude/skills/work-selfie
```

然后重启 agent，对它说一句：

```text
用 WorkSelfie 给我的工作方式拍张自拍。
```

Agent 会先告诉你它准备读取什么数据，等你确认后再开始。默认产物会先落到本地，不会自动发出去。

## 聊天太多怕漏？

很多人的真实工作不是 30 天几百条消息，而是一年几万条：群里救火、私聊对齐、会后补方案、深夜回“我看一下”。一次性把聊天记录塞给 agent，最容易被截断，最后分析出来就像只看了你工作的冰山一角。

这时让 WorkSelfie 按月份跑：

```bash
python3 scripts/main.py --provider dws --monthly-export --days 365 --dry-run
```

这里的 `--dry-run` 只是不发送/不更新最终快照，月度导出文件仍会写到本地。

它会尽可能按月份翻页导出聊天记录，并在本地生成：

```text
~/Downloads/work-selfie/monthly-chat/
├── 2026-01/messages.jsonl
├── 2026-01/monthly-analysis.md
├── 2026-02/messages.jsonl
├── 2026-02/monthly-analysis.md
└── manifest.json
```

每个月的 `monthly-analysis.md` 会先拆出这个月的「重点工作、进展、用户行为特性」，再把所有月份合起来做最终 WorkSelfie。这样看到的不是某几段高光聊天，而是你一年里真实的工作轨迹。

## 公司用钉钉还是飞书？

WorkSelfie 的底层不是绑死某一个办公软件，而是通过 CLI provider 读取你授权的工作痕迹：

- 公司用钉钉：走 `dws`。
- 公司用飞书 / Lark：预留 `lark-cli` 入口。

配置好 skill 后，你可以先让 agent 帮你检查并引导配置对应 CLI：

```bash
python3 scripts/bootstrap_cli.py --provider auto --dry-run
```

确认计划没问题后，让 agent 跑一键自检：

```bash
python3 scripts/bootstrap_cli.py --provider auto
```

如果 CLI 不存在，它会明确告诉 agent 需要先安装 `dws` 还是 `lark-cli`，或通过 `WORKSELFIE_DWS_BIN` / `WORKSELFIE_LARK_BIN` 指向已有二进制。

如果你明确知道公司用哪个：

```bash
python3 scripts/bootstrap_cli.py --provider dws --dry-run
python3 scripts/bootstrap_cli.py --provider lark --dry-run
```

`dws` 是当前已接通的采集路径；`lark-cli` 已预留 provider、鉴权和数据源映射入口，适合后续扩展到飞书团队。

## 如果你只想看 Demo

不用接任何真实数据，也可以重新生成 README 里的四张虚构示例卡：

```bash
cd work-selfie
python3 scripts/generate_demo_cards.py
```

生成后会看到：

```text
examples/cards/demo-grid.png
```

## 适合谁玩

- 想知道“我在团队里到底像什么角色”的打工人。
- 想把自己的工作风格做成一张有传播感卡片的人。
- 想让团队成员用轻松方式互相理解协作风格的人。
- 想给 agent 增加一个「读懂我」能力的 builder。
- 想把沉闷的聊天记录、会议痕迹、协作数据变成有趣内容的人。

## 一句话介绍

**WorkSelfie turns your work traces into a shareable workplace selfie card and self-analysis report.**
