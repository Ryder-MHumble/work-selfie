#!/usr/bin/env python3
"""
self-distill 报告发送层

通过 dws chat 把报告和名片发回用户（私聊给自己）
"""

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

# 加 scripts/ 到 path，让 send_report 能 import analyze 里的常量
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import SBTI_STYLE_MAP, SBTI_CANDIDATES  # 5 章 SBTI 风格解读 + 列未入围候选


# Prefer PATH for portability; WORKSELFIE_DWS_BIN can point to a custom dws binary.
DWS_BIN = (
    os.environ.get("WORKSELFIE_DWS_BIN")
    or os.environ.get("SELF_DISTILL_DWS_BIN")
    or shutil.which("dws")
    or "dws"
)


def run_dws(args: List[str], timeout: int = 60) -> Optional[Dict[str, Any]]:
    """调 dws 命令，解析 JSON"""
    cmd = [DWS_BIN] + args + ["--format", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            print(f"  dws 错误 ({result.returncode}): {result.stderr.strip()[:300]}", file=sys.stderr)
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"  dws 返回非 JSON: {result.stdout[:300]}", file=sys.stderr)
            return None
    except subprocess.TimeoutExpired:
        print(f"  dws 超时（{timeout}s）", file=sys.stderr)
        return None
    except FileNotFoundError:
        print(f"  dws binary 不存在: {DWS_BIN}", file=sys.stderr)
        return None


