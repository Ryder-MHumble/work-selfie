#!/usr/bin/env python3
"""
self-distill 数据采集层

调用 dws 拉 4 类数据，全部 in-memory 处理，**绝不**写 raw_data 到 skill 目录。

支持的数据源：
  1. chat        →  dws chat message list-by-sender --sender-user-id <self>
  2. minutes     →  dws minutes list mine
  3. doc         →  dws doc search --creator-uids <self>
  4. aitable     →  dws aitable base list（最近访问，无 creator 过滤能力）

每个数据源独立 try/except，失败不阻塞其他维度。
"""

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Prefer PATH for portability; WORKSELFIE_DWS_BIN can point to a custom dws binary.
DWS_BIN = (
    os.environ.get("WORKSELFIE_DWS_BIN")
    or os.environ.get("SELF_DISTILL_DWS_BIN")
    or shutil.which("dws")
    or "dws"
)

CST = timezone(timedelta(hours=8))


# ---------- 数据结构 ----------

@dataclass
class ChatMessage:
    """聊天消息（仅保留 self-distill 需要的字段）"""
    content: str
    create_time: str  # ISO
    conversation_id: str
    conversation_title: str
    is_single_chat: bool
    sender_nick: str


@dataclass
class MinuteItem:
    """听记/会议条目"""
    title: str
    create_time: str
    meeting_id: str


@dataclass
class DocItem:
    """文档条目（仅元数据，不含正文）"""
    name: str
    creator_uid: str
    create_time_ms: int
    node_id: str
    extension: str  # adoc/axls/appt 等


@dataclass
class AitableItem:
    """AI 表格条目（仅元数据）"""
    base_id: str
    base_name: str


@dataclass
class CollectionResult:
    """完整采集结果（in-memory）"""
    user_id: str
    user_name: str
    window_start: str
    window_end: str
    messages: List[ChatMessage] = field(default_factory=list)
    minutes: List[MinuteItem] = field(default_factory=list)
    docs: List[DocItem] = field(default_factory=list)
    aitables: List[AitableItem] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    def to_summary_counts(self) -> Dict[str, Any]:
        """生成 snapshot 用的 data_sources 摘要（不包含任何 raw_data）"""
        return {
            "chat": {
                "status": "ok" if "chat" not in self.errors else "error",
                "message_count": len(self.messages),
                "conversation_count": len({m.conversation_id for m in self.messages}),
                "error": self.errors.get("chat", None),
            },
            "minutes": {
                "status": "ok" if "minutes" not in self.errors else "error",
                "meeting_count": len(self.minutes),
                "error": self.errors.get("minutes", None),
            },
            "doc": {
                "status": "ok" if "doc" not in self.errors else "error",
                "doc_count": len(self.docs),
                "error": self.errors.get("doc", None),
            },
            "aitable": {
                "status": "ok" if "aitable" not in self.errors else "error",
                "base_count": len(self.aitables),
                "error": self.errors.get("aitable", None),
            },
        }


# ---------- 工具函数 ----------

def run_dws(args: List[str], timeout: int = 60) -> Optional[Dict[str, Any]]:
    """调 dws 命令，解析 JSON 输出"""
    cmd = [DWS_BIN] + args + ["--format", "json"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            print(f"  dws 退出码 {result.returncode}: {result.stderr.strip()[:200]}", file=sys.stderr)
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"  dws 返回非 JSON: {result.stdout[:200]}", file=sys.stderr)
            return None
    except subprocess.TimeoutExpired:
        print(f"  dws 超时（{timeout}s）", file=sys.stderr)
        return None
    except FileNotFoundError:
        print(f"  dws binary 不存在: {DWS_BIN}", file=sys.stderr)
        return None


# ---------- 各数据源采集 ----------

