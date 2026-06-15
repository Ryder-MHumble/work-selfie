#!/usr/bin/env python3
"""
self-distill 主流程编排

端到端：
  1. 知情同意（必须 Y 确认）
  2. 读取 snapshot → 决定窗口（全量 vs 增量）
  3. 数据采集（in-memory）
  4. 分析引擎（表达+行为+趣味）
  5. 与上次 diff
  6. 拼装报告
  7. 渲染名片 PNG
  8. 预览（dry-run）→ 用户确认
  9. 发送（dws chat send）
  10. 更新 snapshot
  11. 清理 /tmp 文件
"""

import sys
import os
import time
import json
import argparse
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

# 加 scripts/ 到 path
SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from snapshot import (
    load_snapshot, save_snapshot, empty_snapshot, is_incremental,
    get_incremental_start, verify_user_match, diff_snapshots, get_window, CST,
)
from collect_self import collect_all, get_self
from analyze import analyze_all
from render_card import render_card
from monthly_export import default_output_dir, export_monthly_chats, summarize_export_result
from send_report import (
    send_text_message, send_image_message, send_report_as_doc, share_doc_to_user,
    build_report_text, DWS_BIN,
)
from analyze import SBTI_STYLE_MAP  # 报告里需要给 SBTI 加风格解读


# ---------- 知情同意 ----------

CONSENT_FULL = """
🔮 自查知情同意

我准备从你的钉钉工作台采集以下数据，用于本次自我分析：

  📩 消息     你发送的所有消息（默认最近 30 天）
               └ 包含：文本消息、表情回应、文件消息的标题
               └ 不含：图片/视频的二进制内容

  🎙️ 听记     你发起的会议/听记列表
               └ 包含：会议标题、参会人、时长
               └ 不含：转写内容、录音

  📄 文档     你创建的钉钉文档
               └ 包含：标题、字数、最后编辑时间
               └ 不含：文档正文

  📊 表格     你创建的 AI 表格
               └ 包含：表格名、字段数、记录数
               └ 不含：记录内容

数据处理（重点）：

  ✓ 原始消息/文档只活在本次 Python 进程的内存中
  ✓ 分析完成后立即从内存释放，关闭会话即丢失
  ✓ 持久化到 skill 目录的只有「分析结果摘要」，不含任何原文
  ✓ 你的数据不会上传到任何 AI 训练集
  ✓ 野兽派×二次元名片 PNG 是临时文件，发送后立即删除

数据不会被永久保留，但你仍然可以：

  • 删除 ~/.hermes/skills/self-distill/data/last_snapshot.json
    （这会清掉历史基线，下次跑变成「全量」模式）
  • 删除 /tmp/self-distill-*.png（如果还有残留）
  • 随时撤回 dws 机器人的发消息权限

预计耗时：3-5 分钟
副作用：你的钉钉会收到 2 条消息（1 条报告 + 1 张名片）

确认开始？回复 Y 继续 / n 取消
"""


