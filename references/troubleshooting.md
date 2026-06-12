# 故障排查

> 记录 self-distill 在 匿名样本 2026-06-11 真实跑（30/90 天）中的失败模式与降级策略。

## 失败降级原则

**任何数据源失败 → 跳过该维度，不让全流程挂。**

每个失败必须有：
1. stderr 打印具体错误
2. 在最终报告里标注「⚠️ 本维度数据采集失败：<原因>」
3. 不影响其他维度

## 已知失败场景

### 1. `dws contact user get-self` 失败

**可能原因**：
- dws 未配置 / 未登录
- 钉钉企业服务发现未注册 user get-self

**处理**：
- 整个 skill 无法启动，提示用户检查 dws 配置

### 2. `dws chat message list-by-sender` 失败 / 速率限制

**可能原因**：
- 90 天/180 天消息量过大，API 速率限制
- 翻页 cursor 过期

**处理**：
- 自动缩短窗口（90d → 30d → 14d）
- 重试 1 次
- 仍失败则跳过消息维度

### 3. `dws minutes list mine` 失败

**可能原因**：
- 用户没有发起过会议
- 服务未开通

**处理**：
- 标注「⚠️ 听记数据未采集（你近期没有发起过会议）」
- 不影响其他维度

### 4. `dws doc search` 无结果

**可能原因**：
- 用户没创建过文档
- creatorUid 过滤过严

**处理**：
- 标注「⚠️ 文档数据未采集」
- 尝试 `doc search` 不带 creatorUid，作为 fallback

### 5. `dws aitable base list` 无结果

**可能原因**：
- 用户没创建过表格
- 服务未开通

**处理**：
- 标注「⚠️ 表格数据未采集」

### 6. dws 机器人发消息失败

**可能原因**：
- robot-code 无效
- 机器人不在用户的会话中
- **中风险 scope 未授权**（`PAT_MEDIUM_RISK_NO_PERMISSION`）——见 §10
- PNG >20MB（`dt_media_upload` 失败）→ 改用 `--msg-type file --file-path` 直传本地文件

**处理**：
- 文本消息成功 + 图片失败：报告说"卡片生成失败，但报告已发送"
- 全部失败：保存报告到临时文件，提示用户手动查看 `/tmp/self-distill-*.md`
- PNG >20MB 降级：把 PNG 转 JPEG 压缩，重试
- **本 skill 默认不发钉钉**——必须显式 `--send-to-dingtalk` 才走此路径

### 7. 隐私知情同意超时

**可能原因**：
- 用户 5 分钟没回复

**处理**：
- 自动取消
- 不写任何文件
- 不发任何消息

### 8. last_snapshot.json userId 不匹配

**可能原因**：
- 用户换了钉钉账号
- 多账号冲突

**处理**：
- 提示用户「检测到历史 snapshot 来自不同账号」
- 选项：
  - 1) 保留历史，强制合并（不安全，标 userId mismatch）
  - 2) 备份旧 snapshot 到 .bak，全量重新开始
  - 3) 取消

### 9. ⚠️ dws `list-by-sender` 翻页触顶（**silent failure**——最隐蔽！）

**症状**：
- 把窗口从 30 天扩到 90 天后，报告里「消息数」几乎不变
- 不会报错，dws 也不会超时，但数据明显不全
- 典型数据：30 天 1471 条 → 90 天还是 1471 条（**触顶 1500 触发**）

**根因**：
- `collect_chat()` 默认 `max_pages=30` × `--limit 50` = **1500 条触顶**
- 翻页循环在 `hasMore=False` 时停止——但若 `hasMore=True` 触发了 `max_pages` 也会**静默退出**不报错
- 关键：dws 翻页触顶 = 数据被截断但**无任何错误日志**

**修复**（已落到 `collect_self.py`）：
- 默认改为 `max_pages=50` × `--limit 100` = 5000 条（覆盖约 90 天）
- 真全量用 `max_pages=200` = 20,000 条（覆盖 1 年+）
- **关键**：`--limit 100` 比 `--limit 50` 高效一倍（每页翻页开销相同）

**验证**（必做！）：
- 跑完后看 `data_sources.chat.message_count` 是否与窗口长度匹配
- 30 天 200 条/天预期 ≈ 6000 条；返回 5000 触顶 → 报警并提示调高 `max_pages`
- 90 天预期 ≈ 18000 条；返回 5000 → 大概率触顶，必须跑全量
- **比例公式**：`消息数 ≈ 窗口天数 × 日均消息数`；偏差 >50% 大概率触顶

**预防**：
- 跑 `--days 90` 以上窗口时，main.py 应自动判断是否需要 `max_pages=200`
- 跑完后**自动 sanity check**（"90 天预期 1.8 万条，实际 5000 条，差异过大" → 报警）

