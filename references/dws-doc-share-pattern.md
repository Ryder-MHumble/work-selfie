# dws 发送「长报告为钉钉文档」pattern

> 来源：2026-06-11 v1 重构。
> 问题：完整 markdown 报告 3000+ 字塞进 IM 消息里被钉钉 markdown 渲染限制截断 + 难读。
> 解决：报告转 alidocs 在线文档，私聊消息只发文档链接 + 1 张卡片 PNG。

## 流程

```
完整报告 .md (本地)
  ↓ dws doc create --content-file
钉钉在线文档 (alidocs)
  ↓ dws chat message send --text 文档链接
用户私聊 (1 条 markdown 消息：链接 + 标题)
  ↓ dws chat message send --msg-type file --file-path png
用户私聊 (1 张图片消息：卡片 PNG)
```

## 关键命令

**Step 1 · 创建钉钉文档**：

```bash
dws doc create \
  --name "🔮 自查报告 · Demo User · 2026-06-11" \
  --content-file /tmp/self-distill-report-demo-user-1718088000.md \
  -y
```

- `--content-file` 从 UTF-8 文件读（**推荐**：长/多行/表格无 shell escape 问题）
- `--content` 只适合 <2KB 短文本
- `--content -` 从 stdin 读（heredoc 也行）
- `-y` 跳过确认（AI Agent 模式）

**返回**：JSON 含 `data.id`（文档 nodeId）和 `data.url`（alidocs URL）

**Step 2 · 分享链接到私聊**：

```python
doc_url = f"https://alidocs.dingtalk.com/i/nodes/{doc_id}"
text = f"📄 你的完整自查报告已生成：[点击查看]({doc_url})"

dws_chat_args = [
    "chat", "message", "send",
    "--user", user_id,
    "--title", "📄 自查报告（完整版）",
    "--text", text,
]
```

**Step 3 · 发送卡片 PNG**（独立另一条消息）：

```python
dws_chat_args = [
    "chat", "message", "send",
    "--user", user_id,
    "--msg-type", "file",
    "--file-path", png_path,
    "--title", "🖼️ 你的 Profile Card（基于报告生成）",
]
```

## 实施位置

- 函数：`scripts/send_report.py` 的 `send_report_as_doc()` + `share_doc_to_user()` + `send_image_message()`
- 调用：`scripts/main.py` Step 6b 发送流程

## 权限要求

⚠️ `dws doc create` 需要中风险 scope `doc:create`（PAT_MEDIUM_RISK）。首次使用报错时：

```bash
dws pat chmod doc:create --grant-type permanent --agentCode self-distill --yes
```

**降级策略**（缺权限时）：
- 跳过文档创建，改为把 .md 作为 `chat message send --msg-type file` 私发
- 这样降级后收件人看到的是「文件下载链接」而不是「在线文档」，可读性差但至少能收到

## 临时文件清理

`/tmp/self-distill-report-*.md` 在发送完成后立即 unlink（持久化的在 Step 10 拷到 `~/Downloads/`）。

## 反模式

- ❌ 把 3000 字报告用 `dws chat message send --text` 直接发（被 markdown 长度限制截断）
- ❌ 把报告 .md 作为 `chat message send --msg-type file` 发（收件人看到「文件下载」按钮，不是可读的渲染文档）
- ❌ 创建文档失败后还继续发卡片 PNG（半残交付——用户看不到报告就看到图）

## 适用场景

任何「生成结构化长文 + 私发给用户」场景都可复用：
- 周报 / 月报 / 项目复盘
- 调研报告（deep-research 输出）
- 自我画像 / 数据报告
- 任一 skill 需要把"本地分析产物"推送钉钉的