def get_self() -> Optional[Dict[str, str]]:
    """拿自己 userId + name"""
    print("  查自己 userId ...", file=sys.stderr)
    data = run_dws(["contact", "user", "get-self"])
    if not data:
        return None
    result = data.get("result", [])
    if not result:
        return None
    model = result[0].get("orgEmployeeModel", {})
    return {
        "user_id": model.get("userId", ""),
        "user_name": model.get("orgUserName", ""),
    }


def collect_chat(
    user_id: str, start_iso: str, end_iso: str,
    max_pages: int = 50, page_size: int = 100,
) -> List[ChatMessage]:
    """拉自己发送的所有消息（带 cursor 翻页）

    默认上限：50 页 × 100 条 = 5,000 条（覆盖约 90 天）
    跑全量用 --max-pages 200（20,000 条/1 年+）
    """
    print(f"  拉消息：{start_iso} ~ {end_iso}（max_pages={max_pages}, page_size={page_size}）", file=sys.stderr)
    all_messages: List[ChatMessage] = []
    cursor = "0"
    page = 0

    while page < max_pages:
        data = run_dws([
            "chat", "message", "list-by-sender",
            "--sender-user-id", user_id,
            "--start", start_iso,
            "--end", end_iso,
            "--limit", str(page_size),
            "--cursor", cursor,
        ], timeout=120)
        if not data:
            break

        result = data.get("result", {})
        conv_list = result.get("conversationMessagesList", [])
        if not conv_list:
            break

        for conv in conv_list:
            conv_id = conv.get("openConversationId", "")
            conv_title = conv.get("title", "")
            is_single = conv.get("singleChat", False)
            for msg in conv.get("messages", []):
                content = msg.get("content", "").strip()
                if not content:
                    continue
                all_messages.append(ChatMessage(
                    content=content,
                    create_time=msg.get("createTime", ""),
                    conversation_id=conv_id,
                    conversation_title=conv_title,
                    is_single_chat=is_single,
                    sender_nick=msg.get("sender", ""),
                ))

        page += 1
        has_more = result.get("hasMore", False)
        if not has_more:
            break
        cursor = result.get("nextCursor", "")
        if not cursor or cursor == "0":
            break
        print(f"    翻页 {page}: 已累计 {len(all_messages)} 条", file=sys.stderr)
        time.sleep(0.3)  # 限流保护

    print(f"  ✓ 消息：{len(all_messages)} 条（{page} 页）", file=sys.stderr)
    return all_messages


def collect_minutes(start_iso: str, end_iso: str) -> List[MinuteItem]:
    """拉自己发起的会议/听记"""
    print(f"  拉听记：{start_iso} ~ {end_iso}", file=sys.stderr)
    # minutes 接受 --start --end (date 格式) 或 ISO
    start_short = start_iso[:10]
    end_short = end_iso[:10]
    all_items: List[MinuteItem] = []
    next_token = ""
    page = 0
    max_pages = 10

    while page < max_pages:
        args = [
            "minutes", "list", "mine",
            "--start", start_short,
            "--end", end_short,
            "--max", "20",
        ]
        if next_token:
            args.extend(["--next-token", next_token])
        data = run_dws(args, timeout=60)
        if not data:
            break
        result = data.get("result", {})
        items = result.get("itemList", [])
        for it in items:
            all_items.append(MinuteItem(
                title=it.get("title", "(无标题)"),
                create_time=it.get("createTime", ""),
                meeting_id=it.get("taskUuid") or it.get("meetingId", ""),
            ))
        page += 1
        if not result.get("hasMore", False):
            break
        next_token = result.get("nextToken", "")
        if not next_token:
            break

    print(f"  ✓ 听记：{len(all_items)} 场", file=sys.stderr)
    return all_items


