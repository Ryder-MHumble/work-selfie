# WorkSelfie

> 不是自拍你的脸，是自拍你的工作方式。

[English README](README.en.md)

![WorkSelfie demo cards](examples/cards/demo-grid.png)

你有没有过这种感觉：

- 群里一开会，你总是那个把混乱问题拆成清单的人。
- 别人只看到你发了很多消息，但看不出你是在救火、推进、解释，还是侦察信息。
- 你想给朋友看「我到底是怎么工作的」，但截图聊天记录太无聊，性格测试又太像填表。

WorkSelfie 做的事情很简单：让你的 agent 读取你授权的工作痕迹，然后生成一份有梗但有依据的自我报告，再把结果画成一张可以分享的 4:5 职场自拍卡。

它不是让你填问卷，也不是又一个 KPI 面板。它更像一个会观察你的朋友：看你怎么说话、什么时候出现、怎么推进事情、怎么和别人协作，然后说：

> 「你不像一个普通打工人，你像一个带任务机制的角色。」

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

- 想把自己的工作风格做成一张有传播感卡片的人。
- 想让团队成员用轻松方式互相理解协作风格的人。
- 想给 agent 增加一个「读懂我」能力的 builder。
- 想把沉闷的聊天记录、会议痕迹、协作数据变成有趣内容的人。

## 一句话介绍

**WorkSelfie turns your work traces into a shareable workplace selfie card and self-analysis report.**