def send_text_message(
    user_id: str,
    title: str,
    markdown_content: str,
    uuid_str: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """
    发 Markdown 文本消息给 user（单聊）

    user_id: 自己的 userId（dws contact user get-self 拿）
    title: 消息标题（钉钉 IM 列表里显示）
    markdown_content: Markdown 内容
    dry_run: 只预览不发送
    """
    if dry_run:
        print(f"\n[dry-run] dws chat message send --user {user_id} --title {title!r}", file=sys.stderr)
        print(f"[dry-run] 内容（前 200 字）：{markdown_content[:200]}", file=sys.stderr)
        return True

    args = [
        "chat", "message", "send",
        "--user", user_id,
        "--title", title,
        "--text", markdown_content,
    ]
    if uuid_str:
        args.extend(["--uuid", uuid_str])

    result = run_dws(args, timeout=30)
    if result and result.get("success"):
        print(f"  ✓ 文本消息已发送（title: {title}）", file=sys.stderr)
        return True
    print(f"  ✗ 文本消息发送失败: {result}", file=sys.stderr)
    return False


def send_image_message(
    user_id: str,
    png_path: str,
    title: str = "个人名片",
    dry_run: bool = False,
) -> bool:
    """
    发图片消息（用 --msg-type file 走 dws 内置上传）

    user_id: 自己的 userId
    png_path: 本地 PNG 路径
    title: 消息标题
    dry_run: 只预览不发送
    """
    if not Path(png_path).exists():
        print(f"  ✗ 文件不存在: {png_path}", file=sys.stderr)
        return False

    if dry_run:
        size_kb = Path(png_path).stat().st_size / 1024
        print(f"\n[dry-run] dws chat message send --user {user_id} --msg-type file --file-path {png_path}", file=sys.stderr)
        print(f"[dry-run] 文件大小：{size_kb:.0f}KB", file=sys.stderr)
        return True

    # 注意：dws chat message send --msg-type file --file-path 会自动上传
    args = [
        "chat", "message", "send",
        "--user", user_id,
        "--msg-type", "file",
        "--file-path", png_path,
        "--title", title,
    ]
    result = run_dws(args, timeout=120)
    if result and result.get("success"):
        print(f"  ✓ 图片消息已发送（{title}，{Path(png_path).stat().st_size/1024:.0f}KB）", file=sys.stderr)
        return True
    print(f"  ✗ 图片消息发送失败: {result}", file=sys.stderr)
    return False


def send_image_as_image(
    user_id: str,
    png_path: str,
    title: str = "个人名片",
    dry_run: bool = False,
) -> bool:
    """发图片消息（用 --msg-type image，需要 mediaId）

    实现：调 dws api 直接调钉钉 media upload endpoint
    这是更"原生"的方式（收件人看到的是图片卡片，不是文件）

    失败时 fallback 到 file msgType
    """
    if not Path(png_path).exists():
        print(f"  ✗ 文件不存在: {png_path}", file=sys.stderr)
        return False

    if dry_run:
        size_kb = Path(png_path).stat().st_size / 1024
        print(f"\n[dry-run] image upload + send（{size_kb:.0f}KB）→ user {user_id}", file=sys.stderr)
        return True

    # Step 1: 用 dws api 上传 media
    # 钉钉 media upload: POST https://oapi.dingtalk.com/media/upload
    # params: access_token, type=image, media=@file
    # 但 dws api 不支持 multipart upload（只能 JSON body）
    # 所以这条路径走不通，fallback 到 file msgType
    print("  ⚠️ 钉钉 media upload 需要 multipart，dws api 不支持，fallback 到 file msgType",
          file=sys.stderr)
    return send_image_message(user_id, png_path, title=title, dry_run=dry_run)


def send_report_as_doc(
    user_id: str,
    md_path: str,
    title: str = "自查报告",
    dry_run: bool = False,
) -> Optional[str]:
    """把完整报告 .md 转成钉钉文档发到 user 名下

    返回：doc_id（成功）/ None（失败）
    """
    if not Path(md_path).exists():
        print(f"  ✗ 报告文件不存在: {md_path}", file=sys.stderr)
        return None

    if dry_run:
        size_kb = Path(md_path).stat().st_size / 1024
        print(f"\n[dry-run] dws doc create --name {title!r} --content-file {md_path}（{size_kb:.0f}KB）", file=sys.stderr)
        return "dry-run-doc-id"

    # dws doc create --content-file path
    args = [
        "doc", "create",
        "--name", title,
        "--content-file", str(md_path),
        "-y",  # 跳过确认
    ]
    result = run_dws(args, timeout=60)
    if result and result.get("success"):
        doc_id = result.get("data", {}).get("id") or result.get("id") or "?"
        doc_url = result.get("data", {}).get("url") or result.get("url") or ""
        print(f"  ✓ 钉钉文档已创建: {title}（{doc_id}）", file=sys.stderr)
        if doc_url:
            print(f"    URL: {doc_url}", file=sys.stderr)
        return doc_id
    print(f"  ✗ 钉钉文档创建失败: {result}", file=sys.stderr)
    return None


def share_doc_to_user(
    user_id: str,
    doc_id: str,
    dry_run: bool = False,
) -> bool:
    """把已创建的钉钉文档分享给指定 user（私聊消息形式）

    实现：发一条包含文档链接的 markdown 消息
    """
    if not doc_id or doc_id == "dry-run-doc-id":
        return True

    if dry_run:
        print(f"\n[dry-run] 分享文档 {doc_id} → user {user_id}", file=sys.stderr)
        return True

    # 用 dws chat message send 发一条带 doc URL 的消息
    doc_url = f"https://alidocs.dingtalk.com/i/nodes/{doc_id}"
    text = f"📄 你的完整自查报告已生成：[点击查看]({doc_url})"

    args = [
        "chat", "message", "send",
        "--user", user_id,
        "--title", "📄 自查报告（完整版）",
        "--text", text,
    ]
    result = run_dws(args, timeout=30)
    if result and result.get("success"):
        print(f"  ✓ 文档分享链接已发 → user {user_id}", file=sys.stderr)
        return True
    print(f"  ⚠️ 文档分享消息发送失败: {result}", file=sys.stderr)
    return False


    def send_report_as_doc(
        user_id: str,
        md_path: str,
        title: str = "自查报告",
        dry_run: bool = False,
    ) -> Optional[str]:
        """把完整报告 .md 转成钉钉文档发到 user 名下

        返回：doc_id（成功）/ None（失败）
        """
        if not Path(md_path).exists():
            print(f"  ✗ 报告文件不存在: {md_path}", file=sys.stderr)
            return None

        if dry_run:
            size_kb = Path(md_path).stat().st_size / 1024
            print(f"\n[dry-run] dws doc create --name {title!r} --content-file {md_path}（{size_kb:.0f}KB）", file=sys.stderr)
            return "dry-run-doc-id"

        # dws doc create --content-file path
        args = [
            "doc", "create",
            "--name", title,
            "--content-file", str(md_path),
            "-y",  # 跳过确认
        ]
        result = run_dws(args, timeout=60)
        if result and result.get("success"):
            doc_id = result.get("data", {}).get("id") or result.get("id") or "?"
            doc_url = result.get("data", {}).get("url") or result.get("url") or ""
            print(f"  ✓ 钉钉文档已创建: {title}（{doc_id}）", file=sys.stderr)
            if doc_url:
                print(f"    URL: {doc_url}", file=sys.stderr)
            return doc_id
        print(f"  ✗ 钉钉文档创建失败: {result}", file=sys.stderr)
        return None


    def share_doc_to_user(
        user_id: str,
        doc_id: str,
        dry_run: bool = False,
    ) -> bool:
        """把已创建的钉钉文档分享给指定 user（私聊消息形式）

        实现：发一条包含文档链接的 markdown 消息
        """
        if not doc_id or doc_id == "dry-run-doc-id":
            return True

        if dry_run:
            print(f"\n[dry-run] 分享文档 {doc_id} → user {user_id}", file=sys.stderr)
            return True

        # 用 dws chat message send 发一条带 doc URL 的消息
        doc_url = f"https://alidocs.dingtalk.com/i/nodes/{doc_id}"
        text = f"📄 你的完整自查报告已生成：[点击查看]({doc_url})"

        args = [
            "chat", "message", "send",
            "--user", user_id,
            "--title", "📄 自查报告（完整版）",
            "--text", text,
        ]
        result = run_dws(args, timeout=30)
        if result and result.get("success"):
            print(f"  ✓ 文档分享链接已发 → user {user_id}", file=sys.stderr)
            return True
        print(f"  ⚠️ 文档分享消息发送失败: {result}", file=sys.stderr)
        return False


# ---------- 报告文本拼装 ----------

def build_report_text(
    user_name: str,
    window_start: str,
    window_end: str,
    analysis: Dict[str, Any],   # 整个分析结果 dict（不是拆开的）
    data_sources: Dict[str, Any],
    diff: Optional[Dict[str, Any]] = None,
) -> str:
    """拼装完整深度分析报告（独立于卡片，给用户读的文字报告）

    章节：
      1. 数据概览
      2. 表达 DNA
      3. 行为模式
      4. MBTI 4 维度
      5. 职场 SBTI（8 候选 Top 3 + 证据）
      6. 动物画像（12 候选 Top 5 + 证据）
      7. 5 维趣味推断（决策/沟通/压力/价值观/信息处理）
      8. 性格标签 + Slogan
      9. 历史对比
      10. 隐私边界

    数据可信度分级：🔴 硬数据 / 🟡 软分析 / 🔮 趣味推断
    """
    expression_dna = analysis.get("expression_dna", {})
    behavior_patterns = analysis.get("behavior_patterns", {})
    personality = analysis.get("personality", {})

    chat = data_sources.get("chat", {})
    minutes = data_sources.get("minutes", {})
    doc = data_sources.get("doc", {})
    aitable = data_sources.get("aitable", {})

    def has(status): return status == "ok"

    mbti = personality.get("mbti", {})
    mbti_code = mbti.get("mbti_code", "均衡型")
    if not mbti_code or mbti_code == "均衡型":
        # fallback：4 维硬拼
        mbti_code = "".join(d[0] for d in mbti.values() if d and "(" in d)

    lines = []
    lines.append(f"# 🔮 自查报告 · {user_name}")
    lines.append("")
    lines.append(f"**分析窗口**：{window_start[:10]} ~ {window_end[:10]}（{data_sources.get('chat', {}).get('message_count', 0)} 条消息全量分析）")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ============ 1. 数据概览 ============
    lines.append("## 1. 📊 数据概览")
    lines.append("")
    if has(chat.get("status")):
        lines.append(f"- 🔴 消息：**{chat['message_count']}** 条（{chat.get('conversation_count', 0)} 个会话）")
    if has(minutes.get("status")):
        lines.append(f"- 🔴 听记：{minutes.get('meeting_count', 0)} 场")
    if has(doc.get("status")):
        lines.append(f"- 🔴 文档：{doc.get('doc_count', 0)} 篇")
    if has(aitable.get("status")):
        lines.append(f"- 🔴 AI 表格：{aitable.get('base_count', 0)} 个")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ============ 2. 表达 DNA ============
    if expression_dna:
        lines.append("## 2. 🧬 表达 DNA")
        lines.append("")
        top_kw = [w for w, _ in expression_dna.get("top_keywords", [])[:20]]
        if top_kw:
            lines.append(f"**🔴 Top 20 关键词**：{'、'.join(top_kw)}")
        lines.append("")
        catchphrases = expression_dna.get("catchphrases", [])
        if catchphrases:
            lines.append(f"**🟡 口头禅 Top 5**：")
            for cp in catchphrases[:5]:
                lines.append(f"- 「{cp}」")
            lines.append("")
        ls = expression_dna.get("length_stats", {})
        if ls:
            lines.append(f"**🔴 消息长度分布**：")
            lines.append(f"- 均长：{ls.get('mean', 0):.0f} 字符")
            lines.append(f"- 中位数：{ls.get('median', 0):.0f}")
            lines.append(f"- P90：{ls.get('p90', 0):.0f}")
            lines.append("")
        cat = expression_dna.get("category", {})
        if cat:
            lines.append(f"**🟡 消息画像**：")
            lines.append(f"- 工作词：{cat.get('work_ratio', 0)*100:.1f}%")
            lines.append(f"- 单字回复：{cat.get('single_char_ratio', 0)*100:.1f}%")
            lines.append(f"- 长消息：{cat.get('long_msg_ratio', 0)*100:.1f}%")
            lines.append("")
        emo = expression_dna.get("emotion", {})
        if emo:
            lines.append(f"**🟡 情绪倾向**：积极 {emo.get('positive', 0)*100:.1f}% / 消极 {emo.get('negative', 0)*100:.1f}% / 中性 {emo.get('neutral', 0)*100:.1f}%")
            lines.append("")
        punct = expression_dna.get("punctuation_density", {})
        if punct:
            lines.append(f"**🟡 标点使用密度**：问号 {punct.get('question', 0)*100:.1f}% / 感叹号 {punct.get('exclamation', 0)*100:.1f}% / 逗号 {punct.get('comma', 0)*100:.1f}%")
            lines.append("")
        lines.append("---")
        lines.append("")

    # ============ 3. 行为模式 ============
    if behavior_patterns:
        lines.append("## 3. 📈 行为模式")
        lines.append("")
        collab = behavior_patterns.get("top_collaborators", [])[:10]
        if collab:
            lines.append(f"**🔴 协作 Top 10**：")
            for i, (name, count) in enumerate(collab, 1):
                lines.append(f"{i:2d}. {name}：{count} 条")
            lines.append("")
        gv = behavior_patterns.get("group_vs_p2p", {})
        if gv:
            lines.append(f"**🔴 群聊 vs 单聊**：{gv.get('group', 0)*100:.0f}% 群 / {gv.get('p2p', 0)*100:.0f}% 私聊")
        active = behavior_patterns.get("active_hour_top3", [])
        if active:
            lines.append(f"**🔴 高峰小时**：{active[0]}:00、{active[1]}:00、{active[2]}:00 点")
        wknd = behavior_patterns.get("weekend_ratio", 0)
        late = behavior_patterns.get("late_night_ratio", 0)
        if wknd < 0.05:
            lines.append(f"**🟡 周末活跃**：{wknd*100:.1f}%（工作日专注型）")
        else:
            lines.append(f"**🟡 周末活跃**：{wknd*100:.1f}%")
        if late > 0.05:
            lines.append(f"**🟡 凌晨活跃**：{late*100:.1f}%（夜猫子倾向）")
        else:
            lines.append(f"**🟡 凌晨活跃**：{late*100:.1f}%（基本不熬夜）")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ============ 4. MBTI 4 维度 ============
    mbti_dict = personality.get("mbti", {})
    if mbti_dict:
        lines.append("## 4. 🧠 MBTI 4 维度")
        lines.append("")
        lines.append(f"**🔮 综合判定**：**{mbti_code}**")
        lines.append("")
        lines.append("**🔴 4 维度详细分数**：")
        # 只处理 4 维标准字段（EI/SN/TF/JP），跳过 mbti_code/signal_strength
        for dim_key in ["EI", "SN", "TF", "JP"]:
            dim_val = mbti_dict.get(dim_key, "")
            if not dim_val or "(" not in dim_val:
                continue
            letter = dim_val[0] if dim_val else "?"
            score_str = dim_val[dim_val.find("(")+1:dim_val.find(")")] if "(" in dim_val else "50"
            try:
                score = int(score_str)
            except ValueError:
                score = 50
            other = {"E":"I","I":"E","S":"N","N":"S","T":"F","F":"T","J":"P","P":"J"}.get(letter, "?")
            bar = "█" * (score // 5) + "░" * (20 - score // 5)
            lines.append(f"- **{dim_key}**：{letter} {score}% {bar}（{100-score}% {other}）")
        lines.append("")
        # 信号强度提示
        sig = mbti_dict.get("signal_strength", 0)
        if sig < 40:
            lines.append(f"⚠️ **4 维 max 平均仅 {sig:.0f}%**——MBTI 综合判定**不可全信**，建议用 4 维倾向而非 4 字母概括")
        lines.append("")
        # 主导维度（只处理 4 维标准字段）
        mbti_4d = {k: v for k, v in mbti_dict.items() if k in ("EI", "SN", "TF", "JP")}
        strongest = max(mbti_4d.items(), key=lambda kv: int(kv[1][kv[1].find('(')+1:kv[1].find(')')]) if "(" in kv[1] else 0)
        weakest = min(mbti_4d.items(), key=lambda kv: int(kv[1][kv[1].find('(')+1:kv[1].find(')')]) if "(" in kv[1] else 0)
        lines.append(f"**🟡 最强维度**：{strongest[0]} = {strongest[1]}")
        lines.append(f"**🟡 最弱维度**：{weakest[0]} = {weakest[1]}（说明 4 维倾向较均衡）")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ============ 5. 职场 SBTI（8 候选） ============
    sbti_top3 = analysis.get("sbti_top3", [])
    if sbti_top3:
        lines.append("## 5. 💼 职场 SBTI（8 候选连续评分）")
        lines.append("")
        lines.append("**🔮 8 候选 Top 3**：")
        for i, s in enumerate(sbti_top3, 1):
            style = SBTI_STYLE_MAP.get(s["type"], {})
            label = style.get("label", "")
            desc = style.get("desc_template", style.get("desc", ""))
            lines.append(f"{i}. **{s['type']}**（{s['score']}%）— {label}")
            if desc:
                lines.append(f"   - {desc}")
            lines.append(f"   - 证据：{s['evidence']}")
        lines.append("")
        # 列出未入围的（如果有）
        all_sbti_names = [c["name"] for c in SBTI_CANDIDATES]
        chosen = {s["type"] for s in sbti_top3}
        unchosen = [n for n in all_sbti_names if n not in chosen]
        if unchosen:
            lines.append(f"_其余 5 候选（本次未达 30 分阈值）：{'、'.join(unchosen)}_")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ============ 6. 动物画像（12 候选） ============
    animal_top = analysis.get("animal_top3", [])
    if animal_top:
        lines.append("## 6. 🐾 动物画像（12 候选连续评分）")
        lines.append("")
        lines.append("**🔮 Top 5 候选**：")
        for i, a in enumerate(animal_top[:5], 1):
            lines.append(f"{i}. **{a['name']}**（{a['score']}%）— {a['evidence']}")
        lines.append("")
        # 列后 7 名
        if len(animal_top) > 5:
            tail = "、".join(f"{x['name']} {x['score']}%" for x in animal_top[5:9])
            lines.append(f"**🔮 其余候选**：{tail}...")
            lines.append("")
        lines.append("---")
        lines.append("")

    # ============ 7. 5 维趣味推断 ============
    lines.append("## 7. 🎯 5 维趣味推断")
    lines.append("")
    line_specs = [
        ("决策风格", analysis.get("decision_style", {}), "primary_desc", "primary_score", "all"),
        ("沟通偏好", analysis.get("communication_style", {}), "primary_desc", "primary_score", "all"),
        ("压力反应", analysis.get("stress_response", {}), "primary_desc", "primary_score", "all"),
        ("价值观",   analysis.get("value_tendency", {}), "primary_desc", "primary_score", "all"),
        ("信息处理", analysis.get("info_processing", {}), "primary_desc", "primary_score", "all"),
    ]
    for dim_name, dim_data, desc_key, score_key, all_key in line_specs:
        if not dim_data:
            continue
        primary = dim_data.get("primary", "?")
        desc = dim_data.get(desc_key, "")
        score = dim_data.get(score_key, 0)
        lines.append(f"**🔮 {dim_name}**：**{primary}**（{score}%）")
        lines.append(f"- {desc}")
        # 列出其他候选
        all_cands = dim_data.get(all_key, [])
        if all_cands and len(all_cands) > 1:
            others = " / ".join(f"{c['name']} {c['score']}%" for c in all_cands[1:4])
            lines.append(f"- 其他候选：{others}")
        lines.append("")
    lines.append("---")
    lines.append("")

    # ============ 8. 性格标签 + Slogan ============
    tags = personality.get("tags", [])
    slogans = analysis.get("slogan_candidates", [])
    if tags or slogans:
        lines.append("## 8. 🏷️ 性格标签 + Slogan")
        lines.append("")
        if tags:
            lines.append(f"**🔮 性格标签**：{' / '.join(tags)}")
        if slogans:
            lines.append("")
            lines.append(f"**🔮 Slogan 候选 Top 3**：")
            for s in slogans[:3]:
                lines.append(f"- 「{s}」")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ============ 9. 历史对比 ============
    if diff and not diff.get("is_first_run"):
        lines.append("## 9. 🔄 与上次对比")
        lines.append("")
        if diff.get("delta_message_count"):
            lines.append(f"- 🔴 新增消息：**{diff['delta_message_count']}** 条")
        if diff.get("new_keywords"):
            lines.append(f"- 🔴 新进 Top 关键词：{', '.join(diff['new_keywords'][:5])}")
        if diff.get("dropped_keywords"):
            lines.append(f"- 🔴 掉出 Top 关键词：{', '.join(diff['dropped_keywords'][:5])}")
        if diff.get("new_top_collaborators"):
            lines.append(f"- 🔴 新进 Top 协作：{', '.join(diff['new_top_collaborators'])}")
        if diff.get("mbti_drift"):
            for dim, d in diff["mbti_drift"].items():
                lines.append(f"- 🟡 MBTI {dim}：{d['from']} → {d['to']}（Δ {d['delta']:+d}）")
        lines.append("")
        lines.append(f"_上次运行：{diff.get('previous_run_at', '?')}_")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ============ 10. 隐私边界 ============
    lines.append("## 🔒 隐私边界")
    lines.append("")
    lines.append("- 原始消息/文档内容**从未离开你的 Mac**")
    lines.append("- 采集层用 dws CLI 拉元数据，分析层纯本地 Python 处理")
    lines.append("- 持久化的只有 `~/.hermes/skills/self-distill/data/last_snapshot.json`（分析摘要）")
    lines.append("- 临时 PNG 发送后即删")
    lines.append("- 删除 snapshot → 下次跑全量；删 ~/.hermes/skills/self-distill/data/ → 全新")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"_本报告由 self-distill skill 生成 · v0.9（架构重构中）_")

    return "\n".join(lines)


# ---------- CLI ----------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="self-distill 报告发送测试")
    parser.add_argument("--text-only", action="store_true", help="只发文本，不发图片")
    parser.add_argument("--dry-run", action="store_true", help="只预览不发送")
    parser.add_argument("--image-path", default="/tmp/self-distill-cards/card_html_demo_7d.png")
    args = parser.parse_args()

    if args.dry_run:
        # 测试
        test_text = "## 测试\n\n这是一条测试消息"
        test_uuid = str(uuid.uuid4())
        # 拿自己 userId
        from collect_self import get_self
        info = get_self()
        if info:
            send_text_message(info["user_id"], "测试", test_text, uuid_str=test_uuid, dry_run=True)
            if not args.text_only:
                send_image_message(info["user_id"], args.image_path, dry_run=True)
        else:
            print("无法获取 userId", file=sys.stderr)