def collect_docs(user_id: str, start_iso: str, end_iso: str) -> List[DocItem]:
    """拉自己创建的文档（按 creatorUid 过滤）"""
    print(f"  拉文档：{start_iso} ~ {end_iso}", file=sys.stderr)
    # ISO → 毫秒时间戳
    start_ms = int(datetime.fromisoformat(start_iso).timestamp() * 1000)
    end_ms = int(datetime.fromisoformat(end_iso).timestamp() * 1000)

    all_items: List[DocItem] = []
    cursor = ""
    page = 0
    max_pages = 20

    while page < max_pages:
        args = [
            "doc", "search",
            "--creator-uids", user_id,
            "--created-from", str(start_ms),
            "--created-to", str(end_ms),
            "--limit", "30",
        ]
        if cursor:
            args.extend(["--cursor", cursor])
        data = run_dws(args, timeout=60)
        if not data:
            break
        docs = data.get("documents", [])
        for d in docs:
            all_items.append(DocItem(
                name=d.get("name", "(无标题)"),
                creator_uid=d.get("creatorUid", ""),
                create_time_ms=d.get("createTime", 0),
                node_id=d.get("nodeId", ""),
                extension=d.get("extension", ""),
            ))
        page += 1
        # nextPageToken 在哪？查 help 没显示，假设是 data.nextPageToken
        cursor = data.get("nextPageToken") or data.get("cursor") or ""
        if not cursor or not docs:
            break

    print(f"  ✓ 文档：{len(all_items)} 篇", file=sys.stderr)
    return all_items


def collect_aitables() -> List[AitableItem]:
    """拉自己最近访问的 AI 表格（dws 无 creator 过滤能力，list 即是上限）"""
    print(f"  拉 AI 表格（最近访问）...", file=sys.stderr)
    all_items: List[AitableItem] = []
    cursor = ""
    page = 0
    max_pages = 10

    while page < max_pages:
        args = ["aitable", "base", "list", "--limit", "10"]
        if cursor:
            args.extend(["--cursor", cursor])
        data = run_dws(args, timeout=30)
        if not data:
            break
        data_obj = data.get("data", {})
        bases = data_obj.get("bases", [])
        for b in bases:
            all_items.append(AitableItem(
                base_id=b.get("baseId", ""),
                base_name=b.get("baseName", ""),
            ))
        page += 1
        cursor = data.get("nextCursor") or ""
        if not cursor or not bases:
            break

    print(f"  ✓ AI 表格：{len(all_items)} 个（最近访问）", file=sys.stderr)
    return all_items


# ---------- 顶层入口 ----------