def show_consent(snapshot_exists: bool, skip: bool = False) -> bool:
    """展示知情同意 + 等待用户确认

    snapshot_exists: 是否首次运行
    skip: --skip-consent 时跳过
    """
    if skip:
        return True

    print(CONSENT_FULL, file=sys.stderr)

    if snapshot_exists:
        print("\n📌 检测到历史 snapshot，本次将以「增量模式」运行（仅拉自上次以来的新数据）",
              file=sys.stderr)

    try:
        answer = input("回复 Y/n: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if answer in ("y", "yes", ""):
        return True
    return False


# ---------- 报告拼装 + 预览 ----------

def show_preview(
    report_text: str,
    png_path: Optional[str],
    user_id: str,
):
    """展示报告预览 + 名片预览（给用户最终确认）"""
    print("\n" + "=" * 60, file=sys.stderr)
    print("📋 报告预览（前 500 字符）", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(report_text[:500], file=sys.stderr)
    if len(report_text) > 500:
        print(f"\n... （共 {len(report_text)} 字符）", file=sys.stderr)

    if png_path and Path(png_path).exists():
        size_kb = Path(png_path).stat().st_size / 1024
        print("\n" + "=" * 60, file=sys.stderr)
        print(f"🖼️  名片预览：{png_path}（{size_kb:.0f}KB）", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    print("\n📤 发送目标：你（userId: %s）" % user_id, file=sys.stderr)
    print("📤 将发送：1 条 Markdown 报告 + 1 张 PNG 名片", file=sys.stderr)


def ask_confirm_send() -> bool:
    """等用户最终确认发送"""
    try:
        answer = input("\n确认发送？Y/n: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes", "")


# ---------- 主流程 ----------

def run(
    days: int = 90,
    provider: str = "dws",
    skip_consent: bool = False,
    no_card: bool = False,
    dry_run: bool = False,
    send: bool = False,
    force_full: bool = False,
    style: str = "4x5",
    monthly_export: bool = False,
    monthly_output_dir: Optional[str] = None,
    monthly_max_pages: int = 300,
    monthly_page_size: int = 100,
) -> Dict[str, Any]:
    """主流程入口

    返回：{status, user_id, message_count, sent_text, sent_card, ...}
    """
    t_start = time.time()
    print(f"\n🚀 WorkSelfie 启动（provider={provider}）\n", file=sys.stderr)

    # ===== Step 1: 读 snapshot =====
    old_snapshot = load_snapshot()
    snapshot_exists = old_snapshot is not None
    incremental = is_incremental(old_snapshot) and not force_full

    if incremental:
        print(f"📂 检测到历史 snapshot（{old_snapshot.get('run_count', 0)} 次运行）", file=sys.stderr)
    else:
        print(f"📂 首次运行或强制全量", file=sys.stderr)

    # ===== Step 2: 知情同意 =====
    if not show_consent(snapshot_exists, skip=skip_consent):
        print("\n✗ 用户取消", file=sys.stderr)
        return {"status": "cancelled"}

    # ===== Step 3: 数据采集 =====
    print("\n📥 Step 1/5: 数据采集", file=sys.stderr)
    if incremental and get_incremental_start(old_snapshot):
        start_iso = get_incremental_start(old_snapshot)
        end = datetime.now(CST)
        end_iso = end.strftime("%Y-%m-%dT23:59:59+08:00")
    else:
        window = get_window(days)
        start_iso = window["start"]
        end_iso = window["end"]

    monthly_export_result = None
    if monthly_export:
        monthly_export_dir = monthly_output_dir or str(default_output_dir())
        print(f"  启用按月份聊天导出：{monthly_export_dir}", file=sys.stderr)
        collection = collect_all(
            provider=provider,
            start_iso=start_iso,
            end_iso=end_iso,
            skip_chat=True,
        )
        monthly_export_result = export_monthly_chats(
            start_iso,
            end_iso,
            output_dir=monthly_export_dir,
            provider=provider,
            page_size=monthly_page_size,
            max_pages_per_month=monthly_max_pages,
        )
        collection.messages = monthly_export_result["messages"]
        collection.errors.pop("chat", None)
    else:
        collection = collect_all(provider=provider, start_iso=start_iso, end_iso=end_iso)
    user_id = collection.user_id
    user_name = collection.user_name

    # 校验 userId
    if snapshot_exists and not verify_user_match(old_snapshot, user_id):
        print(f"\n⚠️ 警告：当前 userId ({user_id}) 与历史 snapshot ({old_snapshot.get('user_id')}) 不匹配",
              file=sys.stderr)
        print("建议：--force-full 重置，或删除 ~/.hermes/skills/self-distill/data/last_snapshot.json",
              file=sys.stderr)
        if not ask_confirm_send():
            return {"status": "user_mismatch_cancelled"}

    if not collection.messages and not collection.docs and not collection.aitables:
        print("\n⚠️ 没有任何数据被采集到，退出", file=sys.stderr)
        return {"status": "no_data"}

    # ===== Step 4: 分析 =====
    print("\n🧬 Step 2/5: 分析引擎", file=sys.stderr)
    analysis = analyze_all(collection.messages)

    # ===== Step 5: Diff =====
    print("\n🔄 Step 3/5: 与上次对比", file=sys.stderr)
    new_snapshot = old_snapshot or empty_snapshot(user_id, user_name)
    new_snapshot.update({
        "data_sources": collection.to_summary_counts(),
        "expression_dna": analysis["expression_dna"],
        "behavior_patterns": analysis["behavior_patterns"],
        "personality": analysis["personality"],
        "slogan_candidates": analysis["slogan_candidates"],
        "current_window": {
            "start": collection.window_start,
            "end": collection.window_end,
        },
    })
    if monthly_export_result:
        truncated_months = [
            m["month"] for m in monthly_export_result["months"]
            if m.get("possibly_truncated")
        ]
        new_snapshot["data_sources"]["chat"]["monthly_export"] = {
            "output_dir": monthly_export_result["output_dir"],
            "month_count": len(monthly_export_result["months"]),
            "manifest_path": monthly_export_result["manifest_path"],
            "possibly_truncated_months": truncated_months,
        }
    diff = diff_snapshots(old_snapshot, new_snapshot)
    new_snapshot["diff_from_previous"] = diff
    if not diff.get("is_first_run"):
        print(f"  Δ 新增消息：{diff.get('delta_message_count', 0)}", file=sys.stderr)
        if diff.get("new_keywords"):
            print(f"  Δ 新进关键词：{diff['new_keywords'][:5]}", file=sys.stderr)

    # ===== Step 6a: 拼装完整深度分析报告 =====
    print("\n📝 Step 4/6: 拼装完整深度分析报告", file=sys.stderr)
    report_text = build_report_text(
        user_name=user_name,
        window_start=collection.window_start,
        window_end=collection.window_end,
        analysis=analysis,                # 整个 analysis dict（含所有 5 维推断）
        data_sources=new_snapshot["data_sources"],
        diff=diff,
    )
    # 报告 = source of truth；卡片 = 报告的可视化摘要
    # 报告内容必须足够多足够清晰（10 章：数据概览/表达 DNA/行为/MBTI/SBTI 8/动物/5 维/标签/历史/隐私）

    # ===== Step 6b: 渲染 Profile Card（基于报告内容生成） =====
    print("\n🎨 Step 5/6: 渲染 Profile Card（基于完整报告生成）", file=sys.stderr)
    png_path = None
    if not no_card:
        # 用 /tmp 临时文件
        with tempfile.NamedTemporaryFile(
            mode="w+b", suffix=".png", prefix=f"self-distill-{user_name}-",
            dir="/tmp", delete=False
        ) as f:
            png_path = f.name

        # 构造 render_card 所需的完整 template
        mbti_data = analysis["personality"]["mbti"]
        mbti_code = mbti_data.get("mbti_code", "")
        if not mbti_code or mbti_code == "均衡型":
            # fallback：4 维硬拼
            mbti_code = "".join(d[0] for d in mbti_data.values() if isinstance(d, str) and "(" in d)
        # 卡片只显示 4 字母（信号弱信息不显示在卡片上）
        mbti_4letter = "".join(d[0] for d in mbti_data.values() if isinstance(d, str) and "(" in d)
        from render_card import MBTI_DESC, ANIMAL_EMOJI
        old_snap_for_join = load_snapshot()
        join_date = "2026-06-11"  # 兜底
        if old_snap_for_join and old_snap_for_join.get("first_run_at"):
            join_date = old_snap_for_join["first_run_at"][:10]
        if not join_date and collection.messages:
            join_date = collection.messages[-1].create_time[:10]

        template = {
            "name": user_name,
            "mbti": mbti_4letter,  # 卡片只显示 4 字母
            "mbti_desc": MBTI_DESC.get(mbti_4letter, "多场景切换"),
            "sbti_code": analysis["sbti_top3"][0]["type"] if analysis.get("sbti_top3") else "均衡型",
            "sbti_label": analysis["sbti_style"]["label"],
            "sbti_desc": analysis["sbti_style"]["desc"],
            "sneaky_label": analysis["sneaky_label"]["label"],
            "personality_traits": analysis["personality_traits"],
            "slogan_long": analysis["slogan_long"],
            "kpi_happy": analysis["kpi_happy"],
            "animal": analysis["personality"]["animal"]["primary"],
            "animal_emoji": ANIMAL_EMOJI.get(analysis["personality"]["animal"]["primary"], "🐾"),
            "animal_match": int(analysis["personality"]["animal"]["primary_match"] * 100),
            "employee_id": collection.user_id[-6:] if collection.user_id else "000000",
            "join_date": join_date,
            "date": time.strftime("%Y-%m-%d"),
        }
        # 把 messages_count 注入 analysis（render_card 里 PERSONA_LIBRARY 的 classify_func 用 _n）
        analysis["_messages_count"] = len(collection.messages)
        render_card(template, png_path, style=style, analysis=analysis)

    # ===== Step 7: 预览 + 用户确认 =====
    show_preview(report_text, png_path, user_id)

    if dry_run:
        print("\n[dry-run] 跳过发送，跳过持久化", file=sys.stderr)
        return {
            "status": "dry_run",
            "report_text_length": len(report_text),
            "png_path": png_path,
            "monthly_export": summarize_export_result(monthly_export_result),
        }

    if send and not ask_confirm_send():
        print("\n✗ 用户取消发送", file=sys.stderr)
        if png_path and os.path.exists(png_path):
            os.unlink(png_path)
        return {"status": "send_cancelled"}

    # ===== Step 8: 发送（先报告文档，再卡片 PNG） =====
    print("\n📤 Step 6/6: 发送（先报告文档，再卡片 PNG）", file=sys.stderr)
    sent_doc = False
    sent_card = False

    if send:
        # 8a: 完整报告 → 钉钉文档（"长文"用文档承载，不挤 IM）
        report_md_tmp = Path("/tmp") / f"self-distill-report-{user_name}-{int(time.time())}.md"
        report_md_tmp.write_text(report_text, encoding="utf-8")
        doc_title = f"🔮 自查报告 · {user_name} · {time.strftime('%Y-%m-%d')}"
        doc_id = send_report_as_doc(
            user_id=user_id,
            md_path=str(report_md_tmp),
            title=doc_title,
        )
        if doc_id and doc_id != "dry-run-doc-id":
            sent_doc = share_doc_to_user(user_id, doc_id)
        elif doc_id == "dry-run-doc-id":
            sent_doc = True
        # 删除临时 md（持久化的在 Step 10 拷到 ~/Downloads/）
        if report_md_tmp.exists():
            try:
                report_md_tmp.unlink()
            except OSError:
                pass

        # 8b: 卡片 PNG（基于报告生成的可视化摘要）
        if sent_doc and png_path:
            sent_card = send_image_message(
                user_id=user_id,
                png_path=png_path,
                title="🖼️ 你的 Profile Card（基于报告生成）",
            )
        elif not sent_doc:
            print("  ⚠️ 报告文档发送失败，跳过卡片（避免半残交付）", file=sys.stderr)

    # ===== Step 9: 持久化 =====
    save_snapshot(new_snapshot)
    print(f"\n✓ snapshot 已更新（run_count = {new_snapshot['run_count']}）", file=sys.stderr)

    # ===== Step 10: 复制到 ~/Downloads/ (本地交付：1 .md + 1 .png) =====
    downloads_dir = Path.home() / "Downloads"
    saved_files = []
    try:
        import shutil
        # 名片 PNG
        if png_path and os.path.exists(png_path):
            out_png = downloads_dir / Path(png_path).name
            shutil.copy(png_path, out_png)
            saved_files.append(str(out_png))
            print(f"  ✓ 名片已保存到 {out_png}", file=sys.stderr)
        # 报告 .md
        report_md_path = downloads_dir / f"self-distill-{user_name}-{days}d.md"
        report_md_path.write_text(report_text, encoding="utf-8")
        saved_files.append(str(report_md_path))
        print(f"  ✓ 完整报告已保存到 {report_md_path}", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️ 本地保存失败: {e}", file=sys.stderr)

    elapsed = time.time() - t_start
    print(f"\n🎉 完成。耗时 {elapsed:.1f}s", file=sys.stderr)
    if send:
        print(f"  钉钉：报告文档 {'✓' if sent_doc else '✗'} | 卡片 PNG {'✓' if sent_card else '✗'}",
              file=sys.stderr)
    else:
        print(f"  本地交付：{len(saved_files)} 个文件（~/Downloads/）", file=sys.stderr)

    return {
        "status": "success",
        "user_id": user_id,
        "user_name": user_name,
        "message_count": new_snapshot["data_sources"]["chat"]["message_count"],
        "sent_doc": sent_doc,
        "sent_card": sent_card,
        "elapsed_sec": round(elapsed, 1),
        "saved_files": saved_files,
        "monthly_export": summarize_export_result(monthly_export_result),
    }


# ---------- CLI ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="self-distill 主流程")
    parser.add_argument("--days", type=int, default=90, help="时间窗口天数（默认 90；全年可用 --days 365）")
    parser.add_argument("--provider", default="dws", choices=["dws", "lark", "auto"],
                        help="办公软件 CLI provider（当前 dws 实采，lark 入口预留）")
    parser.add_argument("--skip-consent", action="store_true", help="跳过知情同意（仅当用户已明确授权）")
    parser.add_argument("--no-card", action="store_true", help="只发文本，不出 PNG 名片")
    parser.add_argument("--dry-run", action="store_true", help="只预览不发送")
    parser.add_argument("--send", action="store_true",
                        help="【可选】真发钉钉（默认不发，输出到 ~/Downloads/）")
    parser.add_argument("--force-full", action="store_true", help="强制全量（忽略历史 snapshot）")
    parser.add_argument("--bg-color", default="#1A2B5E", help="(已弃用) 名片背景色")
    parser.add_argument("--iris-color", default="#D62828", help="(已弃用) 名片眼睛颜色")
    parser.add_argument("--style", default="4x5", choices=["1x1", "4x5", "9x16"],
                        help="名片比例 (默认 4x5 = 720x900 小红书帖图)")
    parser.add_argument("--monthly-export", action="store_true",
                        help="按月份拉取并保存聊天记录，同时生成每月 monthly-analysis.md")
    parser.add_argument("--monthly-output-dir", default=None,
                        help="月度聊天导出目录（默认 ~/Downloads/work-selfie/monthly-chat）")
    parser.add_argument("--monthly-max-pages", type=int, default=300,
                        help="每个月最多翻页数；触达上限会标记 possibly_truncated")
    parser.add_argument("--monthly-page-size", type=int, default=100,
                        help="每页聊天条数")
    args = parser.parse_args()

    result = run(
        days=args.days,
        provider=args.provider,
        skip_consent=args.skip_consent,
        no_card=args.no_card,
        dry_run=args.dry_run,
        send=args.send,
        force_full=args.force_full,
        style=args.style,
        monthly_export=args.monthly_export,
        monthly_output_dir=args.monthly_output_dir,
        monthly_max_pages=args.monthly_max_pages,
        monthly_page_size=args.monthly_page_size,
    )
    print("\nResult:", json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("status") in ("success", "dry_run") else 1)
