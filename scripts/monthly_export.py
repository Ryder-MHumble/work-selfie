#!/usr/bin/env python3
"""
按月份导出聊天记录并生成月度分析。

原始聊天记录只写到用户指定的本地输出目录（默认 ~/Downloads/work-selfie/monthly-chat），
不写入 skill 的 data/ 目录。
"""

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from analyze import analyze_all
from collect_self import CST, ChatMessage, run_dws


DEFAULT_MONTHLY_EXPORT_DIR = Path.home() / "Downloads" / "work-selfie" / "monthly-chat"
SKILL_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class MonthWindow:
    month: str
    start: datetime
    end: datetime

    @property
    def start_dws(self) -> str:
        return format_dws_time(self.start)

    @property
    def end_dws(self) -> str:
        return format_dws_time(self.end)


def default_output_dir() -> Path:
    return DEFAULT_MONTHLY_EXPORT_DIR


def _reject_skill_data_output_dir(output_root: Path) -> None:
    resolved_output = output_root.expanduser().resolve()
    resolved_data = SKILL_DATA_DIR.resolve()
    if resolved_output == resolved_data or resolved_data in resolved_output.parents:
        raise ValueError("monthly export output_dir must not point to the skill data directory")


def parse_datetime(value: str, *, is_end: bool = False) -> datetime:
    value = value.strip()
    if len(value) == 10:
        suffix = "23:59:59" if is_end else "00:00:00"
        value = f"{value}T{suffix}"
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=None, microsecond=0)


def format_dws_time(dt: datetime) -> str:
    return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _month_end(dt: datetime) -> datetime:
    if dt.month == 12:
        next_month = dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0)
    else:
        next_month = dt.replace(month=dt.month + 1, day=1, hour=0, minute=0, second=0)
    return next_month - timedelta(seconds=1)


def _next_month_start(dt: datetime) -> datetime:
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0)
    return dt.replace(month=dt.month + 1, day=1, hour=0, minute=0, second=0)


def iter_month_windows(start_iso: str, end_iso: str) -> List[MonthWindow]:
    start = parse_datetime(start_iso)
    end = parse_datetime(end_iso, is_end=True)
    if end < start:
        raise ValueError("end_iso must be later than start_iso")

    windows: List[MonthWindow] = []
    cursor = start
    while cursor <= end:
        month_end = min(_month_end(cursor), end)
        windows.append(MonthWindow(cursor.strftime("%Y-%m"), cursor, month_end))
        cursor = _next_month_start(cursor)
    return windows


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "content", "plainText", "title"):
            if value.get(key):
                return str(value[key]).strip()
    return json.dumps(value, ensure_ascii=False)


def _normalize_time(value: Any) -> str:
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, CST).strftime("%Y-%m-%d %H:%M:%S")
    if not value:
        return ""
    text = str(value).strip()
    try:
        return format_dws_time(parse_datetime(text))
    except (TypeError, ValueError):
        return text[:19]


def _first_present(d: Dict[str, Any], keys: List[str], default: Any = "") -> Any:
    for key in keys:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return default