def collect_all(
    provider: str = "dws",
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,
    skip_chat: bool = False,
    skip_minutes: bool = False,
    skip_docs: bool = False,
    skip_aitables: bool = False,
) -> CollectionResult:
    """
    顶层采集入口。

    任何数据源失败不阻塞，只在 result.errors 留痕。
    """
    if provider not in ("dws", "auto"):
        raise NotImplementedError(
            f"{provider} provider is reserved for the next connector. "
            "Run `python3 scripts/bootstrap_cli.py --provider lark --dry-run` "
            "to prepare lark-cli setup/auth first."
        )

    if not user_id or not user_name:
        info = get_self()
        if not info:
            raise RuntimeError("无法查到自己 userId（dws contact user get-self 失败）")
        user_id = info["user_id"]
        user_name = info["user_name"]

    if not start_iso or not end_iso:
        end = datetime.now(CST)
        start = end - timedelta(days=30)
        end_iso = end.strftime("%Y-%m-%dT23:59:59+08:00")
        start_iso = start.strftime("%Y-%m-%dT00:00:00+08:00")

    result = CollectionResult(
        user_id=user_id,
        user_name=user_name,
        window_start=start_iso,
        window_end=end_iso,
    )

    print(f"\n📥 采集开始：{user_name} ({user_id})", file=sys.stderr)
    print(f"   窗口：{start_iso} ~ {end_iso}\n", file=sys.stderr)

    # 1. chat
    if not skip_chat:
        try:
            result.messages = collect_chat(user_id, start_iso, end_iso)
        except Exception as e:
            result.errors["chat"] = str(e)
            print(f"  ⚠️ chat 采集失败: {e}", file=sys.stderr)
    else:
        result.errors["chat"] = "skipped"

    # 2. minutes
    if not skip_minutes:
        try:
            result.minutes = collect_minutes(start_iso, end_iso)
        except Exception as e:
            result.errors["minutes"] = str(e)
            print(f"  ⚠️ minutes 采集失败: {e}", file=sys.stderr)
    else:
        result.errors["minutes"] = "skipped"

    # 3. doc
    if not skip_docs:
        try:
            result.docs = collect_docs(user_id, start_iso, end_iso)
        except Exception as e:
            result.errors["doc"] = str(e)
            print(f"  ⚠️ doc 采集失败: {e}", file=sys.stderr)
    else:
        result.errors["doc"] = "skipped"

    # 4. aitable
    if not skip_aitables:
        try:
            result.aitables = collect_aitables()
        except Exception as e:
            result.errors["aitable"] = str(e)
            print(f"  ⚠️ aitable 采集失败: {e}", file=sys.stderr)
    else:
        result.errors["aitable"] = "skipped"

    print(f"\n📊 采集完成：", file=sys.stderr)
    print(f"   消息：{len(result.messages)}", file=sys.stderr)
    print(f"   听记：{len(result.minutes)}", file=sys.stderr)
    print(f"   文档：{len(result.docs)}", file=sys.stderr)
    print(f"   表格：{len(result.aitables)}", file=sys.stderr)
    if result.errors:
        print(f"   错误：{result.errors}", file=sys.stderr)

    return result


# ---------- CLI ----------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="self-distill 数据采集")
    parser.add_argument("--days", type=int, default=30, help="时间窗口天数")
    parser.add_argument("--start", type=str, default=None, help="起始时间 ISO")
    parser.add_argument("--end", type=str, default=None, help="结束时间 ISO")
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--skip-minutes", action="store_true")
    parser.add_argument("--skip-docs", action="store_true")
    parser.add_argument("--skip-aitables", action="store_true")
    parser.add_argument("--provider", default="dws", choices=["dws", "lark", "auto"],
                        help="办公软件 CLI provider（当前 dws 实采，lark 入口预留）")
    parser.add_argument("--json-summary", action="store_true",
                        help="输出 snapshot 摘要（不含 raw_data）到 stdout")
    args = parser.parse_args()

    end_iso = args.end or datetime.now(CST).strftime("%Y-%m-%dT23:59:59+08:00")
    if args.start:
        start_iso = args.start
    else:
        start_dt = datetime.now(CST) - timedelta(days=args.days)
        start_iso = start_dt.strftime("%Y-%m-%dT00:00:00+08:00")

    result = collect_all(
        provider=args.provider,
        start_iso=start_iso,
        end_iso=end_iso,
        skip_chat=args.skip_chat,
        skip_minutes=args.skip_minutes,
        skip_docs=args.skip_docs,
        skip_aitables=args.skip_aitables,
    )

    if args.json_summary:
        # 仅输出 summary 到 stdout（不含任何 raw_data）
        summary = {
            "user_id": result.user_id,
            "user_name": result.user_name,
            "window": {"start": result.window_start, "end": result.window_end},
            "data_sources": result.to_summary_counts(),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        # 完整模式（调试用，**不要在生产中用**）
        print(f"\n⚠️ 这是 raw_data 输出，仅用于调试。生产中请用 --json-summary", file=sys.stderr)
        output = {
            "user_id": result.user_id,
            "user_name": result.user_name,
            "window": {"start": result.window_start, "end": result.window_end},
            "messages": [asdict(m) for m in result.messages],
            "minutes": [asdict(m) for m in result.minutes],
            "docs": [asdict(d) for d in result.docs],
            "aitables": [asdict(a) for a in result.aitables],
            "errors": result.errors,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