### 10. dws PAT 中风险 scope 未授权（`PAT_MEDIUM_RISK_NO_PERMISSION`）

**症状**：
- 用 `--send-to-dingtalk` 发报告时报错：
  ```
  错误码: PAT_MEDIUM_RISK_NO_PERMISSION
  缺失 scope: "以个人身份发消息"
  grantOptions: ["session", "permanent"]
  ```

**根因**：
- dws CLI 用的 PAT token 没有"中风险"scope（涉及对外发消息、删数据等敏感操作）
- 这是 dws 的"按需授权"机制——不是 bug，是设计

**处理**（引导用户一次性授权）：
```bash
dws pat chmod chat.message:send \
  --grant-type permanent --agentCode self-distill --yes
```

- `chat.message:send` 是发消息 scope
- `permanent` = 永久有效（vs `session` 临时 vs `once` 一次性）
- `--agentCode` = 自己起的 agent 标识（用于审计）
- `--yes` 跳过确认

**降级**：
- 授权失败 → 改回默认本地输出（产物在 `~/Downloads/`）
- 用户拒绝授权 → 记录偏好，下次默认 `--send-to-dingtalk=false`

**dws pat 授权帮助**：
```bash
dws pat chmod --help
dws auth status
```

## 重试策略

| 命令 | 最大重试 | 退避 |
|------|---------|------|
| `dws contact user get-self` | 0 | 立即报错 |
| `dws chat message list-by-sender` | 1 | 5s |
| `dws minutes list mine` | 0 | 立即跳过 |
| `dws doc search` | 0 | 立即跳过 |
| `dws aitable base list` | 0 | 立即跳过 |
| `dws chat message send` | 2 | 3s, 10s |
| `dt_media_upload` | 1 | 5s |

## 性能基线

- 30 天消息量 <5000 条 → 采集 <2min
- 30 天消息量 5000-20000 条 → 采集 2-5min
- 30 天消息量 >20000 条 → 建议缩短窗口
- 名片渲染 3-5s（Chrome headless 单帧出图）
- 总耗时 5-10min 是常态

### 全量窗口实测（匿名样本 2026-06-11 真实数据）

| 窗口 | 消息数 | 端到端耗时 | 翻页参数 | 备注 |
|------|--------|----------|----------|------|
| 30 天 | 1471 | 3.5s | `max_pages=30, limit=50` | **触顶 1500 警示**——见 §9 |
| 90 天 | 3331 | 84s | `max_pages=50, limit=100` | 修复后正常全量 |
| 180 天 | （预估 7000-12000） | 3-5min | `max_pages=100` | |
| 365 天 | （预估 15000-25000） | 8-15min | `max_pages=200` | 真"全量"模式 |

## 日志

**不写日志文件**——避免泄露元数据。所有调试信息走 stderr。

## 已知限制 / 已知坑

- **vision API 静默**：vision_analyze 在 5-7MB 大图上经常不返回内容（self-distill 4 张 toonhub 图遇到）。**绕道**：先用 `sips -Z 800` 压缩到 500KB 以下再喂给 vision
- **Python str.format 转义**：CSS 模板用 `str.format()` 时所有 `{}` 必须转义成 `{{}}`，否则报 `ValueError: Single '}' encountered in format string`
- **matplotlib 字体坑**（已弃用）：`rcParams['font.sans-serif']` 不生效（字体缓存覆盖），必须 `FontProperties(fname=...)` 传 `text()`。**已切到 HTML+CSS+Chrome headless，不再踩这个坑**
- **dws CLI 路径**：默认从 `PATH` 查找 `dws`；如果不在标准 PATH，设置 `SELF_DISTILL_DWS_BIN=/path/to/dws`
- **MBTI 推断的样本量问题**：30 天数据可能误推（如 30 天推 INFJ，90 天才稳定 INTJ）。**最小 60 天窗口**才能拿到稳定 MBTI
- **5 维推断 `min(1.0, ...)` 截断 bug**：详见 [real-run-findings.md §3](./real-run-findings.md#3-5-维推断-min10--截断-bug)
- **MBTI 信号弱时硬判 4 字母**：详见 [real-run-findings.md §4](./real-run-findings.md#4-mbti-信号弱仍硬判新增-signal_strength-字段)
- **dws 系统消息污染关键词/口头禅**：详见 [real-run-findings.md §1](./real-run-findings.md#1-dws-系统消息污染高频坑必须前置过滤)
- **返回 dict 加字段 = 强制遍历所有消费者**：详见 [real-run-findings.md §6](./real-run-findings.md#6-字典扩展的连锁断裂class-level-坑)