def _candidate_roots(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    roots: List[Dict[str, Any]] = []
    for key in ("result", "data"):
        value = data.get(key)
        if isinstance(value, dict):
            roots.append(value)
    roots.append(data)
    return roots


def _find_payload_root(data: Dict[str, Any]) -> Dict[str, Any]:
    for root in _candidate_roots(data):
        if any(key in root for key in ("conversationMessagesList", "messages", "items", "messageList")):
            return root
    return data.get("result", data)


def _extract_pagination(data: Dict[str, Any]) -> Dict[str, Any]:
    root = data.get("result") if isinstance(data.get("result"), dict) else data
    return {
        "has_more": bool(root.get("hasMore") or root.get("has_more")),
        "next_cursor": str(root.get("nextCursor") or root.get("next_cursor") or ""),
    }


def extract_messages_from_response(data: Dict[str, Any]) -> List[ChatMessage]:
    root = _find_payload_root(data)
    conv_list = root.get("conversationMessagesList") or root.get("conversation_messages_list") or []
    messages: List[ChatMessage] = []

    if conv_list:
        for conv in conv_list:
            conv_id = _first_present(conv, ["openConversationId", "conversationId", "cid"])
            conv_title = _first_present(conv, ["title", "conversationTitle", "name"], "(无标题会话)")
            is_single = bool(_first_present(conv, ["singleChat", "isSingleChat"], False))
            for msg in conv.get("messages", []):
                content = _coerce_text(_first_present(msg, ["content", "text", "messageContent"]))
                if not content:
                    continue
                messages.append(ChatMessage(
                    content=content,
                    create_time=_normalize_time(_first_present(msg, ["createTime", "sendTime", "time"])),
                    conversation_id=str(conv_id),
                    conversation_title=str(conv_title),
                    is_single_chat=is_single,
                    sender_nick=str(_first_present(msg, ["sender", "senderNick", "senderName", "from"])),
                ))
        return messages

    flat_messages = root.get("messages") or root.get("messageList") or root.get("items") or []
    for msg in flat_messages:
        if not isinstance(msg, dict):
            continue
        content = _coerce_text(_first_present(msg, ["content", "text", "messageContent"]))
        if not content:
            continue
        messages.append(ChatMessage(
            content=content,
            create_time=_normalize_time(_first_present(msg, ["createTime", "sendTime", "time"])),
            conversation_id=str(_first_present(msg, ["openConversationId", "conversationId", "cid"])),
            conversation_title=str(_first_present(msg, ["title", "conversationTitle", "conversationName"], "(无标题会话)")),
            is_single_chat=bool(_first_present(msg, ["singleChat", "isSingleChat"], False)),
            sender_nick=str(_first_present(msg, ["sender", "senderNick", "senderName", "from"])),
        ))
    return messages


def fetch_month_messages(
    window: MonthWindow,
    *,
    page_size: int = 100,
    max_pages: int = 300,
    run_dws_func: Callable[..., Optional[Dict[str, Any]]] = run_dws,
    sleep_seconds: float = 0.3,
) -> Dict[str, Any]:
    messages: List[ChatMessage] = []
    cursor = "0"
    pages = 0
    next_cursor = ""
    possibly_truncated = False

    while pages < max_pages:
        data = run_dws_func([
            "chat", "message", "list-all",
            "--start", window.start_dws,
            "--end", window.end_dws,
            "--limit", str(page_size),
            "--cursor", cursor,
        ], timeout=180)
        if not data:
            break

        messages.extend(extract_messages_from_response(data))
        pages += 1

        page_info = _extract_pagination(data)
        if not page_info["has_more"]:
            break
        next_cursor = page_info["next_cursor"]
        if not next_cursor or next_cursor == "0":
            break
        if pages >= max_pages:
            possibly_truncated = True
            break
        cursor = next_cursor
        if sleep_seconds:
            time.sleep(sleep_seconds)

    return {
        "messages": messages,
        "pages": pages,
        "possibly_truncated": possibly_truncated,
        "next_cursor": next_cursor,
    }


def serialize_message(message: ChatMessage) -> Dict[str, Any]:
    return asdict(message)


def write_month_jsonl(messages: List[ChatMessage], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for message in messages:
            f.write(json.dumps(serialize_message(message), ensure_ascii=False) + "\n")


def _top_conversations(messages: List[ChatMessage], limit: int = 5) -> List[str]:
    counter = Counter(m.conversation_title or "(无标题会话)" for m in messages)
    return [f"{name}({count})" for name, count in counter.most_common(limit)]


def _progress_signals(messages: List[ChatMessage]) -> List[str]:
    words = ["推进", "完成", "上线", "交付", "同步", "评审", "发布", "反馈", "计划", "需求", "方案"]
    counter = Counter()
    for message in messages:
        for word in words:
            if word in message.content:
                counter[word] += 1
    return [f"{word}({count})" for word, count in counter.most_common(8)]


def build_monthly_analysis_markdown(
    *,
    month: str,
    messages: List[ChatMessage],
    metadata: Dict[str, Any],
) -> str:
    analysis = analyze_all(messages)
    expression = analysis["expression_dna"]
    behavior = analysis["behavior_patterns"]

    top_keywords = [f"{word}({count})" for word, count in expression.get("top_keywords", [])[:12]]
    collaborators = [f"{name}({count})" for name, count in behavior.get("top_collaborators", [])[:8]]
    active_hours = behavior.get("active_hour_top3", [])
    group_vs_p2p = behavior.get("group_vs_p2p", {})
    length = behavior.get("message_length_dist", {})

    lines = [
        f"# WorkSelfie 月度分析 · {month}",
        "",
        "## metadata",
        f"- window: {metadata.get('window_start')} ~ {metadata.get('window_end')}",
        f"- message_count: {len(messages)}",
        f"- pages: {metadata.get('pages', 0)}",
        f"- possibly_truncated: {str(metadata.get('possibly_truncated', False)).lower()}",
        "",
        "## 重点工作",
        f"- top_keywords: {', '.join(top_keywords) if top_keywords else '暂无明显关键词'}",
        f"- work_threads: {', '.join(_top_conversations(messages)) if messages else '暂无会话线索'}",
        "",
        "## 进展",
        f"- progress_signals: {', '.join(_progress_signals(messages)) or '暂无明显推进词'}",
        f"- active_hours: {', '.join(str(h) for h in active_hours) if active_hours else '暂无'}",
        f"- conversation_count: {len({m.conversation_id for m in messages})}",
        "",
        "## 用户行为特性",
        f"- collaborators: {', '.join(collaborators) if collaborators else '暂无'}",
        f"- group_vs_p2p: group={group_vs_p2p.get('group', 0)}, p2p={group_vs_p2p.get('p2p', 0)}",
        f"- message_length: mean={length.get('mean', 0)}, p90={length.get('p90', 0)}, p99={length.get('p99', 0)}",
    ]
    if metadata.get("possibly_truncated"):
        lines.extend([
            "",
            "## 完整性提醒",
            "- 本月触达 max_pages_per_month 上限，建议按周重跑该月以避免残留截断。",
        ])
    return "\n".join(lines) + "\n"


def export_monthly_chats(
    start_iso: str,
    end_iso: str,
    *,
    output_dir: Optional[str] = None,
    provider: str = "dws",
    page_size: int = 100,
    max_pages_per_month: int = 300,
    run_dws_func: Callable[..., Optional[Dict[str, Any]]] = run_dws,
    sleep_seconds: float = 0.3,
) -> Dict[str, Any]:
    if provider not in ("dws", "auto"):
        raise NotImplementedError(
            "monthly chat export currently requires the dws provider; "
            "lark-cli can implement the same month-window contract later."
        )

    output_root = Path(output_dir).expanduser() if output_dir else default_output_dir()
    _reject_skill_data_output_dir(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    all_messages: List[ChatMessage] = []
    month_results: List[Dict[str, Any]] = []
    for window in iter_month_windows(start_iso, end_iso):
        print(f"  月度聊天导出：{window.month} {window.start_dws} ~ {window.end_dws}", file=sys.stderr)
        fetched = fetch_month_messages(
            window,
            page_size=page_size,
            max_pages=max_pages_per_month,
            run_dws_func=run_dws_func,
            sleep_seconds=sleep_seconds,
        )
        messages = fetched["messages"]
        all_messages.extend(messages)

        month_dir = output_root / window.month
        raw_path = month_dir / "messages.jsonl"
        analysis_path = month_dir / "monthly-analysis.md"
        write_month_jsonl(messages, raw_path)
        metadata = {
            "window_start": window.start_dws,
            "window_end": window.end_dws,
            "pages": fetched["pages"],
            "possibly_truncated": fetched["possibly_truncated"],
        }
        analysis_path.write_text(
            build_monthly_analysis_markdown(month=window.month, messages=messages, metadata=metadata),
            encoding="utf-8",
        )

        month_results.append({
            "month": window.month,
            "window_start": window.start_dws,
            "window_end": window.end_dws,
            "message_count": len(messages),
            "pages": fetched["pages"],
            "possibly_truncated": fetched["possibly_truncated"],
            "next_cursor": fetched["next_cursor"],
            "raw_path": str(raw_path),
            "analysis_path": str(analysis_path),
        })

    manifest = {
        "start": iter_month_windows(start_iso, end_iso)[0].start_dws if month_results else "",
        "end": iter_month_windows(start_iso, end_iso)[-1].end_dws if month_results else "",
        "month_count": len(month_results),
        "message_count": len(all_messages),
        "months": month_results,
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "output_dir": str(output_root),
        "messages": all_messages,
        "months": month_results,
        "manifest_path": str(output_root / "manifest.json"),
    }


def summarize_export_result(result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not result:
        return None
    return {
        "output_dir": result.get("output_dir", ""),
        "manifest_path": result.get("manifest_path", ""),
        "month_count": len(result.get("months", [])),
        "message_count": len(result.get("messages", [])),
        "months": result.get("months", []),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WorkSelfie 按月份导出聊天记录并生成月度分析")
    parser.add_argument("--start", required=True, help="起始时间，例如 2026-01-01T00:00:00+08:00")
    parser.add_argument("--end", required=True, help="结束时间，例如 2026-06-15T23:59:59+08:00")
    parser.add_argument("--output-dir", default=str(default_output_dir()), help="月度导出目录")
    parser.add_argument("--provider", default="dws", choices=["dws", "auto", "lark"])
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages-per-month", type=int, default=300)
    args = parser.parse_args()

    result = export_monthly_chats(
        args.start,
        args.end,
        output_dir=args.output_dir,
        provider=args.provider,
        page_size=args.page_size,
        max_pages_per_month=args.max_pages_per_month,
    )
    print(json.dumps({
        "output_dir": result["output_dir"],
        "manifest_path": result["manifest_path"],
        "month_count": len(result["months"]),
        "message_count": len(result["messages"]),
    }, ensure_ascii=False, indent=2))
